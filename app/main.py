from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from contextlib import asynccontextmanager

# Import routers for different services
from app.routers import form_analyzer, money_reader, document_reader
from app.config import get_settings
from app.services.keep_alive import keep_alive_service

settings = get_settings()

# Session cleanup background task
async def cleanup_sessions_periodically():
    """Background task to clean up expired sessions every 30 minutes"""
    from app.routers.form_analyzer import session_service
    while True:
        await asyncio.sleep(1800)  # 30 minutes
        try:
            session_service.cleanup_expired_sessions()
        except Exception as e:
            # Log error silently
            pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - session management enabled
    
    # Start background task for session cleanup
    cleanup_task = asyncio.create_task(cleanup_sessions_periodically())
    
    # Start keep-alive service
    base_url = str(settings.base_url).rstrip('/')
    await keep_alive_service.start(f"{base_url}/health")
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    await keep_alive_service.stop()

app = FastAPI(
    title="Insight - Unified AI Services API",
    description="API موحد يجمع تحليل النماذج وقراءة العملات وتحليل المستندات",
    version="2.0.0",
    lifespan=lifespan
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
app.include_router(form_analyzer.router)
app.include_router(money_reader.router, prefix="/money", tags=["Money Reader"])
app.include_router(document_reader.router, prefix="/document", tags=["Document Reader"])

@app.get("/health")
async def health_check():
    """نقطة نهاية للتحقق من صحة التطبيق"""
    return {"status": "healthy", "timestamp": keep_alive_service.last_heartbeat}

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