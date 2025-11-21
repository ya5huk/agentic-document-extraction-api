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

from browser_use import Agent, ChatGoogle

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

        logger.info(
            f"Browser service initialized (headless={headless}, download_dir={download_dir})")

    def _initialize_llm(self):
        """
        Initialize the Gemini LLM.

        This is done lazily to avoid unnecessary initialization.
        """
        if self.llm is None:
            logger.info("Initializing Gemini LLM...")

            # Set environment variable for Gemini API key (browser-use uses this)
            os.environ["GOOGLE_API_KEY"] = self.gemini_api_key

            # Initialize Gemini LLM with proper configuration for browser-use
            self.llm = ChatGoogle(
                model="gemini-flash-latest",
            )

            logger.info("Gemini LLM initialized successfully")

    def _get_browser_config(self):
        """
        Get browser configuration with download settings that force PDF downloads.

        Returns:
            dict: Browser configuration including download preferences
        """
        download_path = str(self.download_dir.absolute())

        # Chrome preferences to force PDF downloads instead of viewing
        chrome_prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # Key setting: always download PDFs
            "safebrowsing.enabled": True,
        }

        return {
            "headless": self.headless,
            "downloads_path": download_path,
            "chrome_prefs": chrome_prefs,
            "args": [
                "--disable-blink-features=AutomationControlled",
                f"--download-dir={download_path}",
            ],
            "ignore_https_errors": True,
        }

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

            # Initialize LLM if not already done
            self._initialize_llm()

            # Create task for the AI agent
            task = f"""
Navigate to this procurement/solicitation page: {url}

Your task is to DOWNLOAD (not just view) ALL PDF documents available on this page to the directory specified in config.

IMPORTANT INSTRUCTIONS:
1. Wait for the page to fully load (wait 3-5 seconds)

2. Look for PDF files and download buttons/links:
   - "Download" buttons or links (PREFERRED - click these first!)
   - Direct PDF links (ending in .pdf)
   - "View Document" or "View Event Package" buttons
   - Document tabs or sections with download options
   - Attachment lists
   - "Event Package" or "Solicitation Package" sections

3. For EACH PDF you find:
   Step A: Click on the PDF link/button to open it

   Step B: If the PDF opens in a NEW BROWSER TAB/WINDOW:
      - Switch to that new tab/window
      - Use keyboard shortcut Ctrl+S (or right-click and select "Save as")
      - This will trigger the Save dialog
      - The file should download automatically to the configured downloads folder
      - Wait 3-5 seconds for the download to complete
      - Close the PDF tab/window
      - Return to the main page to find more PDFs

   Step C: If a direct "Download" button exists:
      - Click it to download the file directly
      - Wait 3-5 seconds for download to complete

4. Repeat for ALL PDFs on the page

5. Download directory: {str(self.download_dir.absolute())}

Common button/link text to look for:
- "Download" or "Download PDF"
- "View Event Package" (this will open PDF in new tab - then use Ctrl+S)
- "View Document" (this will open PDF in new tab - then use Ctrl+S)
- "Save" or "Save As"
- "Attachments"
- "Documents"
- Direct .pdf links (these open in new tab - then use Ctrl+S)

CRITICAL WORKFLOW:
1. Click PDF link → New tab opens with PDF
2. Use Ctrl+S to save the PDF
3. Wait for download to complete
4. Close the PDF tab
5. Return to main page
6. Find next PDF and repeat

Your goal is to DOWNLOAD all PDF files to the folder, not just view them.

Once ALL PDFs are downloaded, confirm completion.
"""

            # Get browser configuration
            browser_config = self._get_browser_config()

            # Create a new agent with the specific task and browser config
            logger.info("Creating Browser Use agent with task...")
            logger.info(
                f"Download directory: {browser_config['downloads_path']}")

            agent = Agent(
                task=task,
                llm=self.llm,
                use_vision=True,
                browser_config=browser_config,
            )

            # Run the agent
            logger.info("Running Browser Use agent...")
            start_time = time.time()

            # Execute the task
            result = await agent.run()

            elapsed_time = time.time() - start_time
            logger.info(f"Agent completed in {elapsed_time:.2f} seconds")
            logger.info(f"Agent result: {result}")

            # Get list of downloaded files
            downloaded_files = self._get_downloaded_files()

            if not downloaded_files:
                logger.warning("No PDF files were downloaded")
                logger.warning(f"Agent result was: {result}")
                return []

            logger.info(
                f"Successfully downloaded {len(downloaded_files)} PDF(s):")
            for file_path in downloaded_files:
                file_size = Path(file_path).stat().st_size
                logger.info(
                    f"  - {Path(file_path).name} ({file_size:,} bytes)")

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
        # Browser Use handles cleanup internally
        logger.info("Browser service closed")

    def get_download_directory(self) -> str:
        """
        Get the absolute path to the download directory.

        Returns:
            Absolute path as string
        """
        return str(self.download_dir.absolute())
