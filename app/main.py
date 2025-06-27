from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import io
from PIL import Image
import base64
import json

from form_analyzer.app.services.yolo import YOLOService
from form_analyzer.app.services.gemini import GeminiService
from form_analyzer.app.services.speech import SpeechService
from form_analyzer.app.services.image import ImageService
from form_analyzer.app.config import get_settings
from form_analyzer.app.models.schemas import FormAnalysisResponse, TextToSpeechRequest, AnnotateImageRequest
from form_analyzer.app.utils.text import process_transcript

settings = get_settings()
app = FastAPI(title="Form Analyzer API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
yolo_service = YOLOService()
gemini_service = GeminiService()
speech_service = SpeechService()
image_service = ImageService()

@app.post("/analyze-form", response_model=FormAnalysisResponse)
async def analyze_form(file: UploadFile = File(...)):
    """
    Main endpoint to analyze a form from an uploaded file.
    Now returns field coordinates and image dimensions as well.
    """
    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        
        corrected_image = image_service.correct_image_orientation(image)
        fields_data, lang_direction = yolo_service.detect_fields(corrected_image)
        if not fields_data:
            raise HTTPException(status_code=400, detail="No fillable fields detected.")

        gpt_image = image_service.create_annotated_image_for_gpt(corrected_image, fields_data, with_numbers=True)
        
        explanation, gpt_fields_raw = gemini_service.get_form_details(gpt_image, lang_direction)
        if not gpt_fields_raw:
            raise HTTPException(status_code=500, detail="AI model failed to extract form details.")

        gpt_fields = [field for field in gpt_fields_raw if field.get("valid", False)]
        final_fields = image_service.combine_yolo_and_gpt_results(fields_data, gpt_fields)

        ui_image = image_service.create_annotated_image_for_gpt(corrected_image, fields_data, with_numbers=True)
        buffered = io.BytesIO()
        ui_image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return FormAnalysisResponse(
            fields=final_fields,
            form_explanation=explanation,
            language_direction=lang_direction,
            annotated_image=img_b64,
            image_width=corrected_image.width,
            image_height=corrected_image.height
        )

    except Exception as e:
        print(f"An unexpected error occurred in analyze_form: {e}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

@app.post("/text-to-speech")
async def convert_text_to_speech(request: TextToSpeechRequest):
    """
    Convert text to speech using the selected provider (Gemini).
    """
    audio_bytes, mime_type = speech_service.text_to_speech(request.text, request.provider)
    
    if audio_bytes == "QUOTA_EXCEEDED":
        raise HTTPException(
            status_code=429,
            detail="لقد تجاوزت حد الاستخدام المجاني لـ Gemini TTS. يرجى التحقق من خطتك والفوترة. (Quota exceeded for Gemini TTS.)"
        )
    
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate audio.")
    
    return Response(content=audio_bytes, media_type=mime_type)

@app.post("/speech-to-text")
async def convert_speech_to_text(file: UploadFile = File(...), language_code: str = "en"):
    """
    Converts speech from an audio file to text using Gemini, forcing a specific language,
    and processes the transcript to convert number words to digits.
    """
    try:
        audio_bytes = await file.read()
        raw_transcript = speech_service.speech_to_text(audio_bytes, language_code=language_code)
        
        if raw_transcript == "QUOTA_EXCEEDED":
            raise HTTPException(
                status_code=429, 
                detail="لقد تجاوزت حد الاستخدام المجاني لـ Gemini. يرجى التحقق من خطتك والفوترة. (Quota exceeded for Gemini API.)"
            )

        if raw_transcript is None:
            raise HTTPException(status_code=500, detail="STT service failed to transcribe audio.")
        
        processed_transcript = process_transcript(raw_transcript, lang=language_code)
        
        return {"text": processed_transcript}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"An unexpected error occurred in speech_to_text: {e}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@app.post("/annotate-image")
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
        print(f"An unexpected error occurred in annotate_image: {e}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}") 