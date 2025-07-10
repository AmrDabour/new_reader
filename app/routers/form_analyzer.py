from fastapi import APIRouter, File, UploadFile, HTTPException, Response, Form
import io
from PIL import Image
import base64
import os
import time
import re
import unicodedata
from pathlib import Path

from app.services.yolo import YOLOService
from app.services.gemini import GeminiService
from app.services.speech import SpeechService
from app.services.image import ImageService
from app.services.session import SessionService
from app.services.pdf_processor import PDFProcessor
from app.services.pdf_merger import PDFMergerService
from app.models.schemas import (
    FormAnalysisResponse, 
    TextToSpeechRequest, 
    AnnotateImageRequest,
    ImageQualityResponse,
    PDFFormAnalysisResponse,
    PDFQualityResponse,
    PDFPageRequest,
    PDFPageResponse,
    PDFInfo
)
from app.utils.text import process_transcript

router = APIRouter(prefix="/form", tags=["Form Analysis"])

# Initialize services
yolo_service = YOLOService()
gemini_service = GeminiService()
speech_service = SpeechService()
image_service = ImageService()
session_service = SessionService()
pdf_processor = PDFProcessor()
pdf_merger = PDFMergerService()

# Store PDF session data
pdf_sessions = {}

@router.post("/check-file", response_model=ImageQualityResponse)
async def check_file_quality(file: UploadFile = File(...)):
    """
    Check image or PDF quality and detect language direction automatically.
    Creates a session to store detected language for future use.
    For PDF files, converts the first page to an image and treats it like a regular image.
    """
    try:
        # Check if this is a PDF file
        if file.filename.lower().endswith('.pdf'):
            # Handle PDF by converting first page to image
            file_content = await file.read()
            
            # Check PDF support
            if not pdf_processor.is_pdf_supported():
                raise HTTPException(
                    status_code=503, 
                    detail="PDF processing not available. Please install PyMuPDF library"
                )
            
            # Validate PDF
            is_valid, validation_message = pdf_processor.validate_pdf_for_forms(file_content)
            if not is_valid:
                raise HTTPException(status_code=400, detail=validation_message)
            
            # Convert first page to image
            try:
                pages_data = pdf_processor.convert_pdf_to_images(file_content)
                if not pages_data:
                    raise HTTPException(status_code=400, detail="Could not convert PDF to image")
                
                # Get first page as image
                first_page = pages_data[0]
                image = first_page["image"]
                
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")
        else:
            # Handle regular image files
            image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        
        # Create new session
        session_id = session_service.create_session()
        
        # Check image quality and detect language automatically
        language_direction, quality_good, quality_message = gemini_service.detect_language_and_quality(image)
        
        # Simple form explanation based on basic image analysis (no YOLO or heavy processing)
        form_explanation = ""
        if quality_good:
            try:
                # Get quick form explanation only (no field details)
                form_explanation = gemini_service.get_quick_form_explanation(image, language_direction) or ""
            except Exception as e:
                # If form explanation fails, continue without it
                pass
        
        # Store detected language in session
        try:
            session_service.update_session(session_id, 'pdf_mode', file.filename.lower().endswith('.pdf'))
            session_service.update_session(session_id, 'language_direction', language_direction)
            session_service.update_session(session_id, 'image_width', image.width)
            session_service.update_session(session_id, 'image_height', image.height)
            if form_explanation:
                session_service.update_session(session_id, 'form_explanation', form_explanation)
        except Exception as session_error:
            # Continue without session updates if there's an error
            pass
        
        return ImageQualityResponse(
            language_direction=language_direction,
            quality_good=quality_good,
            quality_message=quality_message,
            image_width=image.width,
            image_height=image.height,
            session_id=session_id,
            form_explanation=form_explanation
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

# Keep the old endpoint for backward compatibility
@router.post("/check-image", response_model=ImageQualityResponse)
async def check_image_quality(file: UploadFile = File(...)):
    """
    Check image quality and detect language direction automatically.
    Creates a session to store detected language for future use.
    (Legacy endpoint - use /check-file for both images and PDFs)
    """
    return await check_file_quality(file)

@router.post("/analyze-form", response_model=FormAnalysisResponse)
async def analyze_form(file: UploadFile = File(...), session_id: str = Form(None), language_direction: str = Form(None)):
    """
    Main endpoint to analyze a form from an uploaded file.
    Can use session_id to get previously detected language, or manual language_direction.
    Handles both images and PDFs (converts PDF first page to image).
    """
    try:
        # 1. Load and process file (image or PDF)
        if file.filename.lower().endswith('.pdf'):
            # Handle PDF by converting first page to image
            file_content = await file.read()
            
            # Check PDF support
            if not pdf_processor.is_pdf_supported():
                raise HTTPException(status_code=503, detail="PDF processing not available")
            
            # Convert first page to image
            try:
                pages_data = pdf_processor.convert_pdf_to_images(file_content)
                if not pages_data:
                    raise HTTPException(status_code=400, detail="Could not convert PDF to image")
                
                # Get first page as image
                first_page = pages_data[0]
                image = first_page["image"]
                
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")
        else:
            # Handle regular image files
            image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        
        # 2. Correct image orientation
        corrected_image = image_service.correct_image_orientation(image)
        
        # 3. Determine language to use
        final_language = language_direction  # Manual selection has priority
        
        if not final_language and session_id:
            # Try to get language from session
            session_data = session_service.get_session(session_id)
            if session_data and 'language_direction' in session_data:
                final_language = session_data['language_direction']
        
        if not final_language:
            # Fallback to default
            final_language = "rtl"
        
        # 4. Detect fields using YOLO with determined language
        fields_data = yolo_service.detect_fields_with_language(corrected_image, final_language)
        if not fields_data:
            raise HTTPException(status_code=400, detail="No fillable fields detected.")

        # 5. Create annotated image for Gemini (with numbers)
        gpt_image = image_service.create_annotated_image_for_gpt(corrected_image, fields_data, with_numbers=True)
        
        # 6. Get form fields from Gemini with determined language
        gpt_fields_raw = gemini_service.get_form_fields_only(gpt_image, final_language)
            
        if not gpt_fields_raw:
            raise HTTPException(status_code=500, detail="AI model failed to extract form details.")

        # 7. Filter valid fields and combine results
        gpt_fields = [field for field in gpt_fields_raw if field.get("valid", False)]
        final_fields = image_service.combine_yolo_and_gpt_results(fields_data, gpt_fields)

        # 8. Create or update session for this analysis
        if not session_id:
            session_id = session_service.create_session()
        
        session_service.update_session(session_id, 'language_direction', final_language)
        session_service.update_session(session_id, 'analysis_completed', True)

        # 9. Store the converted image (especially important for PDF files)
        # Convert the corrected image to base64 for consistent handling
        try:
            img_buffer = io.BytesIO()
            corrected_image.save(img_buffer, format="PNG")
            corrected_image_b64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            session_service.update_session(session_id, 'converted_image_b64', corrected_image_b64)
        except Exception as img_save_error:
            print(f"Warning: Could not save converted image to session: {img_save_error}")

        return FormAnalysisResponse(
            fields=final_fields,
            form_explanation="",  # No explanation in analyze-form, only in check-file
            language_direction=final_language,
            image_width=corrected_image.width,
            image_height=corrected_image.height,
            session_id=session_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a specific session when user is done.
    """
    try:
        success = session_service.delete_session(session_id)
        if success:
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting session: {e}")

@router.get("/session-info")
async def get_session_info():
    """
    Get information about active sessions (for debugging/monitoring).
    """
    try:
        # Clean up expired sessions first
        session_service.cleanup_expired_sessions()
        
        return {
            "active_sessions": session_service.get_session_count(),
            "session_timeout": session_service.session_timeout
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting session info: {e}")

@router.post("/text-to-speech")
async def convert_text_to_speech(request: TextToSpeechRequest):
    """
    Convert text to speech using the selected provider (Gemini).
    """
    audio_bytes, mime_type = speech_service.text_to_speech(request.text, request.provider)
    
    if audio_bytes == "QUOTA_EXCEEDED":
        raise HTTPException(
            status_code=429,
            detail="Quota exceeded for Gemini TTS."
        )
    
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate audio.")
    
    return Response(content=audio_bytes, media_type=mime_type)

@router.post("/speech-to-text")
async def convert_speech_to_text(file: UploadFile = File(...), language_code: str = "en"):
    """
    Converts speech from an audio file to text using Gemini.
    """
    try:
        audio_bytes = await file.read()
        raw_transcript = speech_service.speech_to_text(audio_bytes, language_code=language_code)
        
        if raw_transcript == "QUOTA_EXCEEDED":
            raise HTTPException(
                status_code=429, 
                detail="Quota exceeded for Gemini API."
            )

        if raw_transcript is None:
            raise HTTPException(status_code=500, detail="STT service failed to transcribe audio.")
        
        processed_transcript = process_transcript(raw_transcript, lang=language_code)
        
        return {"text": processed_transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@router.post("/annotate-image")
async def annotate_image_endpoint(request: AnnotateImageRequest):
    """
    Receives the original image and user data, draws the data onto the
    image, and returns the final annotated image.
    Now supports both image files and PDF files (converts first page to image).
    """
    try:
        print(f"🔍 Received annotate request:")
        print(f"   - texts_dict: {request.texts_dict}")
        print(f"   - ui_fields count: {len(request.ui_fields) if request.ui_fields else 0}")
        print(f"   - has signature: {bool(request.signature_image_b64)}")
        
        # Decode the base64 data
        image_bytes = base64.b64decode(request.original_image_b64)
        print(f"   - Decoded {len(image_bytes)} bytes")
        
        # Try to open as image first
        try:
            original_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            print(f"   - Successfully opened as image: {original_image.size}")
        except Exception as img_error:
            print(f"   - Failed to open as image: {img_error}")
            # If it fails, maybe it's PDF bytes - try to convert
            try:
                print("   - Attempting PDF conversion...")
                # Check if we have PDF processor available
                if not pdf_processor.is_pdf_supported():
                    raise HTTPException(status_code=503, detail="PDF processing not available")
                
                # Convert PDF first page to image
                pages_data = pdf_processor.convert_pdf_to_images(image_bytes)
                if not pages_data:
                    raise HTTPException(status_code=400, detail="Could not convert PDF to image")
                
                # Get first page as image
                first_page = pages_data[0]
                original_image = first_page["image"]
                print(f"   - Successfully converted PDF to image: {original_image.size}")
                
            except Exception as pdf_error:
                print(f"   - PDF conversion also failed: {pdf_error}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Could not process file as image or PDF: {str(pdf_error)}"
                )
        
        final_image = image_service.create_final_annotated_image(
            image=original_image,
            texts_dict=request.texts_dict,
            ui_fields=request.ui_fields,
            signature_image_b64=request.signature_image_b64,
            signature_field_id=request.signature_field_id
        )
        
        buffered = io.BytesIO()
        final_image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        
        print(f"✅ Annotation successful, returning {len(img_bytes)} bytes")
        return Response(content=img_bytes, media_type="image/png")

    except Exception as e:
        print(f"❌ Error in annotate_image_endpoint: {str(e)}")
        print(f"   - Error type: {type(e).__name__}")
        import traceback
        print(f"   - Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@router.post("/process-pdf", response_model=PDFFormAnalysisResponse)
async def process_pdf(file: UploadFile = File(...), session_id: str = Form(None)):
    """
    Process an uploaded PDF file, analyze its content, and extract form data.
    """
    try:
        # 1. Read and decode the PDF file
        pdf_bytes = await file.read()
        
        # 2. Create or get session
        if not session_id:
            session_id = session_service.create_session()
        
        # 3. Process PDF and extract information
        pdf_info, form_fields = pdf_processor.process_pdf(pdf_bytes, session_id)
        
        # 4. Update session with extracted information
        session_service.update_session(session_id, 'pdf_info', pdf_info)
        session_service.update_session(session_id, 'form_fields', form_fields)
        
        return PDFFormAnalysisResponse(
            session_id=session_id,
            pdf_info=pdf_info,
            form_fields=form_fields
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@router.post("/pdf-page", response_model=PDFPageResponse)
async def pdf_page(request: PDFPageRequest):
    """
    Extract a specific page from a PDF as an image.
    """
    try:
        # 1. Validate and get the session
        session_data = session_service.get_session(request.session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # 2. Get the PDF bytes from the session
        pdf_bytes = session_data.get('pdf_bytes')
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="No PDF data found in session")
        
        # 3. Extract the requested page
        image_bytes = pdf_processor.extract_page_as_image(pdf_bytes, request.page_number)
        
        if image_bytes is None:
            raise HTTPException(status_code=500, detail="Failed to extract page as image")
        
        return PDFPageResponse(
            session_id=request.session_id,
            page_number=request.page_number,
            image_data=image_bytes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@router.get("/ping")
def ping():
    return {"msg": "pong"}

# =============================================================================
# PDF FORM ANALYSIS ENDPOINTS
# =============================================================================

@router.post("/check-pdf", response_model=PDFQualityResponse)
async def check_pdf_quality(file: UploadFile = File(...)):
    """
    فحص جودة PDF وتحديد معلوماته الأساسية
    إنشاء جلسة وتحويل جميع الصفحات إلى صور للمعالجة
    """
    try:
        # التحقق من نوع الملف
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="يجب أن يكون الملف من نوع PDF")
        
        # التحقق من دعم PDF
        if not pdf_processor.is_pdf_supported():
            raise HTTPException(
                status_code=503, 
                detail="معالجة PDF غير متوفرة. يرجى تثبيت PyMuPDF library"
            )
        
        # قراءة محتوى الملف
        file_content = await file.read()
        
        # التحقق من صحة PDF
        is_valid, validation_message = pdf_processor.validate_pdf_for_forms(file_content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=validation_message)
        
        # الحصول على معلومات PDF
        pdf_info_raw = pdf_processor.get_pdf_info(file_content)
        pdf_info = PDFInfo(
            total_pages=pdf_info_raw.get("total_pages", 0),
            title=pdf_info_raw.get("title", ""),
            author=pdf_info_raw.get("author", ""),
            subject=pdf_info_raw.get("subject", "")
        )
        
        # تحويل PDF إلى صور
        pages_data = pdf_processor.convert_pdf_to_images(file_content)
        
        # إنشاء جلسة جديدة
        session_id = session_service.create_session()
        
        # تحديد اللغة المُوصى بها (افتراضياً RTL للعربية)
        recommended_language = "rtl"
        
        # تخزين بيانات PDF في الجلسة المؤقتة
        pdf_sessions[session_id] = {
            "filename": file.filename,
            "pdf_info": pdf_info,
            "pages_data": pages_data,
            "file_content": file_content,
            "recommended_language": recommended_language
        }
        
        # تحديث جلسة المستخدم
        session_service.update_session(session_id, 'pdf_mode', True)
        session_service.update_session(session_id, 'total_pages', pdf_info.total_pages)
        session_service.update_session(session_id, 'language_direction', recommended_language)
        
        # إنشاء رسالة شرح للنموذج
        form_explanation = f"تم العثور على مستند PDF يحتوي على {pdf_info.total_pages} صفحة. سيتم تحليل كل صفحة للبحث عن حقول قابلة للتعبئة."
        
        return PDFQualityResponse(
            pdf_info=pdf_info,
            quality_good=True,
            quality_message=validation_message,
            session_id=session_id,
            form_explanation=form_explanation,
            recommended_language=recommended_language
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في معالجة PDF: {str(e)}")

@router.post("/analyze-pdf", response_model=PDFFormAnalysisResponse)
async def analyze_pdf_form(session_id: str = Form(...), language_direction: str = Form(None)):
    """
    تحليل جميع صفحات PDF للبحث عن النماذج القابلة للتعبئة
    """
    try:
        # التحقق من وجود الجلسة
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة أو منتهية الصلاحية")
        
        pdf_session = pdf_sessions[session_id]
        pages_data = pdf_session["pages_data"]
        pdf_info = pdf_session["pdf_info"]
        
        # تحديد اللغة المُستخدمة
        final_language = language_direction or pdf_session["recommended_language"]
        
        # تحليل كل صفحة
        analyzed_pages = []
        total_fields = 0
        pages_with_fields = 0
        
        for page_data in pages_data:
            try:
                page_number = page_data["page_number"]
                page_image = page_data["image"]
                
                # تصحيح اتجاه الصورة
                corrected_image = image_service.correct_image_orientation(page_image)
                
                # البحث عن الحقول باستخدام YOLO
                fields_data = yolo_service.detect_fields_with_language(corrected_image, final_language)
                
                if fields_data:
                    # إنشاء صورة مُرقمة للذكاء الاصطناعي
                    gpt_image = image_service.create_annotated_image_for_gpt(
                        corrected_image, fields_data, with_numbers=True
                    )
                    
                    # الحصول على تسميات الحقول من Gemini
                    gpt_fields_raw = gemini_service.get_form_fields_only(gpt_image, final_language)
                    
                    if gpt_fields_raw:
                        # تصفية الحقول الصحيحة
                        gpt_fields = [field for field in gpt_fields_raw if field.get("valid", False)]
                        final_fields = image_service.combine_yolo_and_gpt_results(fields_data, gpt_fields)
                        
                        # إضافة معرف الصفحة لكل حقل
                        for field in final_fields:
                            field['page_number'] = page_number
                            field['box_id'] = f"page_{page_number}_{field['box_id']}"
                        
                        total_fields += len(final_fields)
                        pages_with_fields += 1
                    else:
                        final_fields = []
                else:
                    final_fields = []
                
                # إنشاء تحليل الصفحة
                page_analysis = {
                    "page_number": page_number,
                    "fields": final_fields,
                    "language_direction": final_language,
                    "image_width": corrected_image.width,
                    "image_height": corrected_image.height,
                    "has_fields": len(final_fields) > 0,
                    "field_count": len(final_fields)
                }
                
                analyzed_pages.append(page_analysis)
                
            except Exception as e:
                # في حالة خطأ في معالجة صفحة معينة، أضف صفحة فارغة
                analyzed_pages.append({
                    "page_number": page_data["page_number"],
                    "fields": [],
                    "language_direction": final_language,
                    "image_width": page_data["width"],
                    "image_height": page_data["height"],
                    "has_fields": False,
                    "field_count": 0,
                    "error": f"خطأ في معالجة الصفحة: {str(e)}"
                })
        
        # تحديث بيانات الجلسة
        pdf_session["analyzed_pages"] = analyzed_pages
        pdf_session["final_language"] = final_language
        
        # تحديث جلسة المستخدم
        session_service.update_session(session_id, 'analysis_completed', True)
        session_service.update_session(session_id, 'language_direction', final_language)
        session_service.update_session(session_id, 'total_fields', total_fields)
        session_service.update_session(session_id, 'pages_with_fields', pages_with_fields)
        
        return PDFFormAnalysisResponse(
            pdf_info=pdf_info,
            pages=analyzed_pages,
            session_id=session_id,
            total_fields=total_fields,
            pages_with_fields=pages_with_fields,
            recommended_language=final_language
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في تحليل PDF: {str(e)}")

@router.get("/pdf/{session_id}/page/{page_number}", response_model=PDFPageResponse)
async def get_pdf_page(session_id: str, page_number: int):
    """
    الحصول على صفحة محددة من PDF مع الحقول المُحللة
    """
    try:
        # التحقق من وجود الجلسة
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة")
        
        pdf_session = pdf_sessions[session_id]
        
        # التحقق من رقم الصفحة
        total_pages = pdf_session["pdf_info"].total_pages
        if page_number < 1 or page_number > total_pages:
            raise HTTPException(status_code=400, detail=f"رقم صفحة غير صحيح. يجب أن يكون بين 1 و {total_pages}")
        
        # البحث عن الصفحة المطلوبة
        pages_data = pdf_session["pages_data"]
        analyzed_pages = pdf_session.get("analyzed_pages", [])
        
        # الحصول على بيانات الصورة
        page_data = next((p for p in pages_data if p["page_number"] == page_number), None)
        if not page_data:
            raise HTTPException(status_code=404, detail="بيانات الصفحة غير موجودة")
        
        # الحصول على تحليل الصفحة
        page_analysis = next((p for p in analyzed_pages if p["page_number"] == page_number), None)
        
        if page_analysis:
            fields = page_analysis["fields"]
            language_direction = page_analysis["language_direction"]
            has_fields = page_analysis["has_fields"]
        else:
            # إذا لم يكن هناك تحليل، أرجع صفحة فارغة
            fields = []
            language_direction = pdf_session.get("final_language", "rtl")
            has_fields = False
        
        return PDFPageResponse(
            page_number=page_number,
            total_pages=total_pages,
            fields=fields,
            image_base64=page_data["image_base64"],
            language_direction=language_direction,
            has_fields=has_fields,
            session_id=session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الحصول على الصفحة: {str(e)}")

@router.post("/pdf/{session_id}/annotate-page")
async def annotate_pdf_page(
    session_id: str,
    page_number: int = Form(...),
    texts_dict: str = Form(...),  # JSON string
    signature_image_b64: str = Form(None),
    signature_field_id: str = Form(None)
):
    """
    إضافة التعبئة النهائية لصفحة محددة من PDF
    """
    try:
        import json
        
        # التحقق من وجود الجلسة
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة")
        
        pdf_session = pdf_sessions[session_id]
        
        # تحويل JSON إلى dict
        try:
            texts_dict_parsed = json.loads(texts_dict)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="بيانات النص غير صحيحة")
        
        # الحصول على بيانات الصفحة
        page_data = next((p for p in pdf_session["pages_data"] if p["page_number"] == page_number), None)
        if not page_data:
            raise HTTPException(status_code=404, detail="الصفحة غير موجودة")
        
        # الحصول على تحليل الصفحة
        analyzed_pages = pdf_session.get("analyzed_pages", [])
        page_analysis = next((p for p in analyzed_pages if p["page_number"] == page_number), None)
        
        if not page_analysis:
            raise HTTPException(status_code=400, detail="لم يتم تحليل هذه الصفحة بعد")
        
        # إنشاء الصورة النهائية
        original_image = page_data["image"]
        ui_fields = page_analysis["fields"]
        
        # التأكد من وجود ui_fields في الصيغة الصحيحة
        if not ui_fields:
            # إنشاء ui_fields بناءً على الحقول الموجودة
            ui_fields = []
            for i, field in enumerate(page_analysis.get("fields", [])):
                ui_fields.append({
                    "box_id": field.get("box_id", f"box_{i}"),
                    "label": field.get("label", f"Field {i+1}"),
                    "type": field.get("type", "textbox"),
                    "box": field.get("box", [0, 0, 100, 30])
                })
        
        try:
            final_image = image_service.create_final_annotated_image(
                image=original_image,
                texts_dict=texts_dict_parsed,
                ui_fields=ui_fields,
                signature_image_b64=signature_image_b64,
                signature_field_id=signature_field_id
            )
        except Exception as img_error:
            # في حالة فشل الرسم، أرجع الصورة الأصلية
            final_image = original_image
            print(f"Warning: Failed to annotate image: {img_error}")
        
        # تحويل إلى bytes وإرجاع
        buffered = io.BytesIO()
        final_image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        
        return Response(content=img_bytes, media_type="image/png")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في إنشاء الصورة النهائية: {str(e)}")

# =============================================================================
# UNIFIED PDF MULTIPAGE ENDPOINTS
# =============================================================================

@router.post("/explore-pdf", response_model=dict)
async def explore_pdf(file: UploadFile = File(...)):
    """
    المرحلة الأولى: استكشاف PDF وعرض عدد الصفحات
    هذا endpoint يتعامل مع PDF فقط ويحضر للتدفق الجديد
    """
    try:
        # التحقق من نوع الملف
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="يجب أن يكون الملف من نوع PDF")
        
        # التحقق من دعم PDF
        if not pdf_processor.is_pdf_supported():
            raise HTTPException(
                status_code=503, 
                detail="معالجة PDF غير متوفرة. يرجى تثبيت PyMuPDF library"
            )
        
        # قراءة محتوى الملف
        file_content = await file.read()
        
        # التحقق من صحة PDF
        is_valid, validation_message = pdf_processor.validate_pdf_for_forms(file_content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=validation_message)
        
        # الحصول على معلومات PDF
        pdf_info_raw = pdf_processor.get_pdf_info(file_content)
        total_pages = pdf_info_raw.get("total_pages", 0)
        
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="لا يحتوي ملف PDF على صفحات صالحة")
        
        # تحويل جميع الصفحات إلى صور
        pages_data = pdf_processor.convert_pdf_to_images(file_content)
        if not pages_data:
            raise HTTPException(status_code=400, detail="فشل في تحويل صفحات PDF إلى صور")
        
        # إنشاء جلسة جديدة
        session_id = session_service.create_session()
        
        # تخزين بيانات PDF في الجلسة المؤقتة
        pdf_sessions[session_id] = {
            "filename": file.filename,
            "total_pages": total_pages,
            "pages_data": pages_data,
            "file_content": file_content,
            "current_stage": "explore",  # explore -> explain -> analyze -> fill -> complete
            "current_page": 1,
            "explained_pages": [],
            "analyzed_pages": [],
            "filled_pages": {},
            "language_direction": "rtl"  # افتراضي
        }
        
        # تحديث جلسة المستخدم
        session_service.update_session(session_id, 'pdf_multipage_mode', True)
        session_service.update_session(session_id, 'total_pages', total_pages)
        session_service.update_session(session_id, 'current_stage', 'explore')
        
        return {
            "session_id": session_id,
            "total_pages": total_pages,
            "filename": file.filename,
            "title": pdf_info_raw.get("title", ""),
            "message": f"تم العثور على مستند PDF يحتوي على {total_pages} صفحة. سنقوم أولاً بشرح محتوى كل صفحة، ثم تحليل وتعبئة النماذج.",
            "stage": "explore",
            "ready_for_explanation": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في استكشاف PDF: {str(e)}")

@router.post("/explain-pdf-page", response_model=dict)
async def explain_pdf_page(session_id: str = Form(...), page_number: int = Form(...)):
    """
    المرحلة الثانية: شرح محتوى صفحة محددة من PDF
    """
    try:
        # التحقق من وجود الجلسة
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة أو منتهية الصلاحية")
        
        pdf_session = pdf_sessions[session_id]
        
        # التحقق من رقم الصفحة
        if page_number < 1 or page_number > pdf_session["total_pages"]:
            raise HTTPException(
                status_code=400, 
                detail=f"رقم صفحة غير صحيح. يجب أن يكون بين 1 و {pdf_session['total_pages']}"
            )
        
        # البحث عن بيانات الصفحة
        page_data = next(
            (p for p in pdf_session["pages_data"] if p["page_number"] == page_number), 
            None
        )
        if not page_data:
            raise HTTPException(status_code=404, detail="بيانات الصفحة غير موجودة")
        
        # تصحيح اتجاه الصورة
        page_image = page_data["image"]
        corrected_image = image_service.correct_image_orientation(page_image)
        
        # فحص اللغة والجودة
        language_direction, quality_good, quality_message = gemini_service.detect_language_and_quality(corrected_image)
        
        # الحصول على شرح محتوى الصفحة
        form_explanation = ""
        if quality_good:
            try:
                # استخدام فانكشن الشرح فقط بدون تحليل الحقول
                explanation = gemini_service.get_quick_form_explanation(corrected_image, language_direction)
                form_explanation = explanation or f"هذه هي الصفحة رقم {page_number} من المستند."
            except Exception as e:
                form_explanation = f"هذه هي الصفحة رقم {page_number} من المستند. (لم يتمكن من تحليل المحتوى تلقائياً)"
        else:
            form_explanation = f"هذه هي الصفحة رقم {page_number} من المستند. {quality_message}"
        
        # تحديث معلومات الجلسة
        pdf_session["language_direction"] = language_direction
        pdf_session["current_page"] = page_number
        
        # إضافة الصفحة إلى قائمة الصفحات المشروحة
        if page_number not in pdf_session["explained_pages"]:
            pdf_session["explained_pages"].append(page_number)
        
        # تحديد ما إذا كانت هناك صفحة تالية
        has_next_page = page_number < pdf_session["total_pages"]
        next_page_number = page_number + 1 if has_next_page else None
        
        # تحديد ما إذا كان بإمكان البدء في التحليل
        all_pages_explained = len(pdf_session["explained_pages"]) >= pdf_session["total_pages"]
        
        return {
            "session_id": session_id,
            "page_number": page_number,
            "total_pages": pdf_session["total_pages"],
            "explanation": form_explanation,
            "language_direction": language_direction,
            "quality_good": quality_good,
            "quality_message": quality_message,
            "has_next_page": has_next_page,
            "next_page_number": next_page_number,
            "all_pages_explained": all_pages_explained,
            "image_width": corrected_image.width,
            "image_height": corrected_image.height
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في شرح الصفحة: {str(e)}")

@router.post("/analyze-pdf-page", response_model=dict)
async def analyze_pdf_page(session_id: str = Form(...), page_number: int = Form(...)):
    """
    المرحلة الثالثة: تحليل وتعبئة صفحة محددة من PDF
    """
    try:
        # التحقق من وجود الجلسة
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة أو منتهية الصلاحية")
        
        pdf_session = pdf_sessions[session_id]
        
        # التحقق من رقم الصفحة
        if page_number < 1 or page_number > pdf_session["total_pages"]:
            raise HTTPException(
                status_code=400, 
                detail=f"رقم صفحة غير صحيح. يجب أن يكون بين 1 و {pdf_session['total_pages']}"
            )
        
        # التحقق من وجود تحليل سابق لهذه الصفحة
        existing_analysis = next(
            (p for p in pdf_session.get("analyzed_pages", []) if p["page_number"] == page_number),
            None
        )
        
        if existing_analysis:
            print(f"📋 Page {page_number} already analyzed, returning existing analysis")
            return {
                "session_id": session_id,
                "page_number": page_number,
                "total_pages": pdf_session["total_pages"],
                "has_fields": existing_analysis.get("has_fields", False),
                "fields": existing_analysis.get("fields", []),
                "language_direction": existing_analysis.get("language_direction", "rtl"),
                "image_width": existing_analysis.get("image_width", 0),
                "image_height": existing_analysis.get("image_height", 0),
                "has_next_page": page_number < pdf_session["total_pages"],
                "next_page_number": page_number + 1 if page_number < pdf_session["total_pages"] else None,
                "all_pages_analyzed": len(pdf_session.get("analyzed_pages", [])) >= pdf_session["total_pages"],
                "field_count": len(existing_analysis.get("fields", []))
            }
        
        # البحث عن بيانات الصفحة
        page_data = next(
            (p for p in pdf_session["pages_data"] if p["page_number"] == page_number), 
            None
        )
        if not page_data:
            raise HTTPException(status_code=404, detail="بيانات الصفحة غير موجودة")
        
        # تصحيح اتجاه الصورة
        page_image = page_data["image"]
        corrected_image = image_service.correct_image_orientation(page_image)
        
        # تحديد اللغة المُستخدمة
        language_direction = pdf_session.get("language_direction", "rtl")
        
        # البحث عن الحقول باستخدام YOLO
        fields_data = yolo_service.detect_fields_with_language(corrected_image, language_direction)
        
        if not fields_data:
            # لا توجد حقول قابلة للتعبئة في هذه الصفحة
            pdf_session["analyzed_pages"].append({
                "page_number": page_number,
                "has_fields": False,
                "fields": [],
                "message": "لا توجد حقول قابلة للتعبئة في هذه الصفحة"
            })
            
            has_next_page = page_number < pdf_session["total_pages"]
            next_page_number = page_number + 1 if has_next_page else None
            all_pages_analyzed = len(pdf_session["analyzed_pages"]) >= pdf_session["total_pages"]
            
            return {
                "session_id": session_id,
                "page_number": page_number,
                "total_pages": pdf_session["total_pages"],
                "has_fields": False,
                "fields": [],
                "message": "لا توجد حقول قابلة للتعبئة في هذه الصفحة",
                "has_next_page": has_next_page,
                "next_page_number": next_page_number,
                "all_pages_analyzed": all_pages_analyzed,
                "language_direction": language_direction
            }
        
        # إنشاء صورة مُرقمة للذكاء الاصطناعي
        gpt_image = image_service.create_annotated_image_for_gpt(corrected_image, fields_data, with_numbers=True)
        
        # الحصول على تسميات الحقول من Gemini
        try:
            gpt_fields_raw = gemini_service.get_form_fields_only(gpt_image, language_direction)
        except Exception as gemini_error:
            print(f"Warning: Gemini analysis failed for page {page_number}: {gemini_error}")
            gpt_fields_raw = None
        
        if not gpt_fields_raw:
            # الاعتماد على YOLO فقط إذا فشل Gemini
            print(f"Warning: Using YOLO-only results for page {page_number} due to Gemini failure")
            final_fields = []
            for i, field_data in enumerate(fields_data):
                field = {
                    'box_id': f'field_{i+1}',
                    'label': f'حقل {i+1}',  # تسمية افتراضية
                    'type': 'text',  # نوع افتراضي
                    'coordinates': field_data.get('coordinates', []),
                    'page_number': page_number
                }
                final_fields.append(field)
        else:
            # تصفية الحقول الصحيحة ودمج النتائج
            gpt_fields = [field for field in gpt_fields_raw if field.get("valid", False)]
            final_fields = image_service.combine_yolo_and_gpt_results(fields_data, gpt_fields)
        
        # إضافة معرف فريد لكل حقل مع رقم الصفحة والتأكد من وجود جميع الخصائص المطلوبة
        for field in final_fields:
            field['page_number'] = page_number
            original_box_id = field.get('box_id', f'field_{len(final_fields)}')
            field['box_id'] = f"page_{page_number}_{original_box_id}"
            
            # التأكد من وجود الخصائص المطلوبة وتوحيد الأنواع
            if 'type' not in field:
                field['type'] = 'text'  # افتراضي
            elif field['type'] == 'textbox':
                field['type'] = 'text'  # توحيد النوع
            
            if 'label' not in field:
                field['label'] = f'حقل {field.get("box_id", "غير معروف")}'
            if 'coordinates' not in field:
                field['coordinates'] = []
        
        # حفظ تحليل الصفحة
        page_analysis = {
            "page_number": page_number,
            "has_fields": True,
            "fields": final_fields,
            "language_direction": language_direction,
            "image_width": corrected_image.width,
            "image_height": corrected_image.height,
            "corrected_image_b64": None  # سيتم ملؤها عند الحاجة
        }
        
        # تخزين الصورة المصححة كـ base64 للاستخدام في التعبئة
        try:
            img_buffer = io.BytesIO()
            corrected_image.save(img_buffer, format="PNG")
            corrected_image_b64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            page_analysis["corrected_image_b64"] = corrected_image_b64
        except Exception as img_save_error:
            print(f"Warning: Could not save corrected image for page {page_number}: {img_save_error}")
        
        # التحقق من وجود تحليل سابق لهذه الصفحة وحذفه لتجنب التكرار
        existing_analysis_indices = [
            i for i, p in enumerate(pdf_session["analyzed_pages"]) 
            if p["page_number"] == page_number
        ]
        for idx in reversed(existing_analysis_indices):  # حذف من الخلف للأمام لتجنب مشاكل الفهرسة
            pdf_session["analyzed_pages"].pop(idx)
            print(f"🗑️ Removed duplicate analysis for page {page_number}")
        
        pdf_session["analyzed_pages"].append(page_analysis)
        pdf_session["current_stage"] = "analyze"
        pdf_session["current_page"] = page_number
        
        # تحديد ما إذا كانت هناك صفحة تالية
        has_next_page = page_number < pdf_session["total_pages"]
        next_page_number = page_number + 1 if has_next_page else None
        all_pages_analyzed = len(pdf_session["analyzed_pages"]) >= pdf_session["total_pages"]
        
        return {
            "session_id": session_id,
            "page_number": page_number,
            "total_pages": pdf_session["total_pages"],
            "has_fields": True,
            "fields": final_fields,
            "language_direction": language_direction,
            "image_width": corrected_image.width,
            "image_height": corrected_image.height,
            "has_next_page": has_next_page,
            "next_page_number": next_page_number,
            "all_pages_analyzed": all_pages_analyzed,
            "field_count": len(final_fields)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في تحليل الصفحة: {str(e)}")

@router.post("/fill-pdf-page")
async def fill_pdf_page(
    session_id: str = Form(...),
    page_number: int = Form(...),
    texts_dict: str = Form(...),  # JSON string
    signature_image_b64: str = Form(None),
    signature_field_id: str = Form(None)
):
    """
    المرحلة الرابعة: تعبئة صفحة محددة من PDF
    """
    try:
        import json
        
        # التحقق من وجود الجلسة
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة أو منتهية الصلاحية")
        
        pdf_session = pdf_sessions[session_id]
        
        # تحويل JSON إلى dict
        try:
            texts_dict_parsed = json.loads(texts_dict)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="بيانات النص غير صحيحة")
        
        # البحث عن تحليل الصفحة
        page_analysis = next(
            (p for p in pdf_session["analyzed_pages"] if p["page_number"] == page_number),
            None
        )
        if not page_analysis:
            raise HTTPException(status_code=400, detail="لم يتم تحليل هذه الصفحة بعد")
        
        # الحصول على الصورة المصححة
        corrected_image_b64 = page_analysis.get("corrected_image_b64")
        if not corrected_image_b64:
            raise HTTPException(status_code=400, detail="لا توجد صورة متاحة للصفحة")
        
        # تحويل base64 إلى صورة
        image_bytes = base64.b64decode(corrected_image_b64)
        original_image = Image.open(io.BytesIO(image_bytes))
        
        # الحصول على حقول الصفحة
        ui_fields = page_analysis.get("fields", [])
        
        # إنشاء الصورة النهائية المعبأة
        try:
            # تأكد من أن ui_fields في الشكل الصحيح
            validated_fields = []
            for field in ui_fields:
                if isinstance(field, dict):
                    # توحيد أنواع الحقول
                    field_type = field.get('type', 'textbox')
                    
                    # تحويل الأنواع المختلفة لتوحيد المعالجة
                    if field_type in ['text', 'textbox']:
                        field_type = 'textbox'
                    elif field_type in ['checkbox', 'check']:
                        field_type = 'checkbox'
                    
                    # تأكد من وجود الخصائص المطلوبة
                    validated_field = {
                        'box_id': field.get('box_id', ''),
                        'label': field.get('label', ''),
                        'type': field_type,
                        'coordinates': field.get('coordinates', []),
                        'box': field.get('box', [])  # إضافة إحداثيات الصندوق
                    }
                    validated_fields.append(validated_field)
            
            final_image = image_service.create_final_annotated_image(
                image=original_image,
                texts_dict=texts_dict_parsed,
                ui_fields=validated_fields,
                signature_image_b64=signature_image_b64,
                signature_field_id=signature_field_id
            )
        except Exception as img_error:
            # في حالة فشل الرسم، أرجع الصورة الأصلية
            final_image = original_image
            print(f"Warning: Failed to fill page {page_number}: {img_error}")
            print(f"Error type: {type(img_error).__name__}")
            print(f"Error details: {str(img_error)}")
            print(f"UI Fields count: {len(ui_fields)}")
            print(f"Validated fields count: {len(validated_fields)}")
            print(f"Texts dict keys: {list(texts_dict_parsed.keys())}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
        
        # تحويل الصورة النهائية إلى bytes و base64
        buffered = io.BytesIO()
        final_image.save(buffered, format="PNG")
        final_image_bytes = buffered.getvalue()
        final_image_b64 = base64.b64encode(final_image_bytes).decode('utf-8')
        
        # حفظ الصفحة المعبأة (مع استبدال أي نسخة سابقة)
        pdf_session["filled_pages"][page_number] = {
            "page_number": page_number,
            "image_data": final_image_bytes,
            "image_b64": final_image_b64,
            "texts_dict": texts_dict_parsed,
            "width": final_image.width,
            "height": final_image.height,
            "fields": ui_fields
        }
        
        pdf_session["current_stage"] = "fill"
        
        print(f"✅ Page {page_number} filled and saved successfully")
        print(f"📊 Current filled pages: {list(pdf_session['filled_pages'].keys())}")
        
        # تحديد ما إذا كانت هناك صفحة تالية
        has_next_page = page_number < pdf_session["total_pages"]
        next_page_number = page_number + 1 if has_next_page else None
        all_pages_filled = len(pdf_session["filled_pages"]) >= pdf_session["total_pages"]
        
        # إرجاع الصورة المعبأة وحالة التقدم
        return Response(
            content=final_image_bytes, 
            media_type="image/png",
            headers={
                "X-Session-ID": session_id,
                "X-Page-Number": str(page_number),
                "X-Total-Pages": str(pdf_session["total_pages"]),
                "X-Has-Next-Page": str(has_next_page).lower(),
                "X-Next-Page-Number": str(next_page_number) if next_page_number else "",
                "X-All-Pages-Filled": str(all_pages_filled).lower(),
                "X-Ready-For-Download": str(all_pages_filled).lower()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في تعبئة الصفحة: {str(e)}")

@router.get("/download-filled-pdf/{session_id}")
async def download_filled_pdf(session_id: str):
    """
    المرحلة الأخيرة: تحميل PDF واحد يحتوي على جميع الصفحات المعبأة
    """
    try:
        # التحقق من وجود الجلسة
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة أو منتهية الصلاحية")
        
        pdf_session = pdf_sessions[session_id]
        
        # التحقق من أن جميع الصفحات تم تعبئتها
        total_pages = pdf_session["total_pages"]
        filled_pages = pdf_session.get("filled_pages", {})
        
        print(f"🔍 PDF Download Debug:")
        print(f"   Session ID: {session_id}")
        print(f"   Total pages: {total_pages}")
        print(f"   Filled pages count: {len(filled_pages)}")
        print(f"   Filled page numbers: {list(filled_pages.keys())}")
        
        if len(filled_pages) == 0:
            raise HTTPException(status_code=400, detail="لا توجد صفحات معبأة للتحميل")
        
        # التحقق من دعم PDF merger
        if not pdf_merger.is_available():
            raise HTTPException(
                status_code=503,
                detail="خدمة دمج PDF غير متوفرة. يرجى تثبيت PyMuPDF library"
            )
        
        # تحضير قائمة الصفحات للدمج
        pages_for_pdf = []
        for page_num in range(1, total_pages + 1):
            if page_num in filled_pages:
                # استخدم الصفحة المعبأة
                filled_page = filled_pages[page_num]
                pages_for_pdf.append({
                    "page_number": page_num,
                    "image_data": filled_page["image_data"],
                    "width": filled_page.get("width"),
                    "height": filled_page.get("height")
                })
            else:
                # استخدم الصفحة الأصلية إذا لم يتم تعبئتها
                page_data = next(
                    (p for p in pdf_session["pages_data"] if p["page_number"] == page_num),
                    None
                )
                if page_data:
                    # تحويل صورة الصفحة الأصلية إلى bytes
                    img_buffer = io.BytesIO()
                    page_data["image"].save(img_buffer, format="PNG")
                    original_image_bytes = img_buffer.getvalue()
                    
                    pages_for_pdf.append({
                        "page_number": page_num,
                        "image_data": original_image_bytes,
                        "width": page_data.get("width"),
                        "height": page_data.get("height")
                    })
        
        # إنشاء PDF من الصفحات
        original_filename = pdf_session.get("filename", "filled_form.pdf")
        
        # تنظيف اسم الملف من الأحرف غير المدعومة وتحويل العربية لـ ASCII
        
        def sanitize_filename(filename):
            """تنظيف اسم الملف ليكون ASCII فقط ومتوافق مع جميع الأنظمة"""
            try:
                # إزالة الامتداد مؤقتاً
                name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'pdf')
                
                # تحويل إلى unicode normalized أولاً
                name = unicodedata.normalize('NFKD', name)
                
                # إزالة جميع الأحرف غير ASCII (الاحتفاظ بـ ASCII فقط)
                # هذا يشمل إزالة جميع الأحرف العربية والخاصة
                ascii_chars = []
                for char in name:
                    if ord(char) < 128 and (char.isalnum() or char in ' -_'):
                        ascii_chars.append(char)
                
                name = ''.join(ascii_chars)
                
                # تحويل المسافات والشرطات إلى underscore
                name = re.sub(r'[-\s]+', '_', name)
                
                # تنظيف الشرطات السفلية المتكررة
                name = re.sub(r'_+', '_', name).strip('_')
                
                # إزالة أي أحرف متبقية غير آمنة
                name = re.sub(r'[^a-zA-Z0-9_]', '', name)
                
                # إذا كان الاسم فارغاً أو قصير جداً، استخدم اسم افتراضي
                if len(name.strip()) < 3:
                    name = "filled_form"
                
                # التأكد النهائي من أن الاسم ASCII فقط
                final_name = f"{name}_filled.{ext}"
                
                # اختبار نهائي للـ ASCII
                final_name.encode('ascii')
                
                return final_name
                
            except Exception as e:
                print(f"⚠️ Error in sanitize_filename: {e}")
                return "filled_form.pdf"
        
        # تطبيق التنظيف على اسم الملف
        safe_filename = sanitize_filename(original_filename)
        print(f"📝 Original filename: {original_filename}")
        print(f"📝 Safe filename: {safe_filename}")
        print(f"📝 Safe filename length: {len(safe_filename)}")
        print(f"📝 Safe filename ASCII check: {all(ord(c) < 128 for c in safe_filename)}")
        
        try:
            pdf_bytes = pdf_merger.create_pdf_from_images(pages_for_pdf, safe_filename)
            print(f"📄 PDF created successfully: {len(pdf_bytes)} bytes")
            
            # التحقق من صحة PDF
            if len(pdf_bytes) == 0:
                raise ValueError("PDF bytes is empty")
                
        except Exception as merge_error:
            print(f"❌ PDF creation failed: {merge_error}")
            print(f"📄 Pages for PDF: {len(pages_for_pdf)}")
            for i, page in enumerate(pages_for_pdf):
                page_size = len(page.get('image_data', b'')) if page.get('image_data') else 0
                print(f"   Page {i+1}: number={page.get('page_number', 'N/A')}, has_data={page_size} bytes")
            
            # معلومات إضافية للتشخيص
            print(f"📋 PDF Merger available: {pdf_merger.is_available()}")
            print(f"📝 Original filename: {original_filename}")
            print(f"📝 Safe filename: {safe_filename}")
            
            # تحليل نوع الخطأ
            error_message = str(merge_error)
            if "latin-1" in error_message or "codec" in error_message:
                error_detail = "خطأ في ترميز اسم الملف - تم إصلاحه تلقائياً"
            elif "PIL" in error_message or "image" in error_message.lower():
                error_detail = "خطأ في معالجة الصور"
            else:
                error_detail = f"خطأ عام في إنشاء PDF: {error_message}"
            
            raise HTTPException(
                status_code=500,
                detail=error_detail
            )
        
        # تحديث حالة الجلسة
        pdf_session["current_stage"] = "complete"
        
        # إنشاء header آمن لاسم الملف
        # استخدام ASCII فقط لضمان التوافق الكامل
        try:
            # تأكيد مضاعف أن اسم الملف ASCII فقط
            safe_filename.encode('ascii')
            # اختبار إضافي: التأكد من عدم وجود أحرف خاصة في الاسم
            if all(ord(c) < 128 for c in safe_filename):
                content_disposition = f"attachment; filename={safe_filename}"
                print(f"✅ Content-Disposition created successfully: {content_disposition}")
            else:
                raise ValueError("Non-ASCII characters detected")
        except (UnicodeEncodeError, UnicodeDecodeError, ValueError) as encoding_error:
            # إذا فشل، استخدم اسم افتراضي آمن بالكامل
            timestamp = int(time.time())
            default_filename = f"filled_form_{timestamp}.pdf"
            content_disposition = f"attachment; filename={default_filename}"
            print(f"⚠️ Used timestamped default filename due to encoding issue: {encoding_error}")
            print(f"✅ Content-Disposition (fallback): {content_disposition}")
        
        # معالجة آمنة لاسم الملف الأصلي في headers
        try:
            # تنظيف اسم الملف الأصلي ليكون ASCII آمن للـ headers (بدون إضافة _filled)
            if original_filename:
                # إزالة الامتداد مؤقتاً
                name, ext = original_filename.rsplit('.', 1) if '.' in original_filename else (original_filename, 'pdf')
                
                # تحويل إلى unicode normalized أولاً
                name = unicodedata.normalize('NFKD', name)
                
                # إزالة جميع الأحرف غير ASCII (الاحتفاظ بـ ASCII فقط)
                ascii_chars = []
                for char in name:
                    if ord(char) < 128 and (char.isalnum() or char in ' -_'):
                        ascii_chars.append(char)
                
                name = ''.join(ascii_chars)
                
                # تحويل المسافات والشرطات إلى underscore
                name = re.sub(r'[-\s]+', '_', name)
                
                # تنظيف الشرطات السفلية المتكررة
                name = re.sub(r'_+', '_', name).strip('_')
                
                # إزالة أي أحرف متبقية غير آمنة
                name = re.sub(r'[^a-zA-Z0-9_]', '', name)
                
                # إذا كان الاسم فارغاً أو قصير جداً، استخدم اسم افتراضي
                if len(name.strip()) < 3:
                    name = "original_file"
                
                # بناء الاسم النهائي (بدون _filled للاسم الأصلي)
                original_filename_safe = f"{name}.{ext}"
                
                # اختبار نهائي للـ ASCII
                original_filename_safe.encode('ascii')
                
            else:
                original_filename_safe = "original_file.pdf"
        except Exception as header_error:
            print(f"⚠️ Error processing original filename for header: {header_error}")
            original_filename_safe = "original_file.pdf"
        
        print(f"📋 Final headers:")
        print(f"   Content-Disposition: {content_disposition}")
        print(f"   X-Original-Filename: {original_filename_safe}")
        print(f"   Content-Length: {len(pdf_bytes)}")
        
        # التحقق النهائي من صحة جميع headers قبل الإرسال
        headers_dict = {
            "Content-Disposition": content_disposition,
            "Content-Length": str(len(pdf_bytes)),
            "X-Session-ID": session_id,
            "X-Total-Pages": str(total_pages),
            "X-Filled-Pages": str(len(filled_pages)),
            "X-Original-Filename": original_filename_safe
        }
        
        # اختبار كل header للتأكد من صحته
        for header_name, header_value in headers_dict.items():
            try:
                # التأكد أن القيمة string
                header_value_str = str(header_value)
                # التأكد أن القيمة ASCII
                header_value_str.encode('ascii')
                # التأكد أن القيمة لا تحتوي على أحرف خاصة أو مسافات في البداية/النهاية
                if header_name in ["X-Original-Filename", "Content-Disposition"]:
                    # إزالة أي مسافات أو أحرف خاصة
                    header_value_str = header_value_str.strip()
                    if not header_value_str or len(header_value_str) < 3:
                        if header_name == "X-Original-Filename":
                            headers_dict[header_name] = "original_file.pdf"
                        elif header_name == "Content-Disposition":
                            headers_dict[header_name] = "attachment; filename=filled_form.pdf"
                    else:
                        headers_dict[header_name] = header_value_str
                print(f"✅ Header {header_name} validated: {headers_dict[header_name]}")
            except Exception as header_validation_error:
                print(f"⚠️ Header validation failed for {header_name}: {header_validation_error}")
                # تطبيق قيم افتراضية آمنة
                if header_name == "X-Original-Filename":
                    headers_dict[header_name] = "original_file.pdf"
                elif header_name == "Content-Disposition":
                    headers_dict[header_name] = "attachment; filename=filled_form.pdf"
                else:
                    headers_dict[header_name] = str(header_value).encode('ascii', errors='ignore').decode('ascii')
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers=headers_dict
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في تحميل PDF: {str(e)}")

@router.get("/pdf-session-status/{session_id}")
async def get_pdf_session_status(session_id: str):
    """
    الحصول على حالة جلسة PDF متعددة الصفحات
    """
    try:
        if session_id not in pdf_sessions:
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة")
        
        pdf_session = pdf_sessions[session_id]
        
        return {
            "session_id": session_id,
            "filename": pdf_session.get("filename"),
            "total_pages": pdf_session.get("total_pages"),
            "current_stage": pdf_session.get("current_stage"),
            "current_page": pdf_session.get("current_page"),
            "explained_pages": len(pdf_session.get("explained_pages", [])),
            "analyzed_pages": len(pdf_session.get("analyzed_pages", [])),
            "filled_pages": len(pdf_session.get("filled_pages", {})),
            "language_direction": pdf_session.get("language_direction"),
            "ready_for_download": len(pdf_session.get("filled_pages", {})) > 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الحصول على حالة الجلسة: {str(e)}")

@router.delete("/pdf-session/{session_id}")
async def delete_pdf_session(session_id: str):
    """
    حذف جلسة PDF متعددة الصفحات
    """
    try:
        print(f"🗑️ Attempting to delete PDF session: {session_id}")
        print(f"   Current PDF sessions: {list(pdf_sessions.keys())}")
        
        if session_id not in pdf_sessions:
            print(f"❌ PDF session {session_id} not found")
            raise HTTPException(status_code=404, detail="جلسة PDF غير موجودة")
        
        # حذف الجلسة
        deleted_session = pdf_sessions.pop(session_id, None)
        print(f"✅ PDF session {session_id} deleted successfully")
        print(f"   Remaining PDF sessions: {list(pdf_sessions.keys())}")
        
        return {
            "message": f"تم حذف جلسة PDF {session_id} بنجاح",
            "session_id": session_id,
            "had_pages": deleted_session.get("total_pages", 0) if deleted_session else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting PDF session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"خطأ في حذف جلسة PDF: {str(e)}")

# =============================================================================