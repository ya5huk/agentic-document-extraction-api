"""
Browser Service Module

Handles browser automation using Browser Use + Gemini for autonomous
PDF discovery and downloading from procurement websites.
"""

import logging
import os
import time
from pathlib import Path
from typing import List, Optional

from browser_use import Agent
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class BrowserService:
    """
    Service class for browser automation with AI-powered PDF extraction.

    Uses Browser Use library with Gemini to autonomously navigate websites,
    find PDF documents, and download them.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        download_dir: str = "./downloads",
        headless: bool = True,
        timeout: int = 120
    ):
        """
        Initialize browser service with Gemini AI.

        Args:
            gemini_api_key: Gemini API key (defaults to env variable)
            download_dir: Directory for downloaded files (default: ./downloads)
            headless: Run browser in headless mode (default: True)
            timeout: Timeout for operations in seconds (default: 120)

        Raises:
            ValueError: If Gemini API key is missing
        """
        # Get Gemini API key
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError(
                "Gemini API key is required. Please set GEMINI_API_KEY "
                "environment variable or pass it to constructor."
            )

        # Set up download directory
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Browser configuration
        self.headless = headless
        self.timeout = timeout

        # Initialize LLM
        self.llm = None
        self.agent = None

        logger.info(f"Browser service initialized (headless={headless}, download_dir={download_dir})")

    def _initialize_agent(self):
        """
        Initialize the Browser Use agent with Gemini LLM.

        This is done lazily to avoid unnecessary initialization.
        """
        if self.agent is None:
            logger.info("Initializing Browser Use agent with Gemini...")

            # Initialize Gemini LLM
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                google_api_key=self.gemini_api_key,
                temperature=0.1,
            )

            # Initialize Browser Use agent
            self.agent = Agent(
                task="",  # Will be set per operation
                llm=self.llm,
                use_vision=True,
            )

            logger.info("Browser Use agent initialized successfully")

    async def find_and_download_pdfs(self, url: str) -> List[str]:
        """
        Navigate to URL and download all PDF documents found.

        Uses AI to autonomously:
        1. Navigate to the procurement page
        2. Find all PDF links/buttons
        3. Download PDFs to the download directory
        4. Return list of downloaded file paths

        Args:
            url: URL of the procurement/solicitation page

        Returns:
            List of local file paths for downloaded PDFs

        Raises:
            Exception: If navigation or download fails
        """
        try:
            logger.info(f"Starting PDF extraction from: {url}")

            # Clear download directory before starting
            self._clear_download_directory()

            # Initialize agent if not already done
            self._initialize_agent()

            # Create task for the AI agent
            task = f"""
Navigate to this procurement/solicitation page: {url}

Your task is to download ALL PDF documents available on this page. Please:

1. Wait for the page to fully load
2. Look for PDF files in these common locations:
   - Direct PDF links (ending in .pdf)
   - "Download" buttons or links
   - "View Document" or "View Event Package" buttons
   - Document tabs or sections
   - Attachment lists
   - "Event Package" or "Solicitation Package" sections

3. Click on each PDF link/button to download the files
4. Make sure all PDFs are downloaded to the downloads folder

Common button text to look for:
- "View Event Package"
- "Download"
- "View Document"
- "Attachments"
- "Documents"
- "Event Package"
- Any link with .pdf extension

IMPORTANT: Download ALL PDF files you find. Do not skip any documents.

Once all PDFs are downloaded, confirm completion.
"""

            # Update agent task
            self.agent.task = task

            # Run the agent
            logger.info("Running Browser Use agent...")
            start_time = time.time()

            # Execute the task
            result = await self.agent.run()

            elapsed_time = time.time() - start_time
            logger.info(f"Agent completed in {elapsed_time:.2f} seconds")
            logger.info(f"Agent result: {result}")

            # Get list of downloaded files
            downloaded_files = self._get_downloaded_files()

            if not downloaded_files:
                logger.warning("No PDF files were downloaded")
                logger.warning(f"Agent result was: {result}")
                return []

            logger.info(f"Successfully downloaded {len(downloaded_files)} PDF(s):")
            for file_path in downloaded_files:
                file_size = Path(file_path).stat().st_size
                logger.info(f"  - {Path(file_path).name} ({file_size:,} bytes)")

            return downloaded_files

        except Exception as e:
            logger.error(f"Error during PDF extraction: {e}")
            raise Exception(f"Failed to extract PDFs from {url}: {str(e)}")

    def _clear_download_directory(self):
        """
        Clear all files from the download directory before starting.

        This ensures we only track files from the current extraction.
        """
        try:
            if self.download_dir.exists():
                for file_path in self.download_dir.glob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"Cleared: {file_path.name}")
                logger.info("Download directory cleared")
        except Exception as e:
            logger.warning(f"Error clearing download directory: {e}")

    def _get_downloaded_files(self) -> List[str]:
        """
        Get list of all files in the download directory.

        Returns:
            List of absolute file paths
        """
        downloaded_files = []

        if self.download_dir.exists():
            for file_path in self.download_dir.glob("*"):
                if file_path.is_file() and file_path.suffix.lower() == ".pdf":
                    downloaded_files.append(str(file_path.absolute()))

        return sorted(downloaded_files)

    async def close(self):
        """
        Clean up browser resources.

        Call this when done with the browser service.
        """
        if self.agent is not None:
            try:
                # Browser Use handles cleanup internally
                logger.info("Browser service closed")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

    def get_download_directory(self) -> str:
        """
        Get the absolute path to the download directory.

        Returns:
            Absolute path as string
        """
        return str(self.download_dir.absolute())
