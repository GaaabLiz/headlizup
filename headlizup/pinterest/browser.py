"""
Playwright browser lifecycle management for Pinterest.

Handles launching/closing the browser and managing authentication state
persistence so that login is not required on every request.
"""

import os
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from headlizup.pinterest.config import (
    PINTEREST_HEADLESS,
    NAVIGATION_TIMEOUT,
)
from headlizup.config import PINTEREST_AUTH_PATH

logger = logging.getLogger("pinterest.browser")


class PinterestBrowserManager:
    """Manages a singleton Playwright browser instance for Pinterest."""

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        """Lazily start Playwright and launch Chromium."""
        if self._browser is None or not self._browser.is_connected():
            logger.info("[BROWSER] Launching Playwright Chromium (headless=%s)", PINTEREST_HEADLESS)
            self._playwright = await async_playwright().start()
            logger.debug("[BROWSER] Playwright started")
            self._browser = await self._playwright.chromium.launch(
                headless=PINTEREST_HEADLESS,
            )
            logger.info("[BROWSER] Chromium browser launched successfully (PID: %s)", 
                        self._browser.contexts if hasattr(self._browser, 'contexts') else 'N/A')
        else:
            logger.debug("[BROWSER] Reusing existing browser (connected=%s)", self._browser.is_connected())
        return self._browser

    async def new_context(self) -> BrowserContext:
        """
        Create a new browser context, restoring saved authentication
        state if available.
        """
        browser = await self._ensure_browser()
        active_contexts = len(browser.contexts)
        logger.debug("[BROWSER] Creating new context (currently %d active context(s))", active_contexts)

        if os.path.exists(PINTEREST_AUTH_PATH):
            state_size = os.path.getsize(PINTEREST_AUTH_PATH)
            logger.info("[BROWSER] Restoring auth state from %s (%.1f KB)", PINTEREST_AUTH_PATH, state_size / 1024)
            context = await browser.new_context(
                storage_state=PINTEREST_AUTH_PATH,
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            logger.debug("[BROWSER] Context created with restored auth state")
        else:
            logger.info("[BROWSER] No auth state file found at %s — creating fresh context", PINTEREST_AUTH_PATH)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            logger.debug("[BROWSER] Fresh context created (no auth state)")

        context.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
        logger.debug("[BROWSER] Navigation timeout set to %dms", NAVIGATION_TIMEOUT)
        return context

    @staticmethod
    async def save_auth_state(context: BrowserContext) -> None:
        """Persist cookies and local-storage so next request skips login."""
        logger.info("[BROWSER] Saving auth state to %s", PINTEREST_AUTH_PATH)
        os.makedirs(os.path.dirname(PINTEREST_AUTH_PATH), exist_ok=True)
        await context.storage_state(path=PINTEREST_AUTH_PATH)
        state_size = os.path.getsize(PINTEREST_AUTH_PATH)
        logger.info("[BROWSER] Auth state saved (%.1f KB)", state_size / 1024)

    async def close(self) -> None:
        """Gracefully shut down browser and Playwright."""
        if self._browser:
            logger.info("[BROWSER] Closing Playwright browser (%d active context(s))", len(self._browser.contexts))
            await self._browser.close()
            self._browser = None
            logger.debug("[BROWSER] Browser closed")
        if self._playwright:
            logger.debug("[BROWSER] Stopping Playwright")
            await self._playwright.stop()
            self._playwright = None
            logger.debug("[BROWSER] Playwright stopped")
