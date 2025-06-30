from fastapi import APIRouter, File, UploadFile, HTTPException, Response, Form
import io
from PIL import Image
import base64

from app.services.yolo import YOLOService
from app.services.gemini import GeminiService
from app.services.speech import SpeechService
from app.services.image import ImageService
from app.services.session import SessionService
from app.models.schemas import (
    FormAnalysisResponse, 
    TextToSpeechRequest, 
    AnnotateImageRequest,
    ImageQualityResponse
)
from app.utils.text import process_transcript

router = APIRouter(prefix="/form", tags=["Form Analysis"])

# Initialize services
yolo_service = YOLOService()
gemini_service = GeminiService()
speech_service = SpeechService()
image_service = ImageService()
session_service = SessionService()

@router.post("/check-image", response_model=ImageQualityResponse)
async def check_image_quality(file: UploadFile = File(...)):
    """
    Check image quality and detect language direction automatically.
    Creates a session to store detected language for future use.
    """
    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        
        # Create new session
        session_id = session_service.create_session()
        
        # Check image quality and detect language automatically
        language_direction, quality_good, quality_message = gemini_service.detect_language_and_quality(image)
        
        # Store detected language in session
        try:
            session_service.update_session(session_id, 'language_direction', language_direction)
            session_service.update_session(session_id, 'image_width', image.width)
            session_service.update_session(session_id, 'image_height', image.height)
        except Exception as session_error:
            # Continue without session updates if there's an error
            pass
        
        return ImageQualityResponse(
            language_direction=language_direction,
            quality_good=quality_good,
            quality_message=quality_message,
            image_width=image.width,
            image_height=image.height,
            session_id=session_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

@router.post("/analyze-form", response_model=FormAnalysisResponse)
async def analyze_form(file: UploadFile = File(...), session_id: str = Form(None), language_direction: str = Form(None)):
    """
    Main endpoint to analyze a form from an uploaded file.
    Can use session_id to get previously detected language, or manual language_direction.
    """
    try:
        # 1. Load and correct image orientation
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        corrected_image = image_service.correct_image_orientation(image)
        
        # 2. Determine language to use
        final_language = language_direction  # Manual selection has priority
        
        if not final_language and session_id:
            # Try to get language from session
            session_data = session_service.get_session(session_id)
            if session_data and 'language_direction' in session_data:
                final_language = session_data['language_direction']
        
        if not final_language:
            # Fallback to default
            final_language = "rtl"
        
        # 3. Detect fields using YOLO with determined language
        fields_data = yolo_service.detect_fields_with_language(corrected_image, final_language)
        if not fields_data:
            raise HTTPException(status_code=400, detail="No fillable fields detected.")

        # 4. Create annotated image for Gemini (with numbers)
        gpt_image = image_service.create_annotated_image_for_gpt(corrected_image, fields_data, with_numbers=True)
        
        # 5. Get form analysis from Gemini with determined language
        explanation, gpt_fields_raw = gemini_service.get_form_details(gpt_image, final_language)
        if not gpt_fields_raw:
            raise HTTPException(status_code=500, detail="AI model failed to extract form details.")

        # 6. Filter valid fields and combine results
        gpt_fields = [field for field in gpt_fields_raw if field.get("valid", False)]
        final_fields = image_service.combine_yolo_and_gpt_results(fields_data, gpt_fields)

        # 7. Create or update session for this analysis
        if not session_id:
            session_id = session_service.create_session()
        
        session_service.update_session(session_id, 'language_direction', final_language)
        session_service.update_session(session_id, 'analysis_completed', True)

        return FormAnalysisResponse(
            fields=final_fields,
            form_explanation=explanation,
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
    """
    try:
        image_bytes = base64.b64decode(request.original_image_b64)
        original_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        final_image = image_service.create_final_annotated_image(
            image=original_image,
            texts_dict=request.texts_dict,
            ui_fields=request.ui_fields
        )
        
        buffered = io.BytesIO()
        final_image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        
        return Response(content=img_bytes, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@router.get("/ping")
def ping():
    return {"msg": "pong"} 