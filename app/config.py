from pydantic_settings import BaseSettings
from functools import lru_cache
import os


def get_default_base_url() -> str:
    """Determine default URL based on runtime environment"""
    # Check for GitHub CodeSpaces environment variables
    if os.getenv("CODESPACES") == "true":
        codespace_name = os.getenv("CODESPACE_NAME", "")
        if codespace_name:
            return (
                f"https://{codespace_name}-{os.getenv('PORT', '10000')}.app.github.dev"
            )

    # Default value for local development
    return "http://localhost:10000"


class Settings(BaseSettings):
    # Base URL for the application
    base_url: str = None  # Will be set later

    # Google AI Settings - will be loaded from GOOGLE_AI_API_KEY env var
    google_ai_api_key: str

    # YOLO Model Paths - Relative to the WORKDIR in Docker (for form analyzer)
    boxes_model_path: str = "app/models/boxes.pt"
    dot_line_model_path: str = "app/models/dot_line.pt"

    # Tesseract Configuration - loaded from TESSERACT_CMD env var, with a default for Linux
    tesseract_cmd: str = "/usr/bin/tesseract"

    # Port setting - optional
    port: int = 10000

    # Document processing settings (for PPT/PDF reader)
    max_file_size_mb: int = 50
    supported_formats: list = [".pptx", ".ppt", ".pdf"]

    # AI Analysis settings
    gemini_model: str = "gemini-2.5-flash"  # Unified model for all Gemini operations
    gemini_tts_model: str = (
        "gemini-2.5-flash-preview-tts"  # Specialized model for text-to-speech
    )

    # Image processing settings
    image_quality: int = 2  # Scale factor for PDF rendering
    max_image_size: int = (
        4096  # Maximum width/height for images (increased from 1920 for better form analysis quality)
    )

    class Config:
        # Pydantic will automatically look for environment variables
        # that match the field names (case-insensitive).
        # We can also load from a .env file for local development.
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set base_url if not specified
        if not self.base_url:
            self.base_url = get_default_base_url()


@lru_cache()
def get_settings():
    return Settings()
