from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Main Analysis Endpoint ---
class UIField(BaseModel):
    box_id: str
    label: str
    type: str
    box: Optional[List[float]] = None # [x_center, y_center, width, height]

class FormAnalysisResponse(BaseModel):
    fields: List[UIField]
    form_explanation: str
    language_direction: str
    annotated_image: str # base64 encoded image
    image_width: int
    image_height: int

# --- TTS Endpoint ---
class TextToSpeechRequest(BaseModel):
    text: str
    provider: str = "gemini"

# --- Annotation Endpoint ---
class AnnotateImageRequest(BaseModel):
    original_image_b64: str
    texts_dict: Dict[str, Any]
    ui_fields: List[UIField] 