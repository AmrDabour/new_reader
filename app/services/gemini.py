from app.config import get_settings
import google.generativeai as genai
from PIL import Image
import base64
import io
import json
import re
import logging
from typing import Dict, List, Any, Optional

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

    def get_form_details(self, image: Image.Image, language: str):
        """
        Makes a single call to Gemini to get both the field labels and a general
        explanation of the form.
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            lang_name = "Arabic" if language == 'rtl' else "English"
            
            # --- Language-Specific Prompts ---
            if language == 'rtl':
                prompt = f"""
أنت مساعد ذكي متخصص في تحليل النماذج، ومصمم خصيصًا لمساعدة مستخدم كفيف. هدفك الأساسي هو تقديم فهم واضح وموجز للنموذج.

1.  **تحليل وتلخيص:** اقرأ النموذج بالكامل لفهم غرضه. بعد ذلك، قم بإنشاء ملخص مفيد (عدة جمل) **باللغة العربية فقط**. يجب أن يحقق الملخص توازنًا بين الإيجاز وتوفير المعلومات الهامة. يجب أن يتضمن الملخص:
    - الغرض الرئيسي للنموذج (مثال: "هذا طلب للحصول على منحة دراسية...").
    - أي جهات أو مؤسسات أو شروط رئيسية مذكورة بالفعل في النص (مثال: "...مقدمة من ITIDA و NTI..."، "...تتضمن شرطًا جزائيًا في حالة الغياب...").
    - الفئات العامة للمعلومات التي سيحتاج المستخدم إلى تقديمها (مثال: "...سيُطلب منك تقديم تفاصيل شخصية ومعلومات الاتصال وبياناتك الأكاديمية.").
    - الهدف هو إعطاء المستخدم إحساسًا جيدًا بسياق النموذج دون قراءة كل كلمة فيه.

2.  **تحديد الحقول القابلة للتعبئة:** لكل مربع مرقم (1، 2، 3، إلخ) يمثل مكانًا للكتابة للمستخدم:
    - ابحث عن التسمية النصية أو الوصف المقابل بالقرب منه.
    - **حدد ما إذا كان المربع صالحًا بناءً على السياق:** قم بتحليل التسمية والنص المحيط لفهم الغرض من الحقل.
        - يعتبر الحقل **غير صالح** إذا كان النص يشير إلى أنه "للاستخدام الرسمي فقط"، أو مثال، أو مجرد تعليمة، أو إذا كان يحتوي بالفعل على قيمة محددة.
        - يعتبر الحقل **صالحًا** إذا كان غرضه هو الحصول على معلومات من المستخدم بوضوح (مثل: "الاسم"، "العنوان"، "التوقيع").
        - **مربعات الاختيار:** تكون مربعات الاختيار **صالحة** دائمًا تقريبًا. اجعلها غير صالحة فقط إذا لم تكن عنصرًا تفاعليًا بشكل واضح.
    - احتفظ بنص التسمية كما هو مكتوب في النموذج تمامًا، دون ترجمة.

3.  **تنسيق الإخراج:** يجب أن يكون الإخراج كائن JSON واحد فقط، بدون أي نص قبله أو بعده.

    ```json
    {{
      "explanation": "ملخصك المفيد والموجز باللغة العربية.",
      "fields": [
        {{ "id": 1, "label": "نص المربع 1", "valid": true }},
        {{ "id": 2, "label": "نص المربع 2", "valid": false }}
      ]
    }}
    ```"""
            else:
                prompt = f"""You are an intelligent form assistant, specifically designed to help a visually impaired user. Your primary goal is to provide a clear and concise understanding of the form.

1.  **Analyze and Summarize:** Read the entire form to understand its purpose. Then, generate a helpful summary (a few sentences) in **{lang_name} only**. Achieve a balance between being concise and informative. The summary should include:
    - The main purpose of the form (e.g., "This is an application for a scholarship...").
    - Any important entities, organizations, or key conditions already mentioned in the text (e.g., "...offered by ITIDA and NTI...", "...it includes a penalty for absence...").
    - The general categories of information the user will need to provide (e.g., "...you will be asked for personal, contact, and academic details.").
    - The goal is to give the user a good sense of the form's context without reading every single word.

2.  **Identify Fillable Fields:** For each numbered box (1, 2, 3, etc.) that represents a place for the user to write:
    - Find the corresponding text label or description near it.
    - **Determine if the box is valid based on CONTEXT:** Analyze the label and surrounding text to understand the field's purpose.
        - A field is **invalid** if the text implies it is for official use, an example, an instruction, or if it already contains a definitive value.
        - A field is **valid** if its purpose is clearly to capture information from the user (e.g., "Name", "Address", "Signature").
        - **Checkboxes:** A checkbox is almost always **valid**. Only mark it as invalid if it is clearly not an interactive element.
    - Keep the label text exactly as it is written in the form, without translation.

3.  **Format your response strictly as a single JSON object with no other text before or after it.**

    ```json
    {{
      "explanation": "Your helpful, concise summary in {lang_name}.",
      "fields": [
        {{ "id": 1, "label": "Text for box 1", "valid": true }},
        {{ "id": 2, "label": "Text for box 2", "valid": false }}
      ]
    }}
    ```"""

            image_part = {"mime_type": "image/png", "data": img_str}
            response = self.form_model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=9000
                ),
                stream=False
            )
            if not response.candidates or response.candidates[0].finish_reason.name != "STOP":
                return None, None
            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            parsed_json = json.loads(response_text)
            explanation = parsed_json.get("explanation")
            fields = parsed_json.get("fields")
            if isinstance(fields, list) and explanation:
                return explanation, fields
            return None, None
        except (json.JSONDecodeError, Exception) as e:
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