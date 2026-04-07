"""
Playwright browser lifecycle management.

Handles launching/closing the browser and managing authentication state
persistence so that login is not required on every request.
"""

import os
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from headlizup.civitai.config import (
    AUTH_STATE_PATH,
    GBNXD_API_BROWSER_CIVITAI_HEADLESS,
    NAVIGATION_TIMEOUT,
)

logger = logging.getLogger("browser")


class BrowserManager:
    """Manages a singleton Playwright browser instance and reusable auth context."""

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        """Lazily start Playwright and launch Chromium."""
        if self._browser is None or not self._browser.is_connected():
            logger.info("[BROWSER] Launching Playwright Chromium (headless=%s)", GBNXD_API_BROWSER_CIVITAI_HEADLESS)
            self._playwright = await async_playwright().start()
            logger.debug("[BROWSER] Playwright started")
            self._browser = await self._playwright.chromium.launch(
                headless=GBNXD_API_BROWSER_CIVITAI_HEADLESS,
            )
            logger.info("[BROWSER] Chromium launched successfully")
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

        if os.path.exists(AUTH_STATE_PATH):
            state_size = os.path.getsize(AUTH_STATE_PATH)
            logger.info("[BROWSER] Restoring auth state from %s (%.1f KB)", AUTH_STATE_PATH, state_size / 1024)
            context = await browser.new_context(
                storage_state=AUTH_STATE_PATH,
            )
        else:
            logger.info("[BROWSER] No auth state found at %s — creating fresh context", AUTH_STATE_PATH)
            context = await browser.new_context()

        context.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
        logger.debug("[BROWSER] Navigation timeout set to %dms", NAVIGATION_TIMEOUT)
        return context

    @staticmethod
    async def save_auth_state(context: BrowserContext) -> None:
        """Persist cookies and local-storage so next request skips login."""
        logger.info("[BROWSER] Saving auth state to %s", AUTH_STATE_PATH)
        os.makedirs(os.path.dirname(AUTH_STATE_PATH), exist_ok=True)
        await context.storage_state(path=AUTH_STATE_PATH)
        state_size = os.path.getsize(AUTH_STATE_PATH)
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
