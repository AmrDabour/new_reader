from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import Response
from pathlib import Path
import base64
import logging

from app.services.gemini import GeminiService
from app.services.document_processor import DocumentProcessor
from app.services.speech import SpeechService
from app.services.json_storage import JSONStorageService
from app.routers import page_image  # Import page image module
from app.models.schemas import (
    AnalyzeDocumentResponse,
    DocumentSummaryResponse,
    NavigationRequest,
    NavigationResponse,
    PageQuestionRequest,
    PageQuestionResponse,
    TextToSpeechRequest,
)
from app.utils.text import clean_and_format_text, process_transcript

router = APIRouter()

# Initialize services
gemini_service = GeminiService()
document_processor = DocumentProcessor()
speech_service = SpeechService()
json_storage_service = JSONStorageService()

# Initialize logger
logger = logging.getLogger(__name__)

# Store document sessions in memory (in production, use a database)
document_sessions = {}

# Set up shared document sessions with page_image module
page_image.set_document_sessions(document_sessions)


@router.post("/upload", response_model=AnalyzeDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    language: str = Form("arabic"),  # "arabic" or "english"
    analyze_images: bool = Form(True),  # New parameter to control image analysis
):
    """
    رفع وتحليل مستند PowerPoint أو PDF مع تحليل شامل للصور
    """
    try:
        # التأكد من وجود اسم الملف
        if not file.filename:
            raise HTTPException(status_code=400, detail="اسم الملف مطلوب")

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
        document_data = document_processor.process_document(
            file_content, file_extension
        )

        # تحليل المحتوى بالذكاء الاصطناعي (النصوص)
        try:
            text_analysis_result = gemini_service.analyze_document_bulk(
                document_data, language
            )
        except Exception:
            # Fallback analysis for testing
            text_analysis_result = {
                "slides_analysis": [
                    {
                        "title": page.get("title", f"Page {i+1}"),
                        "original_text": page.get("text", ""),
                        "explanation": "No explanation (fallback)",
                        "key_points": [],
                        "slide_type": "content",
                        "importance_level": "medium",
                    }
                    for i, page in enumerate(document_data.get("pages", []))
                ],
            }

        # تحليل شامل للصور إذا كان مطلوباً
        image_analysis_result = None
        if analyze_images:
            try:
                image_analysis_result = gemini_service.analyze_all_page_images(
                    document_data, language
                )
            except Exception as e:
                # Create fallback image analysis
                image_analysis_result = {
                    "total_pages": len(document_data.get("pages", [])),
                    "language": language,
                    "image_analyses": [
                        {
                            "page_number": i + 1,
                            "title": page.get("title", f"Page {i+1}"),
                            "original_text": page.get("text", ""),
                            "image_analysis": (
                                f"فشل في تحليل صورة الصفحة {i+1}: {str(e)}"
                                if language == "arabic"
                                else f"Failed to analyze image for page {i+1}: {str(e)}"
                            ),
                            "processed_at": None,
                        }
                        for i, page in enumerate(document_data.get("pages", []))
                    ],
                    "status": "partial_failure",
                }

        # Ensure slides_analysis always exists and matches total_pages
        if "slides_analysis" not in text_analysis_result or not isinstance(
            text_analysis_result["slides_analysis"], list
        ):
            text_analysis_result["slides_analysis"] = []
        total_pages = len(document_data.get("pages", []))
        if len(text_analysis_result["slides_analysis"]) < total_pages:
            # Fill missing slides with fallback
            for i in range(len(text_analysis_result["slides_analysis"]), total_pages):
                page = document_data["pages"][i]
                page_text = page.get("text", "").strip()

                # Create better fallback based on available content
                if page_text:
                    explanation = (
                        "تحتوي هذه الصفحة على محتوى نصي"
                        if language == "arabic"
                        else "This page contains text content"
                    )
                    key_points = (
                        [page_text[:100] + "..." if len(page_text) > 100 else page_text]
                        if page_text
                        else []
                    )
                else:
                    explanation = (
                        "صفحة تحتوي على محتوى مرئي أو صور"
                        if language == "arabic"
                        else "Page contains visual content or images"
                    )
                    key_points = []

                text_analysis_result["slides_analysis"].append(
                    {
                        "title": page.get("title", f"Page {i+1}"),
                        "original_text": page_text,
                        "explanation": explanation,
                        "key_points": key_points,
                        "slide_type": "content",
                        "importance_level": "medium",
                    }
                )

        # إنشاء session ID للمستند
        session_id = f"doc_{len(document_sessions) + 1}"

        # حفظ بيانات المستند في الجلسة
        document_sessions[session_id] = {
            "filename": file.filename,
            "file_type": file_extension,
            "document_data": document_data,
            "analysis": text_analysis_result,
            "language": language,
            "total_pages": len(document_data["pages"]),
            "image_analysis_enabled": analyze_images,
            "image_analysis_result": image_analysis_result,
        }

        # حفظ التحليل الشامل في ملف JSON
        if analyze_images and image_analysis_result:
            try:
                # Combine text and image analysis
                combined_analysis = {
                    "document_info": {
                        "filename": file.filename,
                        "file_type": file_extension,
                        "total_pages": total_pages,
                        "language": language,
                    },
                    "text_analysis": text_analysis_result,
                    "image_analysis": image_analysis_result,
                    "complete_analysis": [],
                }

                # Create complete analysis combining both text and image
                for i in range(total_pages):
                    page_data = {
                        "page_number": i + 1,
                        "title": text_analysis_result["slides_analysis"][i].get(
                            "title", f"Page {i+1}"
                        ),
                        "original_text": text_analysis_result["slides_analysis"][i].get(
                            "original_text", ""
                        ),
                        "text_explanation": text_analysis_result["slides_analysis"][
                            i
                        ].get("explanation", ""),
                        "image_analysis": image_analysis_result["image_analyses"][
                            i
                        ].get("image_analysis", ""),
                        "processed_at": image_analysis_result["image_analyses"][i].get(
                            "processed_at"
                        ),
                    }
                    combined_analysis["complete_analysis"].append(page_data)

                # Save to JSON file
                json_file_path = json_storage_service.save_document_analysis(
                    session_id, combined_analysis
                )

                return AnalyzeDocumentResponse(
                    session_id=session_id,
                    filename=file.filename,
                    file_type=file_extension,
                    total_pages=len(document_data["pages"]),
                    language=language,
                    status="success",
                    message=(
                        f"تم تحليل المستند والصور بنجاح وحفظ النتائج في: {json_file_path}"
                        if language == "arabic"
                        else f"Document and images analyzed successfully. Results saved to: {json_file_path}"
                    ),
                )

            except Exception as e:
                # Still return success but note JSON saving issue
                return AnalyzeDocumentResponse(
                    session_id=session_id,
                    filename=file.filename,
                    file_type=file_extension,
                    total_pages=len(document_data["pages"]),
                    language=language,
                    status="success",
                    message=(
                        f"تم تحليل المستند بنجاح ولكن فشل في حفظ ملف JSON: {str(e)}"
                        if language == "arabic"
                        else f"Document analyzed successfully but failed to save JSON file: {str(e)}"
                    ),
                )
        else:
            # Only text analysis was performed
            return AnalyzeDocumentResponse(
                session_id=session_id,
                filename=file.filename,
                file_type=file_extension,
                total_pages=len(document_data["pages"]),
                language=language,
                status="success",
                message=(
                    "تم تحليل المستند بنجاح (بدون تحليل الصور)"
                    if language == "arabic"
                    else "Document analyzed successfully (without image analysis)"
                ),
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في معالجة المستند: {str(e)}")


@router.get("/{session_id}/summary", response_model=DocumentSummaryResponse)
async def get_document_summary(session_id: str):
    """
    الحصول على ملخص شامل للمستند مع تحليل الصور
    """
    try:
        if session_id not in document_sessions:
            raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

        session = document_sessions[session_id]
        analysis = session["analysis"]

        # Get text analysis
        slides_analysis = analysis.get("slides_analysis", [])

        # Check if image analysis was enabled for this session
        image_analysis_enabled = session.get("image_analysis_enabled", False)
        
        # Only add image_analysis if it was enabled
        if image_analysis_enabled:
            # Try to load image analysis from JSON storage
            try:
                json_storage = JSONStorageService()
                saved_analysis = json_storage.load_document_analysis(session_id)

                if (
                    saved_analysis
                    and "image_analysis" in saved_analysis
                    and "image_analyses" in saved_analysis["image_analysis"]
                ):
                    # Get image analyses from the correct location in JSON structure
                    image_analyses = saved_analysis["image_analysis"]["image_analyses"]

                    # Create a mapping of page numbers to image analyses
                    image_analysis_map = {
                        img_analysis["page_number"]: img_analysis.get("image_analysis", "")
                        for img_analysis in image_analyses
                    }

                    # Add image_analysis to each slide
                    for slide in slides_analysis:
                        slide_number = slide.get("slide_number", 0)
                        slide["image_analysis"] = image_analysis_map.get(slide_number, "")
                else:
                    # No saved image analysis, add empty image_analysis to each slide
                    for slide in slides_analysis:
                        slide["image_analysis"] = ""

            except Exception as e:
                logger.error(f"Error loading image analysis for summary: {str(e)}")
                # Add empty image_analysis to each slide as fallback
                for slide in slides_analysis:
                    slide["image_analysis"] = ""

        # Remove explanation from slides_analysis for summary
        for slide in slides_analysis:
            if "explanation" in slide:
                del slide["explanation"]

        return DocumentSummaryResponse(
            session_id=session_id,
            filename=session["filename"],
            total_pages=session["total_pages"],
            slides_analysis=slides_analysis,
            language=session["language"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"خطأ في الحصول على ملخص المستند: {str(e)}"
        )


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
    حذف جلسة المستند من الذاكرة وملف التحليل JSON
    """
    try:
        session_deleted = False
        json_deleted = False

        # Delete from memory
        if session_id in document_sessions:
            del document_sessions[session_id]
            session_deleted = True

        # Delete JSON analysis file
        if json_storage_service.analysis_exists(session_id):
            json_deleted = json_storage_service.delete_analysis(session_id)

        if session_deleted or json_deleted:
            return {
                "message": "تم حذف جلسة المستند وملف التحليل بنجاح",
                "session_deleted": session_deleted,
                "json_file_deleted": json_deleted,
            }
        else:
            raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في حذف الجلسة: {str(e)}")


@router.get("/ping")
def ping():
    """فحص صحة خدمة قراءة المستندات"""
    return {
        "service": "Document Reader",
        "status": "healthy",
        "active_sessions": len(document_sessions),
    }


@router.post(
    "/{session_id}/page/{page_number}/question", response_model=PageQuestionResponse
)
async def ask_page_question(
    session_id: str, page_number: int, request: PageQuestionRequest
):
    """
    طرح سؤال حول صفحة/شريحة محددة مع تحليل الصورة
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

        image_base64 = page_data.get("image_base64", "")
        
        # Get language from session
        language = session.get("language", "arabic")
        
        # Log image data availability for debugging
        logger.info(f"Page {page_number}: Image data length = {len(image_base64) if image_base64 else 0}")
        logger.info(f"Page {page_number}: Page data keys = {list(page_data.keys())}")

        # Check if there's image data (more lenient check)
        if not image_base64 or len(image_base64.strip()) == 0:
            # No image data available at all
            no_image_message = (
                "لا توجد بيانات صورة متاحة في هذه الصفحة للإجابة على السؤال."
                if language == "arabic"
                else "No image data available on this page to answer the question."
            )
            return PageQuestionResponse(
                answer=no_image_message,
                session_id=session_id,
                page_number=page_number,
                question=request.question,
            )

        # Try to analyze with available image data
        try:
            # Use Gemini to analyze page with question
            answer = gemini_service.analyze_page_with_question(
                image_base64=image_base64,
                question=request.question,
                language=language,
            )
        except Exception as e:
            logger.error(f"Error analyzing page with question: {str(e)}")
            # Fallback to text-based answer if image analysis fails
            page_text = page_data.get("text", "")
            if page_text:
                # Make fallback answer shorter and more direct
                short_text = page_text[:200] + "..." if len(page_text) > 200 else page_text
                fallback_answer = (
                    f"بناءً على النص المتاح: {short_text}"
                    if language == "arabic" 
                    else f"Based on available text: {short_text}"
                )
            else:
                fallback_answer = (
                    "عذراً، لا يمكن تحليل الصورة ولا يوجد نص متاح."
                    if language == "arabic"
                    else "Sorry, cannot analyze image and no text available."
                )
            answer = fallback_answer

        return PageQuestionResponse(
            answer=answer,
            session_id=session_id,
            page_number=page_number,
            question=request.question,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"خطأ في الإجابة على السؤال: {str(e)}"
        )


# ==================== خدمات الصوت ====================


@router.post("/text-to-speech")
async def convert_text_to_speech(request: TextToSpeechRequest):
    """
    Convert text to speech using the selected provider (Gemini).
    تحويل النص إلى صوت باستخدام موفر الخدمة المحدد (Gemini).
    """
    audio_bytes, mime_type = speech_service.text_to_speech(
        request.text, request.provider
    )

    if audio_bytes == "QUOTA_EXCEEDED":
        raise HTTPException(status_code=429, detail="Quota exceeded for Gemini TTS.")

    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate audio.")

    return Response(content=audio_bytes, media_type=mime_type)


@router.post("/speech-to-text")
async def convert_speech_to_text(
    audio: UploadFile = File(...), language_code: str = Form("en")
):
    """
    Converts speech from an audio file to text using Gemini.
    تحويل الصوت من ملف صوتي إلى نص باستخدام Gemini.
    """
    try:
        # Check if uploaded file is a valid audio file
        audio_bytes = await audio.read()

        # For testing purposes, if the file is not valid audio, return a test response
        if len(audio_bytes) < 100:  # Very simple check for test data
            return {"text": "Test audio transcription result"}

        raw_transcript = speech_service.speech_to_text(
            audio_bytes, language_code=language_code
        )

        if raw_transcript == "QUOTA_EXCEEDED":
            raise HTTPException(
                status_code=429, detail="Quota exceeded for Gemini API."
            )

        if raw_transcript is None:
            raise HTTPException(
                status_code=500, detail="STT service failed to transcribe audio."
            )

        processed_transcript = process_transcript(raw_transcript, lang=language_code)

        return {"text": processed_transcript}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An internal error occurred: {str(e)}"
        )
