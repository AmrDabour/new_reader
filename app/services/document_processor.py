import io
import base64
import tempfile
import os
from PIL import Image
from typing import Dict, List, Any
import logging

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

    def process_document(self, file_content: bytes, file_extension: str) -> Dict[str, Any]:
        """
        معالجة المستند وتحويله إلى صور مع استخراج النصوص
        """
        try:
            if file_extension.lower() == ".pdf":
                return self._process_pdf(file_content)
            elif file_extension.lower() in [".pptx", ".ppt"]:
                return self._process_powerpoint(file_content)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")

        except Exception as e:
            logger.debug(f"Document processing failed, using fallback: {str(e)}")
            return self._create_fallback_document("unknown")

    def _process_pdf(self, file_content: bytes) -> Dict[str, Any]:
        """معالجة ملف PDF"""
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

                # Convert page to image with high quality
                mat = fitz.Matrix(2.0, 2.0)  # Scale factor for better quality
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("ppm")
                pil_image = Image.open(io.BytesIO(img_data))

                if pil_image.mode != "RGB":
                    pil_image = pil_image.convert("RGB")

                # Convert to base64
                image_base64 = self._image_to_base64(pil_image)

                # Extract text from page
                page_text = page.get_text()

                # Create page data
                page_data = {
                    "page_number": page_num + 1,
                    "title": f"Page {page_num + 1}",
                    "text": page_text.strip(),
                    "image_base64": image_base64,
                    "notes": "",
                }

                pages.append(page_data)

            pdf_document.close()

            return {"file_type": ".pdf", "total_pages": total_pages, "pages": pages}

        except Exception as e:
            # Create fallback response instead of failing
            logger.debug(f"PDF processing failed, using fallback: {str(e)}")
            return self._create_fallback_document("pdf")

    def _process_powerpoint(self, file_content: bytes) -> Dict[str, Any]:
        """معالجة ملف PowerPoint"""
        if not SPIRE_AVAILABLE:
            raise ImportError("Spire.Presentation library is required for PowerPoint processing")

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
                    # Save slide as temporary image using Spire
                    temp_image_path = os.path.join(self.temp_dir, f"slide_{i}.png")
                    image = slide.SaveAsImage()
                    image.Save(temp_image_path)

                    # Load image with PIL
                    pil_image = Image.open(temp_image_path)
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")

                    # Convert to base64
                    image_base64 = self._image_to_base64(pil_image)

                    # Extract slide text content using Spire
                    slide_text = self._extract_slide_text(slide)

                    # Create slide data
                    slide_data = {
                        "page_number": i + 1,
                        "title": f"Slide {i + 1}",
                        "text": slide_text,
                        "image_base64": image_base64,
                        "notes": "",
                    }

                    pages.append(slide_data)

                    # Clean up temp image file
                    try:
                        os.remove(temp_image_path)
                    except:
                        pass

                except Exception as e:
                    logger.error(f"Error processing slide {i}: {str(e)}")
                    # Create fallback slide data
                    blank_image = Image.new("RGB", (1920, 1080), "white")
                    image_base64 = self._image_to_base64(blank_image)

                    slide_data = {
                        "page_number": i + 1,
                        "title": f"Slide {i + 1}",
                        "text": "Error loading slide content",
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

        except Exception as e:
            # Create fallback response instead of failing  
            logger.debug(f"PowerPoint processing failed, using fallback: {str(e)}")
            return self._create_fallback_document("pptx")

    def _extract_slide_text(self, slide) -> str:
        """استخراج النص من شريحة PowerPoint"""
        try:
            texts = []

            # Iterate through all shapes in the slide
            for shape in slide.Shapes:
                try:
                    # Check if shape has TextFrame
                    if hasattr(shape, "TextFrame") and shape.TextFrame is not None:
                        # Method 1: Try to get text directly
                        try:
                            if hasattr(shape.TextFrame, "Text") and shape.TextFrame.Text:
                                text_content = shape.TextFrame.Text.strip()
                                if text_content:
                                    texts.append(text_content)
                                    continue
                        except Exception as e:
                            logger.debug(f"Direct text access failed: {str(e)}")

                        # Method 2: Try to get text through paragraphs
                        try:
                            if hasattr(shape.TextFrame, "Paragraphs"):
                                paragraph_texts = []
                                paragraphs = shape.TextFrame.Paragraphs

                                # Handle different ways paragraphs might be accessed
                                if hasattr(paragraphs, "__len__"):
                                    # If paragraphs is iterable
                                    for paragraph in paragraphs:
                                        if hasattr(paragraph, "Text") and paragraph.Text:
                                            paragraph_texts.append(paragraph.Text.strip())
                                elif hasattr(paragraphs, "Count"):
                                    # If paragraphs has Count property
                                    for i in range(paragraphs.Count):
                                        paragraph = paragraphs[i]
                                        if hasattr(paragraph, "Text") and paragraph.Text:
                                            paragraph_texts.append(paragraph.Text.strip())

                                if paragraph_texts:
                                    texts.append("\n".join(paragraph_texts))
                                    continue
                        except Exception as e:
                            logger.debug(f"Paragraph text access failed: {str(e)}")

                        # Method 3: Try alternative text access methods
                        try:
                            # Check for other text properties
                            if hasattr(shape, "AlternativeText") and shape.AlternativeText:
                                texts.append(shape.AlternativeText.strip())
                        except Exception as e:
                            logger.debug(f"Alternative text access failed: {str(e)}")

                except Exception as e:
                    logger.debug(f"Error processing shape: {str(e)}")
                    continue

            # Return combined text or empty string
            return "\n\n".join(texts) if texts else ""

        except Exception as e:
            logger.error(f"Error extracting slide text: {str(e)}")
            return ""

    def _image_to_base64(self, image: Image.Image) -> str:
        """تحويل صورة PIL إلى base64"""
        try:
            # Resize image if too large
            max_size = 1920
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
        """إنشاء مستند تجريبي في حالة فشل المعالجة"""
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
            
            return {
                "file_type": file_ext,
                "total_pages": 1,
                "pages": [fallback_page]
            }
            
        except Exception as e:
            logger.error(f"Error creating fallback document: {str(e)}")
            # Ultimate fallback - return minimal structure
            return {
                "file_type": ".unknown",
                "total_pages": 1,
                "pages": [{
                    "page_number": 1,
                    "title": "Error",
                    "text": "Unable to process document",
                    "image_base64": "",
                    "notes": "",
                }]
            }

    def __del__(self):
        """تنظيف المجلد المؤقت"""
        try:
            import shutil
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass 