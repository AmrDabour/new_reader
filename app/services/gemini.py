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
        """Remove Markdown formatting from text"""
        if not text:
            return text

        # إزالة Bold formatting (**text** و __text__)
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)

        # إزالة Headers (# ## ###)
        text = re.sub(r"^#{1,6}\s*(.*)$", r"\1", text, flags=re.MULTILINE)

        # إزالة Links [text](url)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        # إزالة Code blocks ```code```
        text = re.sub(r"```[^`]*```", "", text, flags=re.DOTALL)

        # إزالة Inline code `code`
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # إزالة Strikethrough ~~text~~
        text = re.sub(r"~~(.*?)~~", r"\1", text)

        # إزالة Italic formatting - لكن فقط إذا لم تكن جزءًا من قائمة
        # تجنب النجوم في بداية السطر (قوائم) أو النجوم المتعددة
        text = re.sub(
            r"(?<!^)(?<!\s)\*([^*\n]+?)\*(?!\s*\n)", r"\1", text, flags=re.MULTILINE
        )
        text = re.sub(
            r"(?<!^)(?<!\s)_([^_\n]+?)_(?!\s*\n)", r"\1", text, flags=re.MULTILINE
        )

        # Convert star marks at line beginnings to normal bullet points
        text = re.sub(r"^\s*\*\s+", "• ", text, flags=re.MULTILINE)

        # تنظيف المسافات الزائدة
        text = re.sub(r"\n\s*\n", "\n\n", text)
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
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

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

            # Add safety settings to reduce blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=1000,
                ),
                safety_settings=safety_settings,
                stream=False,
            )

            # Check response and handle errors
            try:
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = (
                        candidate.finish_reason.name
                        if hasattr(candidate.finish_reason, "name")
                        else str(candidate.finish_reason)
                    )

                    # Check if response was blocked
                    if finish_reason in [
                        "SAFETY",
                        "RECITATION",
                        "OTHER",
                    ] or finish_reason in ["1", "2", "3"]:
                        return (
                            "ltr",
                            True,
                            "Unable to analyze image - defaulting to English",
                        )

                    # Check if not STOP (4)
                    if finish_reason not in ["STOP", "4"]:
                        return (
                            "ltr",
                            True,
                            "Analysis incomplete - defaulting to English",
                        )
                else:
                    return "ltr", True, "No response received - defaulting to English"

                # Try to get text safely
                response_text = getattr(response, "text", None)
                if not response_text:
                    return "ltr", True, "Empty response - defaulting to English"

            except Exception:
                return "ltr", True, "Error analyzing image"

            if (
                not response.candidates
                or response.candidates[0].finish_reason.name not in ["STOP"]
                and str(response.candidates[0].finish_reason) not in ["4"]
            ):
                return "ltr", True, "Unable to analyze image quality"

            response_text = (
                response.text.strip().replace("```json", "").replace("```", "").strip()
            )

            try:
                parsed_json = json.loads(response_text)

                language_direction = parsed_json.get("language_direction", "ltr")
                quality_good = parsed_json.get("quality_good", True)
                quality_message = parsed_json.get(
                    "quality_message", "Image quality check completed"
                )

                return language_direction, quality_good, quality_message
            except json.JSONDecodeError:
                return "ltr", True, "Error analyzing image"

        except (json.JSONDecodeError, Exception):
            return "ltr", True, "Error analyzing image"

    def get_form_details(self, image: Image.Image, language: str):
        """
        Makes a single call to Gemini to get both the field labels and a general
        explanation of the form.
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            lang_name = "Arabic" if language == "rtl" else "English"

            # --- Language-Specific Prompts ---
            if language == "rtl":
                prompt = """
أنت مساعد ذكي متخصص في تحليل النماذج، ومصمم خصيصًا لمساعدة مستخدم كفيف. هدفك الأساسي هو تقديم فهم واضح وموجز للنموذج.

1.  **تحليل وتلخيص:** اقرأ النموذج بالكامل لفهم غرضه. بعد ذلك، قم بإنشاء ملخص مفيد (عدة جمل) **باللغة العربية فقط**. يجب أن يحقق الملخص توازنًا بين الإيجاز وتوفير المعلومات الهامة. يجب أن يتضمن الملخص:
    - الغرض الرئيسي للنموذج (مثال: "هذا طلب للحصول على منحة دراسية...").
    - أي جهات أو مؤسسات أو شروط رئيسية مذكورة بالفعل في النص (مثال: "...مقدمة من ITIDA و NTI..."، "...تتضمن شرطًا جزائيًا في حالة الغياب...").
    - الفئات العامة للمعلومات التي سيحتاج المستخدم إلى تقديمها (مثال: "...سيُطلب منك تقديم تفاصيل شخصية ومعلومات الاتصال وبياناتك الأكاديمية.").
    - الهدف هو إعطاء المستخدم إحساسًا جيدًا بسياق النموذج دون قراءة كل كلمة فيه.

2.  **Identify fillable fields:** For each numbered box (1، 2، 3، إلخ) represents a place for user input:
    - ابحث عن التسمية النصية أو الوصف المقابل بالقرب منه.
    - **حدد ما إذا كان المربع صالحًا بناءً على السياق:** قم بتحليل التسمية والنص المحيط لفهم الغرض من الحقل.
        - Field is considered **invalid** إذا كان النص يشير إلى أنه "for official use only"، or example, or just instruction، or if it already contains specific value.
        - Field is considered **صالحًا** إذا كان غرضه هو الحصول على معلومات من المستخدم بوضوح (مثل: "الاسم"، "العنوان"، "التوقيع").
        - **مربعات الاختيار:** تكون مربعات الاختيار **صالحة** دائمًا تقريبًا. اجعلها invalidة فقط إذا لم تكن عنصرًا تفاعليًا بشكل واضح.
    - احتفظ بنص التسمية كما هو مكتوب في النموذج تمامًا، دون ترجمة.

3.  **تنسيق الإخراج:** يجب أن يكون الإخراج كائن JSON واحد فقط، بدون أي نص قبله أو بعده.

    ```json
    {
      "explanation": "ملخصك المفيد والموجز باللغة العربية.",
      "fields": [
        { "id": 1, "label": "نص المربع 1", "valid": true },
        { "id": 2, "label": "نص المربع 2", "valid": false }
      ]
    }
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

            # Add safety settings to reduce blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=9000,
                ),
                safety_settings=safety_settings,
                stream=False,
            )
            # --- Robust handling for missing/invalid response ---
            try:
                # Handle finish_reason and candidate info
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = (
                        candidate.finish_reason.name
                        if hasattr(candidate.finish_reason, "name")
                        else str(candidate.finish_reason)
                    )

                    # Check if response was blocked for safety reasons
                    # finish_reason 1 = SAFETY, 2 = RECITATION, 3 = OTHER
                    if finish_reason in [
                        "SAFETY",
                        "RECITATION",
                        "OTHER",
                    ] or finish_reason in ["1", "2", "3"]:

                        # Handle safety ratings
                        if (
                            hasattr(candidate, "safety_ratings")
                            and candidate.safety_ratings
                        ):
                            for rating in candidate.safety_ratings:
                                pass

                        # Return a more user-friendly error
                        explanation = (
                            "عذراً، لم نتمكن من تحليل النموذج بسبب قيود الأمان. يرجى المحاولة مرة أخرى أو التأكد من وضوح الصورة."
                            if language == "rtl"
                            else "Sorry, we couldn't analyze the form due to safety restrictions. Please try again or ensure the image is clear."
                        )
                        return explanation, []

                    # Check if not STOP (4)
                    if finish_reason not in ["STOP", "4"]:
                        explanation = (
                            "حدث خطأ في التحليل. يرجى المحاولة مرة أخرى."
                            if language == "rtl"
                            else "An error occurred during analysis. Please try again."
                        )
                        return explanation, []
                else:
                    explanation = (
                        "لم نتمكن من تحليل النموذج. يرجى المحاولة مرة أخرى."
                        if language == "rtl"
                        else "Unable to analyze the form. Please try again."
                    )
                    return explanation, []

                # Try to get text safely
                response_text = getattr(response, "text", None)
                if not response_text:
                    explanation = (
                        "لم نتمكن من الحصول على نتيجة التحليل. يرجى المحاولة مرة أخرى."
                        if language == "rtl"
                        else "Could not get analysis result. Please try again."
                    )
                    return explanation, []

                # Clean and parse the response
                response_text = (
                    response_text.strip()
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

                try:
                    parsed_json = json.loads(response_text)
                except Exception:
                    explanation = (
                        "خطأ في تحليل البيانات المستلمة. يرجى المحاولة مرة أخرى."
                        if language == "rtl"
                        else "Error parsing received data. Please try again."
                    )
                    return explanation, []

                explanation = parsed_json.get("explanation")
                fields = parsed_json.get("fields")

                if isinstance(fields, list) and explanation:
                    return explanation, fields

                explanation = (
                    "البيانات المستلمة غير مكتملة. يرجى المحاولة مرة أخرى."
                    if language == "rtl"
                    else "Received data is incomplete. Please try again."
                )
                return explanation, []

            except Exception:
                explanation = (
                    "حدث خطأ تقني. يرجى المحاولة مرة أخرى."
                    if language == "rtl"
                    else "A technical error occurred. Please try again."
                )
                return explanation, []
        except Exception:
            import traceback

            traceback.print_exc()
            explanation = (
                "حدث خطأ تقني غير متوقع. يرجى المحاولة مرة أخرى."
                if language == "rtl"
                else "An unexpected technical error occurred. Please try again."
            )
            return explanation, []

    def get_form_fields_only(self, image: Image.Image, language: str):
        """
        Get only the form fields without explanation (for when we already have explanation from check-image)
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            lang_name = "Arabic" if language == "rtl" else "English"

            # --- Language-Specific Prompts (fields only) ---
            if language == "rtl":
                prompt = """
أنت مساعد ذكي متخصص في تحليل النماذج. هدفك هو Identify fillable fields فقط.

**Identify fillable fields:** For each numbered box (1، 2، 3، إلخ) represents a place for user input:
- ابحث عن التسمية النصية أو الوصف المقابل بالقرب منه.
- **حدد ما إذا كان المربع صالحًا بناءً على السياق:** قم بتحليل التسمية والنص المحيط لفهم الغرض من الحقل.
    - Field is considered **invalid** إذا كان النص يشير إلى أنه "for official use only"، or example, or just instruction، or if it already contains specific value.
    - Field is considered **صالحًا** إذا كان غرضه هو الحصول على معلومات من المستخدم بوضوح (مثل: "الاسم"، "العنوان"، "التوقيع").
    - **مربعات الاختيار:** تكون مربعات الاختيار **صالحة** دائمًا تقريبًا. اجعلها invalidة فقط إذا لم تكن عنصرًا تفاعليًا بشكل واضح.
- احتفظ بنص التسمية كما هو مكتوب في النموذج تمامًا، دون ترجمة.

**تنسيق الإخراج:** يجب أن يكون الإخراج قائمة JSON فقط، بدون أي نص قبله أو بعده.

```json
[
  { "id": 1, "label": "نص المربع 1", "valid": true },
  { "id": 2, "label": "نص المربع 2", "valid": false }
]
```"""
            else:
                prompt = """You are an intelligent form assistant. Your goal is to identify fillable fields only.

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
  { "id": 1, "label": "Text for box 1", "valid": true },
  { "id": 2, "label": "Text for box 2", "valid": false }
]
```"""

            image_part = {"mime_type": "image/png", "data": img_str}

            # Add safety settings to reduce blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=9000,
                ),
                safety_settings=safety_settings,
                stream=False,
            )
            try:
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = (
                        candidate.finish_reason.name
                        if hasattr(candidate.finish_reason, "name")
                        else str(candidate.finish_reason)
                    )

                    # Check if response was blocked for safety reasons
                    # finish_reason 1 = SAFETY, 2 = RECITATION, 3 = OTHER
                    if finish_reason in [
                        "SAFETY",
                        "RECITATION",
                        "OTHER",
                    ] or finish_reason in ["1", "2", "3"]:

                        # Handle safety ratings
                        if (
                            hasattr(candidate, "safety_ratings")
                            and candidate.safety_ratings
                        ):
                            for rating in candidate.safety_ratings:
                                pass

                        return []

                    # Check if not STOP (4)
                    if finish_reason not in ["STOP", "4"]:
                        return []
                else:
                    return []

                # Try to get text safely
                response_text = getattr(response, "text", None)
                if not response_text:
                    return []

                # Clean and parse the response
                response_text = (
                    response_text.strip()
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

                try:
                    fields = json.loads(response_text)
                except Exception:
                    return []

                if isinstance(fields, list):
                    return fields

                return []

            except Exception:
                return []
        except Exception:
            import traceback

            traceback.print_exc()
            return []

    def get_quick_form_explanation(self, image: Image.Image, language: str) -> str:
        """
        Get a quick form explanation without field detection (lightweight operation)
        Used in check-image endpoint for faster response
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            if language == "rtl":
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

            # Add safety settings to reduce blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0.2, candidate_count=1, max_output_tokens=9000
                ),
                safety_settings=safety_settings,
                stream=False,
            )

            # Check response and handle errors
            try:
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = (
                        candidate.finish_reason.name
                        if hasattr(candidate.finish_reason, "name")
                        else str(candidate.finish_reason)
                    )

                    # Check if response was blocked
                    if finish_reason in [
                        "SAFETY",
                        "RECITATION",
                        "OTHER",
                    ] or finish_reason in ["1", "2", "3"]:
                        fallback_msg = (
                            "عذراً، لم نتمكن من تحليل النموذج بسبب قيود النظام."
                            if language == "rtl"
                            else "Sorry, unable to analyze the form due to system restrictions."
                        )
                        return fallback_msg

                    # Check if not STOP (4) or MAX_TOKENS (3)
                    if finish_reason not in ["STOP", "4", "MAX_TOKENS", "3"]:
                        fallback_msg = (
                            "فشل في تحليل النموذج."
                            if language == "rtl"
                            else "Failed to analyze the form."
                        )
                        return fallback_msg
                else:
                    fallback_msg = (
                        "لم نتمكن من تحليل النموذج."
                        if language == "rtl"
                        else "Unable to analyze the form."
                    )
                    return fallback_msg

                # Try to get text safely
                response_text = getattr(response, "text", None)
                if not response_text:
                    fallback_msg = (
                        "لم نتمكن من الحصول على نتيجة التحليل."
                        if language == "rtl"
                        else "Could not get analysis result."
                    )
                    return fallback_msg

                explanation = self.remove_markdown_formatting(response_text.strip())
                logger.info(f"Form explanation generated: {explanation[:100]}...")
                return explanation

            except Exception:
                fallback_msg = (
                    "خطأ في الحصول على النتيجة."
                    if language == "rtl"
                    else "Error getting result."
                )
                return fallback_msg

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

    def analyze_document_bulk(
        self, document_data: Dict[str, Any], language: str = "arabic"
    ) -> Dict[str, Any]:
        """
        Analyze complete document using Gemini AI
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

            # Add safety settings to reduce blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            # Get AI analysis
            response = self.model.generate_content(
                prompt, safety_settings=safety_settings
            )

            # Check response and handle errors
            try:
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = (
                        candidate.finish_reason.name
                        if hasattr(candidate.finish_reason, "name")
                        else str(candidate.finish_reason)
                    )

                    # Check if response was blocked
                    if finish_reason in [
                        "SAFETY",
                        "RECITATION",
                        "OTHER",
                    ] or finish_reason in ["1", "2", "3"]:
                        return self._create_fallback_analysis(document_data, language)

                    # Check if not STOP (4)
                    if finish_reason not in ["STOP", "4"]:
                        return self._create_fallback_analysis(document_data, language)
                else:
                    return self._create_fallback_analysis(document_data, language)

                # Try to get text safely
                response_text = getattr(response, "text", None)
                if not response_text:
                    return self._create_fallback_analysis(document_data, language)

                analysis_result = self._parse_bulk_analysis_response(
                    response_text, language
                )
                return analysis_result

            except Exception:
                return self._create_fallback_analysis(document_data, language)

        except Exception as e:
            logger.error(f"Error in bulk analysis: {e}")
            return self._create_fallback_analysis(document_data, language)

    def extract_page_number_from_command(
        self, command: str, current_page: int, total_pages: int
    ) -> Optional[int]:
        """استخراج رقم الصفحة من الأمر الصوتي أو النصي"""
        try:
            # تنظيف الأمر
            command = command.strip().lower()

            # Search for numbers in command
            page_number = self._simple_page_extraction(
                command, current_page, total_pages
            )

            if page_number is not None:
                return page_number

            return None

        except Exception as e:
            logger.error(f"Error extracting page number: {e}")
            return None

    def _simple_page_extraction(
        self, command: str, current_page: int, total_pages: int
    ) -> Optional[int]:
        """استخراج بسيط لرقم الصفحة"""

        # قاموس الأرقام العربية
        arabic_numbers = {
            "واحد": 1,
            "اثنين": 2,
            "ثلاثة": 3,
            "أربعة": 4,
            "خمسة": 5,
            "ستة": 6,
            "سبعة": 7,
            "ثمانية": 8,
            "تسعة": 9,
            "عشرة": 10,
            "أول": 1,
            "ثاني": 2,
            "ثالث": 3,
            "رابع": 4,
            "خامس": 5,
            "الأول": 1,
            "الثاني": 2,
            "الثالث": 3,
            "الرابع": 4,
            "الخامس": 5,
        }

        # أوامر خاصة
        if any(word in command for word in ["التالي", "التالية", "next"]):
            return min(current_page + 1, total_pages)
        elif any(word in command for word in ["السابق", "السابقة", "previous", "prev"]):
            # Ensure result stays within 1..total_pages even if current_page is out of range
            return max(min(current_page - 1, total_pages), 1)
        elif any(word in command for word in ["الأول", "البداية", "first", "start"]):
            return 1
        elif any(word in command for word in ["الأخير", "النهاية", "last", "end"]):
            return total_pages

        # البحث عن الأرقام
        numbers = re.findall(r"\d+", command)
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

    def analyze_page_image(
        self, image_base64: str, language: str = "arabic", page_text: str = ""
    ) -> str:
        """تحليل صورة الصفحة باستخدام الذكاء الاصطناعي مع السياق النصي"""
        try:
            if not self.model:
                return (
                    "خدمة تحليل الصور غير متوفرة حالياً"
                    if language == "arabic"
                    else "Image analysis service is currently unavailable"
                )

            if language == "arabic":
                if page_text and page_text.strip():
                    prompt = f"""لديك النص التالي المستخرج من هذه الصفحة:
"{page_text}"

الآن حلل الصورة في سياق هذا النص واشرح المحتوى المرئي مباشرة باللغة العربية:
- اربط العناصر المرئية (مخططات، صور، رسوم بيانية) بالمحتوى النصي
- اشرح كيف تدعم الصورة أو توضح النقاط المذكورة في النص
- إذا كانت الصورة بسيطة: 3-4 جمل تكفي
- إذا كانت معقدة: حتى 8 جمل مع التفاصيل المهمة
- ركز على الربط بين النص والعناصر المرئية
- ابدأ الرد مباشرة بالتحليل بدون مقدمات"""
                else:
                    prompt = """اشرح محتوى هذه الصورة مباشرة باللغة العربية بدون مقدمات.
- إذا كانت الصورة بسيطة: 3 جمل تكفي
- إذا كانت معقدة ومليئة بالتفاصيل: حتى 8 جمل
- ركز على المحتوى الأساسي والعناصر المهمة
- اذكر أي تفاصيل تقنية أو تعليمية أو مخططات أو مفاهيم مهمة
- ابدأ الرد مباشرة بالمحتوى، لا تقل "سأقوم بتحليل" أو "بالتأكيد" أو أي مقدمات"""
            else:
                if page_text and page_text.strip():
                    prompt = f"""Here is the extracted text from this page:
"{page_text}"

Now analyze the image in the context of this text and explain the visual content directly in English:
- Connect visual elements (charts, images, diagrams) with the textual content
- Explain how the image supports or illustrates the points mentioned in the text
- If the image is simple: 3-4 sentences are enough
- If it's complex: up to 8 sentences with important details
- Focus on linking the text with visual elements
- Start the response directly with the analysis without introductions"""
                else:
                    prompt = """Explain the content of this image directly in English without introductions.
- If the image is simple: 3 sentences are enough
- If it's complex with many details: up to 8 sentences
- Focus on the main content and important elements
- Mention any technical, educational details, graphs or important concepts
- Start the response directly with the content, don't say "I will analyze" or "Certainly" or any introductions"""

            # تحويل base64 إلى image part
            image_part = {"mime_type": "image/png", "data": image_base64}

            # Add safety settings to reduce blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, image_part], safety_settings=safety_settings
            )

            # Check response and handle errors
            try:
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = (
                        candidate.finish_reason.name
                        if hasattr(candidate.finish_reason, "name")
                        else str(candidate.finish_reason)
                    )

                    # Check if response was blocked
                    if finish_reason in [
                        "SAFETY",
                        "RECITATION",
                        "OTHER",
                    ] or finish_reason in ["1", "2", "3"]:
                        fallback_msg = (
                            "عذراً، لم نتمكن من تحليل الصورة بسبب قيود النظام."
                            if language == "arabic"
                            else "Sorry, unable to analyze the image due to system restrictions."
                        )
                        return fallback_msg

                    # Check if not STOP (4)
                    if finish_reason not in ["STOP", "4"]:
                        fallback_msg = (
                            "فشل في تحليل الصورة."
                            if language == "arabic"
                            else "Failed to analyze the image."
                        )
                        return fallback_msg
                else:
                    fallback_msg = (
                        "لم نتمكن من تحليل الصورة."
                        if language == "arabic"
                        else "Unable to analyze the image."
                    )
                    return fallback_msg

                # Try to get text safely
                response_text = getattr(response, "text", None)
                if not response_text:
                    fallback_msg = (
                        "لم نتمكن من الحصول على نتيجة التحليل."
                        if language == "arabic"
                        else "Could not get analysis result."
                    )
                    return fallback_msg

                # إزالة تنسيقات Markdown من الرد
                clean_response = self.remove_markdown_formatting(response_text)
                return clean_response

            except Exception:
                fallback_msg = (
                    "خطأ في الحصول على النتيجة."
                    if language == "arabic"
                    else "Error getting result."
                )
                return fallback_msg

        except Exception as e:
            logger.error(f"Error analyzing page image: {e}")
            return (
                "حدث خطأ في تحليل الصورة"
                if language == "arabic"
                else "Error occurred while analyzing the image"
            )

    def has_actual_image_content(self, image_base64: str) -> bool:
        """
        Public method to check if the base64 string contains actual image content
        """
        return self._has_actual_image_content(image_base64)

    def _has_actual_image_content(self, image_base64: str) -> bool:
        """
        Check if the base64 string contains actual image content (not just text rendered as image)
        Returns False for empty, placeholder, text-only slides, or invalid image data
        """
        if not image_base64 or len(image_base64.strip()) == 0:
            return False

        try:
            # Decode base64 to check if it's valid image data
            import base64
            from PIL import Image
            import io

            # Try to decode base64
            image_data = base64.b64decode(image_base64)

            # Check if decoded data is too small (likely not a real image)
            if len(image_data) < 1000:  # Less than 1KB is likely not a meaningful image
                return False

            # Try to open as image to validate it's actual image content
            with Image.open(io.BytesIO(image_data)) as img:
                # Check image dimensions - very small images might be placeholders
                width, height = img.size
                if width < 50 or height < 50:
                    return False

                # Convert to RGB for analysis
                rgb_img = img.convert("RGB")

                # Try advanced analysis with numpy if available
                try:
                    import numpy as np

                    # Convert to numpy array for color analysis
                    img_array = np.array(rgb_img)

                    # Check if image is mostly white/blank (text-only slides often have white backgrounds)
                    # Calculate average color
                    avg_color = np.mean(img_array, axis=(0, 1))

                    # If average color is very close to white (240+ on all channels), likely text-only
                    if all(channel > 240 for channel in avg_color):
                        # Additional check: calculate color variance
                        color_variance = np.var(img_array, axis=(0, 1))
                        avg_variance = np.mean(color_variance)

                        # If variance is very low, it's mostly uniform color (likely text on white)
                        if (
                            avg_variance < 100
                        ):  # Low variance suggests uniform background
                            return False

                    # Check for color diversity - real images typically have more color variation
                    unique_colors = len(
                        np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0)
                    )
                    total_pixels = width * height
                    color_ratio = unique_colors / total_pixels

                    # If color ratio is very low, might be simple text/graphics
                    if (
                        color_ratio < 0.01
                    ):  # Less than 1% unique colors suggests simple content
                        return False

                    # Check if image is mostly transparent (for RGBA images)
                    if img.mode in ("RGBA", "LA"):
                        alpha_channel = img.split()[-1]
                        alpha_data = np.array(alpha_channel)
                        non_transparent_pixels = np.sum(alpha_data > 10)
                        if non_transparent_pixels < (
                            width * height * 0.05
                        ):  # Less than 5% visible content
                            return False

                    # Additional check: detect if image contains complex visual elements
                    # Convert to grayscale for edge detection
                    gray_img = rgb_img.convert("L")
                    gray_array = np.array(gray_img)

                    # Simple edge detection - real images usually have more edges
                    edges = (
                        np.abs(np.diff(gray_array, axis=0)).sum()
                        + np.abs(np.diff(gray_array, axis=1)).sum()
                    )
                    edge_density = edges / (width * height)

                    # If edge density is very low, likely simple text/shapes
                    if edge_density < 5:  # Threshold for edge complexity
                        return False

                except ImportError:
                    # Fallback analysis without numpy - use simpler PIL-based checks
                    logger.info("NumPy not available, using simpler image analysis")

                    # Sample pixels from different areas to check for diversity
                    sample_size = min(width, height, 100)  # Sample up to 100x100 area
                    step_x = max(1, width // sample_size)
                    step_y = max(1, height // sample_size)

                    colors = []
                    for x in range(0, width, step_x):
                        for y in range(0, height, step_y):
                            if x < width and y < height:
                                colors.append(rgb_img.getpixel((x, y)))

                    # Check color diversity
                    unique_colors = len(set(colors))
                    if unique_colors < len(colors) * 0.1:  # Less than 10% unique colors
                        return False

                    # Check if mostly white background
                    white_pixels = sum(
                        1 for r, g, b in colors if r > 240 and g > 240 and b > 240
                    )
                    if (
                        white_pixels > len(colors) * 0.8
                    ):  # More than 80% white-ish pixels
                        return False

                # Image passes all checks - likely contains actual visual content
                return True

        except Exception as e:
            logger.warning(f"Error validating image content: {str(e)}")
            return False

    def analyze_all_page_images(
        self, document_data: Dict[str, Any], language: str = "arabic"
    ) -> Dict[str, Any]:
        """تحليل جميع صور الصفحات وحفظ النتائج في ملف JSON"""
        try:
            if not self.model:
                return {"error": "Image analysis service is currently unavailable"}

            image_analyses = []
            total_pages = len(document_data.get("pages", []))

            for page_index, page_data in enumerate(document_data.get("pages", [])):
                page_number = page_index + 1
                image_base64 = page_data.get("image_base64", "")

                # Check if there's actual image content before running analysis
                if image_base64 and self._has_actual_image_content(image_base64):
                    try:
                        # Get page text for context
                        page_text = page_data.get("text", "")
                        # Analyze each page image only if it contains real content
                        image_analysis = self.analyze_page_image(
                            image_base64, language, page_text
                        )
                    except Exception as e:
                        logger.error(
                            f"Error analyzing image for page {page_number}: {str(e)}"
                        )
                        image_analysis = (
                            f"فشل في تحليل صورة الصفحة {page_number}"
                            if language == "arabic"
                            else f"Failed to analyze image for page {page_number}"
                        )
                else:
                    # No actual image content available - return empty string
                    image_analysis = ""
                    logger.info(
                        f"Page {page_number}: No actual image content detected, skipping analysis"
                    )

                page_analysis = {
                    "page_number": page_number,
                    "title": page_data.get("title", f"Page {page_number}"),
                    "original_text": page_data.get("text", ""),
                    "image_analysis": image_analysis,
                    "processed_at": None,  # Will be set when saving to file
                }

                image_analyses.append(page_analysis)

                # Log progress
                logger.info(f"Analyzed image for page {page_number}/{total_pages}")

            return {
                "total_pages": total_pages,
                "language": language,
                "image_analyses": image_analyses,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Error in bulk image analysis: {e}")
            return {
                "error": f"Error occurred during bulk image analysis: {str(e)}",
                "status": "failed",
            }

    # NOTE: The per-page question analysis endpoint was removed; corresponding method
    # analyze_page_with_question has been deleted to keep the service minimal.

    # =============================================================================
    # HELPER METHODS FOR PPT & PDF READER
    # =============================================================================

    def _create_bulk_analysis_prompt(
        self, slides_data: List[Dict], language: str
    ) -> str:
        """إنشاء prompt شامل لتحليل جميع الشرائح مع تفاصيل كل شريحة"""

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
أنت محلل محتوى متخصص وخبير في تحليل العروض التقديمية والمستندات التعليمية. هدفك هو تقديم تحليل دقيق ومفصل ومفيد لكل شريحة.

محتوى العرض التقديمي:
{slides_text}

قم بتحليل العرض التقديمي وأعطني النتائج بتنسيق JSON التالي بدقة:

{{
  "presentation_summary": "ملخص شامل ومفصل للعرض التقديمي بأكمله (3-5 جمل)",
  "slides_analysis": [
    {{
      "slide_number": رقم_الشريحة,
      "title": "عنوان الشريحة",
      "original_text": "النص الأصلي كما هو",
      "explanation": "شرح مفصل ومعمق للمحتوى، أهميته، السياق، والمفاهيم الرئيسية (4-6 جمل على الأقل)"
    }}
  ]
}}

**متطلبات مهمة:**
1. في حقل "explanation"، قدم تحليلاً شاملاً وواثقاً يشمل:
   - شرح واضح ومؤكد للمفاهيم والأفكار الموجودة
   - السياق والأهمية بثقة
   - العلاقة مع باقي المحتوى
   - أي تفاصيل تقنية أو علمية
   - كيفية فهم وتطبيق هذا المحتوى

2. استخدم لغة واثقة ومؤكدة - تجنب الكلمات المترددة مثل "قد يكون" أو "ربما" أو "محتمل"
3. قدم تفسيرات قاطعة ومباشرة بدلاً من التحذيرات أو التنبيهات
4. تجاهل تماماً أي إشارات في النص الأصلي حول "المحتوى المولد بالذكاء الاصطناعي" أو "قد يكون غير صحيح" - لا تذكرها أبداً في التفسير
5. ركز على المحتوى الفعلي والمفاهيم دون الإشارة إلى مصدر المعلومات أو طريقة توليدها
6. اجعل كل تفسير غنياً بالمعلومات ومفيداً للمتعلم
7. استخدم لغة واضحة ومناسبة للمستوى التعليمي
8. تأكد من أن التحليل دقيق ومبني على المحتوى الفعلي

أجب بـ JSON صحيح فقط، بدون أي نص إضافي أو تحذيرات قبله أو بعده.
"""
        else:
            prompt = f"""
You are an expert content analyst specialized in analyzing presentations and educational documents. Your goal is to provide accurate, detailed and helpful analysis for each slide.

Presentation Content:
{slides_text}

Analyze this presentation and provide results in the following JSON format exactly:

{{
  "presentation_summary": "Comprehensive and detailed summary of the entire presentation (3-5 sentences)",
  "slides_analysis": [
    {{
      "slide_number": slide_number,
      "title": "Slide Title",
      "original_text": "Original text as is",
      "explanation": "Detailed and in-depth explanation of content, its importance, context, and key concepts (at least 4-6 sentences)"
    }}
  ]
}}

**Important Requirements:**
1. In the "explanation" field, provide comprehensive and confident analysis including:
   - Clear and definitive explanation of concepts and ideas present
   - Context and importance with confidence
   - Relationship with other content
   - Any technical or scientific details
   - How this content can be understood or applied

2. Use confident and definitive language - avoid uncertain words like "may be", "might", "possibly", "could be"
3. Provide direct and assertive explanations instead of warnings or disclaimers
4. Completely ignore any references in the original text about "AI-generated content" or "may be incorrect" - never mention them in the explanation
5. Focus on the actual content and concepts without referencing the source or generation method of the information
6. Make each explanation rich with information and helpful for learners
7. Use clear language appropriate for the educational level
8. Ensure analysis is accurate and based on actual content

Respond with valid JSON only, without any additional text, warnings, or disclaimers before or after it.
"""

        return prompt

    def _parse_bulk_analysis_response(
        self, response_text: str, language: str
    ) -> Dict[str, Any]:
        """تحليل استجابة Gemini وتحويلها إلى تنسيق منظم"""
        try:
            # تنظيف النص من أي تنسيقات Markdown
            clean_text = (
                response_text.strip().replace("```json", "").replace("```", "").strip()
            )

            # محاولة تحليل JSON مباشرة
            try:
                parsed_json = json.loads(clean_text)

                # التحقق من وجود البنية المطلوبة
                if (
                    "presentation_summary" in parsed_json
                    and "slides_analysis" in parsed_json
                ):
                    return parsed_json

            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response, trying fallback parsing")

            # إذا فشل التحليل المباشر، استخدم التحليل التقليدي
            sections = response_text.split("\n\n")

            result = {"presentation_summary": "", "slides_analysis": []}

            # استخراج المعلومات من النص بشكل تقليدي
            current_summary = ""
            for section in sections:
                if section.strip():
                    # إذا كان القسم يحتوي على ملخص
                    if (
                        not result["presentation_summary"]
                        and len(section.split("\n")) <= 3
                    ):
                        result["presentation_summary"] = section.strip()
                    else:
                        current_summary += section + " "

            if not result["presentation_summary"]:
                result["presentation_summary"] = (
                    current_summary[:500] + "..."
                    if len(current_summary) > 500
                    else current_summary
                )

            # إنشاء تحليل الشرائح كـ fallback
            result["slides_analysis"] = []

            return result

        except Exception as e:
            logger.error(f"Error parsing bulk analysis response: {e}")
            return self._create_fallback_analysis_from_text(response_text, language)

    def _create_fallback_analysis(
        self, document_data: Dict[str, Any], language: str
    ) -> Dict[str, Any]:
        """إنشاء تحليل احتياطي في حالة فشل Gemini"""
        try:
            pages = document_data.get("pages", [])
            total_pages = len(pages)

            # إنشاء تحليل شرائح مفصل
            slides_analysis = []
            for i, page in enumerate(pages):
                page_text = page.get("text", "").strip()
                page_title = page.get(
                    "title",
                    f"Slide {i+1}" if language == "english" else f"الشريحة {i+1}",
                )

                # إنشاء تفسير مفصل بناءً على المحتوى المتاح
                if page_text:
                    if language == "arabic":
                        explanation = f"تحتوي هذه الشريحة على معلومات أساسية حول {page_title}. المحتوى يتضمن تفاصيل ومفاهيم مهمة تساعد في فهم الموضوع بعمق. النقاط المطروحة مترابطة ومفيدة للتعلم والاستيعاب. هذا المحتوى يشكل جزءاً أساسياً من العرض التقديمي ويساهم في بناء فهم شامل للموضوع الرئيسي."
                    else:
                        explanation = f"This slide contains essential information about {page_title}. The content includes important details and fundamental concepts that help deepen understanding of the topic. The points presented are interconnected and valuable for learning and comprehension. This content forms an essential part of the presentation and contributes to building comprehensive understanding of the main subject."
                else:
                    if language == "arabic":
                        explanation = "هذه الشريحة تحتوي على محتوى مرئي وعناصر تفاعلية مهمة. العناصر المرئية تساعد في توضيح المفاهيم وتعزيز الفهم. المحتوى المقدم يدعم أهداف التعلم ويوفر سياقاً بصرياً للمعلومات. هذه الشريحة تلعب دوراً مكملاً في العرض التقديمي وتساهم في تقديم تجربة تعليمية شاملة."
                    else:
                        explanation = "This slide contains important visual content and interactive elements. The visual elements help clarify concepts and enhance understanding. The content presented supports learning objectives and provides visual context for information. This slide plays a complementary role in the presentation and contributes to delivering a comprehensive educational experience."

                slide_analysis = {
                    "slide_number": i + 1,
                    "title": page_title,
                    "original_text": page_text,
                    "explanation": explanation,
                }
                slides_analysis.append(slide_analysis)

            if language == "arabic":
                presentation_summary = f"هذا العرض التقديمي يحتوي على {total_pages} شريحة تغطي موضوعاً شاملاً ومهماً. المحتوى منظم بطريقة تدريجية تساعد على الفهم والاستيعاب. كل شريحة تحتوي على معلومات قيمة ومترابطة مع باقي المحتوى. العرض يقدم معرفة شاملة وتطبيقية حول الموضوع المطروح."
            else:
                presentation_summary = f"This presentation contains {total_pages} slides covering a comprehensive and important topic. The content is organized in a progressive manner that aids understanding and comprehension. Each slide contains valuable information interconnected with the rest of the content. The presentation provides comprehensive and practical knowledge about the presented topic."

            return {
                "presentation_summary": presentation_summary,
                "slides_analysis": slides_analysis,
            }

        except Exception as e:
            logger.error(f"Error creating fallback analysis: {e}")
            return self._create_fallback_analysis_from_text("", language)

    def _create_fallback_analysis_from_text(
        self, response_text: str, language: str
    ) -> Dict[str, Any]:
        """إنشاء تحليل احتياطي من النص المعطى"""
        if language == "arabic":
            return {
                "presentation_summary": "تم استخراج المحتوى بنجاح ويحتوي على معلومات مفيدة ومتنوعة.",
                "slides_analysis": [
                    {
                        "slide_number": 1,
                        "title": "محتوى العرض",
                        "original_text": response_text or "لا يوجد محتوى متاح.",
                        "explanation": "تحتوي هذه الشريحة على معلومات أساسية ومهمة للموضوع المطروح. المحتوى يساعد في فهم السياق العام ويوفر أساساً للمعرفة المطلوبة.",
                    }
                ],
            }
        else:
            return {
                "presentation_summary": "Content extracted successfully and contains useful and diverse information.",
                "slides_analysis": [
                    {
                        "slide_number": 1,
                        "title": "Presentation Content",
                        "original_text": response_text or "No content available.",
                        "explanation": "This slide contains essential and important information for the presented topic. The content helps understand the general context and provides a foundation for the required knowledge.",
                    }
                ],
            }

    def check_image_quality(
        self, image: Image.Image, language: str = "ar"
    ) -> Tuple[bool, str]:
        """
        يتحقق من جودة الصورة باستخدام Gemini
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

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
                    temperature=0, candidate_count=1, max_output_tokens=500
                ),
            )

            response_text = (
                response.text.strip().replace("```json", "").replace("```", "").strip()
            )
            result = json.loads(response_text)

            return result.get("quality_good", True), result.get(
                "message", "تم فحص الصورة" if language == "ar" else "Image checked"
            )

        except Exception as e:
            logger.error(f"Error checking image quality: {e}")
            fallback_msg = (
                "خطأ في فحص جودة الصورة"
                if language == "ar"
                else "Error checking image quality"
            )
            return True, fallback_msg

    def check_image_quality_with_language(
        self, image: Image.Image, language_direction: str
    ) -> Tuple[bool, str]:
        """
        Check image quality with user-specified language direction
        Returns (quality_good, quality_message)
        """
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Set language for response
            if language_direction == "rtl":
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

            # Add safety settings to reduce blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    candidate_count=1,
                    top_k=1,
                    top_p=0.1,
                    max_output_tokens=1000,
                ),
                safety_settings=safety_settings,
                stream=False,
            )

            # Check response and handle errors
            try:
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = (
                        candidate.finish_reason.name
                        if hasattr(candidate.finish_reason, "name")
                        else str(candidate.finish_reason)
                    )

                    # Check if response was blocked
                    if finish_reason in [
                        "SAFETY",
                        "RECITATION",
                        "OTHER",
                    ] or finish_reason in ["1", "2", "3"]:
                        fallback_msg = (
                            "تم فحص الصورة - قد تحتاج لتحسين الجودة"
                            if language_direction == "rtl"
                            else "Image checked - may need quality improvement"
                        )
                        return True, fallback_msg

                    # Check if not STOP (4)
                    if finish_reason not in ["STOP", "4"]:
                        fallback_msg = (
                            "تم فحص الصورة"
                            if language_direction == "rtl"
                            else "Image checked"
                        )
                        return True, fallback_msg
                else:
                    fallback_msg = (
                        "تم فحص الصورة"
                        if language_direction == "rtl"
                        else "Image checked"
                    )
                    return True, fallback_msg

                # Try to get text safely
                response_text = getattr(response, "text", None)
                if not response_text:
                    fallback_msg = (
                        "تم فحص الصورة"
                        if language_direction == "rtl"
                        else "Image checked"
                    )
                    return True, fallback_msg

            except Exception:
                fallback_msg = (
                    "تم فحص الصورة" if language_direction == "rtl" else "Image checked"
                )
                return True, fallback_msg

            if (
                not response.candidates
                or response.candidates[0].finish_reason.name not in ["STOP"]
                and str(response.candidates[0].finish_reason) not in ["4"]
            ):
                fallback_msg = (
                    "تم فحص الصورة" if language_direction == "rtl" else "Image checked"
                )
                return True, fallback_msg

            response_text = (
                response.text.strip().replace("```json", "").replace("```", "").strip()
            )

            try:
                parsed_json = json.loads(response_text)
            except json.JSONDecodeError:
                return True, "Image analysis completed"

            quality_good = parsed_json.get("quality_good", True)
            quality_message = parsed_json.get(
                "quality_message",
                "تم فحص الصورة" if language_direction == "rtl" else "Image checked",
            )

            return quality_good, quality_message

        except (json.JSONDecodeError, Exception):
            fallback_msg = (
                "خطأ في فحص جودة الصورة"
                if language_direction == "rtl"
                else "Error checking image quality"
            )
            return True, fallback_msg
