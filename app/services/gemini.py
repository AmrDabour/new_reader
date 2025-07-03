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
        self.model = genai.GenerativeModel(settings.gemini_model)

    def remove_markdown_formatting(self, text: str) -> str:
        """إزالة تنسيقات Markdown من النص"""
        if not text:
            return text
        
        # إزالة Bold formatting (**text** و __text__)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'__(.*?)__', r'\1', text)
        
        # إزالة Headers (# ## ###)
        text = re.sub(r'^#{1,6}\s*(.*)$', r'\1', text, flags=re.MULTILINE)
        
        # إزالة Links [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # إزالة Code blocks ```code```
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        
        # إزالة Inline code `code`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # إزالة Strikethrough ~~text~~
        text = re.sub(r'~~(.*?)~~', r'\1', text)
        
        # إزالة Italic formatting - لكن فقط إذا لم تكن جزءًا من قائمة
        # تجنب النجوم في بداية السطر (قوائم) أو النجوم المتعددة
        text = re.sub(r'(?<!^)(?<!\s)\*([^*\n]+?)\*(?!\s*\n)', r'\1', text, flags=re.MULTILINE)
        text = re.sub(r'(?<!^)(?<!\s)_([^_\n]+?)_(?!\s*\n)', r'\1', text, flags=re.MULTILINE)
        
        # تحويل علامات النجوم في بداية الأسطر إلى علامات تعداد عادية
        text = re.sub(r'^\s*\*\s+', '• ', text, flags=re.MULTILINE)
        
        # تنظيف المسافات الزائدة
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text

    def detect_language_and_quality(self, image: Image.Image) -> Tuple[str, bool, str]:
        """
        Detects language direction and checks image quality
        Returns (language_direction, is_good_quality, quality_message)
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            prompt = """
Analyze this image in two steps:

1. **First: Detect Language** - Determine if this form is primarily in Arabic (rtl) or English/other (ltr)

2. **Then: Respond in the SAME detected language** with quality assessment

**Quality Assessment Guidelines:**
- ACCEPTABLE: Minor lighting issues, slight tilt, readable text
- NEEDS IMPROVEMENT: Significantly cropped, very blurry text, major rotation, very poor lighting
- Focus on whether form fields can be detected and text can be read

**Response Format - JSON only:**

```json
{
  "language_direction": "rtl" or "ltr", 
  "quality_good": true or false,
  "quality_message": "Brief assessment and tips in detected language"
}
```

**Example Messages:**
- Arabic form with minor issues: "الصورة مقبولة للتحليل. نصيحة: حاول تحسين الإضاءة قليلاً"
- English form with problems: "Image needs improvement. Try: better lighting and straighten the form"
- Good quality: "الصورة واضحة ومناسبة للتحليل" / "Image is clear and suitable for analysis"

Keep message concise and helpful. Don't be overly strict on minor imperfections.
"""

            image_part = {"mime_type": "image/png", "data": img_str}
            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=1000
                ),
                stream=False
            )
            
            if not response.candidates or response.candidates[0].finish_reason.name != "STOP":
                return 'ltr', True, "Unable to analyze image quality"
                
            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            parsed_json = json.loads(response_text)
            
            language_direction = parsed_json.get("language_direction", 'ltr')
            quality_good = parsed_json.get("quality_good", True)
            quality_message = parsed_json.get("quality_message", "Image quality check completed")
            
            return language_direction, quality_good, quality_message
            
        except (json.JSONDecodeError, Exception) as e:
            return 'ltr', True, "Error analyzing image"

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
            response = self.model.generate_content(
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

    def get_form_fields_only(self, image: Image.Image, language: str):
        """
        Get only the form fields without explanation (for when we already have explanation from check-image)
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            lang_name = "Arabic" if language == 'rtl' else "English"

            # --- Language-Specific Prompts (fields only) ---
            if language == 'rtl':
                prompt = f"""
أنت مساعد ذكي متخصص في تحليل النماذج. هدفك هو تحديد الحقول القابلة للتعبئة فقط.

**تحديد الحقول القابلة للتعبئة:** لكل مربع مرقم (1، 2، 3، إلخ) يمثل مكانًا للكتابة للمستخدم:
- ابحث عن التسمية النصية أو الوصف المقابل بالقرب منه.
- **حدد ما إذا كان المربع صالحًا بناءً على السياق:** قم بتحليل التسمية والنص المحيط لفهم الغرض من الحقل.
    - يعتبر الحقل **غير صالح** إذا كان النص يشير إلى أنه "للاستخدام الرسمي فقط"، أو مثال، أو مجرد تعليمة، أو إذا كان يحتوي بالفعل على قيمة محددة.
    - يعتبر الحقل **صالحًا** إذا كان غرضه هو الحصول على معلومات من المستخدم بوضوح (مثل: "الاسم"، "العنوان"، "التوقيع").
    - **مربعات الاختيار:** تكون مربعات الاختيار **صالحة** دائمًا تقريبًا. اجعلها غير صالحة فقط إذا لم تكن عنصرًا تفاعليًا بشكل واضح.
- احتفظ بنص التسمية كما هو مكتوب في النموذج تمامًا، دون ترجمة.

**تنسيق الإخراج:** يجب أن يكون الإخراج قائمة JSON فقط، بدون أي نص قبله أو بعده.

```json
[
  {{ "id": 1, "label": "نص المربع 1", "valid": true }},
  {{ "id": 2, "label": "نص المربع 2", "valid": false }}
]
```"""
            else:
                prompt = f"""You are an intelligent form assistant. Your goal is to identify fillable fields only.

**Identify Fillable Fields:** For each numbered box (1, 2, 3, etc.) that represents a place for the user to write:
- Find the corresponding text label or description near it.
- **Determine if the box is valid based on CONTEXT:** Analyze the label and surrounding text to understand the field's purpose.
    - A field is **invalid** if the text implies it is for official use, an example, an instruction, or if it already contains a definitive value.
    - A field is **valid** if its purpose is clearly to capture information from the user (e.g., "Name", "Address", "Signature").
    - **Checkboxes:** A checkbox is almost always **valid**. Only mark it as invalid if it is clearly not an interactive element.
- Keep the label text exactly as it is written in the form, without translation.

**Format your response strictly as a JSON array with no other text before or after it.**

```json
[
  {{ "id": 1, "label": "Text for box 1", "valid": true }},
  {{ "id": 2, "label": "Text for box 2", "valid": false }}
]
```"""

            image_part = {"mime_type": "image/png", "data": img_str}
            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=5000
                ),
                stream=False
            )
            if not response.candidates or response.candidates[0].finish_reason.name != "STOP":
                return None
            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            fields = json.loads(response_text)
            if isinstance(fields, list):
                return fields
            return None
        except (json.JSONDecodeError, Exception) as e:
            return None

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

            response = self.model.generate_content([prompt, image])
            
            # إزالة تنسيقات Markdown من الرد
            clean_response = self.remove_markdown_formatting(response.text)
            return clean_response

        except Exception as e:
            return f"خطأ: {str(e)}"

    def get_quick_form_explanation(self, image: Image.Image, language: str) -> str:
        """
        Get a quick form explanation without field detection (lightweight operation)
        Used in check-image endpoint for faster response
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

            if language == 'rtl':
                prompt = """
أنت مساعد ذكي متخصص في تحليل النماذج. اقرأ النموذج في الصورة وقدم ملخصاً مفيداً وموجزاً باللغة العربية.

يجب أن يشمل الملخص:
- الغرض الرئيسي للنموذج (مثل: طلب منحة، تقديم طلب، إقرار، etc.)
- أي جهات أو مؤسسات مذكورة (مثل: جامعات، شركات، وزارات)
- نوع المعلومات المطلوبة (بيانات شخصية، أكاديمية، مهنية)
- أي شروط أو ملاحظات مهمة

أجب بشكل مباشر ومفيد في 2-4 جمل فقط. لا تستخدم تنسيقات markdown.
"""
            else:
                prompt = """
You are an intelligent form assistant. Read the form in the image and provide a helpful, concise summary in English.

The summary should include:
- The main purpose of the form (e.g., scholarship application, registration, declaration, etc.)
- Any important organizations or entities mentioned
- The type of information required (personal, academic, professional data)
- Any important conditions or notes

Respond directly and helpfully in 2-4 sentences only. Do not use markdown formatting.
"""

            image_part = {"mime_type": "image/png", "data": img_str}
            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    candidate_count=1,
                    max_output_tokens=800
                ),
                stream=False
            )
            
            if not response or not response.text:
                logger.warning("Empty response from Gemini for form explanation")
                return ""
                
            explanation = self.remove_markdown_formatting(response.text.strip())
            logger.info(f"Form explanation generated: {explanation[:100]}...")
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating quick form explanation: {e}")
            return ""

    # =============================================================================
    # PPT & PDF READER METHODS
    # =============================================================================

    def analyze_document_bulk(self, document_data: Dict[str, Any], language: str = "arabic") -> Dict[str, Any]:
        """
        تحليل المستند بالكامل باستخدام Gemini AI
        """
        try:
            if not self.model:
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
            response = self.model.generate_content(prompt)
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
            if not self.model:
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
            
            response = self.model.generate_content([prompt, image_part])
            
            # إزالة تنسيقات Markdown من الرد
            clean_response = self.remove_markdown_formatting(response.text)
            return clean_response
            
        except Exception as e:
            logger.error(f"Error analyzing page image: {e}")
            return "حدث خطأ في تحليل الصورة" if language == "arabic" else "Error occurred while analyzing the image"

    def analyze_page_with_question(self, image_base64: str, question: str, language: str = "arabic") -> str:
        """تحليل صورة الصفحة مع الإجابة على سؤال محدد"""
        try:
            if not self.model:
                return "خدمة تحليل الصور غير متوفرة حالياً" if language == "arabic" else "Image analysis service is currently unavailable"
            
            if language == "arabic":
                prompt = f"""انت مساعد ذكي متخصص في تحليل المحتوى التعليمي والوثائق.
                
سؤال المستخدم: {question}

حلل الصورة واجب على السؤال بشكل مفصل ومفيد باللغة العربية.
- ركز على تفاصيل السؤال المطروح
- اعطي شرح واضح ومفصل
- استخدم المعلومات الموجودة في الصورة
- اجعل الإجابة تفصيلية ومفيدة للمستخدم"""
            else:
                prompt = f"""You are an intelligent assistant specialized in analyzing educational content and documents.

User's question: {question}

Analyze the image and answer the question in detail and helpfully in English.
- Focus on the details of the question asked
- Provide clear and detailed explanation  
- Use the information available in the image
- Make the answer detailed and useful for the user"""
            
            # تحويل base64 إلى image part
            image_part = {
                "mime_type": "image/png",
                "data": image_base64
            }
            
            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    candidate_count=1,
                    max_output_tokens=2000
                )
            )
            
            # إزالة تنسيقات Markdown من الرد
            clean_response = self.remove_markdown_formatting(response.text)
            return clean_response
            
        except Exception as e:
            logger.error(f"Error analyzing page with question: {e}")
            return "حدث خطأ في تحليل الصورة والإجابة على السؤال" if language == "arabic" else "Error occurred while analyzing the image and answering the question"

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
            prompt = f"""
تحليل شامل للعرض التقديمي:

{slides_text}

قم بتحليل العرض التقديمي وأعطني:
1. ملخص عام للمحتوى
2. النقاط الرئيسية
3. الموضوعات المطروحة
4. أي استنتاجات أو توصيات

الرد باللغة العربية:
"""
        else:
            prompt = f"""
Comprehensive Presentation Analysis:

{slides_text}

Analyze this presentation and provide:
1. General summary of content
2. Key points
3. Topics covered
4. Any conclusions or recommendations

Respond in English:
"""

        return prompt

    def _parse_bulk_analysis_response(self, response_text: str, language: str) -> Dict[str, Any]:
        """تحليل استجابة Gemini وتحويلها إلى تنسيق منظم"""
        try:
            # تقسيم النص إلى أقسام
            sections = response_text.split('\n\n')
            
            result = {
                "summary": "",
                "key_points": [],
                "topics": [],
                "conclusions": "",
                "full_analysis": response_text
            }
            
            # استخراج المعلومات من النص
            for section in sections:
                if section.strip():
                    lines = section.strip().split('\n')
                    if len(lines) > 1:
                        result["key_points"].extend([line.strip() for line in lines[1:] if line.strip()])
                    elif len(lines) == 1:
                        if not result["summary"]:
                            result["summary"] = lines[0].strip()
                        else:
                            result["conclusions"] = lines[0].strip()
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing bulk analysis response: {e}")
            return self._create_fallback_analysis_from_text(response_text, language)

    def _create_fallback_analysis(self, document_data: Dict[str, Any], language: str) -> Dict[str, Any]:
        """إنشاء تحليل احتياطي في حالة فشل Gemini"""
        try:
            pages = document_data.get("pages", [])
            total_pages = len(pages)
            # استخراج النصوص
            all_text = []
            for page in pages:
                if page.get("text"):
                    all_text.append(page["text"])
            combined_text = " ".join(all_text)

            if language == "arabic":
                return {
                    "summary": f"هذا مستند يحتوي على {total_pages} صفحة. يتضمن المحتوى معلومات متنوعة.",
                    "key_points": [f"الصفحة {i+1}: {page.get('title', 'بدون عنوان')}" for i, page in enumerate(pages)],
                    "topics": ["محتوى عام", "معلومات متنوعة"],
                    "conclusions": "تم استخراج المحتوى بنجاح.",
                    "full_analysis": combined_text[:1000] + "..." if len(combined_text) > 1000 else combined_text
                }
            else:
                return {
                    "summary": f"This document contains {total_pages} pages with various information.",
                    "key_points": [f"Page {i+1}: {page.get('title', 'No title')}" for i, page in enumerate(pages)],
                    "topics": ["General content", "Various information"],
                    "conclusions": "Content extracted successfully.",
                    "full_analysis": combined_text[:1000] + "..." if len(combined_text) > 1000 else combined_text
                }
        except Exception as e:
            logger.error(f"Error creating fallback analysis: {e}")
            return self._create_fallback_analysis_from_text("", language)

    def _create_fallback_analysis_from_text(self, response_text: str, language: str) -> Dict[str, Any]:
        """إنشاء تحليل احتياطي من النص المعطى"""
        if language == "arabic":
            return {
                "summary": "تم استخراج المحتوى بنجاح.",
                "key_points": ["المحتوى متاح للمراجعة"],
                "topics": ["محتوى عام"],
                "conclusions": "انتهى التحليل.",
                "full_analysis": response_text or "لا يوجد محتوى متاح."
            }
        else:
            return {
                "summary": "Content extracted successfully.",
                "key_points": ["Content available for review"],
                "topics": ["General content"],
                "conclusions": "Analysis completed.",
                "full_analysis": response_text or "No content available."
            }

    def check_image_quality(self, image: Image.Image, language: str = "ar") -> Tuple[bool, str]:
        """
        يتحقق من جودة الصورة باستخدام Gemini
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            if language == "ar":
                prompt = """
تحقق من جودة هذه الصورة للتأكد من أنها مناسبة لتحليل النماذج.

أجب بـ JSON فقط:
{
  "quality_good": true/false,
  "message": "رسالة قصيرة عن جودة الصورة"
}

معايير الجودة:
- جيدة: النص واضح ومقروء، الهيكل مرئي
- سيئة: ضبابية، مظلمة/مضيئة جداً، نص غير مقروء
"""
            else:
                prompt = """
Check the quality of this image to ensure it's suitable for form analysis.

Respond with JSON only:
{
  "quality_good": true/false,
  "message": "Brief message about image quality"
}

Quality criteria:
- Good: Text clearly readable, structure visible
- Bad: Blurry, too dark/bright, unreadable text
"""
            
            image_part = {"mime_type": "image/png", "data": img_str}
            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    max_output_tokens=500
                )
            )
            
            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(response_text)
            
            return result.get("quality_good", True), result.get("message", "تم فحص الصورة" if language == "ar" else "Image checked")
            
        except Exception as e:
            logger.error(f"Error checking image quality: {e}")
            fallback_msg = "خطأ في فحص جودة الصورة" if language == "ar" else "Error checking image quality"
            return True, fallback_msg 

    def check_image_quality_with_language(self, image: Image.Image, language_direction: str) -> Tuple[bool, str]:
        """
        Check image quality with user-specified language direction
        Returns (quality_good, quality_message)
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Set language for response
            if language_direction == 'rtl':
                prompt = """
تحليل جودة الصورة للنموذج العربي:

قيم جودة هذه الصورة لتحليل النماذج واكتب ردك باللغة العربية فقط.

**معايير التقييم:**
- مقبول: مشاكل إضاءة بسيطة، ميلان خفيف، النص مقروء
- يحتاج تحسين: الصورة مقطوعة بشكل كبير، النص مشوش جداً، ميلان شديد، إضاءة سيئة جداً

أرجع JSON فقط:

```json
{
  "quality_good": true أو false,
  "quality_message": "تقييم مختصر ونصائح بالعربية"
}
```

أمثلة للرسائل:
- "الصورة واضحة ومناسبة للتحليل"
- "الصورة مقبولة. نصيحة: حسن الإضاءة قليلاً"
- "الصورة تحتاج تحسين. جرب: إضاءة أفضل وتعديل زاوية التصوير"

لا تكن صارماً جداً على العيوب الصغيرة.
"""
            else:
                prompt = """
Assess image quality for English form analysis:

Evaluate this image for form analysis and respond in English only.

**Assessment Criteria:**
- ACCEPTABLE: Minor lighting issues, slight tilt, readable text
- NEEDS IMPROVEMENT: Significantly cropped, very blurry text, major rotation, very poor lighting

Return JSON only:

```json
{
  "quality_good": true or false,
  "quality_message": "Brief assessment and tips in English"
}
```

Example messages:
- "Image is clear and suitable for analysis"
- "Image is acceptable. Tip: improve lighting slightly"
- "Image needs improvement. Try: better lighting and straighten the form"

Don't be overly strict on minor imperfections.
"""

            image_part = {"mime_type": "image/png", "data": img_str}
            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=1000
                ),
                stream=False
            )
            
            if not response.candidates or response.candidates[0].finish_reason.name != "STOP":
                fallback_msg = "تم فحص الصورة" if language_direction == 'rtl' else "Image checked"
                return True, fallback_msg
                
            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            try:
                parsed_json = json.loads(response_text)
            except json.JSONDecodeError as json_error:
                return True, "Image analysis completed"
            
            quality_good = parsed_json.get("quality_good", True)
            quality_message = parsed_json.get("quality_message", "تم فحص الصورة" if language_direction == 'rtl' else "Image checked")
            
            return quality_good, quality_message
            
        except (json.JSONDecodeError, Exception) as e:
            fallback_msg = "خطأ في فحص جودة الصورة" if language_direction == 'rtl' else "Error checking image quality"
            return True, fallback_msg

    def check_currency_image_quality(self, image: Image.Image) -> Tuple[bool, str]:
        """
        فحص جودة صورة العملة قبل التحليل
        Returns (quality_good, quality_message)
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            prompt = """
فحص جودة صورة العملة:

قيم جودة هذه الصورة لتحليل العملات النقدية واكتب ردك بالعربية.

**معايير التقييم للعملات:**
- مقبول: العملة مرئية وواضحة، يمكن قراءة الأرقام والنصوص، إضاءة مناسبة
- يحتاج تحسين: العملة مشوشة جداً، الأرقام غير مقروءة، إضاءة سيئة، العملة مقطوعة من الصورة

**ركز على:**
- وضوح الأرقام على العملة
- رؤية العملة كاملة في الإطار
- جودة الإضاءة
- حدة الصورة

أرجع JSON فقط:

```json
{
  "quality_good": true أو false,
  "quality_message": "رسالة مختصرة عن جودة الصورة ونصائح للتحسين"
}
```

أمثلة للرسائل:
- "الصورة واضحة ومناسبة لتحليل العملة"
- "الصورة مقبولة. نصيحة: حسن الإضاءة قليلاً"
- "الصورة غير واضحة. أعد التصوير مع إضاءة أفضل وتأكد من وضوح الأرقام"
- "العملة مقطوعة من الصورة. أعد التصوير مع تضمين العملة كاملة"

كن دقيقاً في التقييم لأن تحليل العملة يتطلب وضوحاً عالياً.
"""

            image_part = {"mime_type": "image/png", "data": img_str}
            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    max_output_tokens=1000
                ),
                stream=False
            )
            
            if not response.candidates or response.candidates[0].finish_reason.name != "STOP":
                return True, "تم فحص الصورة"
                
            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            try:
                parsed_json = json.loads(response_text)
                quality_good = parsed_json.get("quality_good", True)
                quality_message = parsed_json.get("quality_message", "تم فحص جودة الصورة")
                return quality_good, quality_message
            except json.JSONDecodeError:
                return True, "تم فحص جودة الصورة"
            
        except Exception as e:
            logger.error(f"Error checking currency image quality: {e}")
            return True, "خطأ في فحص جودة الصورة"