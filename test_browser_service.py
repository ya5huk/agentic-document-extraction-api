"""
Test Script for Browser Service

This script tests the BrowserService functionality with a real procurement URL.
Run this after setting up your .env file with GEMINI_API_KEY.

Usage:
    python test_browser_service.py [url]

Example:
    python test_browser_service.py https://caleprocure.ca.gov/event/0850/0000036230

Requirements:
    - .env file with GEMINI_API_KEY
    - Chrome/Chromium browser installed
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from services.browser_service import BrowserService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test URLs from CLAUDE.md
TEST_URLS = {
    "ecal1": "https://caleprocure.ca.gov/event/0850/0000036230",
    "ecal2": "https://caleprocure.ca.gov/event/2660/07A6065",
    "ecal3": "https://caleprocure.ca.gov/event/75021/0000035944",
    "sourcewell1": "https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/68914ced-5e07-409d-b301-b10001e4bbb0/#Document",
    "sourcewell2": "https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/88c9616c-5685-4cae-b7fa-9c8ad726c38d/#Document",
    "sourcewell3": "https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/321c8f90-b43d-46ae-a8e4-41ac7587bc19/#Document",
}


async def test_browser_service(url: str):
    """
    Test the BrowserService with a procurement URL.

    Args:
        url: URL to test (procurement/solicitation page)
    """
    logger.info("=" * 70)
    logger.info("Starting Browser Service Test")
    logger.info("=" * 70)

    # Load environment variables
    load_dotenv()

    # Check for Gemini API key
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY environment variable not set")
        logger.error("Please create a .env file with your Gemini API key")
        sys.exit(1)

    logger.info(f"Test URL: {url}")
    logger.info("")

    browser_service = None

    try:
        # Initialize browser service
        logger.info("1. Initializing Browser Service...")
        browser_service = BrowserService(
            download_dir="./downloads",
            headless=False,  # Set to False to see browser in action
            timeout=120
        )
        logger.info("✓ Browser Service initialized successfully")

        # Test PDF extraction
        logger.info("\n2. Finding and downloading PDFs...")
        logger.info(f"   Navigating to: {url}")
        logger.info("   This may take 1-2 minutes depending on the page...")
        logger.info("")

        downloaded_files = await browser_service.find_and_download_pdfs(url)

        if downloaded_files:
            logger.info("\n" + "=" * 70)
            logger.info(f"✓ Successfully downloaded {len(downloaded_files)} PDF(s):")
            logger.info("=" * 70)

            for file_path in downloaded_files:
                file_size = Path(file_path).stat().st_size
                logger.info(f"  📄 {Path(file_path).name}")
                logger.info(f"     Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
                logger.info(f"     Path: {file_path}")
                logger.info("")

            logger.info("=" * 70)
            logger.info("✓ Browser Service test completed successfully!")
            logger.info("=" * 70)

        else:
            logger.warning("\n" + "=" * 70)
            logger.warning("⚠ No PDF files were downloaded")
            logger.warning("=" * 70)
            logger.warning("This could mean:")
            logger.warning("  1. The page has no downloadable PDFs")
            logger.warning("  2. The PDFs require authentication")
            logger.warning("  3. The AI agent couldn't find the PDF links")
            logger.warning("  4. The page structure is different than expected")
            logger.warning("")
            logger.warning("Try:")
            logger.warning("  - Running with headless=False to see what's happening")
            logger.warning("  - Checking if the URL is correct and accessible")
            logger.warning("  - Testing with a different URL")

    except Exception as e:
        logger.error("\n" + "=" * 70)
        logger.error(f"✗ Test failed with error: {e}")
        logger.error("=" * 70)

        # Print helpful troubleshooting info
        logger.info("\nTroubleshooting tips:")
        logger.info("  1. Check that GEMINI_API_KEY is set in .env")
        logger.info("  2. Verify Chrome/Chromium is installed")
        logger.info("  3. Check internet connection")
        logger.info("  4. Try a different test URL")
        logger.info("  5. Check logs above for specific errors")

        sys.exit(1)

    finally:
        # Clean up
        if browser_service:
            await browser_service.close()
            logger.info("\nBrowser service closed")


def print_usage():
    """Print usage instructions and available test URLs."""
    print("\nBrowser Service Test Script")
    print("=" * 70)
    print("\nUsage:")
    print("  python test_browser_service.py [url]")
    print("\nIf no URL is provided, the default California eCal URL will be used.")
    print("\nAvailable test URLs:")
    print("\nCalifornia eCal:")
    print(f"  1. {TEST_URLS['ecal1']}")
    print(f"  2. {TEST_URLS['ecal2']}")
    print(f"  3. {TEST_URLS['ecal3']}")
    print("\nSourceWell:")
    print(f"  4. {TEST_URLS['sourcewell1']}")
    print(f"  5. {TEST_URLS['sourcewell2']}")
    print(f"  6. {TEST_URLS['sourcewell3']}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Parse command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h", "help"]:
            print_usage()
            sys.exit(0)
        test_url = sys.argv[1]
    else:
        # Use default test URL (California eCal)
        test_url = TEST_URLS["ecal1"]
        logger.info(f"No URL provided, using default: {test_url}")

    # Run the async test
    asyncio.run(test_browser_service(test_url))
