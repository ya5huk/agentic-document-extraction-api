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

from browser_use import Agent, Browser, ChatGoogle, ChatOpenAI, Tools, ActionResult

logger = logging.getLogger(__name__)


class BrowserService:
    """
    Service class for browser automation with AI-powered PDF extraction.

    Uses Browser Use library with Gemini to autonomously navigate websites,
    find PDF documents, and download them.
    """

    def __init__(
        self,
        download_dir: str = "./downloads",
        headless: bool = True,
        timeout: int = 120
    ):
        """
        Initialize browser service with AI model.

        Args:
            download_dir: Directory for downloaded files (default: ./downloads)
            headless: Run browser in headless mode (default: True)
            timeout: Timeout for operations in seconds (default: 120)

        Raises:
            ValueError: If required API key is missing
        """
        # Get model selection from environment (default to gemini)
        self.model_type = os.getenv("BROWSER_MODEL", "gemini").lower()

        # Get authentication credentials (optional)
        self.auth_username = os.getenv("SITE_USERNAME")
        self.auth_password = os.getenv("SITE_PASSWORD")

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
            f"Browser service initialized (model={self.model_type}, headless={headless}, download_dir={download_dir})")

    def _initialize_llm(self):
        """
        Initialize the LLM based on BROWSER_MODEL environment variable.

        Supports both Gemini and OpenAI models.
        This is done lazily to avoid unnecessary initialization.
        """
        if self.llm is None:
            if self.model_type == "openai":
                logger.info("Initializing OpenAI LLM...")

                # Get OpenAI API key from environment
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if not openai_api_key:
                    raise ValueError(
                        "OpenAI API key is required when BROWSER_MODEL=openai. "
                        "Please set OPENAI_API_KEY environment variable."
                    )
                else:
                    logger.info("OpenAI API key found in environment")

                # Set environment variable (browser-use uses this)
                os.environ["OPENAI_API_KEY"] = openai_api_key

                # Initialize OpenAI LLM
                self.llm = ChatOpenAI(
                    model="gpt-4o",
                )

                logger.info(
                    "OpenAI LLM (gpt-4o) initialized successfully")

            else:  # Default to gemini
                logger.info("Initializing Gemini LLM...")

                # Get Gemini API key from environment
                gemini_api_key = os.getenv("GEMINI_API_KEY")
                if not gemini_api_key:
                    raise ValueError(
                        "Gemini API key is required when BROWSER_MODEL=gemini. "
                        "Please set GEMINI_API_KEY environment variable."
                    )

                # Set environment variable (browser-use uses this)
                os.environ["GOOGLE_API_KEY"] = gemini_api_key

                # Initialize Gemini LLM
                self.llm = ChatGoogle(
                    model="gemini-2.5-pro",
                )

                logger.info(
                    "Gemini LLM (gemini-flash-latest) initialized successfully")

    def _initialize_browser(self):
        """
        Initialize the Browser with download settings.

        This is done lazily to avoid unnecessary initialization.
        """
        if self.browser is None:
            logger.info("Initializing Browser with download settings...")

            download_path = str(self.download_dir.absolute())

            # Create Browser instance with download path
            self.browser = Browser(
                downloads_path=download_path,
                headless=self.headless,
            )

            logger.info(
                f"Browser initialized with downloads_path: {download_path}")

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

        @tools.action('Download the PDF file from the current browser tab. Call this immediately after a PDF opens in a new tab or when viewing a PDF. This tool will automatically press Ctrl+S to save the PDF to disk.')
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

        # SKIPPING AGENT JUST FOR TESTING, RETURNING DOWNLOADED FILES DIRECTLY
        # Get list of downloaded files
        # downloaded_files = self._get_downloaded_files()

        # if not downloaded_files:
        #     logger.warning("No PDF files were downloaded")
        #     logger.warning(f"Agent result was: {result}")
        #     return []

        # return downloaded_files

        # TEST END

        try:
            logger.info(f"Starting PDF extraction from: {url}")

            # Clear download directory before starting
            self._clear_download_directory()

            # Initialize LLM and Browser if not already done
            self._initialize_llm()
            self._initialize_browser()

            # Create custom tools for this task (following browser-use pattern)
            tools = self._create_download_tools()

            # Build auth instructions if credentials are available
            auth_info = ""
            if self.auth_username and self.auth_password:
                auth_info = f"""
If you encounter a login page, use these credentials:
- Username: {self.auth_username}
- Password: {self.auth_password}

"""

            # Create task for the AI agent
            task = f"""
Navigate to this procurement/solicitation page: {url}

{auth_info}Your task is to DOWNLOAD (not just view) ALL PDF documents available on this page.

IMPORTANT: Use this 3-PHASE WORKFLOW to handle different download behaviors:

═══════════════════════════════════════════════════════════════════════════════
PHASE 1: INITIATE ALL PDF DOWNLOADS
═══════════════════════════════════════════════════════════════════════════════

1. Wait for the page to fully load (wait 2-3 seconds)

2. SCROLL THROUGH THE ENTIRE PAGE to ensure all content is visible:
   - Scroll down to the bottom of the page
   - Some PDFs might be hidden below the fold
   - Make sure all sections and attachments are loaded
   - Wait 1 second after scrolling for content to render

3. COUNT how many PDF download buttons/links are on the page:
   - CRITICAL: Look in MULTIPLE places for PDF files:
     * Attachments section/table (often the main location)
     * "Download" or "View" buttons next to each PDF filename
     * Direct PDF links (ending in .pdf)
     * "Event Package" or "Solicitation Package" sections
     * Tabs or expandable sections that might hide PDFs
   - COUNT EACH individual PDF file - if you see 4 rows in an attachments table, that's 4 PDFs
   - VERIFY your count by listing each PDF filename you found
   - Note the TOTAL COUNT - you must download this many PDFs
   - Example: "Found 4 PDFs: file1.pdf, file2.pdf, file3.pdf, file4.pdf"
   - DOUBLE-CHECK: Does the count match the number of download buttons you see?

4. For EACH PDF download button/link, click it and IMMEDIATELY check what happens:

   SCENARIO A: MODAL POPUP APPEARS
   - If a modal/dialog appears with a "Download Attachment" or similar button
   - Click the download button inside the modal
   - Wait 1 second for the download to start
   - Close the modal if needed
   - Continue to next PDF

   SCENARIO B: NEW TAB OPENS WITH PDF VIEWER
   - If a new tab opens showing the PDF in browser viewer
   - Immediately call the download_pdf_from_viewer tool with the tab's URL
   - Wait for the tool to confirm successful download
   - Continue to next PDF

   SCENARIO C: DIRECT DOWNLOAD (NO MODAL, NO NEW TAB)
   - If neither a modal nor a new tab appears
   - The file is downloading directly
   - Wait 1 second
   - Continue to next PDF

5. Keep track of how many PDFs you've processed - it must match the total count from step 3

6. Repeat steps 4-5 for ALL PDF download buttons/links on the page

═══════════════════════════════════════════════════════════════════════════════
PHASE 2: CLEANUP
═══════════════════════════════════════════════════════════════════════════════

7. After all PDF downloads are initiated (including calling download_pdf_from_viewer for any PDF viewer tabs):
   - Close any remaining open tabs
   - Return to the main page

═══════════════════════════════════════════════════════════════════════════════
PHASE 3: VALIDATION AND COMPLETION
═══════════════════════════════════════════════════════════════════════════════

8. VALIDATE that you downloaded ALL PDFs:
   - Compare: How many PDFs did you count in step 3?
   - Compare: How many PDFs did you successfully download?
   - These numbers MUST MATCH
   - If they don't match, scroll through the page again to find missing PDFs

9. Once validation is complete, mark the task as done with a simple completion message

DOWNLOAD DIRECTORY: {str(self.download_dir.absolute())}
All PDFs must be saved to this exact location.

IMPORTANT NOTES:
- Different websites behave differently - be adaptive!
- Always check what happens after clicking a download button
- Handle modals by clicking the download button inside them
- Handle PDF viewer tabs by calling download_pdf_from_viewer tool immediately
- Handle direct downloads by just waiting a moment

When you are completely finished, mark the task as done.
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
