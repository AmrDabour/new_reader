from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers for different services
from app.routers import form_analyzer, money_reader, document_reader, shared

app = FastAPI(
    title="Insight - Unified AI Services API",
    description="API موحد يجمع تحليل النماذج وقراءة العملات وتحليل المستندات"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(form_analyzer.router, prefix="/form", tags=["Form Analyzer"])
app.include_router(money_reader.router, prefix="/money", tags=["Money Reader"])
app.include_router(document_reader.router, prefix="/document", tags=["Document Reader"])
app.include_router(shared.router, tags=["Shared Services"])

@app.get("/")
async def root():
    """الصفحة الرئيسية للـ API الموحد"""
    return {
        "message": "مرحباً بك في Insight - خدمات الذكاء الاصطناعي الموحدة",
        "services": [
            {
                "name": "Form Analyzer",
                "description": "تحليل النماذج واستخراج الحقول القابلة للتعبئة",
                "prefix": "/form"
            },
            {
                "name": "Money Reader", 
                "description": "تحليل العملات والأوراق النقدية",
                "prefix": "/money"
            },
            {
                "name": "Document Reader",
                "description": "قراءة وتحليل ملفات PowerPoint والـ PDF",
                "prefix": "/document"
            }
        ]
    } 