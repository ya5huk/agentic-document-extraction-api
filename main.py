from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging

from app.models import ExtractionRequest, ExtractionResponse, HealthResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Agentic Document Extraction API",
    description="API service for autonomous PDF extraction from procurement websites",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify API is running.

    Returns:
        HealthResponse: Status and version information
    """
    logger.info("Health check requested")
    return HealthResponse(status="healthy", version="1.0.0")


@app.post("/extract", response_model=ExtractionResponse, tags=["Extraction"])
async def extract_pdfs(request: ExtractionRequest):
    """
    Extract PDFs from the provided URL and upload to S3.

    Args:
        request: ExtractionRequest containing URL and S3 configuration

    Returns:
        ExtractionResponse: Status and list of uploaded file paths

    Raises:
        HTTPException: If extraction fails
    """
    logger.info(f"Extraction requested for URL: {request.url}")

    try:
        # TODO: Implement browser automation and PDF extraction
        # TODO: Implement S3 upload

        # Placeholder response
        return ExtractionResponse(
            status="pending",
            files=[],
            message="Extraction functionality will be implemented in Phase 5 & 6"
        )

    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        dict: Welcome message and documentation links
    """
    return {
        "message": "Agentic Document Extraction API",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
