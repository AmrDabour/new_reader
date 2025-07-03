"""
Form Reader Application - Flutter Development Reference

This Streamlit application demonstrates the following key features for Flutter implementation:

1. Image Upload and Processing:
   - Accept image files (jpg, png, jpeg, bmp, pdf)
   - Send images to backend API for analysis
   - Display live preview of annotated forms

2. Voice Input (Speech-to-Text):
   - Record audio from microphone
   - Convert speech to text via API
   - Support for Arabic and English languages

3. Voice Output (Text-to-Speech):
   - Convert text prompts to speech
   - Optional voice guidance for users

4. Form Field Processing:
   - Text fields with keyboard/voice input
   - Checkbox fields
   - Signature fields with image upload
   - Live form preview updates

5. API Integration:
   - POST /form/check-image (quality check)
   - POST /form/analyze-form (field detection) 
   - POST /form/annotate-image (final form generation)
   - POST /form/text-to-speech (voice output)
   - POST /form/speech-to-text (voice input)

6. Session Management:
   - Maintain form state across interactions
   - Handle field navigation and validation

Key Flutter Packages Needed:
- http (API calls)
- image_picker (image selection)
- speech_to_text (voice input)
- flutter_tts (voice output) 
- file_picker (file operations)

Backend API Base URL: {API_BASE_URL}
"""

import streamlit as st
import requests
import base64
from PIL import Image
import io
import os
import json
import re
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
            payload = {
                "original_image_b64": base64.b64encode(st.session_state.original_image_bytes).decode('utf-8'),
                "texts_dict": st.session_state.get('form_data', {}),
                "ui_fields": st.session_state.get('ui_fields', []),
                "signature_image_b64": st.session_state.get("signature_b64"), # إضافة التوقيع
                "signature_field_id": st.session_state.get("signature_field_id") # إضافة معرف حقل التوقيع
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

def main():
    # UI Configuration
    st.set_page_config(layout="wide")

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

    # Voice Assistant Toggle - Make it prominent
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
        if voice_enabled:
            speak("تم تفعيل قراءة الإرشادات صوتياً", force_speak=True)
    
    st.info("ملاحظة: المايك للإدخال الصوتي متاح دائماً في جميع الحقول")
    st.divider()

    # Form Reader Section
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
                
                # Start analysis immediately for the new file
                with st.spinner("جاري فحص الصورة..."):
                    try:
                        # First, check image quality
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        quality_response = requests.post(f"{API_BASE_URL}/form/check-image", files=files)
                        
                        if quality_response.status_code == 200:
                            quality_data = quality_response.json()
                            
                            # Store all necessary data in session state
                            st.session_state.update({
                                'session_id': quality_data.get('session_id'),
                                'language_direction': quality_data.get('language_direction', 'rtl'),
                                'image_width': quality_data.get('image_width'),
                                'image_height': quality_data.get('image_height'),
                                'form_explanation': quality_data.get('form_explanation', ''),
                                'quality_data': quality_data,
                                'show_continue': True  # Enable continue button
                            })
                            
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

            # Show continue button if quality check passed
            if st.session_state.show_continue and not st.session_state.start_analysis:
                ready_msg = "جاهز لتحليل النموذج..."
                st.write(ready_msg)
                if st.session_state.voice_enabled:
                    speak(ready_msg, force_speak=True)
                if st.button("متابعة", use_container_width=True, key="continue_to_analysis"):
                    st.session_state.start_analysis = True
                    if st.session_state.voice_enabled:
                        speak("بدء تحليل النموذج...", force_speak=True)
                    st.rerun()

            # --- Main Form Analysis Logic ---
            if st.session_state.get('start_analysis'):
                # Start form analysis immediately
                analysis_message = get_prompt('analyzing_form')
                with st.spinner(analysis_message):
                    if st.session_state.voice_enabled:
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
                            # Update session state with analysis results
                            st.session_state.update({
                                'ui_fields': data.get('fields', []),
                                'language_direction': data.get('language_direction', 'rtl'),
                                'image_width': data.get('image_width'),
                                'image_height': data.get('image_height'),
                                'form_data': {},
                                'current_field_index': 0,
                                'conversation_stage': 'filling_fields',
                                'show_continue': False  # Hide continue button after analysis
                            })
                            
                            # Store analysis data for future use
                            st.session_state.voice_settings['last_analysis'] = {
                                'ui_fields': st.session_state.ui_fields,
                                'language_direction': st.session_state.language_direction,
                                'image_width': st.session_state.image_width,
                                'image_height': st.session_state.image_height,
                                'conversation_stage': st.session_state.conversation_stage,
                                'current_field_index': st.session_state.current_field_index,
                                'original_image_bytes': st.session_state.original_image_bytes,
                                'session_id': st.session_state.session_id
                            }
                            
                            # Analysis completed successfully
                            st.session_state.analysis_running = False
                            st.session_state.start_analysis = False
                            st.rerun()
                        else:
                            st.error(f"خطأ في تحليل النموذج: {response.text}")
                            st.session_state.analysis_running = False
                            st.session_state.start_analysis = False
                            st.session_state.show_continue = True  # Show continue button again on error
                            st.stop()
                    except Exception as e:
                        st.error(f"خطأ غير متوقع في التحليل: {str(e)}")
                        st.session_state.analysis_running = False
                        st.session_state.start_analysis = False
                        st.session_state.show_continue = True  # Show continue button again on error
                        st.stop()

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
            
            if stage == 'filling_fields' and not st.session_state.get('analysis_running'):
                if current_index < len(ui_fields):
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
                            # Make the audio recorder smaller and less prominent
                            st.markdown("""
                                <style>
                                    .stAudio {
                                        display: none;
                                    }
                                    .streamlit-expanderHeader {
                                        display: none;
                                    }
                                </style>
                            """, unsafe_allow_html=True)
                            
                            audio = audiorecorder(
                                "اضغط للتحدث",  
                                "جاري التسجيل... اضغط للإيقاف", 
                                key=f"audio_{current_index}"
                            )
                            
                            if len(audio) > 0:
                                with st.spinner(get_prompt('stt_spinner')):
                                    wav_bytes = audio.export(format="wav").read()
                                    transcript_response = speech_to_text(wav_bytes, lang_code)
                                if transcript_response:
                                    # Extract the actual transcript text from the response
                                    transcript = transcript_response.get('text', '') if isinstance(transcript_response, dict) else str(transcript_response)
                                    
                                    skip_words = ['تجاوز', 'تخطي', 'skip', 'next']
                                    if any(word in transcript.lower() for word in skip_words):
                                        st.session_state.current_field_index += 1
                                        # Update stored form data
                                        st.session_state.voice_settings['form_data'] = st.session_state.form_data
                                        st.rerun()
                                    else:
                                        st.session_state.pending_transcript = transcript
                                        st.session_state.conversation_stage = 'confirmation'
                                        st.rerun()
                                else: 
                                    if len(audio.stream_data) > 0:
                                        st.error(get_prompt('stt_error'))

                    # Keyboard Input - only show text input options for non-signature fields
                    if not is_signature_field(label):
                        st.markdown(f"**{get_prompt('or_type_prompt')}**")
                    
                    field_key = f"keyboard_input_{current_index}"
                    if field_type == 'checkbox':
                        current_value = st.session_state.form_data.get(field['box_id'], False)
                        checkbox_value = st.checkbox(label, key=field_key, value=current_value)
                        # Update form data immediately when checkbox changes
                        if checkbox_value != current_value:
                            st.session_state.form_data[field['box_id']] = checkbox_value
                            update_live_image()
                    else:
                        # Check if this is a signature field
                        if is_signature_field(label):
                            # This is a signature field - show signature upload instead of text input
                            st.markdown(f"**{get_prompt('upload_signature_prompt')}**")
                            signature_file = st.file_uploader(
                                "ارفع صورة التوقيع", 
                                type=["png", "jpg", "jpeg"], 
                                key=f"signature_{current_index}"
                            )
                            
                            if signature_file is not None:
                                # Convert signature to base64 and store it
                                signature_bytes = signature_file.read()
                                signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
                                st.session_state.signature_b64 = signature_b64
                                
                                # Store the signature field box_id for the backend to know where to place it
                                st.session_state.signature_field_id = field['box_id']
                                
                                # Don't put any text in form_data for signature fields
                                # The backend will handle placing the signature image
                                
                                # Update live image with signature
                                update_live_image()
                                
                                # Show success message
                                st.success("تم رفع التوقيع بنجاح!")
                                
                                # Show preview of uploaded signature
                                st.image(signature_bytes, caption="التوقيع المرفوع", width=200)
                        else:
                            # Regular text field
                            current_value = st.session_state.form_data.get(field['box_id'], "")
                            text_value = st.text_input(label, key=field_key, value=current_value)
                            # Update form data if text has changed
                            if text_value != current_value:
                                st.session_state.form_data[field['box_id']] = text_value
                                update_live_image()

                    col1, col2 = st.columns([3, 1])
                    if col1.button(get_prompt('save_and_next_button'), key=f"save_{current_index}", use_container_width=True):
                        # Move to next field
                        st.session_state.current_field_index += 1
                        # Update stored form data
                        st.session_state.voice_settings['form_data'] = st.session_state.form_data
                        st.rerun()
                    if col2.button(get_prompt('skip_button'), key=f"skip_{current_index}", use_container_width=True):
                        st.session_state.current_field_index += 1
                        # Update stored form data
                        st.session_state.voice_settings['form_data'] = st.session_state.form_data
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
                
                # Skip confirmation for signature fields since they use file upload
                if is_signature_field(field['label']):
                    st.session_state.conversation_stage = 'filling_fields'
                    st.rerun()
                
                # Confirmation display logic (now using the form's language)
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
                    st.session_state.conversation_stage = 'filling_fields'
                    st.rerun()
                if col2.button(get_prompt('retry_button'), key=f"retry_{current_index}", use_container_width=True):
                    if st.session_state.voice_enabled:
                        speak(get_prompt('retry_prompt'))
                    st.session_state.conversation_stage = 'filling_fields'
                    st.rerun()

            elif stage == 'review':
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