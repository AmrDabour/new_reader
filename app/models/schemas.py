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
    form_explanation: str = ""  # Form explanation if quality is good


# --- Main Analysis Endpoint ---
class UIField(BaseModel):
    box_id: str
    label: str
    type: str
    box: Optional[List[float]] = None  # [x_center, y_center, width, height]


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
    signature_image_b64: Optional[str] = None  # New field to receive signature image
    signature_field_id: Optional[str] = (
        None  # Signature field ID to determine image placement
    )


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
    image_analysis: str  # Added image analysis field


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


# =============================================================================
# PDF FORM ANALYSIS SCHEMAS
# =============================================================================


class PDFInfo(BaseModel):
    total_pages: int
    title: str = ""
    author: str = ""
    subject: str = ""


class PDFPageAnalysis(BaseModel):
    page_number: int
    fields: List[UIField]
    language_direction: str
    image_width: int
    image_height: int
    has_fields: bool = False
    field_count: int = 0


class PDFFormAnalysisResponse(BaseModel):
    pdf_info: PDFInfo
    pages: List[PDFPageAnalysis]
    session_id: str
    total_fields: int = 0
    pages_with_fields: int = 0
    recommended_language: str = "rtl"


class PDFQualityResponse(BaseModel):
    pdf_info: PDFInfo
    quality_good: bool
    quality_message: str
    session_id: str
    form_explanation: str = ""
    recommended_language: str = "rtl"


# --- PDF Navigation for multi-page forms ---
class PDFPageRequest(BaseModel):
    session_id: str
    page_number: int


class PDFPageResponse(BaseModel):
    page_number: int
    total_pages: int
    fields: List[UIField]
    image_base64: str
    language_direction: str
    has_fields: bool
    session_id: str
