# Form Analyzer - AI-Powered Form Reading System

نظام ذكي لتحليل وقراءة النماذج مع دعم خاص لمساعدة المكفوفين وضعاف البصر.

## 🌟 المميزات الرئيسية

### 📋 تحليل النماذج (Form Analysis)

- **تحليل ذكي للنماذج**: صور ومستندات PDF متعددة الصفحات
- **شرح تفاعلي**: توضيح محتوى النماذج صوتياً
- **تعبئة موجهة**: مساعدة في ملء الحقول خطوة بخطوة
- **دعم متعدد اللغات**: العربية والإنجليزية مع معالجة RTL

### 🔊 المساعدات الصوتية

- **تحويل النص إلى كلام (TTS)**: قراءة المحتوى بوضوح
- **تحويل الكلام إلى نص (STT)**: إدخال البيانات صوتياً
- **تنقل صوتي**: التحكم في التطبيق عبر الأوامر الصوتية

### 📱 واجهات متعددة

- **Streamlit UI**: واجهة ويب تفاعلية
- **FastAPI Backend**: API موثق ومرن
- **Flutter Mobile**: تطبيق جوال (ملفات جاهزة للتطوير)
- **REST API**: لدمج النظام مع تطبيقات أخرى

### 🔧 تقنيات متقدمة

- **معالجة الصور**: OpenCV و PIL
- **ذكاء اصطناعي**: Google Gemini
- **OCR**: Tesseract مع دعم العربية
- **تحليل النصوص**: معالجة متقدمة للغة العربية

## 🚀 التثبيت السريع

### ⚡ طريقة سريعة (Windows)

```powershell
# تشغيل سكريبت الإعداد التلقائي
.\setup.ps1
```

أو استخدم:

```cmd
# تشغيل سكريبت إعداد Command Prompt
setup.bat
```

### 📋 التثبيت اليدوي

```bash
# 1. استنساخ المشروع
git clone <your-repo>
cd new_reader

# 2. إنشاء بيئة افتراضية (مُوصى)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# تثبيت المتطلبات
pip install -r requirements.txt

# 3. تثبيت المتطلبات
pip install -r requirements.txt

# 4. إعداد متغيرات البيئة (اختياري)
# إنشاء ملف .env
GOOGLE_API_KEY=your_gemini_api_key_here
API_BASE_URL=http://127.0.0.1:8000
```

### 🐳 استخدام Docker

```bash
# تشغيل المشروع بـ Docker
docker-compose up -d

# عرض الـ logs
docker-compose logs -f
```

## 🎯 التشغيل

### 1. واجهة Streamlit (مُوصى للاختبار)

```bash
streamlit run ui.py --server.port 8501
```

الوصول: `http://localhost:8501`

### 2. FastAPI Backend فقط

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

الوصول:

- API: `http://localhost:8000`
- توثيق API: `http://localhost:8000/docs`

### 3. استخدام المهمة المحددة مسبقاً

```bash
# من VS Code Terminal
> Tasks: Run Task > "Run Form Analyzer with PDF Support"
```

## 📱 تطوير تطبيق Flutter

تم توفير ملفات Flutter جاهزة للتطوير:

```
flutter_screens.dart      # شاشات التطبيق
flutter_api_services.dart # خدمات API
flutter_main_app.dart     # التطبيق الرئيسي
```

للمزيد من التفاصيل، راجع: **FLUTTER_IMPLEMENTATION_GUIDE.md**

## 📚 التوثيق

| ملف | الوصف |
|-----|--------|
| `README.md` | دليل عام للمشروع |
| `SETUP_GUIDE.md` | دليل تفصيلي للإعداد |
| `API_DETAILED_DOCUMENTATION.md` | توثيق API كامل |
| `FLUTTER_IMPLEMENTATION_GUIDE.md` | دليل تطوير Flutter |
| `UI_FLOW_DETAILED_GUIDE.md` | مخطط سير العمل |

## 🛠️ الاستخدام

### 📋 تحليل النماذج

1. **رفع النموذج**: صورة أو PDF
2. **الاستكشاف**: فهم محتوى النموذج
3. **الشرح**: شرح تفصيلي لكل صفحة/قسم
4. **التحليل**: تحديد الحقول القابلة للتعبئة
5. **التعبئة**: ملء الحقول بالصوت أو النص
6. **المراجعة**: مراجعة وتنزيل النموذج المكتمل

### 🎙️ الأوامر الصوتية

- **"نعم" / "لا"**: للحقول المربعة
- **محتوى نصي**: للحقول النصية
- **"التالي"**: الانتقال للحقل التالي
- **"السابق"**: العودة للحقل السابق
- **"إنهاء"**: إنهاء التعبئة

## 🔧 إعدادات متقدمة

### متغيرات البيئة

```env
# إعدادات API
GOOGLE_API_KEY=your_gemini_api_key
API_BASE_URL=http://127.0.0.1:8000

# إعدادات التشغيل
DEBUG=true
MAX_FILE_SIZE=10MB
SESSION_TIMEOUT=30

# إعدادات OCR
TESSDATA_PREFIX=/path/to/tessdata
```

### إعدادات Tesseract OCR

```bash
# Windows: تحميل وتثبيت من
# https://github.com/UB-Mannheim/tesseract/wiki

# Linux
sudo apt-get install tesseract-ocr tesseract-ocr-ara

# macOS  
brew install tesseract tesseract-lang
```

## التكوين

أنشئ ملف `.env` واملأ البيانات التالية:

```env
# مطلوب
GOOGLE_AI_API_KEY=your_google_ai_api_key_here

# اختياري
TESSERACT_CMD=/usr/bin/tesseract  # Linux
# TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe  # Windows

PORT=10000
GEMINI_MODEL=gemini-2.5-flash
MAX_FILE_SIZE_MB=50
IMAGE_QUALITY=2
MAX_IMAGE_SIZE=1920
```

## 🏃‍♂️ تشغيل التطبيق

### تشغيل محلي

```bash
# تشغيل الخادم
uvicorn app.main:app --reload --host 0.0.0.0 --port 10000

# أو استخدام script التشغيل
python run.py
```

### تشغيل بـ Docker

```bash
docker-compose up
```

الـ API ستعمل على: `http://localhost:10000`

## استخدام الـ API

### Form Analyzer Endpoints

```bash
# تحليل نموذج
curl -X POST "http://localhost:10000/form/analyze" \
  -H "Content-Type: multipart/form-data" \
  -F "image=@form.png" \
  -F "language=rtl"

# إضافة تعليقات على النموذج
curl -X POST "http://localhost:10000/form/annotate" \
  -H "Content-Type: multipart/form-data" \
  -F "image=@form.png" \
  -F "language=rtl" \
  -F 'fields=[{"id":1,"label":"الاسم","valid":true}]'
```

### Document Reader Endpoints

```bash
# رفع مستند
curl -X POST "http://localhost:10000/document/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "language=arabic"

# قراءة صفحة
curl "http://localhost:10000/document/{session_id}/page/1"

# التنقل
curl -X POST "http://localhost:10000/document/{session_id}/navigate" \
  -H "Content-Type: application/json" \
  -d '{"command": "التالي"}'
```

### Shared Services

```bash
# تحويل نص إلى كلام
curl -X POST "http://localhost:10000/text-to-speech" \
  -H "Content-Type: application/json" \
  -d '{"text": "مرحبا", "provider": "gemini"}'

# تحويل كلام إلى نص
curl -X POST "http://localhost:10000/speech-to-text" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@speech.wav"
```

## الاختبار

```bash
# تشغيل جميع الاختبارات
python test_api.py

# اختبار خدمة محددة
python test_api.py --endpoint form
python test_api.py --endpoint document
python test_api.py --endpoint shared

# اختبار على خادم مختلف
python test_api.py --url http://your-server.com
```

## النشر على Render

1. **رفع الكود إلى GitHub**
2. **ربط المستودع بـ Render**
3. **استخدام `render.yaml` للتكوين التلقائي**
4. **إضافة `GOOGLE_AI_API_KEY` في إعدادات البيئة**

أو استخدام Render CLI:

```bash
render deploy
```

## هيكل المشروع

```
insight/
├── app/
│   ├── main.py              # تطبيق FastAPI الرئيسي
│   ├── config.py            # إعدادات التطبيق
│   ├── models/
│   │   ├── schemas.py       # نماذج Pydantic
│   │   ├── boxes.pt         # نموذج YOLO للصناديق
│   │   └── dot_line.pt      # نموذج YOLO للخطوط
│   ├── services/
│   │   ├── gemini.py        # خدمة Gemini AI موحدة
│   │   ├── speech.py        # خدمة الكلام
│   │   ├── yolo.py          # خدمة YOLO
│   │   ├── image.py         # معالجة الصور
│   │   ├── ocr.py           # خدمة OCR
│   │   └── document_processor.py  # معالج المستندات
│   ├── routers/
│   │   ├── form_analyzer.py    # endpoints Form Analyzer
│   │   ├── document_reader.py  # endpoints Document Reader
│   │   └── shared.py          # endpoints المشتركة
│   └── utils/
│       ├── arabic.py           # أدوات اللغة العربية
│       ├── text.py            # أدوات النصوص
│       └── image_helpers.py   # مساعدات الصور
├── Dockerfile              # ملف Docker
├── docker-compose.yml      # تكوين Docker Compose
├── render.yaml            # تكوين Render
├── requirements.txt       # متطلبات Python
├── test_api.py           # اختبارات شاملة
├── .env.example          # مثال ملف البيئة
└── README.md             # هذا الملف
```

## التخصيص

### إضافة نماذج جديدة

عدل `app/models/schemas.py` لإضافة نماذج Pydantic جديدة.

### إضافة خدمات جديدة

أضف خدمات في `app/services/` واستوردها في `app/main.py`.

### إضافة endpoints جديدة

أنشئ routers جديدة في `app/routers/` وأضفها للتطبيق الرئيسي.

## 🐛 استكشاف الأخطاء

### مشاكل شائعة

- **API Key غير صحيح**: تأكد من إضافة Google AI API Key في `.env`
- **Tesseract غير موجود**: ثبت Tesseract OCR وحدد المسار الصحيح
- **مشاكل الأذونات**: تأكد من أذونات القراءة/الكتابة للمجلدات

### سجلات الأخطاء

```bash
# عرض السجلات في Docker
docker-compose logs -f

# عرض سجلات خدمة محددة
docker-compose logs insight-api
```

## 📞 الدعم

للحصول على المساعدة:

1. تحقق من سجلات الأخطاء
2. تأكد من تكوين المتطلبات بشكل صحيح
3. استخدم ملف الاختبار للتأكد من عمل الـ endpoints

## الترخيص

هذا المشروع تحت رخصة MIT.
