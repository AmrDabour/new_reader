from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Google AI Settings - will be loaded from GOOGLE_AI_API_KEY env var
    google_ai_api_key: str

    # YOLO Model Paths - Relative to the WORKDIR in Docker
    boxes_model_path: str = "app/models/boxes.pt"
    dot_line_model_path: str = "app/models/dot_line.pt"

    # Tesseract Configuration - loaded from TESSERACT_CMD env var, with a default for Linux
    tesseract_cmd: str = "/usr/bin/tesseract"

    class Config:
        # Pydantic will automatically look for environment variables
        # that match the field names (case-insensitive).
        # We can also load from a .env file for local development.
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()