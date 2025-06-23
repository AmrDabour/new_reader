from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Tuple, Any
from PIL.Image import Image
from pydantic.config import ConfigDict

class Field(BaseModel):
    box_id: str
    label: str
    type: str  # "textbox" or "checkbox"
    original_box: tuple  # (x, y, w, h)

class FormAnalysisResponse(BaseModel):
    fields: List[Field]
    form_explanation: str
    language_direction: str  # "rtl" or "ltr"

class TextResponse(BaseModel):
    text: str
    confidence: Optional[float]

class AudioResponse(BaseModel):
    text: str
    confidence: float

class FormGenerationRequest(BaseModel):
    texts: Dict[str, str]
    ui_fields: List[Field]

class TextToSpeechRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None
    language_direction: str = "ltr"  # "rtl" or "ltr"

class SpeechToTextResponse(BaseModel):
    original_transcript: str
    processed_transcript: str

class AnnotateFormRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    image: Image
    texts: Dict[str, str]  # box_id -> text
    fields: List[Field] 