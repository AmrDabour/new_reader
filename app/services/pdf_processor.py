import io
import base64
from typing import List, Dict, Any, Tuple
from PIL import Image
import logging

logger = logging.getLogger(__name__)

# PDF processing libraries
try:
    import fitz  # PyMuPDF

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyMuPDF not available. PDF support disabled.")


class PDFProcessor:
    """PDF processor for form analysis"""

    def __init__(self):
        self.max_pages = 50  # Maximum number of pages for processing
        self.dpi = 600  # Image conversion quality (increased from 300 for better form analysis)

    def is_pdf_supported(self) -> bool:
        """Check if PDF processing is supported"""
        return PDF_AVAILABLE

    def convert_pdf_to_images(self, file_content: bytes) -> List[Dict[str, Any]]:
        """
        Convert PDF to a collection of images with page information

        Returns:
            List[Dict]: List of page information containing:
                - page_number: Page number
                - image: PIL Image object
                - image_base64: Base64 encoded image
                - width: Image width
                - height: Image height
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyMuPDF library is required for PDF processing")

        try:
            # Open PDF from bytes
            file_stream = io.BytesIO(file_content)
            pdf_document = fitz.open(stream=file_stream, filetype="pdf")

            total_pages = len(pdf_document)

            # Check page count
            if total_pages > self.max_pages:
                pdf_document.close()
                raise ValueError(
                    f"PDF has too many pages ({total_pages}). Maximum allowed: {self.max_pages}"
                )

            pages_data = []

            for page_num in range(total_pages):
                try:
                    page = pdf_document[page_num]

                    # Convert page to high quality image
                    mat = fitz.Matrix(
                        self.dpi / 72, self.dpi / 72
                    )  # Convert DPI to zoom factor
                    pix = page.get_pixmap(matrix=mat)

                    # Convert to PIL Image
                    img_data = pix.tobytes("ppm")
                    pil_image = Image.open(io.BytesIO(img_data))

                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")

                    # Convert to base64
                    image_base64 = self._image_to_base64(pil_image)

                    page_data = {
                        "page_number": page_num + 1,
                        "image": pil_image,
                        "image_base64": image_base64,
                        "width": pil_image.width,
                        "height": pil_image.height,
                    }

                    pages_data.append(page_data)

                except Exception as e:
                    logger.error(f"Error processing page {page_num + 1}: {str(e)}")
                    # Create fallback page in case of error
                    fallback_image = Image.new(
                        "RGB", (2100, 2970), "white"
                    )  # A4 size at 300 DPI
                    fallback_base64 = self._image_to_base64(fallback_image)

                    pages_data.append(
                        {
                            "page_number": page_num + 1,
                            "image": fallback_image,
                            "image_base64": fallback_base64,
                            "width": fallback_image.width,
                            "height": fallback_image.height,
                            "error": f"Failed to process page: {str(e)}",
                        }
                    )

            pdf_document.close()
            return pages_data

        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            raise

    def get_pdf_info(self, file_content: bytes) -> Dict[str, Any]:
        """
        الحصول على معلومات PDF الأساسية

        Returns:
            Dict: معلومات PDF تحتوي على:
                - total_pages: عدد الصفحات
                - title: عنوان المستند (إذا متوفر)
                - author: المؤلف (إذا متوفر)
                - subject: الموضوع (إذا متوفر)
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyMuPDF library is required for PDF processing")

        try:
            file_stream = io.BytesIO(file_content)
            pdf_document = fitz.open(stream=file_stream, filetype="pdf")

            metadata = pdf_document.metadata
            info = {
                "total_pages": len(pdf_document),
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
            }

            pdf_document.close()
            return info

        except Exception as e:
            logger.error(f"Error getting PDF info: {str(e)}")
            return {"total_pages": 0, "error": str(e)}

    def extract_page_text(self, file_content: bytes, page_number: int) -> str:
        """
        Extract text from specific page in PDF

        Args:
            file_content: محتوى ملف PDF
            page_number: رقم الصفحة (يبدأ من 1)

        Returns:
            str: Text extracted from page
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyMuPDF library is required for PDF processing")

        try:
            file_stream = io.BytesIO(file_content)
            pdf_document = fitz.open(stream=file_stream, filetype="pdf")

            if page_number < 1 or page_number > len(pdf_document):
                pdf_document.close()
                raise ValueError(f"Invalid page number: {page_number}")

            page = pdf_document[page_number - 1]  # Convert to zero-based index
            text = page.get_text()

            pdf_document.close()
            return text.strip()

        except Exception as e:
            logger.error(f"Error extracting text from page {page_number}: {str(e)}")
            return ""

    def split_pdf_by_language(
        self, pages_data: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize PDF pages by language direction (RTL/LTR)
        This function can be expanded later to use AI for language detection

        Args:
            pages_data: List of PDF pages converted to images

        Returns:
            Dict: Pages categorized by language direction
        """
        categorized = {"rtl": [], "ltr": [], "mixed": []}

        # حالياً نضع جميع الصفحات تحت RTL كافتراضي
        # Can be improved later using AI for text analysis
        for page_data in pages_data:
            categorized["rtl"].append(page_data)

        return categorized

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL image to base64"""
        try:
            # Reduce image size if too large
            max_size = 4096  # الحد الأقصى للعرض أو الارتفاع
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Convert to base64
            buffer = io.BytesIO()
            # Use high quality for forms - PNG is lossless so quality parameter not needed
            image.save(buffer, format="PNG", optimize=True)
            img_bytes = buffer.getvalue()

            return base64.b64encode(img_bytes).decode("utf-8")

        except Exception as e:
            logger.error(f"Error converting image to base64: {str(e)}")
            raise

    def validate_pdf_for_forms(self, file_content: bytes) -> Tuple[bool, str]:
        """
        Validate PDF for form analysis

        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        try:
            info = self.get_pdf_info(file_content)

            if "error" in info:
                return False, f"Error reading PDF: {info['error']}"

            total_pages = info.get("total_pages", 0)

            if total_pages == 0:
                return False, "PDF is empty or corrupted"

            if total_pages > self.max_pages:
                return (
                    False,
                    f"PDF has too many pages ({total_pages}). Maximum allowed: {self.max_pages}",
                )

            # Additional checks can be added here
            # such as checking for fillable forms

            return True, f"PDF is valid for processing ({total_pages} pages)"

        except Exception as e:
            return False, f"Error validating PDF: {str(e)}"
