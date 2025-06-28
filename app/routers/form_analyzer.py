from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import Response
import base64
import io
import json
from PIL import Image

from app.services.yolo import YOLOService
from app.services.gemini import GeminiService
from app.services.image import ImageService
from app.models.schemas import FormAnalysisResponse

router = APIRouter()

# Initialize services
yolo_service = YOLOService()
gemini_service = GeminiService()
image_service = ImageService()

@router.post("/analyze", response_model=FormAnalysisResponse)
async def analyze_form(image: UploadFile = File(...), language: str = Form("rtl")):
    """
    Main endpoint to analyze a form from an uploaded file.
    Now returns field coordinates and image dimensions as well.
    """
    try:
        print("[API] /form/analyze request received.")
        image_data = Image.open(io.BytesIO(await image.read())).convert("RGB")
        corrected_image = image_service.correct_image_orientation(image_data)
        fields_data, lang_direction = yolo_service.detect_fields(corrected_image)
        
        # Use the language parameter from form data
        if language:
            lang_direction = language
        if not fields_data:
            print("[API] No fillable fields detected by YOLO.")
            raise HTTPException(status_code=400, detail="No fillable fields detected.")

        gpt_image = image_service.create_annotated_image_for_gpt(corrected_image, fields_data, with_numbers=True)
        explanation, gpt_fields_raw = gemini_service.get_form_details(gpt_image, lang_direction)
        if not gpt_fields_raw:
            print("[API] AI model failed to extract form details.")
            raise HTTPException(status_code=500, detail="AI model failed to extract form details.")

        gpt_fields = [field for field in gpt_fields_raw if field.get("valid", False)]
        final_fields = image_service.combine_yolo_and_gpt_results(fields_data, gpt_fields)

        ui_image = image_service.create_annotated_image_for_gpt(corrected_image, fields_data, with_numbers=True)
        buffered = io.BytesIO()
        ui_image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        print("[API] /form/analyze request completed.")
        return FormAnalysisResponse(
            fields=final_fields,
            form_explanation=explanation,
            language_direction=lang_direction,
            annotated_image=img_b64,
            image_width=corrected_image.width,
            image_height=corrected_image.height
        )

    except Exception as e:
        print(f"[API] Error in analyze_form: {e}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

@router.post("/annotate")
async def annotate_image_endpoint(
    image: UploadFile = File(...),
    language: str = Form("rtl"),
    fields: str = Form(...)
):
    """
    Receives the original image and user data, draws the data onto the
    image, and returns the final annotated image.
    """
    try:
        # Parse fields JSON
        fields_data = json.loads(fields)
        
        # Read and process image
        original_image = Image.open(io.BytesIO(await image.read())).convert("RGB")
        
        # Create a simple annotated image for testing
        # In a real implementation, you would use the fields_data to annotate
        buffered = io.BytesIO()
        original_image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        
        return Response(content=img_bytes, media_type="image/png")

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in fields parameter")
    except Exception as e:
        print(f"An unexpected error occurred in annotate_image: {e}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@router.get("/ping")
def ping():
    """فحص صحة خدمة تحليل النماذج"""
    return {"service": "Form Analyzer", "status": "healthy"} 