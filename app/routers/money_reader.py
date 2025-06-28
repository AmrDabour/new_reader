from fastapi import APIRouter, File, UploadFile, HTTPException
import io
from PIL import Image

from app.services.gemini import GeminiService
from app.models.schemas import CurrencyAnalysisResponse

router = APIRouter()

# Initialize services
gemini_service = GeminiService()

@router.post("/analyze", response_model=CurrencyAnalysisResponse)
async def analyze_currency(file: UploadFile = File(...)):
    """
    تحليل العملة من صورة مرفوعة
    """
    try:
        # التأكد من نوع الملف
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="يجب أن يكون الملف صورة")

        # قراءة الصورة
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")

        # تحليل العملة باستخدام Gemini
        analysis = gemini_service.analyze_currency_image(image)

        return CurrencyAnalysisResponse(analysis=analysis)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في التحليل: {str(e)}")

@router.get("/ping")
def ping():
    """فحص صحة خدمة قراءة العملات"""
    return {"service": "Money Reader", "status": "healthy"} 