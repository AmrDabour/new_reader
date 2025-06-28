# Insight - Unified AI Analysis Platform

مشروع موحد يجمع ثلاث خدمات ذكية في منصة واحدة:
- **Form Analyzer** - تحليل وقراءة النماذج للمكفوفين
- **Money Reader** - قراءة العملات بالصوت السعودي
- **Document Reader** - قراءة ملفات PowerPoint و PDF

## المميزات

### Form Analyzer
- تحليل النماذج وشرح محتواها
- تحديد الحقول القابلة للتعبئة
- إضافة تعليقات صوتية على النماذج
- دعم العربية والإنجليزية

### Money Reader
- تحليل صور العملات
- رد بالهجة السعودية الخليجية
- تحديد القيم والمجاميع

### Document Reader
- رفع ملفات PowerPoint و PDF
- التنقل بين الصفحات صوتياً
- تحليل المحتوى بالذكاء الاصطناعي
- أوامر التنقل باللغة العربية

### الخدمات المشتركة
- تحويل النص إلى كلام (TTS)
- تحويل الكلام إلى نص (STT)
- معالجة الصور والمستندات

## المتطلبات

- Python 3.11+
- Google AI API Key (Gemini)
- Tesseract OCR
- Docker (اختياري)

## ⚙️ التثبيت

### 1. التثبيت المحلي

```bash
# استنساخ المشروع
git clone <your-repo>
cd insight

# إنشاء بيئة افتراضية
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# تثبيت المتطلبات
pip install -r requirements.txt

# إنشاء ملف .env
cp .env.example .env
# عدل الملف وأضف Google AI API Key
```

### 2. باستخدام Docker

```bash
# إنشاء ملف .env أولاً
echo "GOOGLE_AI_API_KEY=your_api_key_here" > .env

# تشغيل بـ Docker Compose
docker-compose up --build

# أو تشغيل Docker فقط
docker build -t insight-api .
docker run -p 10000:10000 --env-file .env insight-api
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

### Money Reader Endpoints

```bash
# تحليل عملة
curl -X POST "http://localhost:10000/money/analyze" \
  -H "Content-Type: multipart/form-data" \
  -F "image=@currency.jpg"
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
python test_api.py --endpoint money
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
│   │   ├── money_reader.py     # endpoints Money Reader  
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