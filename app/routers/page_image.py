"""
Page Image Endpoint Module

This module contains the page image endpoint and all its related functionality.
It provides the ability to retrieve page/slide images from processed documents.

Endpoint: GET /document/{session_id}/page/{page_number}/image
Purpose: Get Page Image - Returns the image of a specific page/slide
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import base64
import logging
from typing import Dict, Any

# Initialize logger
logger = logging.getLogger(__name__)

# Create router for page image endpoints
router = APIRouter()

# Document sessions storage (shared with main document_reader)
# In production, this should be replaced with a proper database or cache
document_sessions: Dict[str, Any] = {}


def set_document_sessions(sessions: Dict[str, Any]):
    """
    Set the document sessions dictionary from the main module
    This function should be called by the main document_reader module
    to share the sessions data
    """
    global document_sessions
    document_sessions = sessions


def get_document_sessions() -> Dict[str, Any]:
    """
    Get the current document sessions dictionary
    """
    return document_sessions


def validate_session_and_page(session_id: str, page_number: int) -> Dict[str, Any]:
    """
    Validate session exists and page number is valid
    Returns the session data if valid
    Raises HTTPException if invalid
    """
    if session_id not in document_sessions:
        raise HTTPException(status_code=404, detail="جلسة المستند غير موجودة")

    session = document_sessions[session_id]

    if page_number < 1 or page_number > session["total_pages"]:
        raise HTTPException(status_code=400, detail="رقم الصفحة غير صحيح")

    return session


def get_page_data(session: Dict[str, Any], page_number: int) -> Dict[str, Any]:
    """
    Extract page data from session for the specified page number
    Returns the page data dictionary
    Raises HTTPException if page data is invalid
    """
    page_index = page_number - 1

    if "document_data" not in session or "pages" not in session["document_data"]:
        raise HTTPException(status_code=500, detail="بيانات المستند غير صحيحة")

    pages = session["document_data"]["pages"]

    if page_index >= len(pages):
        raise HTTPException(status_code=404, detail="بيانات الصفحة غير موجودة")

    page_data = pages[page_index]

    if "image_base64" not in page_data:
        raise HTTPException(status_code=404, detail="صورة الصفحة غير متوفرة")

    return page_data


def decode_image_data(image_base64: str) -> bytes:
    """
    Decode base64 image data to bytes
    Returns the decoded image bytes
    Raises HTTPException if decoding fails
    """
    try:
        if not image_base64 or not image_base64.strip():
            raise HTTPException(status_code=404, detail="صورة الصفحة فارغة")

        # Decode base64 image
        image_data = base64.b64decode(image_base64)

        if len(image_data) == 0:
            raise HTTPException(status_code=404, detail="بيانات الصورة فارغة")

        return image_data

    except base64.binascii.Error as e:
        logger.error(f"Base64 decoding error: {str(e)}")
        raise HTTPException(status_code=500, detail="خطأ في فك ترميز الصورة")
    except Exception as e:
        logger.error(f"Image decoding error: {str(e)}")
        raise HTTPException(status_code=500, detail="خطأ في معالجة بيانات الصورة")


def create_image_response(image_data: bytes, media_type: str = "image/png") -> Response:
    """
    Create FastAPI Response object for image data
    Returns Response object with image content
    """
    return Response(content=image_data, media_type=media_type)


def get_page_image_info(session_id: str, page_number: int) -> Dict[str, Any]:
    """
    Get information about a page image without returning the actual image data
    Useful for checking if an image exists and getting metadata
    """
    try:
        session = validate_session_and_page(session_id, page_number)
        page_data = get_page_data(session, page_number)

        image_base64 = page_data.get("image_base64", "")
        has_image = bool(image_base64 and image_base64.strip())

        image_info = {
            "session_id": session_id,
            "page_number": page_number,
            "has_image": has_image,
            "page_title": page_data.get("title", f"Page {page_number}"),
            "image_size_bytes": len(base64.b64decode(image_base64)) if has_image else 0,
            "image_base64_length": len(image_base64) if has_image else 0,
        }

        return image_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting page image info: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"خطأ في الحصول على معلومات الصورة: {str(e)}"
        )


# ==================== MAIN ENDPOINT ====================


@router.get("/{session_id}/page/{page_number}/image")
async def get_page_image(session_id: str, page_number: int):
    """
    الحصول على صورة الصفحة/الشريحة

    Get Page Image Endpoint

    Args:
        session_id (str): The document session ID
        page_number (int): The page number to retrieve (1-based)

    Returns:
        Response: FastAPI Response object containing the image data as PNG

    Raises:
        HTTPException:
            - 404 if session doesn't exist
            - 400 if page number is invalid
            - 404 if page image is not available
            - 500 if there's an internal error

    Example Usage:
        GET /document/doc_1/page/1/image

    Response:
        Content-Type: image/png
        Body: Raw PNG image data
    """
    try:
        # Step 1: Validate session and page number
        session = validate_session_and_page(session_id, page_number)
        logger.info(f"Validated session {session_id} and page {page_number}")

        # Step 2: Get page data
        page_data = get_page_data(session, page_number)
        logger.info(f"Retrieved page data for page {page_number}")

        # Step 3: Decode image data
        image_base64 = page_data["image_base64"]
        image_data = decode_image_data(image_base64)
        logger.info(f"Decoded image data, size: {len(image_data)} bytes")

        # Step 4: Create and return response
        response = create_image_response(image_data, "image/png")
        logger.info(
            f"Successfully returned image for session {session_id}, page {page_number}"
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as they already have proper status codes and messages
        raise
    except Exception as e:
        # Log unexpected errors and return generic error response
        logger.error(f"Unexpected error in get_page_image: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"خطأ في الحصول على صورة الصفحة: {str(e)}"
        )


# ==================== MODULE INFORMATION ====================


def get_module_info():
    """
    Get information about this page image module
    """
    return {
        "module_name": "Page Image Endpoint Module",
        "version": "1.0.0",
        "description": "Handles page/slide image retrieval from processed documents",
        "endpoints": [
            {
                "path": "/{session_id}/page/{page_number}/image",
                "method": "GET",
                "description": "Get page image as PNG",
            },
        ],
        "dependencies": ["fastapi", "base64 (built-in)", "logging (built-in)"],
    }


if __name__ == "__main__":
    # Module information when run directly
    import json

    print(json.dumps(get_module_info(), indent=2))
