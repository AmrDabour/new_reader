import google.generativeai as genai
import base64
import io
from PIL import Image
from typing import Tuple, List, Dict, Optional
from ..config import get_settings
import json

settings = get_settings()

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.google_ai_api_key)
        
        generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 2000,
        }
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
        
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-pro-vision',
            generation_config=generation_config,
            safety_settings=safety_settings
        )

    def get_form_details(self, image: Image.Image, language: str) -> Tuple[Optional[str], Optional[List[Dict]]]:
        """
        Makes a single call to Gemini to get both the field labels and a general
        explanation of the form.
        """
        try:
            # Convert image to bytes
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_bytes = buffered.getvalue()

            lang_name = "Arabic" if language == 'rtl' else "English"

            prompt = f"""
You are an expert in document analysis. I am providing you with an image of a form where potential input fields are numbered.
Your task is to perform two actions and return the result as a single JSON object.

1.  **Extract Labels**: For each numbered area on the image, extract the exact text label that describes it.
    -   Do NOT summarize or invent labels. Extract the text as you see it.
    -   **CRITICAL FOR ARABIC**: For any text in Arabic, you MUST extract the characters verbatim. Do not romanize, translate, or interpret Arabic names or words. Preserve the original Arabic script with perfect precision.
2.  **Generate Explanation**: Based on the labels you just extracted, write a brief, friendly summary of the form's purpose and what information the user will need to provide. This explanation MUST be in {lang_name}.

Return a single, valid JSON object with the following structure and nothing else. Do not wrap it in markdown.
{{
  "explanation": "The explanation you generated in {lang_name}.",
  "fields": [
    {{ "id": 1, "label": "The label for box 1" }},
    {{ "id": 2, "label": "The label for box 2" }}
  ]
}}
"""
            response = self.model.generate_content(
                [prompt, image_bytes],
                stream=False
            )
            
            result = response.text
            parsed_json = json.loads(result)
            
            explanation = parsed_json.get("explanation")
            fields = parsed_json.get("fields")

            if isinstance(fields, list) and explanation:
                return explanation, fields
            
            return None, None

        except Exception as e:
            print(f"Error in Gemini service: {e}")
            return None, None 