from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers for different services
from app.routers import form_analyzer, document_reader, page_image
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Insight - Unified AI Services API",
    description="Unified API combining form analysis and document analysis",
    version="2.0.0",
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
app.include_router(document_reader.router, prefix="/document", tags=["Document Reader"])
app.include_router(page_image.router, prefix="/document", tags=["Page Images"])


@app.get("/")
async def root():
    """Main API endpoint"""
    return {
        "message": "Welcome to Insight - Unified AI Services",
        "services": [
            {
                "name": "Form Analyzer",
                "description": "Analyze forms and extract fillable fields",
                "prefix": "/form",
            },
            {
                "name": "Document Reader",
                "description": "Read and analyze PowerPoint and PDF files",
                "prefix": "/document",
            },
        ],
    }
