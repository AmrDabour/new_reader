## Form API Documentation for Flutter

This document describes all endpoints under the `/form` prefix, including request/response shapes, content types, typical flows, and common errors. Use this as the integration spec for the Flutter app.

Notes
- Base URL/port is environment-specific. Default local dev port: 10000. Example: http://localhost:10000
- All responses are UTF‑8. No authentication is required.
- Image processing: scanner‑like correction is applied on upload, then the corrected image is cached in a server session for reuse. Pipeline:
  - Document border detection and perspective warp (top‑down view)
  - Deskew via Hough lines (near‑horizontal)
  - OCR‑based upright orientation (0/90/180/270) with 180° flip disambiguation
  - Fit to max dimension (settings.max_image_size) with aspect ratio preserved
- Debug images saved under app/logs/forms: “{timestamp}_{session_id}_{stage}.png” where stage ∈ {corrected, analysis_input}.
- Prerequisites: Tesseract should be installed and accessible at settings.tesseract_cmd (default /usr/bin/tesseract) with eng and ara language data; otherwise, heuristics are used.

---

## Data Models

- UIField
  - box_id: string
  - label: string
  - type: "textbox" | "checkbox"
  - box: [x, y, w, h] (numbers)

---

## Image Flow

### POST /form/check-file
- Purpose: Upload an image or PDF (first page). The server applies scanner-like correction (border warp, deskew, OCR-based upright orientation, fit), checks quality, detects language, optionally returns a short explanation, and stores the corrected image in the session.
- Content-Type: multipart/form-data
- Body
  - file: UploadFile (image/* or application/pdf)
- Response 200 (ImageQualityResponse)
  - language_direction: "rtl" | "ltr"
  - quality_good: bool
  - quality_message: string
  - image_width: int
  - image_height: int
  - session_id: string
  - form_explanation: string
- Notes: The corrected image is stored in session as base64 (converted_image_b64) and reused by analyze-form. A PNG of the corrected image is also saved to app/logs/forms for QA.
- Errors: 400, 503 (PDF disabled), 500

Example Response
{
  "language_direction": "rtl",
  "quality_good": true,
  "quality_message": "Good lighting and readable text",
  "image_width": 1200,
  "image_height": 1700,
  "session_id": "abcd-1234",
  "form_explanation": "..."
}

<!-- /form/check-image removed; use /form/check-file for images and PDFs -->

### POST /form/analyze-form
- Purpose: Analyze fields on the already corrected image stored in the session. Do not send a file.
- Content-Type: multipart/form-data
- Body
  - session_id: string (required)
  - language_direction: string (optional; if omitted, uses session value or defaults to "rtl")
- Response 200 (FormAnalysisResponse)
  - fields: UIField[]
  - form_explanation: string (empty for this endpoint)
  - language_direction: "rtl" | "ltr"
  - image_width: int
  - image_height: int
  - session_id: string
- Errors: 400 (no session image; call /form/check-file first), 500

Example Response
{
  "fields": [
    { "box_id": "box_0", "label": "Name", "type": "textbox", "box": [100,200,300,40] },
    { "box_id": "box_1", "label": "Agree", "type": "checkbox", "box": [450,600,20,20] }
  ],
  "form_explanation": "",
  "language_direction": "rtl",
  "image_width": 1200,
  "image_height": 1700,
  "session_id": "abcd-1234"
}

### POST /form/annotate-image
- Purpose: Render final filled image by drawing texts, checkboxes, and optional signature.
- Content-Type: application/json
- Body (AnnotateImageRequest)
  - original_image_b64: string (Base64)
  - texts_dict: { [box_id: string]: string | boolean }
  - ui_fields: UIField[]
  - signature_image_b64: string (optional, Base64)
  - signature_field_id: string (optional)
- Response 200: image/png (bytes)
- Notes: For checkboxes, send true to mark checked. Arabic text is supported and rendered right-to-left.

---

## Image Correction Details (reference)
- Border detection: finds largest convex 4-point contour and applies perspective transform to top‑down.
- Deskew: estimates median angle from near‑horizontal Hough lines and rotates to zero.
- Upright orientation: uses Tesseract OSD to choose among 0/90/180/270; if ambiguous, compares OCR confidence vs. 180° and flips only when clearly better.
- Fit: resizes to settings.max_image_size max(width,height) while preserving aspect.

If Tesseract is not available, orientation falls back to edge‑projection heuristics.

Example Request (body JSON)
{
  "original_image_b64": "<base64>",
  "texts_dict": { "box_0": "Ahmed Ali", "box_1": true },
  "ui_fields": [
    { "box_id": "box_0", "label": "Name", "type": "textbox", "box": [100,200,300,40] },
    { "box_id": "box_1", "label": "Agree", "type": "checkbox", "box": [450,600,20,20] }
  ],
  "signature_image_b64": "<optional base64>",
  "signature_field_id": "box_2"
}

---

## Sessions

### DELETE /form/session/{session_id}
- Delete a single session. Response 200: { message }

### GET /form/session-info
- Operational info. Response 200: { active_sessions, session_timeout }

---

## Speech

### POST /form/text-to-speech
- Content-Type: application/json
- Body
  - text: string
  - provider: "gemini" (default)
- Response 200: audio/* (bytes). May respond 429 on quota.

### POST /form/speech-to-text
- Content-Type: multipart/form-data
- Body
  - file: UploadFile (audio/*)
  - language_code: string (default "en")
- Response 200: { text: string }

---

## PDF Flow (Option A: Simple quality + full analyze)

### POST /form/check-pdf
- Validate PDF and create session.
- Content-Type: multipart/form-data
- Body: file: UploadFile (application/pdf)
- Response 200 (PDFQualityResponse)
  - pdf_info: { total_pages, title, author, subject }
  - quality_good: bool
  - quality_message: string
  - session_id: string
  - form_explanation: string
  - recommended_language: "rtl" | "ltr"

### POST /form/analyze-pdf
- Analyze all pages with previously created session.
- Content-Type: multipart/form-data
- Body
  - session_id: string (required)
  - language_direction: string (optional)
- Response 200 (PDFFormAnalysisResponse)
  - pdf_info, pages: PDFPageAnalysis[], session_id, total_fields, pages_with_fields, recommended_language

---

## PDF Flow (Option B: Multi-page step-by-step)

### POST /form/explore-pdf
- Upload PDF, convert pages to images, and create session for multi-step flow.
- Content-Type: multipart/form-data
- Body: file: UploadFile (application/pdf)
- Response 200: { session_id, total_pages, filename, title, message, stage: "explore" }

### POST /form/explain-pdf-page
- Content-Type: multipart/form-data
- Body
  - session_id: string
  - page_number: int
- Response 200: { session_id, page_number, total_pages, explanation, language_direction, quality_good, quality_message, has_next_page, next_page_number, all_pages_explained, image_width, image_height }

### POST /form/analyze-pdf-page
- Content-Type: multipart/form-data
- Body
  - session_id: string
  - page_number: int
- Response 200: { session_id, page_number, total_pages, has_fields, fields: UIField[], language_direction, image_width, image_height, has_next_page, next_page_number, all_pages_analyzed, field_count }

### POST /form/fill-pdf-page
- Render a filled image for one page.
- Content-Type: multipart/form-data
- Body
  - session_id: string
  - page_number: int
  - texts_dict: string (JSON string)
  - signature_image_b64: string (optional)
  - signature_field_id: string (optional)
- Response 200: image/png (bytes)
- Response Headers: X-Session-ID, X-Page-Number, X-Total-Pages, X-Has-Next-Page, X-Next-Page-Number, X-All-Pages-Filled, X-Ready-For-Download

### GET /form/download-filled-pdf/{session_id}
- Download the final merged PDF with all filled pages.
- Response 200: application/pdf (bytes) with Content-Disposition filename.

### GET /form/pdf-session-status/{session_id}
- Response 200: { session_id, filename, total_pages, current_stage, current_page, explained_pages, analyzed_pages, filled_pages, language_direction, ready_for_download }

### DELETE /form/pdf-session/{session_id}
- Delete the multi-page PDF session.

### POST /form/pdf/{session_id}/annotate-page
- Content-Type: multipart/form-data
- Path param: session_id
- Body
  - page_number: int
  - texts_dict: string (JSON string)
  - signature_image_b64: string (optional)
  - signature_field_id: string (optional)
- Response 200: image/png (bytes)

### POST /form/pdf-page
- Extract a specific PDF page as an image.
- Content-Type: application/json
- Body: { session_id: string, page_number: int }
- Response 200: { page_number, total_pages, fields: UIField[], image_base64, language_direction, has_fields, session_id }

---

## Typical Sequences

Image Forms
1) POST /form/check-file (multipart: file)
2) POST /form/analyze-form (multipart: session_id)
3) Optional: POST /form/annotate-image (json) to get a final rendered PNG

PDF Forms (Multi-page)
1) POST /form/explore-pdf (multipart: file)
2) For each page: explain → analyze → fill
3) GET /form/download-filled-pdf/{session_id}

---

## Errors & Status Codes
- 200: Success
- 400: Bad request (missing file/session, invalid PDF, conversion failure)
- 429: Quota exceeded (TTS/STT)
- 503: PDF processing/merging unavailable (PyMuPDF missing)
- 500: Internal server error

---

## Implementation Notes for Flutter
- Use multipart/form-data for endpoints that accept files (check-file, explore-pdf, etc.).
- Use application/json for annotate-image and pdf-page.
- Persist `session_id` from the check/explore step and reuse it across subsequent calls.
- For checkboxes, send `true` in `texts_dict` keyed by the checkbox `box_id`.
