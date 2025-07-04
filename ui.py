"""
Form Reader Application - Enhanced with PDF Multipage Support
"""

import streamlit as st
import requests
import base64
from PIL import Image
import io
import os
import json
import re
import traceback
from audiorecorder import audiorecorder

# --- Configuration ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# --- Enhanced Prompts for PDF Multipage Support ---
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
        'ltr': "Provide the information for '{label}'"
    },
    'heard_you_say': {
        'rtl': "سمعتك تقول '{transcript}'",
        'ltr': "I heard you say '{transcript}'"
    },
    'stt_error': {
        'rtl': "لم أتمكن من فهم الصوت. من فضلك حاول مرة أخرى",
        'ltr': "I couldn't understand the audio. Please try again"
    },
    'review_prompt': {
        'rtl': "اكتمل النموذج. يمكنك الآن تحميله كملف صورة (PNG) أو كملف (PDF).",
        'ltr': "The form is complete. You can now download it as a PNG image or a PDF file."
    },
    'download_png': {
        'rtl': "تنزيل كـ PNG",
        'ltr': "Download as PNG"
    },
    'download_pdf': {
        'rtl': "تنزيل كـ PDF",
        'ltr': "Download as PDF"
    },
    'pdf_exploring': {
        'rtl': "جاري استكشاف ملف PDF...",
        'ltr': "Exploring PDF file..."
    },
    'pdf_found_pages': {
        'rtl': "تم العثور على {total_pages} صفحة في ملف PDF",
        'ltr': "Found {total_pages} pages in the PDF file"
    },
    'pdf_explain_stage': {
        'rtl': "مرحلة الشرح: سنقوم أولاً بشرح محتوى كل صفحة",
        'ltr': "Explanation stage: We will first explain the content of each page"
    },
    'pdf_explaining_page': {
        'rtl': "جاري شرح الصفحة {page_number} من {total_pages}...",
        'ltr': "Explaining page {page_number} of {total_pages}..."
    },
    'pdf_analyze_stage': {
        'rtl': "مرحلة التحليل: البحث عن الحقول القابلة للتعبئة",
        'ltr': "Analysis stage: Looking for fillable fields"
    },
    'pdf_analyzing_page': {
        'rtl': "جاري تحليل الصفحة {page_number} من {total_pages}...",
        'ltr': "Analyzing page {page_number} of {total_pages}..."
    },
    'pdf_filling_page': {
        'rtl': "تعبئة الصفحة {page_number} من {total_pages}",
        'ltr': "Filling page {page_number} of {total_pages}"
    },
    'pdf_next_page': {
        'rtl': "الانتقال للصفحة التالية",
        'ltr': "Go to next page"
    },
    'pdf_start_analysis': {
        'rtl': "بدء تحليل جميع الصفحات",
        'ltr': "Start analyzing all pages"
    },
    'pdf_download_complete': {
        'rtl': "تم الانتهاء من جميع الصفحات. يمكنك الآن تحميل ملف PDF الكامل",
        'ltr': "All pages completed. You can now download the complete PDF file"
    },
    'pdf_download_filled': {
        'rtl': "تحميل PDF المعبأ",
        'ltr': "Download Filled PDF"
    },
    'pdf_no_fields_page': {
        'rtl': "لا توجد حقول قابلة للتعبئة في هذه الصفحة",
        'ltr': "No fillable fields found on this page"
    },
    'stt_spinner': { 
        'rtl': "جاري تحويل الصوت إلى نص...", 
        'ltr': "Transcribing audio..." 
    },
    'confirmation_prompt_no_voice': { 
        'rtl': "هل هذا صحيح؟", 
        'ltr': "Is this correct?" 
    },
    'confirm_button': { 
        'rtl': "تأكيد", 
        'ltr': "Confirm" 
    },
    'retry_button': { 
        'rtl': "إعادة المحاولة", 
        'ltr': "Retry" 
    },
    'continue_button': { 
        'rtl': "متابعة", 
        'ltr': "Continue" 
    },
    'or_type_prompt': { 
        'rtl': "أو، أدخل إجابتك في الأسفل:", 
        'ltr': "Or, type your answer below:" 
    },
    'save_and_next_button': { 
        'rtl': "حفظ والمتابعة", 
        'ltr': "Save and Continue" 
    },
    'skip_button': { 
        'rtl': "تخطي هذا الحقل", 
        'ltr': "Skip this field" 
    },
    'toggle_voice_label': { 
        'rtl': "تفعيل قراءة الإرشادات صوتياً", 
        'ltr': "Enable Voice Reading" 
    },
    'checkbox_checked': { 
        'rtl': "تحديد الخانة", 
        'ltr': "Checked" 
    },
    'checkbox_unchecked': { 
        'rtl': "عدم تحديد الخانة", 
        'ltr': "Unchecked" 
    },
    'retry_prompt': { 
        'rtl': "تمام، لنجرب مرة أخرى", 
        'ltr': "Okay, let's try that again" 
    },
    'checking_image': { 
        'rtl': "جاري فحص جودة الصورة...", 
        'ltr': "Checking image quality..." 
    },
    'poor_quality': { 
        'rtl': "جودة الصورة غير كافية. هل تريد المتابعة على أي حال؟", 
        'ltr': "Image quality is poor. Do you want to continue anyway?" 
    },
    'analyzing_form': { 
        'rtl': "جاري تحليل النموذج، من فضلك انتظر...", 
        'ltr': "Analyzing form, please wait..." 
    },
    'error_checking_quality': { 
        'rtl': "حدث خطأ أثناء فحص جودة الصورة", 
        'ltr': "Error checking image quality" 
    },
    'error_analyzing_form': { 
        'rtl': "حدث خطأ أثناء تحليل النموذج", 
        'ltr': "Error analyzing form" 
    },
    'download_success': { 
        'rtl': "تم حفظ النموذج بنجاح!", 
        'ltr': "Form saved successfully!" 
    },
    'upload_signature_prompt': { 
        'rtl': "ارفع صورة توقيعك هنا", 
        'ltr': "Upload your signature image here" 
    },
}

def is_signature_field(label):
    """Checks if a field label indicates a signature using direct keyword matching."""
    if not label:
        return False
    
    import re
    # Keep the original label for word boundary checking
    label_lower = label.lower()
    
    # All possible signature keywords (Arabic and English variations)
    signature_keywords = [
        # English variations - more specific to avoid false positives
        'signature', 'signatures', 'signed', 'signhere', 'sign here', 'signby', 'sign by', 
        'signdate', 'sign date', 'autograph', 'endorsement',
        
        # Arabic variations
        'توقيع', 'التوقيع', 'توقيعي', 'توقيعك', 'توقيعه', 'توقيعها',
        'امضاء', 'الامضاء', 'امضائي', 'امضاؤك', 'امضاؤه', 'امضاؤها',
        'اعتماد', 'موافقة', 'تصديق', 'ختم', 'الختم',
        'وقع', 'يوقع', 'موقع', 'موقعة', 'موقعه',
        'اوقع', 'يووقع', 'مووقع'  # Common misspellings
    ]
    
    # Check for exact keyword matches or word boundaries for English
    for keyword in signature_keywords:
        keyword_lower = keyword.lower()
        
        # For Arabic keywords, check if they appear as standalone words
        if any(char in '\u0600-\u06FF' for char in keyword):
            # Arabic - check if keyword exists as complete word
            if keyword_lower in label_lower:
                # Additional check: make sure it's not part of a larger Arabic word
                start_idx = label_lower.find(keyword_lower)
                if start_idx != -1:
                    # Check boundaries for Arabic text
                    before = start_idx == 0 or not label_lower[start_idx-1].isalpha()
                    after = start_idx + len(keyword_lower) >= len(label_lower) or not label_lower[start_idx + len(keyword_lower)].isalpha()
                    if before and after:
                        return True
        else:
            # English - use word boundaries to avoid matching "sign" in "design"
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            if re.search(pattern, label_lower):
                return True
    
    return False

def get_prompt(key, **kwargs):
    """Gets a prompt from the dictionary based on the form's language."""
    lang = st.session_state.get('language_direction', 'ltr')
    prompt_template = PROMPTS.get(key, {}).get(lang, f"Missing prompt for key: {key}")
    try:
        return prompt_template.format(**kwargs)
    except KeyError as e:
        print(f"❌ Missing key in prompt formatting: {e}")
        print(f"📋 Template: {prompt_template}")
        print(f"📋 Args: {kwargs}")
        return prompt_template  # Return unformatted template if formatting fails

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
    
    # Don't speak if voice is not enabled and not forced
    if not force_speak and not st.session_state.get('voice_enabled', False):
        return
        
    try:
        response = requests.post(
            f"{API_BASE_URL}/document/text-to-speech",
            json={"text": text, "provider": "gemini"}
        )
        
        if response.status_code == 200:
            # تشغيل الصوت مباشرة باستخدام st.audio
            audio_bytes = response.content
            audio_b64 = base64.b64encode(audio_bytes).decode()
            audio_tag = f'<audio autoplay="true" src="data:audio/wav;base64,{audio_b64}"></audio>'
            st.markdown(audio_tag, unsafe_allow_html=True)
            
            # احتياطي: استخدام st.audio إذا لم يعمل الـ HTML5 audio
            if not force_speak:
                st.audio(audio_bytes, format="audio/wav")
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
            result = response.json()
            # تأكد من أن النتيجة تحتوي على نص
            if isinstance(result, dict):
                return result.get('text', '')
            return str(result)
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
            # Check if we're in multi-page PDF mode
            is_multipage_pdf_mode = st.session_state.get('pdf_multipage_mode', False)
            
            if is_multipage_pdf_mode and st.session_state.get('current_pdf_stage') == 'fill':
                # Use PDF-specific annotation endpoint for multi-page PDFs
                import json
                session_id = st.session_state.get('pdf_session_id')
                current_page = st.session_state.get('pdf_current_page', 1)
                
                if session_id:
                    form_data = {
                        'page_number': current_page,
                        'texts_dict': json.dumps(st.session_state.get('form_data', {})),
                        'signature_image_b64': st.session_state.get("signature_b64", ""),
                        'signature_field_id': st.session_state.get("signature_field_id", "")
                    }
                    
                    response = requests.post(
                        f"{API_BASE_URL}/form/fill-pdf-page",
                        data=form_data
                    )
                    
                    if response.status_code == 200:
                        # Store the new live image, replacing the previous one
                        st.session_state.annotated_image_b64 = base64.b64encode(response.content).decode('utf-8')
                    else:
                        print(f"❌ PDF live update failed: {response.status_code}")
                else:
                    st.warning("No PDF session found for live preview")
            else:
                # Use regular image annotation endpoint
                payload = {
                    "original_image_b64": base64.b64encode(st.session_state.original_image_bytes).decode('utf-8'),
                    "texts_dict": st.session_state.get('form_data', {}),
                    "ui_fields": st.session_state.get('ui_fields', []),
                    "signature_image_b64": st.session_state.get("signature_b64"),
                    "signature_field_id": st.session_state.get("signature_field_id")
                }
                response = requests.post(f"{API_BASE_URL}/form/annotate-image", json=payload)
                if response.status_code == 200:
                    st.session_state.annotated_image_b64 = base64.b64encode(response.content).decode('utf-8')
                else:
                    st.warning(f"Could not update live image preview: {response.status_code}")
        except requests.RequestException as e:
            st.warning(f"Connection error while updating preview: {e}")

def cleanup_session():
    """Clean up the session safely"""
    session_id = st.session_state.get('session_id')
    pdf_session_id = st.session_state.get('pdf_session_id')
    
    # Cleanup regular session
    if session_id:
        try:
            response = requests.delete(f"{API_BASE_URL}/form/session/{session_id}")
            if response.status_code == 200:
                del st.session_state['session_id']
        except:
            pass
    
    # Cleanup PDF session
    if pdf_session_id:
        try:
            print(f"🗑️ UI: Attempting to delete PDF session: {pdf_session_id}")
            response = requests.delete(f"{API_BASE_URL}/form/pdf-session/{pdf_session_id}")
            print(f"🗑️ UI: Delete response status: {response.status_code}")
            if response.status_code == 200:
                print(f"✅ UI: PDF session deleted successfully")
                del st.session_state['pdf_session_id']
            else:
                print(f"❌ UI: Failed to delete PDF session: {response.text}")
        except Exception as e:
            print(f"❌ UI: Error deleting PDF session: {e}")
            pass

def save_final_image(image_bytes, file_type="PNG", page_suffix=""):
    """Save the final image and clean up session only after successful download"""
    try:
        filename_base = "filled_form"
        if page_suffix:
            filename_base = f"filled_form_{page_suffix}"
            
        if file_type == "PNG":
            if st.download_button(
                label=get_prompt('download_png'),
                data=image_bytes,
                file_name=f"{filename_base}.png",
                mime="image/png",
                on_click=cleanup_session
            ):
                st.success(get_prompt('download_success'))
        elif file_type == "PDF":
            pdf_buf = io.BytesIO()
            final_image = Image.open(io.BytesIO(image_bytes))
            final_image.convert("RGB").save(pdf_buf, format="PDF")
            if st.download_button(
                label=get_prompt('download_pdf'),
                data=pdf_buf.getvalue(),
                file_name=f"{filename_base}.pdf",
                mime="application/pdf",
                on_click=cleanup_session
            ):
                st.success(get_prompt('download_success'))
    except Exception as e:
        st.error(f"Error preparing download: {str(e)}")

def main():
    # UI Configuration
    st.set_page_config(layout="wide", page_title="Form Reader - PDF Support")

    # Initialize state
    if 'voice_enabled' not in st.session_state:
        st.session_state.voice_enabled = False
    if 'voice_settings' not in st.session_state:
        st.session_state.voice_settings = {
            'enabled': False,
            'last_analysis': None,
            'form_data': None
        }
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'conversation_stage' not in st.session_state:
        st.session_state.conversation_stage = None

    # Voice Assistant Toggle
    st.markdown("### إعدادات المساعد الصوتي للقراءة")
    voice_enabled = st.toggle(
        "تفعيل قراءة الإرشادات صوتياً (للاستماع فقط)", 
        value=st.session_state.voice_enabled,
        key="voice_toggle",
        help="فعّل هذا الخيار لسماع الإرشادات والنصوص بالصوت. المايك للإدخال متاح دائماً"
    )
    
    # Update voice settings if changed
    if voice_enabled != st.session_state.voice_enabled:
        st.session_state.voice_enabled = voice_enabled
        if voice_enabled and st.session_state.get('conversation_stage') is not None:
            speak("تم تفعيل قراءة الإرشادات صوتياً", force_speak=True)
    
    st.divider()

    # Initialize session state if not exists
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.last_uploaded_filename = None
        st.session_state.analysis_running = False
        st.session_state.conversation_stage = None
        st.session_state.quality_data = None
        st.session_state.start_analysis = False
        st.session_state.form_data = {}
        st.session_state.current_field_index = 0
        st.session_state.show_continue = False
        st.session_state.voice_enabled = False
        st.session_state.pdf_multipage_mode = False

    # File Upload
    uploaded_file = st.file_uploader(
        "قم برفع صورة أو ملف PDF للنموذج",
        type=["jpg", "png", "jpeg", "bmp", "pdf"],
        key="form_uploader"
    )
    
    if uploaded_file:
        # Check if this is a new file
        if st.session_state.last_uploaded_filename != uploaded_file.name:
            # Store voice settings before clearing
            voice_enabled = st.session_state.voice_enabled
            
            # Reset session state for new file
            for key in list(st.session_state.keys()):
                if key not in ['initialized', 'voice_enabled', 'voice_toggle']:
                    del st.session_state[key]
            
            # Restore basic state
            st.session_state.last_uploaded_filename = uploaded_file.name
            st.session_state.analysis_running = True
            st.session_state.conversation_stage = None
            st.session_state.voice_enabled = voice_enabled
            st.session_state.quality_data = None
            st.session_state.start_analysis = False
            st.session_state.show_continue = False
            
            # Check file type and decide workflow
            file_extension = uploaded_file.name.lower().split('.')[-1]
            is_pdf = file_extension == 'pdf'
            
            if is_pdf:
                # =============================================================================
                # NEW PDF MULTIPAGE WORKFLOW
                # =============================================================================
                st.session_state.pdf_multipage_mode = True
                st.session_state.current_pdf_stage = 'explore'
                
                check_message = get_prompt('pdf_exploring')
                with st.spinner(check_message):
                    try:
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        explore_response = requests.post(f"{API_BASE_URL}/form/explore-pdf", files=files)
                        
                        print(f"🔍 DEBUG: Response status: {explore_response.status_code}")
                        print(f"🔍 DEBUG: Response headers: {explore_response.headers}")
                        
                        if explore_response.status_code == 200:
                            explore_data = explore_response.json()
                            print(f"🔍 DEBUG: Response data: {explore_data}")
                            
                            # Store PDF exploration data
                            st.session_state.update({
                                'pdf_session_id': explore_data.get('session_id'),
                                'pdf_total_pages': explore_data.get('total_pages'),
                                'pdf_filename': explore_data.get('filename'),
                                'pdf_message': explore_data.get('message'),
                                'pdf_current_page': 1,
                                'pdf_stage': explore_data.get('stage'),
                                'language_direction': 'rtl',
                                'analysis_running': False,
                                'show_continue': False,
                                'pdf_ready_for_explanation': True
                            })
                            
                            # Show initial PDF info
                            total_pages_value = explore_data.get('total_pages', 0)
                            if total_pages_value and total_pages_value > 0:
                                # إزالة رسالة عدد الصفحات كما طلب المستخدم
                                pass
                            else:
                                st.error("لم يتم العثور على صفحات صالحة في ملف PDF")
                            
                            # Show the PDF message
                            if explore_data.get('message'):
                                st.info(explore_data.get('message'))
                                if st.session_state.voice_enabled:
                                    speak(explore_data.get('message'), force_speak=True)
                            
                        else:
                            error_msg = f"خطأ في استكشاف PDF: {explore_response.text}"
                            st.error(error_msg)
                            if st.session_state.voice_enabled:
                                speak(error_msg, force_speak=True)
                            st.session_state.analysis_running = False
                            st.stop()
                    except requests.RequestException as e:
                        error_msg = f"خطأ في الاتصال بالخادم: {str(e)}"
                        st.error(error_msg)
                        if st.session_state.voice_enabled:
                            speak(error_msg, force_speak=True)
                        st.session_state.analysis_running = False
                        st.stop()
                    except Exception as e:
                        error_msg = f"خطأ غير متوقع في PDF: {str(e)}"
                        st.error(error_msg)
                        print(f"🔍 DEBUG: Full error details: {traceback.format_exc()}")
                        if st.session_state.voice_enabled:
                            speak(error_msg, force_speak=True)
                        st.session_state.analysis_running = False
                        st.stop()
            else:
                # =============================================================================
                # REGULAR IMAGE WORKFLOW (unchanged)
                # =============================================================================
                check_message = "جاري فحص الصورة..."
                
                with st.spinner(check_message):
                    try:
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        quality_response = requests.post(f"{API_BASE_URL}/form/check-file", files=files)
                        
                        if quality_response.status_code == 200:
                            quality_data = quality_response.json()
                            
                            # Store all necessary data in session state
                            session_update = {
                                'session_id': quality_data.get('session_id'),
                                'language_direction': quality_data.get('language_direction', 'rtl') or quality_data.get('recommended_language', 'rtl'),
                                'form_explanation': quality_data.get('form_explanation', ''),
                                'quality_data': quality_data,
                                'show_continue': True,  # Enable continue button
                                'is_pdf': False
                            }
                            
                            # Add file-specific data
                            session_update.update({
                                'image_width': quality_data.get('image_width'),
                                'image_height': quality_data.get('image_height'),
                                'pdf_mode': False  # Regular image
                            })
                            
                            st.session_state.update(session_update)
                            
                            # Show quality results immediately
                            if not quality_data.get('quality_good', False):
                                warning_msg = quality_data.get('quality_message', 'جودة الصورة غير كافية')
                                st.warning(warning_msg)
                                if st.session_state.voice_enabled:
                                    speak(warning_msg, force_speak=True)
                            
                            if quality_data.get('form_explanation'):
                                explanation = quality_data.get('form_explanation')
                                st.info(explanation)
                                if st.session_state.voice_enabled:
                                    speak(explanation, force_speak=True)
                            
                            # Show continue button after successful quality check
                            st.session_state.analysis_running = False
                            st.session_state.show_continue = True
                        else:
                            error_msg = f"خطأ في فحص الصورة: {quality_response.text}"
                            st.error(error_msg)
                            if st.session_state.voice_enabled:
                                speak(error_msg, force_speak=True)
                            st.session_state.analysis_running = False
                            st.session_state.show_continue = False
                            st.stop()
                    except Exception as e:
                        error_msg = f"خطأ غير متوقع: {str(e)}"
                        st.error(error_msg)
                        if st.session_state.voice_enabled:
                            speak(error_msg, force_speak=True)
                        st.session_state.analysis_running = False
                        st.session_state.show_continue = False
                        st.stop()

        # =============================================================================
        # PDF MULTIPAGE WORKFLOW LOGIC
        # =============================================================================
        if st.session_state.get('pdf_multipage_mode'):
            pdf_stage = st.session_state.get('current_pdf_stage', 'explore')
            
            # STAGE 1: EXPLANATION PHASE
            if pdf_stage == 'explore' and st.session_state.get('pdf_ready_for_explanation'):
                st.markdown("### " + get_prompt('pdf_explain_stage'))
                
                # Show progress
                current_page = st.session_state.get('pdf_current_page', 1)
                total_pages = st.session_state.get('pdf_total_pages', 1)
                
                if current_page <= total_pages:
                    explain_message = get_prompt('pdf_explaining_page', 
                        page_number=current_page, 
                        total_pages=total_pages
                    )
                    
                    # Display explanation if it exists
                    explanation_key = f'page_{current_page}_explanation'
                    if explanation_key in st.session_state:
                        st.markdown("---")  # Separator
                        st.info(st.session_state[explanation_key])
                        
                        # Speak explanation if voice enabled (but don't force it every time)
                        explanation_spoken_key = f'explanation_spoken_{current_page}'
                        if st.session_state.voice_enabled and explanation_spoken_key not in st.session_state:
                            speak(st.session_state[explanation_key])
                            st.session_state[explanation_spoken_key] = True
                        
                        st.markdown("---")  # Separator
                        
                        # Show next page explanation button if there are more pages
                        if current_page < total_pages:
                            next_page = current_page + 1
                            if st.button(f"شرح الصفحة {next_page}", use_container_width=True, key=f"explain_next_{current_page}"):
                                st.session_state.pdf_current_page = next_page
                                st.rerun()
                        else:
                            # All pages explained, show analysis button
                            if st.button("بدء تحليل جميع الصفحات", use_container_width=True, key="start_analysis", type="primary"):
                                st.session_state.current_pdf_stage = 'ready_for_analysis'
                                st.session_state.pdf_current_page = 1
                                st.rerun()
                    else:
                        # Button to explain current page (only if not explained yet)
                        if st.button(f"شرح الصفحة {current_page}", use_container_width=True, key=f"explain_page_{current_page}"):
                            with st.spinner(explain_message):
                                if st.session_state.voice_enabled:
                                    speak(explain_message)
                                
                                try:
                                    data = {
                                        'session_id': st.session_state.pdf_session_id,
                                        'page_number': current_page
                                    }
                                    
                                    explain_response = requests.post(
                                        f"{API_BASE_URL}/form/explain-pdf-page",
                                        data=data
                                    )
                                    
                                    if explain_response.status_code == 200:
                                        explain_data = explain_response.json()
                                        
                                        # Store the explanation in session state to display it
                                        st.session_state[explanation_key] = explain_data.get('explanation', '')
                                        st.session_state.language_direction = explain_data.get('language_direction', 'rtl')
                                        
                                        st.rerun()
                                    else:
                                        st.error(f"خطأ في شرح الصفحة: {explain_response.text}")
                                except Exception as e:
                                    st.error(f"خطأ في شرح الصفحة: {str(e)}")
            
            # STAGE 2: READY FOR ANALYSIS
            elif pdf_stage == 'ready_for_analysis':
                st.success("✅ تم شرح جميع الصفحات!")
                st.markdown("### " + get_prompt('pdf_analyze_stage'))
                
                if st.button(get_prompt('pdf_start_analysis'), use_container_width=True, type="primary"):
                    st.session_state.current_pdf_stage = 'analyze'
                    st.session_state.pdf_current_page = 1
                    st.rerun()
            
            # STAGE 3: ANALYSIS PHASE
            elif pdf_stage == 'analyze':
                current_page = st.session_state.get('pdf_current_page', 1)
                total_pages = st.session_state.get('pdf_total_pages', 1)
                
                if current_page <= total_pages:
                    analyze_message = get_prompt('pdf_analyzing_page', 
                        page_number=current_page, 
                        total_pages=total_pages
                    )
                    
                    st.markdown(f"### {analyze_message}")
                    
                    # Auto-analyze current page
                    if f'analyzed_page_{current_page}' not in st.session_state:
                        with st.spinner(analyze_message):
                            if st.session_state.voice_enabled:
                                speak(analyze_message)
                            
                            try:
                                data = {
                                    'session_id': st.session_state.pdf_session_id,
                                    'page_number': current_page
                                }
                                
                                analyze_response = requests.post(
                                    f"{API_BASE_URL}/form/analyze-pdf-page",
                                    data=data
                                )
                                
                                if analyze_response.status_code == 200:
                                    analyze_data = analyze_response.json()
                                    
                                    # Store analysis results
                                    st.session_state[f'analyzed_page_{current_page}'] = analyze_data
                                    
                                    if analyze_data.get('has_fields', False):
                                        st.success(f"✅ تم العثور على {analyze_data.get('field_count', 0)} حقل في الصفحة {current_page}")
                                        # Move to filling stage for this page
                                        st.session_state.current_pdf_stage = 'fill'
                                        st.session_state.current_field_index = 0
                                        st.session_state.form_data = {}
                                        st.session_state.ui_fields = analyze_data.get('fields', [])
                                        st.session_state.conversation_stage = 'filling_fields'
                                    else:
                                        # No fields in this page, move to next
                                        no_fields_msg = get_prompt('pdf_no_fields_page')
                                        st.info(no_fields_msg)
                                        if st.session_state.voice_enabled:
                                            speak(no_fields_msg)
                                        
                                        if analyze_data.get('has_next_page', False):
                                            st.session_state.pdf_current_page = current_page + 1
                                        else:
                                            # All pages analyzed, ready for completion
                                            st.session_state.current_pdf_stage = 'complete'
                                    
                                    st.rerun()
                                else:
                                    st.error(f"خطأ في تحليل الصفحة: {analyze_response.text}")
                            except Exception as e:
                                st.error(f"خطأ في تحليل الصفحة: {str(e)}")
                    else:
                        # Page already analyzed, show results
                        analyze_data = st.session_state[f'analyzed_page_{current_page}']
                        if analyze_data.get('has_fields', False):
                            st.session_state.current_pdf_stage = 'fill'
                            st.session_state.current_field_index = 0
                            st.session_state.form_data = {}
                            st.session_state.ui_fields = analyze_data.get('fields', [])
                            st.session_state.conversation_stage = 'filling_fields'
                            st.rerun()
                        else:
                            # No fields, continue to next page
                            if current_page < total_pages:
                                st.session_state.pdf_current_page = current_page + 1
                                st.rerun()
                            else:
                                st.session_state.current_pdf_stage = 'complete'
                                st.rerun()
                else:
                    # All pages analyzed
                    st.session_state.current_pdf_stage = 'complete'
                    st.rerun()
            
            # STAGE 4: FILL CURRENT PAGE (uses existing form filling logic)
            elif pdf_stage == 'fill':
                current_page = st.session_state.get('pdf_current_page', 1)
                total_pages = st.session_state.get('pdf_total_pages', 1)
                
                fill_message = get_prompt('pdf_filling_page', 
                    page_number=current_page, 
                    total_pages=total_pages
                )
                st.markdown(f"### {fill_message}")
                
                # Use the same form filling logic as regular images
                # After form is filled (in review stage), show completion button
                stage = st.session_state.get('conversation_stage')
                if stage == 'review':
                    if st.button("إنهاء تعبئة هذه الصفحة", use_container_width=True, type="primary"):
                        # Fill this page with collected data
                        try:
                            import json
                            fill_data = {
                                'session_id': st.session_state.pdf_session_id,
                                'page_number': current_page,
                                'texts_dict': json.dumps(st.session_state.get('form_data', {})),
                                'signature_image_b64': st.session_state.get("signature_b64", ""),
                                'signature_field_id': st.session_state.get("signature_field_id", "")
                            }
                            
                            fill_response = requests.post(
                                f"{API_BASE_URL}/form/fill-pdf-page",
                                data=fill_data
                            )
                            
                            if fill_response.status_code == 200:
                                st.success(f"✅ تم الانتهاء من تعبئة الصفحة {current_page}")
                                
                                # Mark page as filled
                                st.session_state[f'filled_page_{current_page}'] = True
                                
                                # Check if there are more pages
                                if current_page < total_pages:
                                    st.session_state.pdf_current_page = current_page + 1
                                    st.session_state.current_pdf_stage = 'analyze'  # Analyze next page
                                    st.session_state.conversation_stage = None
                                    # Clear form data for next page
                                    st.session_state.form_data = {}
                                    st.session_state.current_field_index = 0
                                    if f'analyzed_page_{current_page + 1}' in st.session_state:
                                        del st.session_state[f'analyzed_page_{current_page + 1}']
                                else:
                                    # All pages completed
                                    st.session_state.current_pdf_stage = 'complete'
                                
                                st.rerun()
                            else:
                                st.error(f"خطأ في تعبئة الصفحة: {fill_response.text}")
                        except Exception as e:
                            st.error(f"خطأ في تعبئة الصفحة: {str(e)}")
            
            # STAGE 5: COMPLETION - DOWNLOAD PDF
            elif pdf_stage == 'complete':
                st.success(get_prompt('pdf_download_complete'))
                
                if st.button(get_prompt('pdf_download_filled'), use_container_width=True, type="primary"):
                    try:
                        download_response = requests.get(
                            f"{API_BASE_URL}/form/download-filled-pdf/{st.session_state.pdf_session_id}"
                        )
                        
                        if download_response.status_code == 200:
                            pdf_bytes = download_response.content
                            filename = st.session_state.get('pdf_filename', 'filled_form.pdf')
                            if not filename.lower().endswith('_filled.pdf'):
                                filename = filename.replace('.pdf', '_filled.pdf')
                            
                            st.download_button(
                                label="📄 " + get_prompt('pdf_download_filled'),
                                data=pdf_bytes,
                                file_name=filename,
                                mime="application/pdf",
                                use_container_width=True
                            )
                            
                            st.success("✅ تم إنشاء ملف PDF بنجاح!")
                            
                            # Cleanup PDF session after download
                            try:
                                cleanup_response = requests.delete(
                                    f"{API_BASE_URL}/form/pdf-session/{st.session_state.pdf_session_id}"
                                )
                                if cleanup_response.status_code == 200:
                                    print("✅ PDF session cleaned up successfully after download")
                                    if 'pdf_session_id' in st.session_state:
                                        del st.session_state['pdf_session_id']
                                else:
                                    print(f"❌ Failed to cleanup PDF session: {cleanup_response.text}")
                            except Exception as cleanup_error:
                                print(f"❌ Error during PDF session cleanup: {cleanup_error}")
                                pass  # Ignore cleanup errors
                        else:
                            st.error(f"خطأ في تحميل PDF: {download_response.text}")
                    except Exception as e:
                        st.error(f"خطأ في تحميل PDF: {str(e)}")

        # =============================================================================
        # REGULAR IMAGE/SINGLE PDF WORKFLOW (only if not multipage)
        # =============================================================================
        elif not st.session_state.get('pdf_multipage_mode'):
            # Show continue button if quality check passed
            if st.session_state.get('show_continue') and not st.session_state.get('start_analysis'):
                ready_msg = "جاهز لتحليل النموذج..."
                st.write(ready_msg)
                if st.session_state.voice_enabled and st.session_state.get('session_id'):
                    speak(ready_msg, force_speak=True)
                if st.button("متابعة", use_container_width=True, key="continue_to_analysis"):
                    st.session_state.start_analysis = True
                    if st.session_state.voice_enabled and st.session_state.get('session_id'):
                        speak("بدء تحليل النموذج...", force_speak=True)
                    st.rerun()

            # Main Form Analysis Logic
            if st.session_state.get('start_analysis'):
                analysis_message = get_prompt('analyzing_form')
                
                with st.spinner(analysis_message):
                    if st.session_state.voice_enabled:
                        speak(analysis_message)

                    try:
                        # Store original image bytes for later use in live updates
                        image_bytes = uploaded_file.getvalue()
                        st.session_state.original_image_bytes = image_bytes
                        
                        # Analyze the form with the session ID
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
                            # Update session state with analysis results
                            st.session_state.update({
                                'ui_fields': data.get('fields', []),
                                'language_direction': data.get('language_direction', 'rtl'),
                                'image_width': data.get('image_width'),
                                'image_height': data.get('image_height'),
                                'form_data': {},
                                'current_field_index': 0,
                                'conversation_stage': 'filling_fields',
                                'show_continue': False
                            })
                            
                            # Analysis completed successfully
                            st.session_state.analysis_running = False
                            st.session_state.start_analysis = False
                            st.rerun()
                        else:
                            st.error(f"خطأ في تحليل النموذج: {response.text}")
                            st.session_state.analysis_running = False
                            st.session_state.start_analysis = False
                            st.session_state.show_continue = True
                            st.stop()
                    except Exception as e:
                        st.error(f"خطأ غير متوقع في التحليل: {str(e)}")
                        st.session_state.analysis_running = False
                        st.session_state.start_analysis = False
                        st.session_state.show_continue = True
                        st.stop()

    # =============================================================================
    # SHARED FORM FILLING LOGIC (used by both regular images and PDF pages)
    # =============================================================================
    stage = st.session_state.get('conversation_stage')
    ui_fields = st.session_state.get('ui_fields', [])
    current_index = st.session_state.get('current_field_index', 0)
    
    # Determine language direction for the current session
    lang_code = 'ar' if st.session_state.get('language_direction') == 'rtl' else 'en'

    # Form filling stages
    if stage == 'filling_fields' and not st.session_state.get('analysis_running'):
        if current_index < len(ui_fields):
            # Reset field counter when moving to a new field to clear audio recorder
            if 'last_field_index' not in st.session_state:
                st.session_state.last_field_index = current_index
                st.session_state.field_reset_counter = 0
            elif st.session_state.last_field_index != current_index:
                st.session_state.last_field_index = current_index
                st.session_state.field_reset_counter = st.session_state.get('field_reset_counter', 0) + 1
                # Clear any pending transcript when moving to new field
                if 'pending_transcript' in st.session_state:
                    del st.session_state.pending_transcript
            
            field = ui_fields[current_index]
            label, field_type = field['label'], field['type']
            prompt = get_prompt('checkbox_prompt', label=label) if field_type == 'checkbox' else get_prompt('text_prompt', label=label)
            st.info(prompt)
            if st.session_state.voice_enabled:
                speak(prompt)
            
            # Voice Input (Always available for non-signature fields)
            if not is_signature_field(label):
                # Voice input section
                voice_container = st.container()
                with voice_container:
                    st.markdown("اضغط للتحدث:")
                    
                    audio = audiorecorder(
                        "اضغط للتحدث",  
                        "جاري التسجيل... اضغط للإيقاف", 
                        key=f"audio_{current_index}_{st.session_state.get('field_reset_counter', 0)}"
                    )
                    
                    if len(audio) > 0:
                        with st.spinner(get_prompt('stt_spinner')):
                            wav_bytes = audio.export(format="wav").read()
                            transcript_response = speech_to_text(wav_bytes, lang_code)
                        if transcript_response:
                            transcript = transcript_response.get('text', '') if isinstance(transcript_response, dict) else str(transcript_response)
                            
                            skip_words = ['تجاوز', 'تخطي', 'skip', 'next']
                            if any(word in transcript.lower() for word in skip_words):
                                st.session_state.current_field_index += 1
                                st.session_state.field_reset_counter = st.session_state.get('field_reset_counter', 0) + 1
                                st.session_state.voice_settings['form_data'] = st.session_state.form_data
                                
                                if st.session_state.current_field_index >= len(ui_fields):
                                    st.session_state.conversation_stage = 'review'
                                st.rerun()
                            else:
                                st.session_state.pending_transcript = transcript
                                st.session_state.conversation_stage = 'confirmation'
                                st.rerun()
                        else: 
                            if len(audio.stream_data) > 0:
                                st.error(get_prompt('stt_error'))

            # Keyboard Input
            if not is_signature_field(label):
                st.markdown(f"**{get_prompt('or_type_prompt')}**")
            
            field_key = f"keyboard_input_{current_index}"
            if field_type == 'checkbox':
                current_value = st.session_state.form_data.get(field['box_id'], False)
                checkbox_value = st.checkbox(label, key=field_key, value=current_value)
                if checkbox_value != current_value:
                    st.session_state.form_data[field['box_id']] = checkbox_value
                    update_live_image()
            else:
                # Check if this is a signature field
                if is_signature_field(label):
                    st.markdown(f"**{get_prompt('upload_signature_prompt')}**")
                    signature_file = st.file_uploader(
                        "ارفع صورة التوقيع", 
                        type=["png", "jpg", "jpeg"], 
                        key=f"signature_{current_index}"
                    )
                    
                    if signature_file is not None:
                        signature_bytes = signature_file.read()
                        signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
                        st.session_state.signature_b64 = signature_b64
                        st.session_state.signature_field_id = field['box_id']
                        
                        update_live_image()
                        st.success("تم رفع التوقيع بنجاح!")
                        st.image(signature_bytes, caption="التوقيع المرفوع", width=200)
                else:
                    # Regular text field
                    current_value = st.session_state.form_data.get(field['box_id'], "")
                    text_value = st.text_input(label, key=field_key, value=current_value)
                    if text_value != current_value:
                        st.session_state.form_data[field['box_id']] = text_value
                        update_live_image()

            col1, col2 = st.columns([3, 1])
            if col1.button(get_prompt('save_and_next_button'), key=f"save_{current_index}", use_container_width=True):
                st.session_state.current_field_index += 1
                st.session_state.field_reset_counter = st.session_state.get('field_reset_counter', 0) + 1
                st.session_state.voice_settings['form_data'] = st.session_state.form_data
                
                if st.session_state.current_field_index >= len(ui_fields):
                    st.session_state.conversation_stage = 'review'
                st.rerun()
            elif col2.button(get_prompt('skip_button'), key=f"skip_{current_index}", use_container_width=True):
                st.session_state.current_field_index += 1
                st.session_state.field_reset_counter = st.session_state.get('field_reset_counter', 0) + 1
                st.session_state.voice_settings['form_data'] = st.session_state.form_data
                
                if st.session_state.current_field_index >= len(ui_fields):
                    st.session_state.conversation_stage = 'review'
                st.rerun()
        else:
            # All fields completed - move to review stage
            st.session_state.conversation_stage = 'review'
            st.rerun()

    if stage == 'confirmation':
        raw_transcript = st.session_state.get('pending_transcript', "")
        if not raw_transcript:
            st.session_state.conversation_stage = 'filling_fields'
            st.rerun()

        field = ui_fields[current_index]
        
        # Skip confirmation for signature fields
        if is_signature_field(field['label']):
            st.session_state.conversation_stage = 'filling_fields'
            st.rerun()
        
        # Confirmation display logic
        if field['type'] == 'checkbox':
            positive_words = ['نعم', 'أجل', 'حدد', 'صح', 'تمام', 'yes', 'check', 'ok', 'correct', 'right']
            is_positive = any(word in raw_transcript.lower() for word in positive_words)
            display_transcript = get_prompt('checkbox_checked') if is_positive else get_prompt('checkbox_unchecked')
        else:
            display_transcript = raw_transcript
        
        st.info(get_prompt('heard_you_say', transcript=display_transcript))
        if st.session_state.voice_enabled:
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
            st.session_state.field_reset_counter = st.session_state.get('field_reset_counter', 0) + 1
            
            if st.session_state.current_field_index >= len(ui_fields):
                st.session_state.conversation_stage = 'review'
            else:
                st.session_state.conversation_stage = 'filling_fields'
            st.rerun()
        if col2.button(get_prompt('retry_button'), key=f"retry_{current_index}", use_container_width=True):
            st.session_state.field_reset_counter = st.session_state.get('field_reset_counter', 0) + 1
            if st.session_state.voice_enabled:
                speak(get_prompt('retry_prompt'))
            st.session_state.conversation_stage = 'filling_fields'
            st.rerun()

    if stage == 'review':
        # Only show review for regular images (PDF has its own review in the PDF workflow)
        if not st.session_state.get('pdf_multipage_mode'):
            review_message = get_prompt('review_prompt')
            if st.session_state.voice_enabled:
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
                            "ui_fields": st.session_state.get('ui_fields', []),
                            "signature_image_b64": st.session_state.get("signature_b64"),
                            "signature_field_id": st.session_state.get("signature_field_id")
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

if __name__ == "__main__":
    main()
