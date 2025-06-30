from app.config import get_settings
import google.generativeai as genai
from PIL import Image
import base64
import io
import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple

settings = get_settings()
genai.configure(api_key=settings.google_ai_api_key)

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        try:
            self.form_model = genai.GenerativeModel(settings.gemini_model)
            self.currency_model = genai.GenerativeModel(settings.gemini_model)
            self.document_model = genai.GenerativeModel(settings.gemini_model)
            self.vision_model = genai.GenerativeModel(settings.gemini_model)
            logger.info("Gemini AI service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI: {e}")
            self.form_model = None
            self.currency_model = None
            self.document_model = None
            self.vision_model = None

    # =============================================================================
    # FORM ANALYZER METHODS
    # =============================================================================

    def get_form_details(self, image: Image.Image, language: str) -> Tuple[Optional[str], Optional[List[Dict]]]:
        """
        Makes a single call to Gemini to get both the field labels and a general
        explanation of the form.
        """
        try:
            # Check if model is available
            if not self.form_model:
                return None, None

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
            # Pass the PIL Image directly to Gemini
            response = self.form_model.generate_content(
                [prompt, image],
                stream=False
            )
            
            # Check if response is valid
            if not response or not response.text:
                print("Empty response from Gemini in get_form_details")
                return None, None
            
            result = response.text.strip()
            print(f"Raw Gemini response in get_form_details: {result[:200]}...")  # Log for debugging
            
            # Clean the response - remove markdown formatting if present
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()
            
            # Try to parse JSON
            try:
                parsed_json = json.loads(result)
            except json.JSONDecodeError as json_err:
                print(f"JSON decode error in get_form_details: {json_err}")
                print(f"Problematic response: {result}")
                return None, None
            
            explanation = parsed_json.get("explanation")
            fields = parsed_json.get("fields")

            if isinstance(fields, list) and explanation:
                return explanation, fields
            
            return None, None

        except Exception as e:
            print(f"Error in Gemini service: {e}")
            return None, None

    # =============================================================================
    # MONEY READER METHODS
    # =============================================================================

    def analyze_currency_image(self, image: Image.Image):
        """
        تحليل صورة العملة باستخدام Gemini API
        """
        try:
            # النص التوجيهي المختصر
            prompt = """
            حلل العملات واطلع النتيجة بلهجة خليجية سعودية:
            
            - لو عملة واحدة أو ورقة واحدة: عندك [القيمة]
            - لو أكثر من واحدة: عندك [المبلغ الإجمالي]، وفيه [تفاصيل الأوراق]
            
            أمثلة:
            - عندك 50 ريال
            - عندك 120 ريال، ورقة 50 ريال و 3 ورقات 20 ريال
            
            استخدم اللهجة الخليجية السعودية فقط.
            اجعل الرد خالي من اي ترحيب
            """

            response = self.currency_model.generate_content([prompt, image])
            return response.text

        except Exception as e:
            return f"خطأ: {str(e)}"

    # =============================================================================
    # PPT & PDF READER METHODS
    # =============================================================================

    def analyze_document_bulk(self, document_data: Dict[str, Any], language: str = "arabic") -> Dict[str, Any]:
        """
        تحليل المستند بالكامل باستخدام Gemini AI
        """
        try:
            if not self.document_model:
                return self._create_fallback_analysis(document_data, language)

            # Prepare slides data for analysis
            slides_data = []
            for page in document_data["pages"]:
                slide_data = {
                    "slide_number": page["page_number"],
                    "title": page["title"],
                    "text": page["text"],
                    "notes": page.get("notes", ""),
                }
                slides_data.append(slide_data)

            # Create analysis prompt
            prompt = self._create_bulk_analysis_prompt(slides_data, language)

            # Get AI analysis
            response = self.document_model.generate_content(prompt)
            analysis_result = self._parse_bulk_analysis_response(response.text, language)

            return analysis_result

        except Exception as e:
            logger.error(f"Error in bulk analysis: {e}")
            return self._create_fallback_analysis(document_data, language)

    def extract_page_number_from_command(self, command: str, current_page: int, total_pages: int) -> Optional[int]:
        """استخراج رقم الصفحة من الأمر الصوتي أو النصي"""
        try:
            # تنظيف الأمر
            command = command.strip().lower()
            
            # البحث عن الأرقام في الأمر
            page_number = self._simple_page_extraction(command, current_page, total_pages)
            
            if page_number is not None:
                return page_number
                
            return None
            
        except Exception as e:
            logger.error(f"Error extracting page number: {e}")
            return None

    def _simple_page_extraction(self, command: str, current_page: int, total_pages: int) -> Optional[int]:
        """استخراج بسيط لرقم الصفحة"""
        
        # قاموس الأرقام العربية
        arabic_numbers = {
            "واحد": 1, "اثنين": 2, "ثلاثة": 3, "أربعة": 4, "خمسة": 5,
            "ستة": 6, "سبعة": 7, "ثمانية": 8, "تسعة": 9, "عشرة": 10,
            "أول": 1, "ثاني": 2, "ثالث": 3, "رابع": 4, "خامس": 5,
            "الأول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4, "الخامس": 5
        }
        
        # أوامر خاصة
        if any(word in command for word in ["التالي", "التالية", "next"]):
            return min(current_page + 1, total_pages)
        elif any(word in command for word in ["السابق", "السابقة", "previous", "prev"]):
            return max(current_page - 1, 1)
        elif any(word in command for word in ["الأول", "البداية", "first", "start"]):
            return 1
        elif any(word in command for word in ["الأخير", "النهاية", "last", "end"]):
            return total_pages
        
        # البحث عن الأرقام
        numbers = re.findall(r'\d+', command)
        for num_str in numbers:
            try:
                page_num = int(num_str)
                if 1 <= page_num <= total_pages:
                    return page_num
            except ValueError:
                continue
        
        # البحث عن الأرقام العربية
        for word, number in arabic_numbers.items():
            if word in command and 1 <= number <= total_pages:
                return number
        
        return None

    def analyze_page_image(self, image_base64: str, language: str = "arabic") -> str:
        """تحليل صورة الصفحة باستخدام الذكاء الاصطناعي"""
        try:
            if not self.vision_model:
                return "خدمة تحليل الصور غير متوفرة حالياً" if language == "arabic" else "Image analysis service is currently unavailable"
            
            if language == "arabic":
                prompt = """حلل هذه الصورة واكتب وصف مختصر باللغة العربية.
                ركز على المحتوى الأساسي والعناصر المهمة في الصورة."""
            else:
                prompt = """Analyze this image and write a brief description in English.
                Focus on the main content and important elements in the image."""
            
            # تحويل base64 إلى image part
            image_part = {
                "mime_type": "image/png",
                "data": image_base64
            }
            
            response = self.vision_model.generate_content([prompt, image_part])
            return response.text
            
        except Exception as e:
            logger.error(f"Error analyzing page image: {e}")
            return "حدث خطأ في تحليل الصورة" if language == "arabic" else "Error occurred while analyzing the image"

    # =============================================================================
    # HELPER METHODS FOR PPT & PDF READER
    # =============================================================================

    def _create_bulk_analysis_prompt(self, slides_data: List[Dict], language: str) -> str:
        """إنشاء prompt شامل لتحليل جميع الشرائح"""

        # Prepare slides text
        slides_text = ""
        for slide in slides_data:
            if language == "arabic":
                slides_text += f"\n--- الشريحة {slide['slide_number']} ---\n"
                if slide["title"]:
                    slides_text += f"العنوان: {slide['title']}\n"
                if slide["text"]:
                    slides_text += f"المحتوى: {slide['text']}\n"
                if slide["notes"]:
                    slides_text += f"الملاحظات: {slide['notes']}\n"
            else:
                slides_text += f"\n--- Slide {slide['slide_number']} ---\n"
                if slide["title"]:
                    slides_text += f"Title: {slide['title']}\n"
                if slide["text"]:
                    slides_text += f"Content: {slide['text']}\n"
                if slide["notes"]:
                    slides_text += f"Notes: {slide['notes']}\n"

        if language == "arabic":
            prompt_header = f"أحلل هذا العرض التقديمي بالكامل. العرض يحتوي على {len(slides_data)} شريحة."
            json_instruction = "أعطني فقط JSON بدون أي نص إضافي."
        else:
            prompt_header = f"Analyze this presentation completely. The presentation contains {len(slides_data)} slides."
            json_instruction = "Return only JSON with no additional text."

        prompt = f"""{prompt_header}

{slides_text}

Return analysis for each slide in the following JSON format:

{{
  "presentation_summary": "Brief summary of the entire presentation",
  "total_slides": {len(slides_data)},
  "slides_analysis": [
    {{
      "slide_number": 1,
      "title": "Slide title",
      "original_text": "Original slide text",
      "explanation": "brief description",
      "key_points": ["Key point 1", "Key point 2"],
      "slide_type": "content",
      "importance_level": "medium"
    }}
  ]
}}

{json_instruction}"""

        return prompt

    def _parse_bulk_analysis_response(self, response_text: str, language: str) -> Dict[str, Any]:
        """تحليل استجابة الذكاء الاصطناعي"""
        try:
            # Clean the response
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            # Parse JSON
            analysis_data = json.loads(response_text.strip())

            # Validate structure
            if "slides_analysis" not in analysis_data:
                raise ValueError("Missing slides_analysis in response")

            return analysis_data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return self._create_fallback_analysis_from_text(response_text, language)
        except Exception as e:
            logger.error(f"Analysis parsing error: {e}")
            return self._create_fallback_analysis_from_text(response_text, language)

    def _create_fallback_analysis(self, document_data: Dict[str, Any], language: str) -> Dict[str, Any]:
        """إنشاء تحليل احتياطي في حالة فشل التحليل الأساسي"""

        if language == "arabic":
            summary_text = "تم إنشاء تحليل أساسي للمستند"
            slide_explanation_template = "هذه هي الصفحة رقم {i} من المستند."
            content_text = "محتوى الصفحة"
            slide_type = "محتوى"
            importance = "متوسط"
            slide_title_template = "الصفحة {i}"
        else:
            summary_text = "Basic document analysis generated"
            slide_explanation_template = "This is page {i} of the document."
            content_text = "Page content"
            slide_type = "content"
            importance = "medium"
            slide_title_template = "Page {i}"

        slides_analysis = []
        for i, page in enumerate(document_data["pages"], 1):
            slide_analysis = {
                "slide_number": i,
                "title": page.get("title", slide_title_template.format(i=i)),
                "original_text": page.get("text", content_text),
                "explanation": slide_explanation_template.format(i=i),
                "key_points": [content_text],
                "slide_type": slide_type,
                "importance_level": importance
            }
            slides_analysis.append(slide_analysis)

        return {
            "presentation_summary": summary_text,
            "total_slides": len(document_data["pages"]),
            "slides_analysis": slides_analysis
        }

    def _create_fallback_analysis_from_text(self, response_text: str, language: str) -> Dict[str, Any]:
        """إنشاء تحليل احتياطي من النص المُستلم"""
        
        if language == "arabic":
            summary_text = f"تحليل أساسي: {response_text[:200]}..."
            slide_explanation = "تحليل أساسي للصفحة"
            content_text = "محتوى الصفحة"
            slide_type = "محتوى"
            importance = "متوسط"
        else:
            summary_text = f"Basic analysis: {response_text[:200]}..."
            slide_explanation = "Basic page analysis"
            content_text = "Page content"
            slide_type = "content"
            importance = "medium"

        # إنشاء تحليل واحد كمثال
        slides_analysis = [{
            "slide_number": 1,
            "title": "Page 1",
            "original_text": content_text,
            "explanation": slide_explanation,
            "key_points": [content_text],
            "slide_type": slide_type,
            "importance_level": importance
        }]

        return {
            "presentation_summary": summary_text,
            "total_slides": 1,
            "slides_analysis": slides_analysis
        }

    def check_image_quality(self, image: Image.Image, language: str = "ar") -> Tuple[bool, str]:
        """
        Check if the uploaded image is suitable for form analysis.
        Returns (is_suitable, feedback_message)
        """
        try:
            # Check if model is available
            if not self.form_model:
                fallback_message = "خدمة فحص جودة الصورة غير متاحة حالياً." if language == "ar" else "Image quality check service is currently unavailable."
                return False, fallback_message

            lang_instruction = "Arabic" if language == "ar" else "English"

            prompt = f"""
You are an AI assistant helping visually impaired users take better photos of forms and documents.

Analyze this image and check if it's suitable for form analysis. Consider these factors:
1. Image clarity and sharpness
2. Lighting conditions
3. Document visibility and completeness
4. Blur or motion blur
5. Angle and orientation
6. Whether it's actually a form/document

Respond with a JSON object in this exact format:
{{
  "is_suitable": true/false,
  "feedback": "Your detailed feedback message in {lang_instruction}"
}}

Guidelines for feedback:
- If suitable: Give encouraging message and confirm it's ready for analysis
- If not suitable: Explain the specific problem(s) and give clear instructions on how to improve the photo
- Be supportive and helpful for visually impaired users
- Use simple, clear language
- Provide specific actionable advice

The feedback must be in {lang_instruction} language.
"""

            # Pass the PIL Image directly to Gemini
            response = self.form_model.generate_content(
                [prompt, image],
                stream=False
            )
            
            # Check if response is valid
            if not response or not response.text:
                print("Empty response from Gemini")
                fallback_message = "لم أتمكن من تحليل الصورة. يرجى المحاولة مرة أخرى." if language == "ar" else "Could not analyze the image. Please try again."
                return False, fallback_message
            
            result = response.text.strip()
            print(f"Raw Gemini response: {result[:200]}...")  # Log first 200 chars for debugging
            
            # Clean the response - remove markdown formatting if present
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()
            
            # Try to parse JSON
            try:
                parsed_json = json.loads(result)
            except json.JSONDecodeError as json_err:
                print(f"JSON decode error: {json_err}")
                print(f"Problematic response: {result}")
                # Provide a fallback response
                fallback_message = "تم استلام الصورة ولكن لم أتمكن من تحليلها بشكل كامل. يرجى التأكد من أن الصورة واضحة وتحتوي على نموذج أو مستند." if language == "ar" else "Image received but could not be fully analyzed. Please ensure the image is clear and contains a form or document."
                return False, fallback_message
            
            is_suitable = parsed_json.get("is_suitable", False)
            feedback = parsed_json.get("feedback", "Unable to analyze image quality.")

            return is_suitable, feedback

        except Exception as e:
            print(f"Error in image quality check: {e}")
            fallback_message = "حدث خطأ في فحص جودة الصورة. يرجى المحاولة مرة أخرى." if language == "ar" else "Error checking image quality. Please try again."
            return False, fallback_message 