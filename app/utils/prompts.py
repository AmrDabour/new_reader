PROMPTS = {
    'greeting': {
        'rtl': "أهلاً بك! سأساعدك في ملء هذا النموذج. لنبدأ بالبيان الأول",
        'ltr': "Hello! I will help you fill out this form. Let's start with the first field"
    },
    'checkbox_prompt': {
        'rtl': "هل تريد تحديد خانة '{label}'؟ قل نعم أو لا",
        'ltr': "Do you want to check the box for '{label}'? Please say yes or no"
    },
    'text_prompt': {
        'rtl': "من فضلك، أدخل البيانات الخاصة بـ '{label}'",
        'ltr': "Please, provide the information for '{label}'"
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
        'rtl': "لقد انتهينا من تعبئة كل البيانات. ماذا تريد أن تفعل الآن؟ يمكنك أن تقول 'مراجعة'، 'تنزيل صورة'، أو 'تنزيل PDF'",
        'ltr': "We have finished filling all the fields. What would you like to do now? You can say 'review', 'download image', or 'download PDF'"
    },
    'command_error': {
        'rtl': "لم أفهم طلبك. من فضلك قل 'مراجعة'، 'تنزيل صورة'، أو 'تنزيل PDF'",
        'ltr': "I didn't understand your request. Please say 'review', 'download image', or 'download PDF'"
    },
    'review_prompt': {
        'rtl': "النموذج جاهز. يمكنك مراجعته وتنزيله من الأدوات أدناه",
        'ltr': "The form is ready. You can review and download it from the tools below"
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
    'preview_caption': {
        'rtl': "معاينة النموذج المعبأ",
        'ltr': "Preview of the filled form"
    },
    'speak_button_label': {
        'rtl': "اضغط للتحدث",
        'ltr': "Click to Speak"
    },
    'recording_button_label': {
        'rtl': "جاري التسجيل... اضغط مرة أخرى للإيقاف",
        'ltr': "Recording... Click again to STOP"
    },
    'stt_spinner': {
        'rtl': "جاري تحويل الصوت إلى نص...",
        'ltr': "Transcribing audio..."
    },
    'command_spinner': {
        'rtl': "جاري تحليل طلبك...",
        'ltr': "Analyzing your command..."
    },
    'confirmation_prompt': {
        'rtl': "هل تقصد؟\n{transcript}",
        'ltr': "Did you mean?\n{transcript}"
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
    'confirmation_error_prompt': {
        'rtl': "لم أفهم، من فضلك قل 'نعم' أو 'لا'.",
        'ltr': "I didn't understand. Please say 'yes' or 'no'."
    },
    'confirm_button': {
        'rtl': "تأكيد",
        'ltr': "Confirm"
    },
    'retry_button': {
        'rtl': "إعادة المحاولة",
        'ltr': "Retry"
    },
    'confirmation_prompt_no_voice': {
        'rtl': "هل هذا صحيح؟",
        'ltr': "Is this correct?"
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
        'rtl': "تفعيل المساعد الصوتي",
        'ltr': "Enable Voice Assistant"
    }
}

def get_prompt(key: str, **kwargs) -> str:
    """
    Gets the prompt in the correct language based on the language direction
    """
    language_direction = kwargs.pop('language_direction', 'ltr')
    prompt_template = PROMPTS.get(key, {}).get(language_direction, f"Missing prompt for key: {key}")
    return prompt_template.format(**kwargs) 