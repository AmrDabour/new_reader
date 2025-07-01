from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# =============================================================================
# FORM ANALYZER SCHEMAS
# =============================================================================

# --- Image Quality Check Endpoint ---
class ImageQualityResponse(BaseModel):
    language_direction: str
    quality_good: bool
    quality_message: str
    image_width: int
    image_height: int
    session_id: str  # Added for session management

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
    image_width: int
    image_height: int
    session_id: str  # Added for session management

# --- Annotation Endpoint ---
class AnnotateImageRequest(BaseModel):
    original_image_b64: str
    texts_dict: Dict[str, Any]
    ui_fields: List[UIField]

# =============================================================================
# MONEY READER SCHEMAS
# =============================================================================

class CurrencyAnalysisResponse(BaseModel):
    analysis: str
    status: str = "success"

# =============================================================================
# PPT & PDF READER SCHEMAS
# =============================================================================

# --- Upload Document Endpoint ---
class AnalyzeDocumentResponse(BaseModel):
    session_id: str
    filename: str
    file_type: str  # .pptx, .ppt, .pdf
    total_pages: int
    language: str  # "arabic" or "english"
    presentation_summary: str
    status: str
    message: str

# --- Page/Slide Analysis ---
class SlideAnalysisResponse(BaseModel):
    page_number: int
    title: str
    original_text: str
    explanation: str
    key_points: List[str]
    slide_type: Optional[str] = "content"
    importance_level: Optional[str] = "medium"
    image_data: Optional[str] = ""
    paragraphs: Optional[List[str]] = []
    word_count: Optional[int] = 0
    reading_time: Optional[float] = 0.0

# --- Document Summary ---
class DocumentSummaryResponse(BaseModel):
    session_id: str
    filename: str
    total_pages: int
    presentation_summary: str
    slides_analysis: List[Dict[str, Any]]
    language: str

# --- Navigation ---
class NavigationRequest(BaseModel):
    command: str  # Voice or text command like "go to page 5", "وديني لصفحة 10"
    current_page: int

class NavigationResponse(BaseModel):
    success: bool
    new_page: Optional[int] = None
    message: str

# --- Document Processing Data Models ---
class DocumentPage(BaseModel):
    page_number: int
    title: str
    text: str
    image_base64: str
    notes: Optional[str] = ""

class DocumentData(BaseModel):
    filename: str
    file_type: str
    total_pages: int
    pages: List[DocumentPage]

# --- AI Analysis Models ---
class SlideAnalysis(BaseModel):
    slide_number: int
    title: str
    original_text: str
    explanation: str
    key_points: List[str]
    slide_type: str
    importance_level: str

class DocumentAnalysis(BaseModel):
    presentation_summary: str
    total_slides: int
    slides_analysis: List[SlideAnalysis]
    language: str

# --- Page Question Analysis ---
class PageQuestionRequest(BaseModel):
    question: str  # النص المستخرج من الصوت

class PageQuestionResponse(BaseModel):
    answer: str
    session_id: str
    page_number: int
    question: str

# =============================================================================
# SHARED SCHEMAS
# =============================================================================

# --- Text to Speech ---
class TextToSpeechRequest(BaseModel):
    text: str
    provider: str = "gemini"

# --- Error Response ---
class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int

# --- Health Check ---
class HealthResponse(BaseModel):
    status: str
    service: str
    active_sessions: int = 0