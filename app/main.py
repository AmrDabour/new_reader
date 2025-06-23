from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io
from PIL import Image
import uuid
import fitz
from typing import List, Optional, Dict
import numpy as np
import logging

from .services.ocr import detect_text_in_region
from .services.yolo import YOLOService
from .services.gpt import GPTService
from .services.speech import text_to_speech, speech_to_text, SpeechService
from .services.image import create_annotated_image
from .utils.image import correct_image_orientation, calculate_iou
from .utils.arabic import is_arabic_text, compare_boxes_rtl
from .utils.text import process_transcript
from .config import get_settings
from .models.schemas import (
    FormAnalysisResponse,
    Field,
    TextToSpeechRequest,
    SpeechToTextResponse,
    AnnotateFormRequest
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Form Analyzer API",
    description="API for analyzing and filling forms with OCR and GPT support",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # في البيئة الإنتاجية، يجب تحديد الdomains المسموح بها
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
try:
    yolo_service = YOLOService()
    gpt_service = GPTService()
    speech_service = SpeechService()
    logger.info("Services initialized successfully")
except Exception as e:
    logger.error(f"Error initializing services: {e}")
    raise

@app.get("/")
async def root():
    """Root endpoint to check if the API is running"""
    return {"status": "ok", "message": "Form Analyzer API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/analyze-form", response_model=FormAnalysisResponse)
async def analyze_form(file: UploadFile = File(...)):
    """
    Analyze a form image or PDF and detect fields
    """
    try:
        contents = await file.read()
        
        # Handle PDF files
        if file.content_type == "application/pdf":
            pdf_doc = fitz.open(stream=contents, filetype="pdf")
            if len(pdf_doc) == 0:
                raise HTTPException(status_code=400, detail="PDF file is empty")
            
            # For now, we'll process only the first page
            page = pdf_doc.load_page(0)
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            pdf_doc.close()
        else:
            # Handle image files
            image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Correct image orientation
        image = correct_image_orientation(image)
        
        # Detect fields using YOLO
        fields = yolo_service.detect_fields(image)
        
        # Create annotated image for GPT
        base_img = image.copy().convert("RGBA")
        annotated_image = create_annotated_image(base_img, fields)
        
        # Get form details from GPT
        language_direction = "rtl" if fields and is_arabic_text(fields[0]["label"]) else "ltr"
        explanation, gpt_fields = gpt_service.get_form_details(annotated_image, language_direction)
        
        # Process and return results
        return FormAnalysisResponse(
            fields=fields,
            form_explanation=explanation,
            language_direction=language_direction
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/text-to-speech")
async def convert_text_to_speech(request: TextToSpeechRequest):
    """
    Convert text to speech using ElevenLabs
    """
    try:
        audio_bytes = text_to_speech(
            text=request.text,
            voice_id=request.voice_id,
            language_direction=request.language_direction
        )
        return audio_bytes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/speech-to-text", response_model=SpeechToTextResponse)
async def convert_speech_to_text(
    audio_file: UploadFile = File(...),
    language_code: str = "en"
):
    """
    Convert speech to text using ElevenLabs
    """
    try:
        audio_bytes = await audio_file.read()
        transcript = speech_to_text(audio_bytes, language_code)
        if transcript:
            processed_transcript = process_transcript(transcript, language_code)
            return SpeechToTextResponse(
                original_transcript=transcript,
                processed_transcript=processed_transcript
            )
        raise HTTPException(status_code=400, detail="Could not transcribe audio")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/annotate-form")
async def annotate_form(request: AnnotateFormRequest):
    """
    Draw text and checkmarks on form image
    """
    try:
        # Create annotated image
        annotated = create_annotated_image(
            request.image,
            request.texts,
            request.fields
        )
        
        if annotated:
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            annotated.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            return img_byte_arr
        raise HTTPException(status_code=400, detail="Could not annotate image")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-audio", response_model=TextResponse)
async def process_audio(file: UploadFile, language_code: str = 'en'):
    """
    Process audio file and return transcribed text
    """
    try:
        audio_bytes = await file.read()
        transcript = speech_service.speech_to_text(audio_bytes, language_code)
        if transcript:
            processed = speech_service.process_transcript(transcript, language_code)
            return TextResponse(text=processed)
        raise HTTPException(status_code=400, detail="Could not process audio")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/text-to-speech")
async def text_to_speech(text: str, is_arabic: bool = False):
    """
    Convert text to speech and return audio file
    """
    try:
        audio_bytes = speech_service.text_to_speech(text, is_arabic)
        if audio_bytes:
            return StreamingResponse(
                io.BytesIO(audio_bytes),
                media_type="audio/mpeg"
            )
        raise HTTPException(status_code=400, detail="Could not generate audio")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-form")
async def generate_form(
    original_image: UploadFile,
    request: FormGenerationRequest,
    output_format: str = "pdf"
):
    """
    Generate filled form and return as PDF or PNG
    """
    try:
        image_bytes = await original_image.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        annotated = image_service.create_annotated_image(
            image,
            request.texts,
            request.ui_fields
        )
        
        if not annotated:
            raise HTTPException(status_code=400, detail="Could not generate form")
        
        # Prepare output
        output = io.BytesIO()
        if output_format == "pdf":
            annotated.convert('RGB').save(output, format='PDF')
            media_type = "application/pdf"
            filename = "filled_form.pdf"
        else:
            annotated.save(output, format='PNG')
            media_type = "image/png"
            filename = "filled_form.png"
        
        output.seek(0)
        return StreamingResponse(
            output,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("PORT", 10000))
    host = "0.0.0.0"
    
    print(f"Starting server on {host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=False) 