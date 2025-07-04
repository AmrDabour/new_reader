import io
import base64
from typing import List, Dict, Any, Optional, Tuple
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
    """معالج PDF خاص لنماذج التحليل"""
    
    def __init__(self):
        self.max_pages = 50  # الحد الأقصى لعدد الصفحات للمعالجة
        self.dpi = 300  # جودة التحويل للصور
    
    def is_pdf_supported(self) -> bool:
        """التحقق من دعم معالجة PDF"""
        return PDF_AVAILABLE
    
    def convert_pdf_to_images(self, file_content: bytes) -> List[Dict[str, Any]]:
        """
        تحويل PDF إلى مجموعة من الصور مع معلومات كل صفحة
        
        Returns:
            List[Dict]: قائمة بمعلومات كل صفحة تحتوي على:
                - page_number: رقم الصفحة
                - image: PIL Image object
                - image_base64: الصورة مُرمزة بـ base64
                - width: عرض الصورة
                - height: ارتفاع الصورة
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyMuPDF library is required for PDF processing")
        
        try:
            # فتح PDF من البايتات
            file_stream = io.BytesIO(file_content)
            pdf_document = fitz.open(stream=file_stream, filetype="pdf")
            
            total_pages = len(pdf_document)
            
            # التحقق من عدد الصفحات
            if total_pages > self.max_pages:
                pdf_document.close()
                raise ValueError(f"PDF has too many pages ({total_pages}). Maximum allowed: {self.max_pages}")
            
            pages_data = []
            
            for page_num in range(total_pages):
                try:
                    page = pdf_document[page_num]
                    
                    # تحويل الصفحة إلى صورة عالية الجودة
                    mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)  # تحويل DPI إلى معامل التكبير
                    pix = page.get_pixmap(matrix=mat)
                    
                    # تحويل إلى PIL Image
                    img_data = pix.tobytes("ppm")
                    pil_image = Image.open(io.BytesIO(img_data))
                    
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")
                    
                    # تحويل إلى base64
                    image_base64 = self._image_to_base64(pil_image)
                    
                    page_data = {
                        "page_number": page_num + 1,
                        "image": pil_image,
                        "image_base64": image_base64,
                        "width": pil_image.width,
                        "height": pil_image.height
                    }
                    
                    pages_data.append(page_data)
                    
                except Exception as e:
                    logger.error(f"Error processing page {page_num + 1}: {str(e)}")
                    # إنشاء صفحة احتياطية في حالة الخطأ
                    fallback_image = Image.new("RGB", (2100, 2970), "white")  # حجم A4 بدقة 300 DPI
                    fallback_base64 = self._image_to_base64(fallback_image)
                    
                    pages_data.append({
                        "page_number": page_num + 1,
                        "image": fallback_image,
                        "image_base64": fallback_base64,
                        "width": fallback_image.width,
                        "height": fallback_image.height,
                        "error": f"Failed to process page: {str(e)}"
                    })
            
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
                "producer": metadata.get("producer", "")
            }
            
            pdf_document.close()
            return info
            
        except Exception as e:
            logger.error(f"Error getting PDF info: {str(e)}")
            return {"total_pages": 0, "error": str(e)}
    
    def extract_page_text(self, file_content: bytes, page_number: int) -> str:
        """
        استخراج النص من صفحة محددة في PDF
        
        Args:
            file_content: محتوى ملف PDF
            page_number: رقم الصفحة (يبدأ من 1)
        
        Returns:
            str: النص المستخرج من الصفحة
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyMuPDF library is required for PDF processing")
        
        try:
            file_stream = io.BytesIO(file_content)
            pdf_document = fitz.open(stream=file_stream, filetype="pdf")
            
            if page_number < 1 or page_number > len(pdf_document):
                pdf_document.close()
                raise ValueError(f"Invalid page number: {page_number}")
            
            page = pdf_document[page_number - 1]  # تحويل إلى zero-based index
            text = page.get_text()
            
            pdf_document.close()
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text from page {page_number}: {str(e)}")
            return ""
    
    def split_pdf_by_language(self, pages_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        تصنيف صفحات PDF حسب اتجاه اللغة (RTL/LTR)
        هذه الدالة يمكن توسيعها لاحقاً لاستخدام AI في تحديد اللغة
        
        Args:
            pages_data: قائمة صفحات PDF المحولة إلى صور
            
        Returns:
            Dict: صفحات مُصنفة حسب اتجاه اللغة
        """
        categorized = {
            "rtl": [],
            "ltr": [],
            "mixed": []
        }
        
        # حالياً نضع جميع الصفحات تحت RTL كافتراضي
        # يمكن تحسين هذا لاحقاً باستخدام AI لتحليل النص
        for page_data in pages_data:
            categorized["rtl"].append(page_data)
        
        return categorized
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """تحويل صورة PIL إلى base64"""
        try:
            # تقليل حجم الصورة إذا كانت كبيرة جداً
            max_size = 2100  # الحد الأقصى للعرض أو الارتفاع
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # تحويل إلى base64
            buffer = io.BytesIO()
            # استخدام جودة عالية للنماذج
            image.save(buffer, format="PNG", optimize=True, quality=95)
            img_bytes = buffer.getvalue()
            
            return base64.b64encode(img_bytes).decode("utf-8")
            
        except Exception as e:
            logger.error(f"Error converting image to base64: {str(e)}")
            raise
    
    def validate_pdf_for_forms(self, file_content: bytes) -> Tuple[bool, str]:
        """
        التحقق من صلاحية PDF لتحليل النماذج
        
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        try:
            info = self.get_pdf_info(file_content)
            
            if "error" in info:
                return False, f"خطأ في قراءة PDF: {info['error']}"
            
            total_pages = info.get("total_pages", 0)
            
            if total_pages == 0:
                return False, "PDF فارغ أو تالف"
            
            if total_pages > self.max_pages:
                return False, f"PDF يحتوي على صفحات كثيرة ({total_pages}). الحد الأقصى المسموح: {self.max_pages}"
            
            # يمكن إضافة فحوصات أخرى هنا
            # مثل التحقق من وجود نماذج قابلة للتعبئة
            
            return True, f"PDF صالح للمعالجة ({total_pages} صفحة)"
            
        except Exception as e:
            return False, f"خطأ في التحقق من PDF: {str(e)}"
