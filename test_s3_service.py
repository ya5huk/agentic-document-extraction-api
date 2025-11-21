"""
Test Script for S3 Service

This script tests the S3Service functionality with a dummy PDF file.
Run this after setting up your .env file with AWS credentials.

Usage:
    python test_s3_service.py <bucket_name> [prefix]

Example:
    python test_s3_service.py my-test-bucket test/

Requirements:
    - .env file with AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    - An accessible S3 bucket for testing
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from services.s3_service import S3Service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_dummy_pdf(filename: str = "test_document.pdf") -> Path:
    """
    Create a simple dummy PDF file for testing.

    Args:
        filename: Name of the PDF file to create

    Returns:
        Path to the created PDF file
    """
    # Ensure downloads directory exists
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    # Create PDF path
    pdf_path = downloads_dir / filename

    logger.info(f"Creating dummy PDF: {pdf_path}")

    # Create a simple PDF with reportlab
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setTitle("Test Document")

    # Add some content
    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, 750, "Test Document for S3 Upload")

    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "This is a test PDF created by the S3 service test script.")
    c.drawString(100, 680, "It contains sample text to verify PDF creation and upload.")
    c.drawString(100, 660, "Generated for Agentic Document Extraction API testing.")

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(100, 620, "File: test_document.pdf")
    c.drawString(100, 600, "Purpose: S3 upload verification")

    # Add a simple rectangle
    c.rect(100, 400, 400, 150, stroke=1, fill=0)
    c.drawString(120, 500, "This document demonstrates successful PDF generation")
    c.drawString(120, 480, "and S3 upload capabilities for the extraction API.")

    # Save the PDF
    c.save()

    logger.info(f"Created PDF: {pdf_path} ({pdf_path.stat().st_size} bytes)")

    return pdf_path


def test_s3_service(test_bucket: str, test_prefix: str = "test/"):
    """
    Test the S3Service with a dummy PDF file.

    Args:
        test_bucket: S3 bucket name for testing
        test_prefix: S3 key prefix for testing (default: "test/")
    """
    logger.info("=" * 60)
    logger.info("Starting S3 Service Test")
    logger.info("=" * 60)

    # Load environment variables
    load_dotenv()

    # Check for required environment variables
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please create a .env file with AWS credentials")
        sys.exit(1)

    logger.info(f"Test bucket: {test_bucket}")
    logger.info(f"Test prefix: {test_prefix}")

    try:
        # Initialize S3 service
        logger.info("\n1. Initializing S3 Service...")
        s3_service = S3Service()
        logger.info("✓ S3 Service initialized successfully")

        # Test bucket validation
        logger.info("\n2. Testing bucket validation...")
        is_valid = s3_service.validate_bucket_access(test_bucket)
        if is_valid:
            logger.info(f"✓ Bucket '{test_bucket}' is accessible")
        else:
            logger.error(f"✗ Bucket '{test_bucket}' is not accessible")
            logger.error("Please check bucket name and permissions")
            sys.exit(1)

        # Create dummy PDF
        logger.info("\n3. Creating dummy PDF...")
        pdf_path = create_dummy_pdf()
        logger.info(f"✓ Created dummy PDF: {pdf_path}")

        # Test single file upload
        logger.info("\n4. Testing single file upload...")
        s3_key = f"{test_prefix}test_document.pdf"
        s3_uri = s3_service.upload_file(
            file_path=str(pdf_path),
            bucket=test_bucket,
            s3_key=s3_key
        )
        logger.info(f"✓ Successfully uploaded: {s3_uri}")

        # Create multiple dummy PDFs for batch upload test
        logger.info("\n5. Testing multiple file upload...")
        pdf_paths = []
        for i in range(3):
            pdf = create_dummy_pdf(f"test_batch_{i+1}.pdf")
            pdf_paths.append(str(pdf))

        s3_uris = s3_service.upload_multiple_files(
            file_paths=pdf_paths,
            bucket=test_bucket,
            s3_prefix=f"{test_prefix}batch/"
        )

        logger.info(f"✓ Successfully uploaded {len(s3_uris)} files:")
        for uri in s3_uris:
            logger.info(f"  - {uri}")

        # Test error handling (non-existent file)
        logger.info("\n6. Testing error handling...")
        try:
            s3_service.upload_file(
                file_path="nonexistent_file.pdf",
                bucket=test_bucket,
                s3_key="test/should_fail.pdf"
            )
            logger.error("✗ Should have raised FileNotFoundError")
        except FileNotFoundError:
            logger.info("✓ Correctly raised FileNotFoundError for missing file")

        # Cleanup test files
        logger.info("\n7. Cleaning up local test files...")
        for pdf_path in [pdf_path] + [Path(p) for p in pdf_paths]:
            if pdf_path.exists():
                pdf_path.unlink()
                logger.info(f"  Deleted: {pdf_path}")

        logger.info("\n" + "=" * 60)
        logger.info("✓ All S3 Service tests passed successfully!")
        logger.info("=" * 60)

        logger.info("\nTest files uploaded to S3:")
        logger.info(f"  - {s3_uri}")
        for uri in s3_uris:
            logger.info(f"  - {uri}")

        logger.info("\nNote: Test files remain in S3. Delete them manually if needed.")

    except Exception as e:
        logger.error("\n" + "=" * 60)
        logger.error(f"✗ Test failed with error: {e}")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    # Parse command-line arguments
    if len(sys.argv) < 2:
        logger.error("Usage: python test_s3_service.py <bucket_name> [prefix]")
        logger.error("Example: python test_s3_service.py my-test-bucket test/")
        sys.exit(1)

    bucket_name = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else "test/"

    test_s3_service(bucket_name, prefix)
