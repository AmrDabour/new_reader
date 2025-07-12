from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import routers for different services
from app.routers import form_analyzer, money_reader, document_reader
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Insight - Unified AI Services API",
    description="Unified API combining form analysis, currency reading, and document analysis",
    version="2.0.0"
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

@app.get("/")
async def root():
    """Main API endpoint"""
    return {
        "message": "Welcome to Insight - Unified AI Services",
        "services": [
            {
                "name": "Form Analyzer",
                "description": "Analyze forms and extract fillable fields",
                "prefix": "/form"
            },
            {
                "name": "Money Reader", 
                "description": "Analyze currencies and banknotes",
                "prefix": "/money"
            },
            {
                "name": "Document Reader",
                "description": "Read and analyze PowerPoint and PDF files",
                "prefix": "/document"
            }
        ]
    } 