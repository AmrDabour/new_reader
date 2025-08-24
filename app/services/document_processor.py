import io
import base64
import tempfile
import os
from PIL import Image
from typing import Dict, List, Any
import logging
from app.utils.text import clean_and_format_text

logger = logging.getLogger(__name__)

# Document processing libraries
try:
    from spire.presentation.common import *
    from spire.presentation import *

    SPIRE_AVAILABLE = True
except ImportError:
    SPIRE_AVAILABLE = False
    logger.warning("Spire.Presentation not available. PowerPoint support disabled.")

try:
    import fitz  # PyMuPDF

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyMuPDF not available. PDF support disabled.")


class DocumentProcessor:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def process_document(
        self, file_content: bytes, file_extension: str
    ) -> Dict[str, Any]:
        """
        Process document and convert to images with text extraction
        """
        try:
            if file_extension.lower() == ".pdf":
                return self._process_pdf(file_content)
            elif file_extension.lower() in [".pptx", ".ppt"]:
                return self._process_powerpoint(file_content)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")

        except Exception:
            return self._create_fallback_document("unknown")

    def _process_pdf(self, file_content: bytes) -> Dict[str, Any]:
        """Process PDF file with embedded image extraction"""
        if not PDF_AVAILABLE:
            raise ImportError("PyMuPDF library is required for PDF processing")

        try:
            # Open PDF from bytes - create file-like object
            file_stream = io.BytesIO(file_content)
            pdf_document = fitz.open(stream=file_stream, filetype="pdf")
            pages = []
            total_pages = len(pdf_document)

            for page_num in range(total_pages):
                page = pdf_document[page_num]

                # Extract text from page and clean it
                page_text = page.get_text()
                cleaned_text = clean_and_format_text(page_text)

                # Extract embedded images from this page
                embedded_images = self._extract_embedded_images_from_pdf(
                    page, pdf_document
                )

                # Use first embedded image if available, otherwise create page render
                if embedded_images:
                    image_base64 = embedded_images[0]  # Use first embedded image
                else:
                    # Fallback: render page as image if no embedded images
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("ppm")
                    pil_image = Image.open(io.BytesIO(img_data))
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")
                    image_base64 = self._image_to_base64(pil_image)

                # Create page data
                page_data = {
                    "page_number": page_num + 1,
                    "title": f"Page {page_num + 1}",
                    "text": cleaned_text,
                    "image_base64": image_base64,
                    "notes": "",
                    "has_embedded_images": len(embedded_images) > 0,
                    "embedded_images_count": len(embedded_images),
                }

                pages.append(page_data)

            pdf_document.close()

            return {"file_type": ".pdf", "total_pages": total_pages, "pages": pages}

        except Exception:
            # Create fallback response instead of failing
            return self._create_fallback_document("pdf")

    def _process_powerpoint(self, file_content: bytes) -> Dict[str, Any]:
        """Process PowerPoint file"""
        if not SPIRE_AVAILABLE:
            raise ImportError(
                "Spire.Presentation library is required for PowerPoint processing"
            )

        try:
            # Save content to temporary file
            temp_file = os.path.join(self.temp_dir, "temp_presentation.pptx")
            with open(temp_file, "wb") as f:
                f.write(file_content)

            # Load presentation using Spire.Presentation
            presentation = Presentation()
            presentation.LoadFromFile(temp_file)

            pages = []
            total_slides = len(presentation.Slides)

            for i, slide in enumerate(presentation.Slides):
                try:
                    # Extract slide text first (safer operation)
                    slide_text = self._extract_slide_text(slide)

                    # Extract embedded images from slide
                    embedded_images = self._extract_embedded_images_from_slide(slide)

                    # Use first embedded image if available, otherwise render slide
                    if embedded_images:
                        image_base64 = embedded_images[0]  # Use first embedded image
                    else:
                        # Fallback: render slide as image if no embedded images
                        image_base64 = self._save_slide_as_image(slide, i)

                    # Create slide data
                    slide_data = {
                        "page_number": i + 1,
                        "title": f"Slide {i + 1}",
                        "text": slide_text,
                        "image_base64": image_base64,
                        "notes": "",
                        "has_embedded_images": len(embedded_images) > 0,
                        "embedded_images_count": len(embedded_images),
                    }

                    pages.append(slide_data)

                except Exception as e:
                    logger.warning(f"Error processing slide {i}: {str(e)}")
                    # Create fallback slide data with text extraction attempt
                    try:
                        slide_text = self._extract_slide_text(slide)
                    except:
                        slide_text = f"Slide {i + 1} content could not be extracted"

                    # Create simple fallback image
                    blank_image = Image.new("RGB", (1920, 1080), "white")
                    image_base64 = self._image_to_base64(blank_image)

                    slide_data = {
                        "page_number": i + 1,
                        "title": f"Slide {i + 1}",
                        "text": slide_text,
                        "image_base64": image_base64,
                        "notes": "",
                    }
                    pages.append(slide_data)

            # Cleanup
            presentation.Dispose()
            try:
                os.remove(temp_file)
            except:
                pass

            return {"file_type": ".pptx", "total_pages": total_slides, "pages": pages}

        except Exception:
            # Create fallback response instead of failing
            return self._create_fallback_document("pptx")

    def _save_slide_as_image(self, slide, slide_index: int) -> str:
        """Save slide as image with font error handling"""
        temp_image_path = None
        try:
            # Try to save slide as image
            temp_image_path = os.path.join(self.temp_dir, f"slide_{slide_index}.png")

            # Try different methods to get slide image
            try:
                # Method 1: Standard SaveAsImage
                image = slide.SaveAsImage()
                image.Save(temp_image_path)
            except Exception as font_error:
                # Check if it's a font-related error
                error_msg = str(font_error).lower()
                if "font" in error_msg or "cannot found font" in error_msg:
                    logger.warning(
                        f"Font error in slide {slide_index}, trying alternative method: {font_error}"
                    )
                    # Try alternative method or create fallback
                    return self._create_fallback_slide_image(slide_index)
                else:
                    # Re-raise if it's not a font error
                    raise

            # Load and process the saved image
            if os.path.exists(temp_image_path):
                pil_image = Image.open(temp_image_path)
                if pil_image.mode != "RGB":
                    pil_image = pil_image.convert("RGB")

                # Convert to base64
                image_base64 = self._image_to_base64(pil_image)
                return image_base64
            else:
                # If file wasn't created, use fallback
                return self._create_fallback_slide_image(slide_index)

        except Exception as e:
            logger.warning(f"Failed to save slide {slide_index} as image: {str(e)}")
            return self._create_fallback_slide_image(slide_index)

        finally:
            # Clean up temp image file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.remove(temp_image_path)
                except:
                    pass

    def _create_fallback_slide_image(self, slide_index: int) -> str:
        """Create fallback image for slide"""
        try:
            # Create a simple image with slide number
            fallback_image = Image.new("RGB", (1920, 1080), "white")

            # You could add text or graphics here if PIL supports it
            # For now, just return the white image
            return self._image_to_base64(fallback_image)

        except Exception as e:
            logger.error(
                f"Failed to create fallback image for slide {slide_index}: {str(e)}"
            )
            # Return empty string as last resort
            return ""

    def _extract_slide_text(self, slide) -> str:
        """Extract text from slide"""
        text_parts = []

        try:
            # Method 1: Try to get all text from slide directly
            try:
                if hasattr(slide, "GetAllTexts"):
                    all_text = slide.GetAllTexts()
                    if all_text and all_text.strip():
                        return clean_and_format_text(all_text)
            except Exception:
                pass

            # Method 2: Extract text from shapes
            try:
                for shape_index in range(slide.Shapes.Count):
                    shape = slide.Shapes[shape_index]

                    try:
                        # Check different ways to access text
                        text_content = None

                        # Try TextFrame approach
                        if hasattr(shape, "TextFrame") and shape.TextFrame is not None:
                            text_frame = shape.TextFrame

                            # Try direct Text property
                            if hasattr(text_frame, "Text") and text_frame.Text:
                                text_content = text_frame.Text.strip()

                            # Try Paragraphs approach
                            elif (
                                hasattr(text_frame, "Paragraphs")
                                and text_frame.Paragraphs
                            ):
                                para_texts = []
                                try:
                                    for para_index in range(
                                        text_frame.Paragraphs.Count
                                    ):
                                        para = text_frame.Paragraphs[para_index]
                                        if hasattr(para, "Text") and para.Text:
                                            para_texts.append(para.Text.strip())
                                except Exception:
                                    # Try iterating directly
                                    for para in text_frame.Paragraphs:
                                        if hasattr(para, "Text") and para.Text:
                                            para_texts.append(para.Text.strip())

                                if para_texts:
                                    text_content = "\n".join(para_texts)

                        # Try alternative text access methods
                        if not text_content:
                            if (
                                hasattr(shape, "AlternativeText")
                                and shape.AlternativeText
                            ):
                                text_content = shape.AlternativeText.strip()
                            elif hasattr(shape, "Title") and shape.Title:
                                text_content = shape.Title.strip()

                        # Add text if found
                        if text_content and text_content.strip():
                            text_parts.append(text_content)

                    except Exception:
                        continue

            except Exception:
                pass

            # Method 3: Try Notes or other slide properties
            try:
                if hasattr(slide, "NotesPage") and slide.NotesPage:
                    notes_page = slide.NotesPage
                    if (
                        hasattr(notes_page, "NotesTextFrame")
                        and notes_page.NotesTextFrame
                    ):
                        notes_text = notes_page.NotesTextFrame.Text
                        if notes_text and notes_text.strip():
                            text_parts.append(f"Notes: {notes_text.strip()}")
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Error extracting text from slide: {str(e)}")

        # Clean and format the extracted text
        combined_text = "\n".join(text_parts) if text_parts else ""
        return clean_and_format_text(combined_text)

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL image to base64"""
        try:
            # Resize image if too large
            max_size = 4096  # Increased from 1920 for better quality
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            img_bytes = buffer.getvalue()

            return base64.b64encode(img_bytes).decode("utf-8")

        except Exception as e:
            logger.error(f"Error converting image to base64: {str(e)}")
            raise

    def get_supported_formats(self) -> List[str]:
        """الحصول على الأنواع المدعومة"""
        formats = []
        if SPIRE_AVAILABLE:
            formats.extend([".pptx", ".ppt"])
        if PDF_AVAILABLE:
            formats.append(".pdf")
        return formats

    def is_format_supported(self, file_extension: str) -> bool:
        """التحقق من دعم نوع الملف"""
        return file_extension.lower() in self.get_supported_formats()

    def _create_fallback_document(self, file_type: str) -> Dict[str, Any]:
        """Create dummy document in case of processing failure"""
        try:
            # Create a simple white image as fallback
            fallback_image = Image.new("RGB", (1920, 1080), "white")
            image_base64 = self._image_to_base64(fallback_image)

            # Create fallback content based on file type
            if file_type == "pdf":
                content_text = "Document content could not be loaded. PDF processing is temporarily unavailable."
                file_ext = ".pdf"
            elif file_type == "pptx":
                content_text = "Presentation content could not be loaded. PowerPoint processing is temporarily unavailable."
                file_ext = ".pptx"
            else:
                content_text = "Document content could not be loaded. File format processing is temporarily unavailable."
                file_ext = ".unknown"

            fallback_page = {
                "page_number": 1,
                "title": "Document Preview Unavailable",
                "text": content_text,
                "image_base64": image_base64,
                "notes": "",
            }

            return {"file_type": file_ext, "total_pages": 1, "pages": [fallback_page]}

        except Exception as e:
            logger.error(f"Error creating fallback document: {str(e)}")
            # Ultimate fallback - return minimal structure
            return {
                "file_type": ".unknown",
                "total_pages": 1,
                "pages": [
                    {
                        "page_number": 1,
                        "title": "Error",
                        "text": "Unable to process document",
                        "image_base64": "",
                        "notes": "",
                    }
                ],
            }

    def __del__(self):
        """تنظيف المجلد المؤقت"""
        try:
            import shutil

            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _extract_embedded_images_from_pdf(self, page, pdf_document) -> List[str]:
        """Extract actual embedded images from PDF page"""
        images = []
        try:
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]

                    # Convert to PIL Image
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")

                    image_base64 = self._image_to_base64(pil_image)
                    images.append(image_base64)

                except Exception as e:
                    logger.warning(
                        f"Failed to extract embedded image {img_index}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.warning(f"Failed to get embedded images from page: {str(e)}")

        return images

    def _extract_embedded_images_from_slide(self, slide) -> List[str]:
        """Extract actual embedded images from PowerPoint slide"""
        images = []
        try:
            for shape_index in range(slide.Shapes.Count):
                try:
                    shape = slide.Shapes[shape_index]

                    # Check if shape is an image/picture
                    if hasattr(shape, "ShapeType") and hasattr(shape, "Image"):
                        try:
                            # Try to access image data
                            if hasattr(shape.Image, "Data") and shape.Image.Data:
                                image_data = shape.Image.Data
                                pil_image = Image.open(io.BytesIO(image_data))
                                if pil_image.mode != "RGB":
                                    pil_image = pil_image.convert("RGB")

                                image_base64 = self._image_to_base64(pil_image)
                                images.append(image_base64)

                        except Exception as img_error:
                            logger.debug(
                                f"Could not extract image from shape {shape_index}: {str(img_error)}"
                            )
                            continue

                except Exception as shape_error:
                    logger.debug(
                        f"Could not process shape {shape_index}: {str(shape_error)}"
                    )
                    continue

        except Exception as e:
            logger.warning(f"Failed to extract embedded images from slide: {str(e)}")

        return images
