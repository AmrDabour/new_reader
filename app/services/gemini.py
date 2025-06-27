from app.config import get_settings
import google.generativeai as genai
from PIL import Image
import base64
import io
import json

settings = get_settings()
genai.configure(api_key=settings.google_ai_api_key)

class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def get_form_details(self, image: Image.Image, language: str):
        """
        Makes a single call to Gemini to get both the field labels and a general
        explanation of the form.
        """
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

        try:
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
                finish_reason_name = response.candidates[0].finish_reason.name if response.candidates else "NO_CANDIDATES"
                safety_ratings = response.candidates[0].safety_ratings if response.candidates else "N/A"
                print(f"Gemini call did not finish successfully. Reason: {finish_reason_name}")
                print(f"Safety Ratings: {safety_ratings}")
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    print(f"Prompt Feedback: {response.prompt_feedback}")
                return None, None

            response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            parsed_json = json.loads(response_text)
            explanation = parsed_json.get("explanation")
            fields = parsed_json.get("fields")

            if isinstance(fields, list) and explanation:
                return explanation, fields
            return None, None

        except (json.JSONDecodeError, Exception) as e:
            print(f"An error occurred during Gemini form analysis: {e}")
            return None, None 