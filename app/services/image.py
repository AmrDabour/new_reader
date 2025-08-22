from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps
from app.utils.arabic import is_arabic_text, reshape_arabic_text
from app.utils.amiri_font import amiri_manager
from app.config import get_settings
import cv2
import numpy as np
import io
import base64
import re
import pytesseract
import logging

settings = get_settings()
try:
    # Align pytesseract with configured tesseract binary
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
except Exception:
    pass


class ImageService:
    def correct_image_orientation(self, image: Image.Image) -> Image.Image:
        """
        Rotate-only orientation correction to avoid any edge artifacts:
        - Honor EXIF orientation
        - Try 0/90/180/270 and pick the best upright
        - No deskew, no perspective warp, no filtering
        - Fit to max size while preserving aspect ratio
        """
        try:
            # Honor camera EXIF orientation first
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass

            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # Smart upright selection: try 0/90/180/270 and pick the best by OCR+structure
            # Using cv2.rotate ensures exact 90-degree rotations without introducing dark borders.
            img_cv, chosen_angle, details = self._choose_best_upright(img_cv)
            try:
                logging.getLogger(__name__).info(
                    f"Upright angle chosen: {chosen_angle} deg | details={details}"
                )
            except Exception:
                pass

            # Convert and fit to max
            pil_img = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            return self._fit_to_max(pil_img)
        except Exception:
            # Fallback to safe resize only
            return self._fit_to_max(image)

    def _fit_to_max(
        self, image: Image.Image, max_size: Optional[int] = None
    ) -> Image.Image:
        """
        Ensure the image fits within max_size (either width or height),
        preserving aspect ratio. Uses settings.max_image_size by default.
        """
        try:
            limit = max_size or getattr(settings, "max_image_size", 1920)
            if image.width > limit or image.height > limit:
                img_copy = image.copy()
                img_copy.thumbnail((limit, limit), Image.Resampling.LANCZOS)
                return img_copy
            return image
        except Exception:
            # Fallback: return original on any unexpected error
            return image

    # --- Scanner-like helpers ---
    def _upright_by_tesseract_osd(
        self, img_bgr: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Optional[int]]:
        """
        Use Tesseract OSD to determine required rotation (0/90/180/270) and rotate accordingly.
        Returns (rotated image, angle) or (None, None) if OSD fails.
        """
        try:
            # Convert to RGB PIL for pytesseract
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)

            # Upscale small images to help OSD
            min_dim = min(pil.width, pil.height)
            if min_dim < 800:
                scale = 800 / float(min_dim)
                new_size = (int(pil.width * scale), int(pil.height * scale))
                pil = pil.resize(new_size, Image.Resampling.LANCZOS)

            # Run OSD
            osd = pytesseract.image_to_osd(pil, config="--psm 0")
            # Parse rotation angle (degrees to rotate CCW to correct)
            m = re.search(r"Rotate:\s*(\d+)", osd)
            if not m:
                m = re.search(r"Orientation in degrees:\s*(\d+)", osd)
            if not m:
                return None, None
            angle = int(m.group(1)) % 360
            if angle not in (0, 90, 180, 270):
                return None, None

            if angle == 0:
                return img_bgr, 0

            # Tesseract's reported rotation can be interpreted differently across libs.
            # Try both CCW and CW and choose the one with better horizontal structure score.
            def rotate_ccw(src, a):
                h, w = src.shape[:2]
                M = cv2.getRotationMatrix2D((w // 2, h // 2), a, 1.0)
                return cv2.warpAffine(
                    src,
                    M,
                    (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE,
                )

            cand_a = rotate_ccw(img_bgr, angle)  # CCW by +angle
            cand_b = rotate_ccw(img_bgr, -angle)  # CW by +angle

            try:
                s_a = self._orientation_score(cv2.cvtColor(cand_a, cv2.COLOR_BGR2GRAY))
                s_b = self._orientation_score(cv2.cvtColor(cand_b, cv2.COLOR_BGR2GRAY))
                chosen = cand_a if s_a >= s_b else cand_b
                return chosen, angle
            except Exception:
                return cand_a, angle
        except Exception:
            return None, None

    def _ocr_score(self, img_bgr: np.ndarray) -> float:
        """Compute a simple OCR confidence score; higher is better."""
        try:
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            data = pytesseract.image_to_data(
                pil, lang="ara+eng", output_type=pytesseract.Output.DICT
            )
            confs = []
            for txt, conf in zip(data.get("text", []), data.get("conf", [])):
                try:
                    c = float(conf)
                except Exception:
                    continue
                if txt and txt.strip() and c >= 0:
                    confs.append(c)
            if not confs:
                return 0.0
            # Weighted score: average confidence times number of words
            return float(np.mean(confs)) + 0.1 * len(confs)
        except Exception:
            return 0.0

    def _detect_and_warp_document(self, img_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect the largest 4-point contour (likely the document) and warp it to a top-down view.
        Returns warped image or None if no good contour is found.
        """
        try:
            orig = img_bgr
            h, w = orig.shape[:2]
            # Work on a smaller preview for speed
            preview_max = 1000
            scale = 1.0
            if max(h, w) > preview_max:
                scale = preview_max / float(max(h, w))
                preview = cv2.resize(orig, (int(w * scale), int(h * scale)))
            else:
                preview = orig.copy()

            gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(gray, 50, 150)

            contours, _ = cv2.findContours(
                edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
            )
            contours = sorted(contours, key=cv2.contourArea, reverse=True)

            img_area = preview.shape[0] * preview.shape[1]
            for cnt in contours[:10]:  # check top 10 by area
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    area = cv2.contourArea(approx)
                    if area < 0.2 * img_area:  # ignore tiny quads
                        continue
                    pts = approx.reshape(4, 2).astype(np.float32)
                    # Map back to original scale
                    if scale != 1.0:
                        pts = pts / scale
                    warped = self._four_point_transform(orig, pts)
                    return warped
            return None
        except Exception:
            return None

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        # Order points: top-left, top-right, bottom-right, bottom-left
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def _four_point_transform(self, image: np.ndarray, pts: np.ndarray) -> np.ndarray:
        rect = self._order_points(pts)
        (tl, tr, br, bl) = rect

        # compute the width of the new image
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxWidth = int(max(widthA, widthB))

        # compute the height of the new image
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxHeight = int(max(heightA, heightB))

        dst = np.array(
            [
                [0, 0],
                [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1],
                [0, maxHeight - 1],
            ],
            dtype="float32",
        )

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(
            image, M, (maxWidth, maxHeight), flags=cv2.INTER_CUBIC
        )
        return warped

    def _deskew_by_hough(self, img_bgr: np.ndarray) -> np.ndarray:
        try:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180, threshold=120, minLineLength=100, maxLineGap=10
            )
            if lines is not None and len(lines) > 0:
                angles = []
                for l in lines:
                    x1, y1, x2, y2 = l[0]
                    dx = x2 - x1
                    dy = y2 - y1
                    if dx == 0:
                        continue
                    angle = np.degrees(np.arctan2(dy, dx))
                    if -45 <= angle <= 45:
                        angles.append(angle)
                if angles:
                    median_angle = float(np.median(angles))
                    if abs(median_angle) > 0.3:  # avoid tiny rotations
                        h, w = img_bgr.shape[:2]
                        M = cv2.getRotationMatrix2D(
                            (w // 2, h // 2), -median_angle, 1.0
                        )
                        img_bgr = cv2.warpAffine(
                            img_bgr,
                            M,
                            (w, h),
                            flags=cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_REPLICATE,
                        )
        except Exception:
            pass
        return img_bgr

    def _orientation_score(self, gray: np.ndarray) -> float:
        # score favoring clear horizontal structures (forms/text lines)
        edges = cv2.Canny(gray, 50, 150)
        row_profile = np.sum(edges, axis=1).astype(np.float32)
        col_profile = np.sum(edges, axis=0).astype(np.float32)
        row_var = float(np.var(row_profile))
        col_var = float(np.var(col_profile))
        # higher when horizontal structure dominates
        return row_var / (col_var + 1e-6)

    def _auto_upright(self, img_bgr: np.ndarray) -> np.ndarray:
        try:
            candidates = [
                (0, img_bgr),
                (90, cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)),
                (180, cv2.rotate(img_bgr, cv2.ROTATE_180)),
                (270, cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)),
            ]
            best_score = -1.0
            best_img = img_bgr
            for angle, img in candidates:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                score = self._orientation_score(gray)
                if score > best_score:
                    best_score = score
                    best_img = img
            return best_img
        except Exception:
            return img_bgr

    def _choose_best_upright(self, img_bgr: np.ndarray) -> Tuple[np.ndarray, int, dict]:
        """
        Try 0/90/180/270 and pick the one with the highest composite score:
        composite = ocr_score + k * orientation_score. Prefer 0 over 180 on near ties.
        Returns (best_image, angle, details)
        """
        try:
            # Prepare candidates
            candidates = [
                (0, img_bgr),
                (90, cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)),
                (180, cv2.rotate(img_bgr, cv2.ROTATE_180)),
                (270, cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)),
            ]

            results = []
            k = 0.5  # weight for structure score

            # Downscale to speed OCR scoring if very large
            def downscale(bgr: np.ndarray, limit: int = 1200) -> np.ndarray:
                h, w = bgr.shape[:2]
                maxdim = max(h, w)
                if maxdim <= limit:
                    return bgr
                scale = limit / float(maxdim)
                return cv2.resize(
                    bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
                )

            for angle, img in candidates:
                img_small = downscale(img)
                try:
                    ocr = self._ocr_score(img_small)
                except Exception:
                    ocr = 0.0
                try:
                    orient = self._orientation_score(
                        cv2.cvtColor(img_small, cv2.COLOR_BGR2GRAY)
                    )
                except Exception:
                    orient = 0.0
                composite = ocr + k * orient
                results.append(
                    {"angle": angle, "ocr": ocr, "orient": orient, "score": composite}
                )

            # Pick best by score; tie-breakers: prefer angle==0, then prefer angle!=180
            results_sorted = sorted(
                results,
                key=lambda r: (
                    r["score"],
                    1 if r["angle"] == 0 else 0,
                    1 if r["angle"] != 180 else 0,
                ),
                reverse=True,
            )
            best = results_sorted[0]

            # If 180 is best but within a small margin to 0, prefer 0 to avoid upside-down
            if best["angle"] == 180:
                zero = next((r for r in results if r["angle"] == 0), None)
                if zero and (best["score"] - zero["score"]) < 2.0:
                    best = zero

            chosen_angle = int(best["angle"])
            # Return the matching image
            if chosen_angle == 0:
                best_img = candidates[0][1]
            elif chosen_angle == 90:
                best_img = candidates[1][1]
            elif chosen_angle == 180:
                best_img = candidates[2][1]
            else:
                best_img = candidates[3][1]

            details = {"candidates": results}
            return best_img, chosen_angle, details
        except Exception:
            # Fallback to orientation-only upright
            return self._auto_upright(img_bgr), 0, {"fallback": True}

    def create_annotated_image_for_gpt(
        self, image: Image.Image, fields_data: list, with_numbers=True
    ):
        """
        Draws numbered boxes on the image for analysis by the AI model.
        """
        base_img = image.copy().convert("RGBA")
        overlay = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        sorted_boxes = [f["box"] for f in fields_data]
        for i, (x, y, w_box, h_box) in enumerate(sorted_boxes):
            draw.rectangle([x, y, x + w_box, y + h_box], fill=(0, 100, 255, 100))
            if with_numbers:
                text = str(i + 1)
                font_size = max(15, int(h_box * 0.7))
                try:
                    font = ImageFont.truetype("arialbd.ttf", font_size)
                except IOError:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except IOError:
                        font = ImageFont.load_default()

                try:
                    text_bbox = draw.textbbox((0, 0), text, font=font)
                    text_w, text_h = (
                        text_bbox[2] - text_bbox[0],
                        text_bbox[3] - text_bbox[1],
                    )
                except AttributeError:
                    text_w, text_h = draw.textsize(text, font=font)

                text_x = x + (w_box - text_w) / 2
                text_y = y + (h_box - text_h) / 2
                draw.text((text_x, text_y), text, fill="red", font=font)
        return Image.alpha_composite(base_img, overlay)

    def create_final_annotated_image(
        self,
        image: Image.Image,
        texts_dict: dict,
        ui_fields: list,
        signature_image_b64: Optional[str] = None,
        signature_field_id: Optional[str] = None,
    ):
        """
        Draws the user's final text, checkmarks, and signature onto the image.
        """
        if not texts_dict and not signature_image_b64:
            return image

        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)

        # --- Font setup ---
        # Handle both dict and object formats for ui_fields
        text_fields = []
        for f in ui_fields:
            if isinstance(f, dict):
                field_type = f.get("type", "")
                field_box = f.get("box", [])
            else:
                field_type = getattr(f, "type", "")
                field_box = getattr(f, "box", [])

            if field_type in ["textbox", "text"] and field_box:
                text_fields.append(field_box)

        if not text_fields:
            avg_height = 20
        else:
            avg_height = sum(box[3] for box in text_fields) / len(text_fields)
        default_font_size = max(12, int(avg_height * 0.6))  # Ensure minimum font size

        # Try multiple font options for better Arabic support
        arabic_font = None
        default_font = None

        # Use Amiri font manager to get best Arabic font
        arabic_font = amiri_manager.get_arabic_font(default_font_size)

        # خطوط افتراضية للنصوص الإنجليزية
        default_font_options = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "arial.ttf",
        ]

        # تحميل خط افتراضي للنصوص الإنجليزية
        default_font = None
        for font_path in default_font_options:
            try:
                default_font = ImageFont.truetype(font_path, default_font_size)
                break
            except (IOError, OSError):
                continue

        # Fallback in case of no fonts
        if default_font is None:
            default_font = ImageFont.load_default()

        # --- Signature Handling ---
        if signature_image_b64 and signature_field_id:
            try:
                sig_bytes = base64.b64decode(signature_image_b64)
                sig_image = Image.open(io.BytesIO(sig_bytes)).convert("RGBA")

                # Find the specific signature field by its ID
                signature_field_found = False
                for field in ui_fields:
                    # Handle both dict and object formats
                    if isinstance(field, dict):
                        field_box_id = field.get("box_id", "")
                        field_box = field.get("box", [])
                    else:
                        field_box_id = getattr(field, "box_id", "")
                        field_box = getattr(field, "box", [])

                    if field_box_id == signature_field_id and field_box:
                        signature_field_found = True
                        x, y, w, h = map(int, field_box)  # Convert to integers

                        # Resize signature to fit the box with better scaling
                        # Calculate aspect ratios
                        box_ratio = w / h
                        sig_ratio = sig_image.width / sig_image.height

                        # Scale to fit within the box while maintaining aspect ratio
                        if sig_ratio > box_ratio:
                            # Signature is wider, scale by width
                            new_width = int(w * 0.8)  # Use 80% of box width for padding
                            new_height = int(new_width / sig_ratio)
                        else:
                            # Signature is taller, scale by height
                            new_height = int(
                                h * 0.8
                            )  # Use 80% of box height for padding
                            new_width = int(new_height * sig_ratio)

                        # Resize the signature
                        sig_image = sig_image.resize(
                            (new_width, new_height), Image.Resampling.LANCZOS
                        )

                        # Calculate position to center the signature in the box
                        paste_x = int(x + (w - new_width) // 2)
                        paste_y = int(y + (h - new_height) // 2)

                        # Paste the signature
                        annotated.paste(sig_image, (paste_x, paste_y), sig_image)

                        # Remove this field from text processing
                        if field_box_id in texts_dict:
                            del texts_dict[field_box_id]
                        break

            except Exception:
                pass
        elif signature_image_b64:
            # Fallback: if signature_field_id is not provided, use the old method
            try:
                sig_bytes = base64.b64decode(signature_image_b64)
                sig_image = Image.open(io.BytesIO(sig_bytes)).convert("RGBA")

                for field in ui_fields:
                    # Handle both dict and object formats
                    if isinstance(field, dict):
                        field_label = field.get("label", "").lower()
                        field_box = field.get("box", [])
                        field_box_id = field.get("box_id", "")
                    else:
                        field_label = getattr(field, "label", "").lower()
                        field_box = getattr(field, "box", [])
                        field_box_id = getattr(field, "box_id", "")

                    if (
                        any(
                            keyword in field_label
                            for keyword in ["signature", "توقيع", "امضاء"]
                        )
                        and field_box
                    ):
                        x, y, w, h = map(int, field_box)  # Convert to integers

                        # Apply the same improved scaling logic
                        box_ratio = w / h
                        sig_ratio = sig_image.width / sig_image.height

                        if sig_ratio > box_ratio:
                            new_width = int(w * 0.8)
                            new_height = int(new_width / sig_ratio)
                        else:
                            new_height = int(h * 0.8)
                            new_width = int(new_height * sig_ratio)

                        sig_image = sig_image.resize(
                            (new_width, new_height), Image.Resampling.LANCZOS
                        )

                        paste_x = int(x + (w - new_width) // 2)
                        paste_y = int(y + (h - new_height) // 2)

                        annotated.paste(sig_image, (paste_x, paste_y), sig_image)

                        if field_box_id in texts_dict:
                            del texts_dict[field_box_id]
                        break
            except Exception:
                pass

        # --- Text and Checkbox Drawing ---
        for field in ui_fields:
            # Handle both dict and object formats
            if isinstance(field, dict):
                box_id = field.get("box_id", "")
                field_box = field.get("box", [])
                field_type = field.get("type", "")
            else:
                box_id = getattr(field, "box_id", "")
                field_box = getattr(field, "box", [])
                field_type = getattr(field, "type", "")

            value = texts_dict.get(box_id)

            if value and field_box:
                x, y, w, h = field_box

                # Handle field type variations
                if field_type in ["checkbox"] and value is True:
                    # Use multiple methods to draw checkmark
                    self._draw_checkbox_checkmark(draw, x, y, w, h)

                elif (
                    field_type in ["textbox", "text"]
                    and isinstance(value, str)
                    and value.strip()
                ):
                    padding = 4
                    is_arabic = is_arabic_text(value)

                    # Enhanced Arabic text processing using Amiri font manager
                    if is_arabic:
                        # Use new function to process Arabic text correctly
                        # We need to reshape only without reversing direction
                        display_text = reshape_arabic_text(value, for_display=False)
                        font = arabic_font
                    else:
                        display_text = value
                        font = default_font

                    # Calculate text size more accurately
                    try:
                        text_bbox = draw.textbbox((0, 0), display_text, font=font)
                        text_w, text_h = (
                            text_bbox[2] - text_bbox[0],
                            text_bbox[3] - text_bbox[1],
                        )
                    except AttributeError:
                        # Fallback for older PIL versions
                        text_w, text_h = draw.textsize(display_text, font=font)

                    # Adjust font size if text is too large for the box
                    if text_w > (w - 2 * padding):
                        scale_factor = (w - 2 * padding) / text_w
                        new_font_size = max(8, int(default_font_size * scale_factor))

                        if is_arabic:
                            # Use Amiri manager to get font with new size
                            font = amiri_manager.get_arabic_font(new_font_size)
                        else:
                            # Update default font with new size
                            for font_path in default_font_options:
                                try:
                                    font = ImageFont.truetype(font_path, new_font_size)
                                    break
                                except (IOError, OSError):
                                    continue

                        if font is None:
                            font = ImageFont.load_default()

                    # Position text in the middle of the box
                    draw_y = y + h / 2

                    if is_arabic:
                        # Right-align Arabic text and use correct text direction
                        # Arabic text is only reshaped and already in correct right-to-left direction
                        draw.text(
                            (x + w - padding, draw_y),
                            display_text,
                            fill="black",
                            font=font,
                            anchor="rm",
                        )
                    else:
                        # Left-align English text
                        draw.text(
                            (x + padding, draw_y),
                            display_text,
                            fill="black",
                            font=font,
                            anchor="lm",
                        )
        return annotated

    def combine_yolo_and_gpt_results(self, fields_data, gpt_results):
        """
        Merges the results from YOLO (box coordinates) and GPT (labels).
        """
        final_fields = []
        gpt_map = {
            res["id"]: res["label"]
            for res in gpt_results
            if "id" in res and "label" in res
        }
        for i, field_data in enumerate(fields_data):
            box_number = i + 1
            label = gpt_map.get(box_number)
            if label:
                class_name = str(field_data["class"]).lower()
                field_type = (
                    "textbox"
                    if "text" in class_name or "line" in class_name
                    else "checkbox"
                )
                final_fields.append(
                    {
                        "box_id": f"box_{i}",
                        "label": label,
                        "type": field_type,
                        "box": field_data["box"],
                    }
                )
        return final_fields

    def _draw_checkbox_checkmark(self, draw, x, y, w, h):
        """
        Simple checkbox fill - most reliable and visible method
        """
        # Add small padding so it doesn't touch the checkbox border
        padding = 3

        # Fill the entire checkbox area with black
        draw.rectangle(
            [x + padding, y + padding, x + w - padding, y + h - padding],
            fill="black",
            outline="black",
            width=2,
        )
