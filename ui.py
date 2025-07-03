import streamlit as st
import requests
import base64
from PIL import Image
import io
import os
import json
from audiorecorder import audiorecorder

# --- Configuration ---
# On Render, this will be the internal URL of the backend service.
# Locally, you need to run the backend on http://127.0.0.1:8000.
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# --- Prompts & Language Handling ---
PROMPTS = {
    'greeting': {
        'rtl': "أهلاً بك! سأساعدك في ملء هذا النموذج. لنبدأ بالبيان الأول",
        'ltr': "Hello! I will help you fill out this form. Let's start with the first field"
    },
    'checkbox_prompt': {
        'rtl': "هل تريد تحديد خانة '{label}'؟ قل نعم أو لا",
        'ltr': "Do you want to check the box for '{label}'? Say yes or no"
    },
    'text_prompt': {
        'rtl': "أدخل البيانات الخاصة بـ '{label}'",
        'ltr': "Provide the information for '{label}'" # "Please" removed
    },
    'heard_you_say': {
        'rtl': "سمعتك تقول '{transcript}'",
        'ltr': "I heard you say '{transcript}'"
    },
    'stt_error': {
        'rtl': "لم أتمكن من فهم الصوت. من فضلك حاول مرة أخرى",
        'ltr': "I couldn't understand the audio. Please try again"
    },
    'post_filling': {
        'rtl': "اكتمل النموذج. اضغط على 'مراجعة النموذج' للمعاينة والتحميل.",
        'ltr': "Form complete. Click 'Review Form' to preview and download."
    },
    'command_error': {
        'rtl': "لم أفهم طلبك. من فضلك قل 'مراجعة'، 'تنزيل صورة'، أو 'تنزيل PDF'",
        'ltr': "I didn't understand your request. Please say 'review', 'download image', or 'download PDF'"
    },
    'review_prompt': {
        'rtl': "اكتمل النموذج. يمكنك الآن تحميله كملف صورة (PNG) أو كملف (PDF).",
        'ltr': "The form is complete. You can now download it as a PNG image or a PDF file."
    },
    'session_done': {
        'rtl': "انتهت الجلسة. يمكنك تنزيل الملف أو البدء من جديد",
        'ltr': "The session has ended. You can download the file or start over"
    },
    'start_again_button': {
        'rtl': "البدء من جديد بنفس الصورة",
        'ltr': "Start again with the same image"
    },
    'no_fields_found': {
        'rtl': "قام بتحليل الصورة ولم يجد أي حقول صالحة للتعبئة",
        'ltr': "Analyzed the image and found no valid fields to fill"
    },
    'download_png': {
        'rtl': "تنزيل كـ PNG",
        'ltr': "Download as PNG"
    },
    'download_pdf': {
        'rtl': "تنزيل كـ PDF",
        'ltr': "Download as PDF"
    },
    'speak_button_label': {
        'rtl': "اضغط للتحدث",
        'ltr': "Click to Speak"
    },
    'recording_button_label': {
        'rtl': "جاري التسجيل... اضغط مرة أخرى للإيقاف",
        'ltr': "Recording... Click again to STOP"
    },
    'stt_spinner': { 'rtl': "جاري تحويل الصوت إلى نص...", 'ltr': "Transcribing audio..." },
    'command_spinner': { 'rtl': "جاري تحليل طلبك...", 'ltr': "Analyzing your command..." },
    'confirmation_prompt_no_voice': { 'rtl': "هل هذا صحيح؟", 'ltr': "Is this correct?" },
    'confirm_button': { 'rtl': "تأكيد", 'ltr': "Confirm" },
    'retry_button': { 'rtl': "إعادة المحاولة", 'ltr': "Retry" },
    'continue_button': { 'rtl': "متابعة", 'ltr': "Continue" },
    'or_type_prompt': { 'rtl': "أو، أدخل إجابتك في الأسفل:", 'ltr': "Or, type your answer below:" },
    'save_and_next_button': { 'rtl': "حفظ والمتابعة", 'ltr': "Save and Continue" },
    'skip_button': { 'rtl': "تخطي هذا الحقل", 'ltr': "Skip this field" },
    'toggle_voice_label': { 'rtl': "تفعيل المساعد الصوتي", 'ltr': "Enable Voice Assistant" },
    'checkbox_checked': { 'rtl': "تحديد الخانة", 'ltr': "Checked" },
    'checkbox_unchecked': { 'rtl': "عدم تحديد الخانة", 'ltr': "Unchecked" },
    'retry_prompt': { 'rtl': "تمام، لنجرب مرة أخرى", 'ltr': "Okay, let's try that again" },
    'review_form_button': {'rtl': "مراجعة النموذج", 'ltr': "Review Form"},
    'start_over_button': {'rtl': "البدء من جديد", 'ltr': "Start Over"},
    'quota_exceeded_tts': { 'rtl': "لقد تجاوزت حد الاستخدام لخدمة تحويل النص إلى كلام.", 'ltr': "Quota exceeded for Text-to-Speech service." },
    'quota_exceeded_stt': { 'rtl': "لقد تجاوزت حد الاستخدام لخدمة تحويل الكلام إلى نص.", 'ltr': "Quota exceeded for Speech-to-Text service." },
    'checking_image': { 'rtl': "جاري فحص جودة الصورة...", 'ltr': "Checking image quality..." },
    'poor_quality': { 'rtl': "جودة الصورة غير كافية. هل تريد المتابعة على أي حال؟", 'ltr': "Image quality is poor. Do you want to continue anyway?" },
    'analyzing_form': { 'rtl': "جاري تحليل النموذج، من فضلك انتظر...", 'ltr': "Analyzing form, please wait..." },
    'error_checking_quality': { 'rtl': "حدث خطأ أثناء فحص جودة الصورة", 'ltr': "Error checking image quality" },
    'error_analyzing_form': { 'rtl': "حدث خطأ أثناء تحليل النموذج", 'ltr': "Error analyzing form" },
    'download_success': { 'rtl': "تم حفظ النموذج بنجاح!", 'ltr': "Form saved successfully!" },
    'form_tab': { 'rtl': "قارئ النماذج", 'ltr': "Form Reader" },
    'document_tab': { 'rtl': "قارئ المستندات", 'ltr': "Document Reader" },
    'money_tab': { 'rtl': "قارئ العملات", 'ltr': "Money Reader" },
    'upload_document': { 'rtl': "قم برفع ملف PDF أو PowerPoint", 'ltr': "Upload a PDF or PowerPoint file" },
    'upload_money': { 'rtl': "قم برفع صورة للعملة", 'ltr': "Upload an image of the currency" },
    'document_summary': { 'rtl': "ملخص المستند", 'ltr': "Document Summary" },
    'document_navigation': { 'rtl': "التنقل في المستند", 'ltr': "Document Navigation" },
    'document_content': { 'rtl': "محتوى المستند", 'ltr': "Document Content" },
    'currency_result': { 'rtl': "نتيجة تحليل العملة", 'ltr': "Currency Analysis Result" },
}

def get_prompt(key, **kwargs):
    """Gets a prompt from the dictionary based on the form's language."""
    lang = st.session_state.get('language_direction', 'ltr')
    prompt_template = PROMPTS.get(key, {}).get(lang, f"Missing prompt for key: {key}")
    return prompt_template.format(**kwargs)

def play_audio(audio_bytes, mime_type="audio/wav"):
    """Plays audio bytes in the Streamlit app."""
    if not audio_bytes:
        return
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
    audio_tag = f'<audio autoplay="true" src="data:{mime_type};base64,{audio_b64}"></audio>'
    st.markdown(audio_tag, unsafe_allow_html=True)

def speak(text, force_speak=False):
    """تحويل النص إلى كلام"""
    if not text:
        return
        
    try:
        response = requests.post(
            f"{API_BASE_URL}/document/text-to-speech",
            json={"text": text, "provider": "gemini"}
        )
        
        if response.status_code == 200:
            # تشغيل الصوت مباشرة باستخدام st.audio
            st.audio(response.content, format="audio/wav", start_time=0)
        elif response.status_code == 429:
            st.error("تم تجاوز الحد الأقصى لاستخدام خدمة تحويل النص إلى كلام")
        else:
            st.error("فشل في تحويل النص إلى كلام")
    except Exception as e:
        st.error(f"خطأ في تحويل النص إلى كلام: {str(e)}")
        print(f"TTS Error: {str(e)}")  # للتشخيص

def speech_to_text(audio_bytes, language_code="ar"):
    """تحويل الصوت إلى نص"""
    try:
        files = {'audio': ('audio.wav', audio_bytes, 'audio/wav')}
        data = {'language_code': language_code}
        
        response = requests.post(
            f"{API_BASE_URL}/document/speech-to-text",
            files=files,
            data=data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error("فشل في تحويل الصوت إلى نص")
            return None
    except Exception as e:
        st.error(f"خطأ في تحويل الصوت إلى نص: {str(e)}")
        return None

def update_live_image():
    """Calls the backend to get an updated annotated image and stores it in the session."""
    if 'original_image_bytes' not in st.session_state:
        return 

    with st.spinner("Updating form preview..."):
        try:
            payload = {
                "original_image_b64": base64.b64encode(st.session_state.original_image_bytes).decode('utf-8'),
                "texts_dict": st.session_state.get('form_data', {}),
                "ui_fields": st.session_state.get('ui_fields', [])
            }
            response = requests.post(f"{API_BASE_URL}/form/annotate-image", json=payload)
            if response.status_code == 200:
                # Store the new live image, replacing the previous one
                st.session_state.annotated_image_b64 = base64.b64encode(response.content).decode('utf-8')
            else:
                st.warning(f"Could not update live image preview: {response.status_code}")
        except requests.RequestException as e:
            st.warning(f"Connection error while updating preview: {e}")

# Clean up session when user leaves or starts over
def cleanup_session():
    """Clean up the session safely"""
    session_id = st.session_state.get('session_id')
    if session_id:
        try:
            response = requests.delete(f"{API_BASE_URL}/form/session/{session_id}")
            if response.status_code == 200:
                del st.session_state['session_id']
            # Don't raise error for 404 (session already deleted) or 500
        except:
            pass  # Ignore cleanup errors

# Function to handle final image save and cleanup
def save_final_image(image_bytes, file_type="PNG"):
    """Save the final image and clean up session only after successful download"""
    try:
        if file_type == "PNG":
            if st.download_button(
                label=get_prompt('download_png'),
                data=image_bytes,
                file_name="filled_form.png",
                mime="image/png",
                on_click=cleanup_session  # Clean up only after successful download
            ):
                st.success(get_prompt('download_success'))
        elif file_type == "PDF":
            pdf_buf = io.BytesIO()
            final_image = Image.open(io.BytesIO(image_bytes))
            final_image.convert("RGB").save(pdf_buf, format="PDF")
            if st.download_button(
                label=get_prompt('download_pdf'),
                data=pdf_buf.getvalue(),
                file_name="filled_form.pdf",
                mime="application/pdf",
                on_click=cleanup_session  # Clean up only after successful download
            ):
                st.success(get_prompt('download_success'))
    except Exception as e:
        st.error(f"Error preparing download: {str(e)}")

def handle_navigation_command(command):
    """معالجة أوامر التنقل في المستند"""
    try:
        if 'doc_session_id' not in st.session_state:
            st.error("لا يوجد مستند مفتوح")
            return

        current_page = st.session_state.get('current_page', 1)
        
        response = requests.post(
            f"{API_BASE_URL}/document/{st.session_state.doc_session_id}/navigate",
            json={"command": command, "current_page": current_page}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                # مسح علامة القراءة للصفحة الجديدة
                page_read_key = f"page_{result['new_page']}_read"
                if page_read_key in st.session_state:
                    del st.session_state[page_read_key]
                st.session_state.current_page = result["new_page"]
                st.success(result["message"])
                # تحديث عرض الصفحة
                st.experimental_rerun()
            else:
                st.error(result["message"])
        else:
            st.error("حدث خطأ في معالجة الأمر")
    except Exception as e:
        st.error(f"خطأ: {str(e)}")

def process_document(file):
    """معالجة المستند المرفوع وعرض محتواه"""
    try:
        # تحليل الملف
        files = {'file': file}
        data = {'language': 'arabic' if st.session_state.get('language_direction') == 'rtl' else 'english'}
        
        with st.spinner("جاري تحليل المستند..."):
            response = requests.post(f"{API_BASE_URL}/document/upload", files=files, data=data)
            
            if response.status_code != 200:
                st.error("حدث خطأ أثناء تحليل المستند")
                return
        
            result = response.json()
            
            # تخزين معلومات الجلسة
            st.session_state.doc_session_id = result['session_id']
            st.session_state.current_page = 1
            st.session_state.total_pages = result['total_pages']
            st.session_state.filename = result['filename']
            st.session_state.language = result['language']
            
            # عرض رسالة النجاح وملخص المستند
            st.success(result['message'])
            if result.get('presentation_summary'):
                st.info("ملخص المستند:")
                st.write(result['presentation_summary'])
                # قراءة الملخص صوتياً إذا كان المساعد الصوتي مفعل
                if st.session_state.get('voice_enabled', False):
                    speak(result['presentation_summary'])
            
            # تقسيم الواجهة إلى عمودين
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # عرض محتوى الصفحة الحالية
                response = requests.get(
                    f"{API_BASE_URL}/document/{st.session_state.doc_session_id}/page/{st.session_state.current_page}"
                )
                if response.status_code == 200:
                    page_data = response.json()
                    
                    # تجميع النص للقراءة
                    text_to_read = []
        
        # عرض عنوان الصفحة
                    if page_data['title'] and not page_data['title'].startswith('Page '):
                        st.subheader(page_data['title'])
                        text_to_read.append(page_data['title'])
                    
                    # عرض النص الأصلي مقسماً إلى فقرات
                    if page_data.get('paragraphs'):
                        for paragraph in page_data['paragraphs']:
                            st.write(paragraph)
                        text_to_read.extend(page_data['paragraphs'])
                    elif page_data.get('original_text'):
                        st.write(page_data['original_text'])
                        text_to_read.append(page_data['original_text'])
                    
                    # عرض صورة الصفحة
                    if page_data.get('image_data'):
                        st.image(
                            base64.b64decode(page_data['image_data']),
                            use_column_width=True
                        )
                    
                    # عرض معلومات إضافية
                    if page_data.get('word_count') is not None:
                        word_count = page_data['word_count']
                        reading_time = page_data.get('reading_time', 0)
                        if reading_time > 0:
                            reading_time_str = f"{reading_time:.1f}"
                        else:
                            reading_time_str = "أقل من 1"
                        st.caption(f"عدد الكلمات: {word_count} | وقت القراءة التقريبي: {reading_time_str} دقيقة")
                    
                    # قراءة المحتوى تلقائياً إذا كان المساعد الصوتي مفعل
                    if st.session_state.get('voice_enabled', False):
                        # تجنب إعادة القراءة لنفس الصفحة
                        page_read_key = f"page_{st.session_state.current_page}_read"
                        if page_read_key not in st.session_state:
                            combined_text = " ".join(text_to_read).strip()
                            if combined_text:
                                speak(combined_text, force_speak=True)
                            st.session_state[page_read_key] = True
        
                    # قسم الأسئلة
                    st.write("---")
                    st.subheader("اسأل عن هذه الصفحة")
        
                    # مربع إدخال السؤال
                    question = st.text_input("اكتب سؤالك هنا:", key=f"question_input_{st.session_state.current_page}")
                    
                    # زر طرح السؤال
                    if st.button("اسأل", key=f"ask_btn_{st.session_state.current_page}"):
                        if question:
                            with st.spinner("جاري تحليل السؤال..."):
                                response = requests.post(
                                    f"{API_BASE_URL}/document/{st.session_state.doc_session_id}/page/{st.session_state.current_page}/question",
                                    json={"question": question}
                                )
                                if response.status_code == 200:
                                    result = response.json()
                                    st.write("الإجابة:")
                                    st.write(result['answer'])
                                    # قراءة الإجابة صوتياً
                                    if st.session_state.get('voice_enabled', False):
                                        speak(result['answer'])
                                else:
                                    st.error("عذراً، لم أستطع الإجابة على هذا السؤال")
                        else:
                            st.warning("الرجاء كتابة سؤال أولاً")
                    
                    # خيار السؤال الصوتي
                    if st.session_state.get('voice_enabled', False):
                        st.write("---")
                        st.write("أو اطرح سؤالك صوتياً:")
                        audio_bytes = audiorecorder("🎤 اضغط للتحدث", "🔴 جاري التسجيل...", key=f"question_audio_{st.session_state.current_page}")
                        
                        if len(audio_bytes) > 0 and not st.session_state.get('processing_audio_question', False):
                            st.session_state.processing_audio_question = True
                            
                            # تحويل الصوت إلى نص
                            with st.spinner("جاري تحويل الصوت إلى نص..."):
                                lang_code = "ar" if st.session_state.get('language_direction') == 'rtl' else "en"
                                files = {'audio': ('audio.wav', audio_bytes, 'audio/wav')}
                                data = {'language_code': lang_code}
                                
                                response = requests.post(
                                    f"{API_BASE_URL}/document/speech-to-text",
                                    files=files,
                                    data=data
                                )
                                
                                if response.status_code == 200:
                                    question = response.json()
                                    if question:
                                        st.write(f"سؤالك: {question}")
                                        
                                        # إرسال السؤال للتحليل
                                        with st.spinner("جاري تحليل السؤال..."):
                                            response = requests.post(
                                                f"{API_BASE_URL}/document/{st.session_state.doc_session_id}/page/{st.session_state.current_page}/question",
                                                json={"question": question}
                                            )
                                            
                                            if response.status_code == 200:
                                                result = response.json()
                                                st.write("الإجابة:")
                                                st.write(result['answer'])
                                                speak(result['answer'])
                                            else:
                                                st.error("عذراً، لم أستطع الإجابة على هذا السؤال")
                                else:
                                    st.error("فشل في تحويل الصوت إلى نص")
                            
                            st.session_state.processing_audio_question = False
            
            # عرض أزرار التنقل فقط إذا كان هناك أكثر من صفحة واحدة
            if st.session_state.total_pages > 1:
                with col2:
                    st.subheader("التنقل بين الصفحات")
                    
                    # أزرار التنقل
                    col_prev, col_curr, col_next = st.columns(3)
                    with col_prev:
                        if st.button("⬅️ السابق", disabled=st.session_state.current_page <= 1):
                            if st.session_state.current_page > 1:
                                # مسح علامة القراءة للصفحة الجديدة
                                page_read_key = f"page_{st.session_state.current_page - 1}_read"
                                if page_read_key in st.session_state:
                                    del st.session_state[page_read_key]
                                st.session_state.current_page -= 1
                                st.experimental_rerun()
                    
                    with col_curr:
                        st.write(f"صفحة {st.session_state.current_page} من {st.session_state.total_pages}")
                    
                    with col_next:
                        if st.button("التالي ➡️", disabled=st.session_state.current_page >= st.session_state.total_pages):
                            if st.session_state.current_page < st.session_state.total_pages:
                                # مسح علامة القراءة للصفحة الجديدة
                                page_read_key = f"page_{st.session_state.current_page + 1}_read"
                                if page_read_key in st.session_state:
                                    del st.session_state[page_read_key]
                                st.session_state.current_page += 1
                                st.experimental_rerun()
                    
                    # تعليمات التنقل الصوتي
                    if st.session_state.get('voice_enabled', False):
                        st.write("---")
                        st.write("يمكنك استخدام الأوامر الصوتية للتنقل:")
                        st.write("🗣️ قل أحد الأوامر التالية:")
                        st.write("- اذهب إلى الصفحة [رقم]")
                        st.write("- الصفحة التالية")
                        st.write("- الصفحة السابقة")
                        st.write("- الصفحة الأولى")
                        st.write("- الصفحة الأخيرة")
                        
                        # زر التسجيل الصوتي للأوامر
                        st.write("---")
                        st.write("🎤 اضغط على الزر وانطق الأمر:")
                        audio_bytes = audiorecorder("تحدث بالأمر", "🔴 جاري التسجيل...")
                        if len(audio_bytes) > 0 and not st.session_state.get('processing_audio', False):
                            st.session_state.processing_audio = True
                            with st.spinner("جاري تحويل الصوت إلى نص..."):
                                # تحويل الصوت إلى نص
                                lang_code = "ar" if st.session_state.get('language_direction') == 'rtl' else "en"
                                files = {'audio': ('audio.wav', audio_bytes, 'audio/wav')}
                                data = {'language_code': lang_code}
                                response = requests.post(
                                    f"{API_BASE_URL}/document/speech-to-text",
                                    files=files,
                                    data=data
                                )
                                if response.status_code == 200:
                                    command = response.json()
                                    if command:
                                        st.info(f"الأمر المسموع: {command}")
                                        # مسح علامة القراءة عند تنفيذ أمر تنقل
                                        handle_navigation_command(command)
                                else:
                                    st.error("فشل في تحويل الصوت إلى نص")
                            st.session_state.processing_audio = False
    
    except Exception as e:
        st.error(f"حدث خطأ: {str(e)}")

def process_currency(file):
    """معالجة صورة العملة وعرض نتيجة التحليل"""
    try:
        with st.spinner("جاري تحليل العملة..."):
            # إرسال الصورة للتحليل
            files = {'file': (file.name, file.getvalue(), file.type)}
            response = requests.post(f"{API_BASE_URL}/money/analyze", files=files)
            
            if response.status_code == 200:
                result = response.json()
                st.image(file, caption="الصورة المرفوعة", use_column_width=True)
                st.success(result['analysis'])
                if st.session_state.voice_enabled:
                    speak(result['analysis'], force_speak=True)
            
            elif response.status_code == 400:
                # خطأ في جودة الصورة
                error_msg = response.json()['detail']
                st.image(file, caption="الصورة المرفوعة - جودة غير كافية", use_column_width=True)
                st.warning(error_msg)
                if st.session_state.voice_enabled:
                    speak(error_msg, force_speak=True)
            
            else:
                st.image(file, caption="الصورة المرفوعة", use_column_width=True)
                error_msg = "حدث خطأ أثناء تحليل الصورة"
                st.error(error_msg)
                if st.session_state.voice_enabled:
                    speak(error_msg, force_speak=True)
        
    except Exception as e:
        error_msg = f"حدث خطأ: {str(e)}"
        st.error(error_msg)
        if st.session_state.voice_enabled:
            speak("عذراً، حدث خطأ أثناء تحليل الصورة", force_speak=True)

def main():
    # --- UI Components ---
    st.set_page_config(layout="wide")

    # Initialize state correctly, once.
    if 'voice_enabled' not in st.session_state:
        st.session_state.voice_enabled = False
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 'form'
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'document_language' not in st.session_state:
        st.session_state.document_language = 'arabic'

    # Voice Assistant Toggle
    st.session_state.voice_enabled = st.toggle(
        "تفعيل المساعد الصوتي", 
        value=st.session_state.voice_enabled
    )

    # Create tabs
    tabs = st.tabs([
        "قارئ النماذج",
        "قارئ المستندات",
        "قارئ العملات"
    ])

    # Form Reader Tab
    with tabs[0]:
        uploaded_file = st.file_uploader(
            "قم برفع صورة أو ملف PDF للنموذج",
            type=["jpg", "png", "jpeg", "bmp", "pdf"],
            key="form_uploader"
        )
        if uploaded_file:
            st.session_state.active_tab = 'form'
            if st.session_state.get('last_uploaded_filename') != uploaded_file.name:
                # Preserve voice setting and active tab
                voice_setting = st.session_state.voice_enabled
                active_tab = st.session_state.active_tab
                # Clear other state
                for key in list(st.session_state.keys()):
                    if key not in ['voice_enabled', 'active_tab']:
                        del st.session_state[key]
                # Restore settings
                st.session_state.voice_enabled = voice_setting
                st.session_state.active_tab = active_tab
                st.session_state.last_uploaded_filename = uploaded_file.name
                st.session_state.analysis_running = True
                st.rerun()

    # Document Reader Tab
    with tabs[1]:
        # اختيار اللغة
        st.session_state.document_language = st.radio(
            "اختر لغة المستند:",
            options=["arabic", "english"],
            format_func=lambda x: "العربية" if x == "arabic" else "English",
            horizontal=True,
            key="doc_language"
        )
        
        # رفع المستند
        doc_file = st.file_uploader(
            "قم برفع ملف PDF أو PowerPoint",
            type=["pdf", "pptx", "ppt"],
            key="doc_uploader"
        )
        if doc_file:
            st.session_state.active_tab = 'document'
            process_document(doc_file)

    # Money Reader Tab
    with tabs[2]:
        money_file = st.file_uploader(
            "قم برفع صورة للعملة",
            type=["jpg", "jpeg", "png"],
            key="money_uploader"
        )
        if money_file:
            st.session_state.active_tab = 'money'
            process_currency(money_file)

    # --- Main Application Logic ---
    if uploaded_file:
        if st.session_state.get('last_uploaded_filename') != uploaded_file.name:
            # Preserve voice setting
            voice_setting = st.session_state.voice_enabled
            # Clear all other state
            for key in list(st.session_state.keys()):
                if key != 'voice_enabled':
                    del st.session_state[key]
        
            st.session_state.voice_enabled = voice_setting # Restore it
            st.session_state.last_uploaded_filename = uploaded_file.name
            st.session_state.analysis_running = True
            st.rerun()

        if st.session_state.get('analysis_running'):
            # Create a placeholder for the spinner
            spinner_placeholder = st.empty()
            
            # First, check image quality
            with spinner_placeholder:
                with st.spinner(get_prompt('checking_image')):
                    try:
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        quality_response = requests.post(f"{API_BASE_URL}/form/check-image", files=files)
                        
                        if quality_response.status_code == 200:
                            quality_data = quality_response.json()
                            st.session_state.session_id = quality_data.get('session_id')
                            st.session_state.language_direction = quality_data.get('language_direction', 'rtl')
                            st.session_state.image_width = quality_data.get('image_width')
                            st.session_state.image_height = quality_data.get('image_height')
                        else:
                            st.error(get_prompt('error_checking_quality'))
                            st.stop()

                    except Exception as e:
                        st.error(get_prompt('error_checking_quality'))
                        st.stop()

            # Clear the spinner
            spinner_placeholder.empty()
            
            # Check image quality and show warning if needed
            if not quality_data.get('quality_good', False):
                quality_message = quality_data.get('quality_message')
                st.warning(quality_message)
                speak(quality_message)
                if not st.button(get_prompt('continue_button')):
                    st.stop()

            # Now show analysis message and start form analysis
            analysis_message = get_prompt('analyzing_form')
            st.info(analysis_message)
            speak(analysis_message)

            try:
                # Store original image bytes for later use in live updates
                image_bytes = uploaded_file.getvalue()
                st.session_state.original_image_bytes = image_bytes
                
                # Now analyze the form with the session ID
                files = {'file': (uploaded_file.name, image_bytes, uploaded_file.type)}
                response = requests.post(
                    f"{API_BASE_URL}/form/analyze-form",
                    files=files,
                    data={
                        'session_id': st.session_state.session_id,
                        'language_direction': st.session_state.language_direction
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    st.session_state.ui_fields = data.get('fields', [])
                    st.session_state.form_explanation = data.get('form_explanation', "Could not get explanation.")
                    st.session_state.language_direction = data.get('language_direction', 'rtl')
                    st.session_state.image_width = data.get('image_width')
                    st.session_state.image_height = data.get('image_height')
                    st.session_state.form_data = {}
                    st.session_state.current_field_index = 0
                    st.session_state.conversation_stage = 'explanation'
                else:
                    st.error(get_prompt('error_analyzing_form'))
                    st.stop()

            except Exception as e:
                st.error(get_prompt('error_analyzing_form'))
                st.stop()

            st.session_state.analysis_running = False
            st.rerun()

        # --- Display annotated image (it will be updated live) ---
        if 'annotated_image_b64' in st.session_state:
            img_bytes = base64.b64decode(st.session_state.annotated_image_b64)
            st.image(Image.open(io.BytesIO(img_bytes)), caption="Live Form Preview")

        # --- Conversational UI ---
        stage = st.session_state.get('conversation_stage')
        ui_fields = st.session_state.get('ui_fields', [])
        current_index = st.session_state.get('current_field_index', 0)
        
        # Determine language direction for the current session
        lang_code = 'ar' if st.session_state.get('language_direction') == 'rtl' else 'en'
        
        if stage == 'explanation':
            explanation = st.session_state.get('form_explanation', '')
            st.info(explanation)
            speak(explanation)
            if st.button(get_prompt('continue_button'), use_container_width=True):
                st.session_state.conversation_stage = 'filling_fields'
                st.rerun()

        elif stage == 'filling_fields':
            if current_index < len(ui_fields):
                field = ui_fields[current_index]
                label, field_type = field['label'], field['type']
                prompt = get_prompt('checkbox_prompt', label=label) if field_type == 'checkbox' else get_prompt('text_prompt', label=label)
                st.info(prompt)
                speak(prompt)
                
                # Voice Input (Always available)
                audio = audiorecorder(get_prompt('speak_button_label'), get_prompt('recording_button_label'), key=f"audio_{current_index}")
                if len(audio) > 0:
                    with st.spinner(get_prompt('stt_spinner')):
                        wav_bytes = audio.export(format="wav").read()
                        transcript = speech_to_text(wav_bytes, lang_code)
                    if transcript:
                        skip_words = ['تجاوز', 'تخطي', 'skip', 'next']
                        if any(word in transcript.lower() for word in skip_words):
                            st.session_state.current_field_index += 1
                            st.rerun()
                        else:
                            st.session_state.pending_transcript = transcript
                            st.session_state.conversation_stage = 'confirmation'
                            st.rerun()
                    else: 
                        if len(audio.stream_data) > 0:
                            st.error(get_prompt('stt_error'))

                # Keyboard Input
                st.markdown(f"**{get_prompt('or_type_prompt')}**")
                
                field_key = f"keyboard_input_{current_index}"
                if field_type == 'checkbox':
                    current_value = st.session_state.form_data.get(field['box_id'], False)
                    st.checkbox(label, key=field_key, value=current_value)
                else:
                    current_value = st.session_state.form_data.get(field['box_id'], "")
                    st.text_input(label, key=field_key, value=current_value)

                col1, col2 = st.columns([3, 1])
                if col1.button(get_prompt('save_and_next_button'), key=f"save_{current_index}", use_container_width=True):
                    st.session_state.form_data[field['box_id']] = st.session_state[field_key]
                    update_live_image()
                    st.session_state.current_field_index += 1
                    st.rerun()
                if col2.button(get_prompt('skip_button'), key=f"skip_{current_index}", use_container_width=True):
                    st.session_state.current_field_index += 1
                    st.rerun()
            else:
                # All fields are filled, go directly to the review/download stage
                st.session_state.conversation_stage = 'review'
                st.rerun()

        elif stage == 'confirmation':
            raw_transcript = st.session_state.get('pending_transcript', "")
            if not raw_transcript:
                st.session_state.conversation_stage = 'filling_fields'
                st.rerun()

            field = ui_fields[current_index]
            
            # Confirmation display logic (now using the form's language)
            if field['type'] == 'checkbox':
                positive_words = ['نعم', 'أجل', 'حدد', 'صح', 'تمام', 'yes', 'check', 'ok', 'correct', 'right']
                is_positive = any(word in raw_transcript.lower() for word in positive_words)
                display_transcript = get_prompt('checkbox_checked') if is_positive else get_prompt('checkbox_unchecked')
            else:
                display_transcript = raw_transcript
            
            st.info(get_prompt('heard_you_say', transcript=display_transcript))
            speak(get_prompt('confirmation_prompt_no_voice'), force_speak=True)

            col1, col2 = st.columns(2)
            if col1.button(get_prompt('confirm_button'), key=f"confirm_{current_index}", use_container_width=True):
                box_id = field['box_id']
                if field['type'] == 'checkbox':
                    positive_words_for_check = ['نعم', 'أجل', 'حدد', 'صح', 'تمام', 'yes', 'check', 'ok', 'correct', 'right']
                    st.session_state.form_data[box_id] = any(word in raw_transcript.lower() for word in positive_words_for_check)
                else:
                    st.session_state.form_data[box_id] = raw_transcript
                update_live_image()
                st.session_state.current_field_index += 1
                st.session_state.conversation_stage = 'filling_fields'
                st.rerun()
            if col2.button(get_prompt('retry_button'), key=f"retry_{current_index}", use_container_width=True):
                speak(get_prompt('retry_prompt'))
                st.session_state.conversation_stage = 'filling_fields'
                st.rerun()

        elif stage == 'review':
            review_message = get_prompt('review_prompt')
            speak(review_message)
            st.success(review_message)
            
            final_image_bytes = None
            
            # Try to get the latest annotated image
            if 'annotated_image_b64' in st.session_state:
                final_image_bytes = base64.b64decode(st.session_state.annotated_image_b64)
            
            # If no annotated image, generate one
            if not final_image_bytes and 'original_image_bytes' in st.session_state:
                with st.spinner("Generating final image..."):
                    try:
                        payload = {
                            "original_image_b64": base64.b64encode(st.session_state.original_image_bytes).decode('utf-8'),
                            "texts_dict": st.session_state.get('form_data', {}),
                            "ui_fields": st.session_state.get('ui_fields', [])
                        }
                        response = requests.post(f"{API_BASE_URL}/form/annotate-image", json=payload)
                        if response.status_code == 200:
                            final_image_bytes = response.content
                        else:
                            st.error(f"Failed to generate final image: {response.text}")
                    except requests.RequestException as e:
                        st.error(f"Connection error while generating final image: {e}")
            
            if final_image_bytes:
                col1, col2 = st.columns(2)
                with col1:
                    save_final_image(final_image_bytes, "PNG")
                with col2:
                    save_final_image(final_image_bytes, "PDF")

    else:
        pass  # Just show the file uploader without any message

if __name__ == "__main__":
    main() 