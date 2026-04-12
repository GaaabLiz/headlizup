"""
Page Object for Civitai login page.

Encapsulates all interactions with the login form so that selector
changes only need to be updated in config.py.
"""

import logging
import os
from playwright.async_api import Page, expect

from headliz.civitai.config import (
    SELECTORS,
    CIVITAI_LOGIN_URL,
    GBNXD_API_BROWSER_CIVITAI_EMAIL,
    GBNXD_API_BROWSER_CIVITAI_PASSWORD,
    SCREENSHOTS_DIR,
    ACTION_TIMEOUT,
)

logger = logging.getLogger("civitai.login")


class LoginPage:
    """Handles authentication on Civitai."""

    def __init__(self, page: Page):
        self._page = page

    async def dismiss_cookie_consent(self) -> None:
        """Click 'Accept all & visit the site' if the GDPR consent banner is visible.
        Handles both direct page buttons and Sourcepoint iframe-based CMPs."""
        logger.debug("[COOKIE] Checking for GDPR consent banner")
        # Try direct button first
        try:
            btn = self._page.locator(SELECTORS["cookie_accept_button"])
            await btn.wait_for(state="visible", timeout=6_000)
            await btn.click()
            logger.info("[COOKIE] Consent dismissed (direct button)")
            await self._page.wait_for_timeout(1_000)
            return
        except Exception:
            logger.debug("[COOKIE] No direct consent button found")

        # Try inside known iframe patterns (Sourcepoint CMP)
        try:
            frame_loc = self._page.frame_locator(SELECTORS["cookie_accept_iframe"])
            btn = frame_loc.locator(SELECTORS["cookie_accept_button"])
            await btn.wait_for(state="visible", timeout=6_000)
            await btn.click()
            logger.info("[COOKIE] Consent dismissed (iframe button)")
            await self._page.wait_for_timeout(1_000)
            return
        except Exception:
            logger.debug("[COOKIE] No iframe consent button found")

        logger.debug("[COOKIE] No cookie consent banner detected")

    async def is_logged_in(self) -> bool:
        """Check whether the current session is already authenticated."""
        logger.debug("[AUTH] Checking if user is logged in (looking for avatar)")
        try:
            avatar = self._page.locator(SELECTORS["user_avatar"])
            await avatar.wait_for(state="visible", timeout=5_000)
            logger.info("[AUTH] User avatar found — user IS logged in")
            return True
        except Exception:
            logger.info("[AUTH] User avatar not found — user is NOT logged in")
            return False

    async def login(self, email: str | None = None, password: str | None = None) -> None:
        """
        Navigate to the login page and authenticate.

        Falls back to GBNXD_API_BROWSER_CIVITAI_EMAIL / GBNXD_API_BROWSER_CIVITAI_PASSWORD env vars when
        explicit credentials are not provided.

        Raises:
            RuntimeError: if login fails after form submission.
        """
        email = email or GBNXD_API_BROWSER_CIVITAI_EMAIL
        password = password or GBNXD_API_BROWSER_CIVITAI_PASSWORD

        if not email or not password:
            logger.error("[LOGIN] Civitai credentials not configured!")
            raise RuntimeError(
                "Civitai credentials not configured. "
                "Set GBNXD_API_BROWSER_CIVITAI_EMAIL and GBNXD_API_BROWSER_CIVITAI_PASSWORD in .env"
            )

        logger.info("[LOGIN] Starting Civitai login (email: %s)", email[:3] + "***")
        logger.info("[LOGIN] Navigating to: %s", CIVITAI_LOGIN_URL)
        await self._page.goto(CIVITAI_LOGIN_URL, wait_until="load")
        logger.debug("[LOGIN] Login page loaded — URL: %s", self._page.url)
        await self.dismiss_cookie_consent()

        logger.debug("[LOGIN] Filling email field (selector: %s)", SELECTORS["login_email_input"])
        email_input = self._page.locator(SELECTORS["login_email_input"])
        await email_input.fill(email)
        logger.debug("[LOGIN] Email entered")

        # Step 1 → click Continue to reveal the password field
        logger.debug("[LOGIN] Looking for Continue button: %s", SELECTORS["login_continue_button"])
        try:
            continue_btn = self._page.locator(SELECTORS["login_continue_button"])
            await continue_btn.first.click(timeout=5_000)
            logger.debug("[LOGIN] Continue button clicked — waiting for password field")
            await self._page.wait_for_timeout(1_000)
        except Exception:
            logger.debug("[LOGIN] No Continue button found — assuming single-step form")

        logger.debug("[LOGIN] Filling password field (selector: %s)", SELECTORS["login_password_input"])
        password_input = self._page.locator(SELECTORS["login_password_input"])
        await password_input.fill(password)
        logger.debug("[LOGIN] Password entered")

        logger.info("[LOGIN] Submitting login form (selector: %s)", SELECTORS["login_submit_button"])
        submit_btn = self._page.locator(SELECTORS["login_submit_button"])
        await submit_btn.click()
        logger.info("[LOGIN] Login form submitted — waiting for redirect")

        # Wait for navigation after login
        await self._page.wait_for_load_state("load", timeout=ACTION_TIMEOUT)
        logger.debug("[LOGIN] Post-login URL: %s", self._page.url)

        # Verify login succeeded
        if await self.is_logged_in():
            logger.info("[LOGIN] LOGIN SUCCESSFUL")
        else:
            logger.error("[LOGIN] LOGIN FAILED — could not detect logged-in state")
            await self._save_screenshot("login_failed")
            raise RuntimeError(
                "Login failed — could not detect logged-in state after form submission. "
                "Check credentials or inspect the screenshot in /app/screenshots/"
            )

    async def _save_screenshot(self, name: str) -> str:
        """Save a screenshot for debugging and return its path."""
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
        try:
            await self._page.screenshot(path=path, full_page=True)
            file_size = os.path.getsize(path)
            logger.info("[SCREENSHOT] Saved: %s (%.1f KB)", path, file_size / 1024)
        except Exception as e:
            logger.error("[SCREENSHOT] Failed to save '%s': %s", name, e)
        return path
