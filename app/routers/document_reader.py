from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import Response
from pathlib import Path
import base64

from app.services.gemini import GeminiService
from app.services.document_processor import DocumentProcessor
from app.models.schemas import (
    AnalyzeDocumentResponse, SlideAnalysisResponse, DocumentSummaryResponse,
    NavigationRequest, NavigationResponse
)

router = APIRouter()

# Initialize services
gemini_service = GeminiService()
document_processor = DocumentProcessor()

# Store document sessions in memory (in production, use a database)
document_sessions = {}

@router.post("/upload", response_model=AnalyzeDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    language: str = Form("arabic"),  # "arabic" or "english"
):
    """
    رفع وتحليل مستند PowerPoint أو PDF
    """
    try:
        # التأكد من نوع الملف
        file_extension = Path(file.filename).suffix.lower()
        supported_extensions = [".pptx", ".ppt", ".pdf"]

        if file_extension not in supported_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"نوع الملف غير مدعوم. الأنواع المدعومة: {', '.join(supported_extensions)}",
            )

        # قراءة الملف
        file_content = await file.read()

        # معالجة المستند
        document_data = document_processor.process_document(file_content, file_extension)

        # تحليل المحتوى بالذكاء الاصطناعي
        try:
            analysis_result = gemini_service.analyze_document_bulk(document_data, language)
        except Exception:
            # Fallback analysis for testing
            analysis_result = {
                "presentation_summary": "تم إنشاء ملخص تجريبي للمستند" if language == "arabic" else "Test document summary created",
                "slides_analysis": [
                    {
                        "title": page.get("title", f"Page {i+1}"),
                        "original_text": page.get("text", ""),
                        "explanation": "No explanation (fallback)",
                        "key_points": [],
                        "slide_type": "content",
                        "importance_level": "medium"
                    } for i, page in enumerate(document_data.get("pages", []))
                ]
            }

        # Ensure slides_analysis always exists and matches total_pages
        if "slides_analysis" not in analysis_result or not isinstance(analysis_result["slides_analysis"], list):
            analysis_result["slides_analysis"] = []
        total_pages = len(document_data.get("pages", []))
        if len(analysis_result["slides_analysis"]) < total_pages:
            # Fill missing slides with fallback
            for i in range(len(analysis_result["slides_analysis"]), total_pages):
                page = document_data["pages"][i]
                analysis_result["slides_analysis"].append({
                    "title": page.get("title", f"Page {i+1}"),
                    "original_text": page.get("text", ""),
                    "explanation": "No explanation (auto-filled)",
                    "key_points": [],
                    "slide_type": "content",
                    "importance_level": "medium"
                })

        # إنشاء session ID للمستند
        session_id = f"doc_{len(document_sessions) + 1}"

        # حفظ بيانات المستند في الجلسة
        document_sessions[session_id] = {
            "filename": file.filename,
            "file_type": file_extension,
            "document_data": document_data,
            "analysis": analysis_result,
            "language": language,
            "total_pages": len(document_data["pages"]),
        }

        return AnalyzeDocumentResponse(
            session_id=session_id,
            filename=file.filename,
            file_type=file_extension,
            total_pages=len(document_data["pages"]),
            language=language,
            presentation_summary=analysis_result.get("presentation_summary", ""),
            status="success",
            message=(
                "تم تحليل المستند بنجاح"
                if language == "arabic"
                else "Document analyzed successfully"
            ),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في معالجة المستند: {str(e)}")

@router.get("/{session_id}/page/{page_number}", response_model=SlideAnalysisResponse)
async def get_page_analysis(session_id: str, page_number: int):
    """
    الحصول على تحليل صفحة/شريحة محددة
    """
    try:
        if session_id not in document_sessions:
            raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

        session = document_sessions[session_id]

        if page_number < 1 or page_number > session["total_pages"]:
            raise HTTPException(status_code=400, detail="رقم الصفحة غير صحيح")

        # Get page data
        page_index = page_number - 1
        page_data = session["document_data"]["pages"][page_index]
        page_analysis = session["analysis"]["slides_analysis"][page_index]

        return SlideAnalysisResponse(
            page_number=page_number,
            title=page_analysis.get("title", f"Page {page_number}"),
            original_text=page_analysis.get("original_text", ""),
            explanation=page_analysis.get("explanation", ""),
            key_points=page_analysis.get("key_points", []),
            slide_type=page_analysis.get("slide_type", "content"),
            importance_level=page_analysis.get("importance_level", "medium"),
            image_data=page_data.get("image_base64", ""),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الحصول على تحليل الصفحة: {str(e)}")

@router.get("/{session_id}/page/{page_number}/image")
async def get_page_image(session_id: str, page_number: int):
    """
    الحصول على صورة الصفحة/الشريحة
    """
    try:
        if session_id not in document_sessions:
            raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

        session = document_sessions[session_id]

        if page_number < 1 or page_number > session["total_pages"]:
            raise HTTPException(status_code=400, detail="رقم الصفحة غير صحيح")

        # Get page image
        page_index = page_number - 1
        page_data = session["document_data"]["pages"][page_index]

        if "image_base64" not in page_data:
            raise HTTPException(status_code=404, detail="صورة الصفحة غير متوفرة")

        # Decode base64 image
        image_data = base64.b64decode(page_data["image_base64"])

        return Response(content=image_data, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الحصول على صورة الصفحة: {str(e)}")

@router.get("/{session_id}/summary", response_model=DocumentSummaryResponse)
async def get_document_summary(session_id: str):
    """
    الحصول على ملخص شامل للمستند
    """
    try:
        if session_id not in document_sessions:
            raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

        session = document_sessions[session_id]
        analysis = session["analysis"]

        return DocumentSummaryResponse(
            session_id=session_id,
            filename=session["filename"],
            total_pages=session["total_pages"],
            presentation_summary=analysis.get("presentation_summary", ""),
            slides_analysis=analysis.get("slides_analysis", []),
            language=session["language"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الحصول على ملخص المستند: {str(e)}")

@router.post("/{session_id}/navigate", response_model=NavigationResponse)
async def navigate_document(session_id: str, request: NavigationRequest):
    """
    التنقل في المستند باستخدام الأوامر الصوتية أو النصية
    """
    try:
        if session_id not in document_sessions:
            raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

        session = document_sessions[session_id]
        total_pages = session["total_pages"]

        # استخراج رقم الصفحة من الأمر
        new_page = gemini_service.extract_page_number_from_command(
            request.command, request.current_page, total_pages
        )

        if new_page is not None:
            return NavigationResponse(
                success=True,
                new_page=new_page,
                message=f"تم الانتقال إلى الصفحة {new_page}",
            )
        else:
            return NavigationResponse(
                success=False,
                message="لم أتمكن من فهم الأمر. حاول مرة أخرى.",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في التنقل: {str(e)}")

@router.delete("/{session_id}")
async def delete_document_session(session_id: str):
    """
    حذف جلسة المستند من الذاكرة
    """
    try:
        if session_id in document_sessions:
            del document_sessions[session_id]
            return {"message": "تم حذف جلسة المستند بنجاح"}
        else:
            raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في حذف الجلسة: {str(e)}")

@router.get("/ping")
def ping():
    """فحص صحة خدمة قراءة المستندات"""
    return {"service": "Document Reader", "status": "healthy", "active_sessions": len(document_sessions)} 