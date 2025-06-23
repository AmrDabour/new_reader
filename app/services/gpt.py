import openai
import base64
import io
from PIL import Image
from typing import Tuple, List, Dict, Optional
from ..config import get_settings
import json

settings = get_settings()

class GPTService:
    def __init__(self):
        self.client = openai.AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )

    def get_form_details(self, image: Image.Image, language: str) -> Tuple[Optional[str], Optional[List[Dict]]]:
        """
        Makes a single call to GPT-4 to get both the field labels and a general
        explanation of the form.
        """
        try:
            # Convert image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

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

            response = self.client.chat.completions.create(
                model=settings.azure_openai_deployment_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_str}"}
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            parsed_json = json.loads(result)
            
            explanation = parsed_json.get("explanation")
            fields = parsed_json.get("fields")

            if isinstance(fields, list) and explanation:
                return explanation, fields
            
            return None, None

        except Exception as e:
            print(f"Error in GPT service: {e}")
            return None, None 