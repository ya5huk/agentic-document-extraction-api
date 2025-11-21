from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging
from pathlib import Path

from app.models import ExtractionRequest, ExtractionResponse, HealthResponse
from services.browser_service import BrowserService
from services.s3_service import S3Service

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
# If in production, restrict origins appropriately (use environment variables)
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

    Workflow:
    1. Initialize browser service with Gemini AI
    2. Navigate to URL and download all PDFs
    3. Upload PDFs to S3 bucket with specified prefix
    4. Clean up temporary files
    5. Return list of S3 URIs

    Args:
        request: ExtractionRequest containing URL and S3 configuration

    Returns:
        ExtractionResponse: Status and list of uploaded S3 file paths

    Raises:
        HTTPException: If extraction or upload fails
    """
    logger.info("=" * 70)
    logger.info(f"Extraction requested for URL: {request.url}")
    logger.info(f"S3 Bucket: {request.s3_bucket}")
    logger.info(f"S3 Prefix: {request.s3_prefix}")
    logger.info("=" * 70)

    browser_service = None
    downloaded_files = []

    try:
        # Step 1: Initialize browser service
        logger.info("Step 1: Initializing browser service...")
        browser_service = BrowserService(
            download_dir="./downloads",
            headless=True,  # Run in headless mode for production
            timeout=120
        )
        logger.info("✓ Browser service initialized")

        # Step 2: Download PDFs from URL
        logger.info(f"\nStep 2: Downloading PDFs from {request.url}...")
        downloaded_files = await browser_service.find_and_download_pdfs(request.url)

        if not downloaded_files:
            logger.warning("No PDF files were found or downloaded")
            return ExtractionResponse(
                status="success",
                files=[],
                message="No PDF files found on the specified URL"
            )

        logger.info(f"✓ Downloaded {len(downloaded_files)} PDF(s)")

        # Step 3: Initialize S3 service and upload files
        logger.info(f"\nStep 3: Uploading {len(downloaded_files)} PDFs to S3...")
        s3_service = S3Service()

        # Upload all PDFs to S3
        s3_uris = s3_service.upload_multiple_files(
            file_paths=downloaded_files,
            bucket=request.s3_bucket,
            s3_prefix=request.s3_prefix
        )

        logger.info(f"✓ Uploaded {len(s3_uris)} file(s) to S3")

        # Step 4: Clean up temporary files
        logger.info("\nStep 4: Cleaning up temporary files...")
        cleanup_count = 0
        for file_path in downloaded_files:
            try:
                Path(file_path).unlink()
                cleanup_count += 1
                logger.debug(f"Deleted: {Path(file_path).name}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

        logger.info(f"✓ Cleaned up {cleanup_count}/{len(downloaded_files)} temporary file(s)")

        # Step 5: Return success response
        logger.info("\n" + "=" * 70)
        logger.info("✓ Extraction completed successfully!")
        logger.info(f"Total files uploaded: {len(s3_uris)}")
        for uri in s3_uris:
            logger.info(f"  - {uri}")
        logger.info("=" * 70)

        return ExtractionResponse(
            status="success",
            files=s3_uris,
            message=f"Successfully extracted and uploaded {len(s3_uris)} PDF(s)"
        )

    except ValueError as e:
        # Handle validation errors (missing credentials, invalid bucket, etc.)
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Handle all other errors
        logger.error(f"Extraction failed: {str(e)}")
        logger.exception("Full error traceback:")

        # Attempt cleanup on error
        if downloaded_files:
            logger.info("Attempting cleanup of downloaded files...")
            for file_path in downloaded_files:
                try:
                    if Path(file_path).exists():
                        Path(file_path).unlink()
                        logger.debug(f"Cleaned up: {Path(file_path).name}")
                except Exception as cleanup_error:
                    logger.warning(f"Cleanup failed for {file_path}: {cleanup_error}")

        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )

    finally:
        # Always close browser service
        if browser_service:
            await browser_service.close()


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
