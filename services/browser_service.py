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
from urllib.parse import urlparse

from browser_use import Agent, Browser, ChatGoogle, Tools, ActionResult

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
        headless: bool = False,  # Changed to False for testing
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

        # Initialize LLM and Browser
        self.llm = None
        self.browser = None
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

    def _initialize_browser(self):
        """
        Initialize the Browser with download settings.

        This is done lazily to avoid unnecessary initialization.
        """
        if self.browser is None:
            logger.info("Initializing Browser with download settings...")

            download_path = str(self.download_dir.absolute())

            # Chrome preferences to force PDF downloads instead of viewing
            # chrome_prefs = {
            #     "download.default_directory": download_path,
            #     "download.prompt_for_download": False,
            #     "download.directory_upgrade": True,
            #     "plugins.always_open_pdf_externally": True,  # Key setting: always download PDFs
            #     "safebrowsing.enabled": True,
            # }
            # There is no such attribute to browser as chrome_prefs

            # Create Browser instance with downloads_path and chrome preferences
            self.browser = Browser(
                downloads_path=download_path,
                headless=self.headless,
            )

            logger.info("="*70)
            logger.info("BROWSER DOWNLOAD CONFIGURATION")
            logger.info("="*70)
            logger.info(f"Downloads will be saved to: {download_path}")
            logger.info(f"Headless mode: {self.headless}")
            logger.info("="*70)

    def _create_download_tools(self):
        """
        Create custom tools for PDF downloads.

        Creates a custom tool that can download PDFs when they open in
        the browser's PDF viewer, bypassing the limitation where browser-use
        cannot interact with the browser's UI controls.

        Returns:
            Tools instance with registered actions
        """
        logger.info("Creating custom tools for PDF downloads...")

        tools = Tools()

        # Store download_dir for use in the tool closure
        download_dir = self.download_dir

        @tools.action('Download a PDF file that is currently open in the browser PDF viewer. Use this when the PDF is displayed but you cannot click the download button.')
        async def download_pdf_from_viewer(url: str, browser: Browser) -> ActionResult:
            """
            Download PDF from browser's PDF viewer using Playwright API.

            This tool accesses the underlying Playwright browser to trigger
            PDF downloads programmatically, bypassing the browser UI limitation.

            Args:
                url: The URL of the page showing the PDF
                browser: Browser instance (auto-injected by browser-use)

            Returns:
                ActionResult with success/error information
            """
            try:
                logger.info(
                    f"Attempting to download PDF from viewer at: {url}")

                # Access the underlying Playwright browser instance
                playwright_browser = await browser.browser.get_playwright_browser()

                if not playwright_browser.contexts:
                    error_msg = "No active browser context found."
                    logger.error(error_msg)
                    return ActionResult(
                        extracted_content=error_msg,
                        error="No browser context"
                    )

                # Get the browser context
                context = playwright_browser.contexts[0]

                if not context.pages:
                    error_msg = "No active pages found in browser."
                    logger.error(error_msg)
                    return ActionResult(
                        extracted_content=error_msg,
                        error="No pages found"
                    )

                # Find the page that matches the URL
                page = next(
                    (p for p in context.pages if urlparse(url).netloc in p.url),
                    None
                )

                if not page:
                    # If no exact match, try to get the most recent page
                    page = context.pages[-1]
                    logger.warning(
                        f"No page found matching {url}, using most recent page: {page.url}"
                    )

                logger.info(f"Found page: {page.url}")

                # Use Playwright's download event handling with keyboard shortcut
                # Ctrl+S works universally across different PDF viewers
                logger.info("Triggering download with Ctrl+S...")

                async with page.expect_download(timeout=10000) as download_info:
                    await page.keyboard.press('Control+S')

                download = await download_info.value
                filename = download.suggested_filename

                # Save to the configured download directory
                download_path = os.path.join(
                    str(download_dir.absolute()), filename)

                logger.info(f"Saving PDF to: {download_path}")
                await download.save_as(download_path)

                # Verify the file was actually saved
                import time
                time.sleep(1)  # Give filesystem a moment to sync

                if os.path.exists(download_path):
                    file_size = os.path.getsize(download_path)
                    logger.info(f"✓ Successfully downloaded PDF: {filename}")
                    logger.info(f"✓ File size: {file_size:,} bytes")
                    logger.info(f"✓ Location: {download_path}")

                    return ActionResult(
                        extracted_content=f"✓ SUCCESS: Downloaded '{filename}' ({file_size:,} bytes) to {download_path}",
                        include_in_memory=True
                    )
                else:
                    error_msg = f"✗ FAILED: File was not saved to {download_path}"
                    logger.error(error_msg)
                    return ActionResult(
                        extracted_content=error_msg,
                        error="File not found after download"
                    )

            except TimeoutError:
                error_msg = "Timeout waiting for download to start. The PDF might not support direct download, or the page might not be a PDF viewer."
                logger.error(error_msg)
                return ActionResult(
                    extracted_content=error_msg,
                    error="Download timeout"
                )
            except Exception as e:
                error_msg = f"Failed to download PDF: {str(e)}"
                logger.error(error_msg)
                logger.exception("Full error:")
                return ActionResult(
                    extracted_content=error_msg,
                    error=str(e)
                )

        logger.info("Custom tools created successfully")
        return tools

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

            # Initialize LLM and Browser if not already done
            self._initialize_llm()
            self._initialize_browser()

            # Create custom tools for this task (following browser-use pattern)
            tools = self._create_download_tools()

            # Create task for the AI agent
            task = f"""
Navigate to this procurement/solicitation page: {url}

Your task is to DOWNLOAD (not just view) ALL PDF documents available on this page.

IMPORTANT INSTRUCTIONS:

1. Wait for the page to fully load (wait 3-5 seconds)

2. Look for PDF files and download buttons/links:
   - "Download" buttons or links (PREFERRED - click these first!)
   - Direct PDF links (ending in .pdf)
   - "View Document" or "View Event Package" buttons
   - Document tabs or sections with download options
   - Attachment lists
   - "Event Package" or "Solicitation Package" sections

3. For EACH PDF you find - MANDATORY WORKFLOW:

   YOU MUST FOLLOW THIS EXACT SEQUENCE FOR EVERY PDF:

   Step 1: Click the download button/link

   Step 2: IMMEDIATELY check your open tabs - did a new tab open?

   Step 3: If YES (a new tab opened):
      - This means the PDF opened in browser viewer
      - Switch to that new tab
      - YOU MUST call the 'download_pdf_from_viewer' tool with the tab's current URL
      - Wait for tool to return success message
      - Verify the tool output says "Successfully downloaded"
      - Only then close the PDF tab

   Step 4: If NO (no new tab):
      - Wait 5 seconds for direct download
      - Then continue to next PDF

   CRITICAL: If you close a PDF tab without first calling download_pdf_from_viewer,
   the file will NOT be downloaded!

4. Make sure each PDF is fully downloaded before proceeding to the next one.

5. Repeat for ALL PDFs on the page

6. Download directory: {str(self.download_dir.absolute())}

CRITICAL INSTRUCTIONS FOR DOWNLOADING:
- When you click a PDF link/button and it opens in a NEW TAB showing the PDF document,
  you MUST immediately use the 'download_pdf_from_viewer' tool with that tab's URL.
- Do NOT just close the tab without downloading - use the tool first!
- The tool will programmatically save the PDF to the download directory.
- After the tool confirms success, then close the PDF tab and continue.

DOWNLOAD DIRECTORY: {str(self.download_dir.absolute())}
All PDFs must be saved to this exact location.

Your goal is to DOWNLOAD all PDF files to the download directory.
The tool will verify each file was saved and show the exact file path.

Once ALL PDFs are downloaded, confirm completion.
"""

            # Create a new agent with the specific task, browser instance, and custom tools
            logger.info(
                "Creating Browser Use agent with task and custom tools...")
            logger.info(
                f"Download directory: {str(self.download_dir.absolute())}")

            agent = Agent(
                task=task,
                llm=self.llm,
                browser=self.browser,
                use_vision=True,
                tools=tools,  # Use the locally created tools instance
            )

            # Run the agent
            logger.info("Running Browser Use agent...")
            start_time = time.time()

            # Execute the task
            result = await agent.run()

            elapsed_time = time.time() - start_time
            logger.info(f"Agent completed in {elapsed_time:.2f} seconds")
            logger.info(f"Agent result: {result}")

            logger.info("="*60)
            logger.info('Agent history:')
            logger.info("="*60)
            logger.info(f"Is successful: {result.is_successful()}")
            logger.info(f"Were errors: {result.has_errors()}")

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
