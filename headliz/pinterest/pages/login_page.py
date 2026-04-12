"""
Page Object for Pinterest login page.

Encapsulates all interactions with the login form so that selector
changes only need to be updated in config.py.
"""

import asyncio
import logging
import os
import random
from playwright.async_api import Page

from headliz.pinterest.config import (
    SELECTORS,
    PINTEREST_LOGIN_URL,
    PINTEREST_EMAIL,
    PINTEREST_PASSWORD,
    SCREENSHOTS_DIR,
    ACTION_TIMEOUT,
    SLEEP_SHORT,
    SLEEP_MEDIUM,
    SLEEP_LONG,
    TYPING_DELAY_MS,
)

logger = logging.getLogger("pinterest.login")


async def _human_sleep(sleep_range: tuple[float, float], label: str = "") -> None:
    """Sleep for a random duration within the given range to mimic human behavior."""
    duration = random.uniform(*sleep_range)
    if label:
        logger.debug("Sleeping %.1fs (%s)", duration, label)
    await asyncio.sleep(duration)


class PinterestLoginPage:
    """Handles authentication on Pinterest."""

    def __init__(self, page: Page):
        self._page = page

    async def dismiss_cookie_consent(self) -> None:
        """Click 'Accept' if the cookie consent banner is visible."""
        logger.debug("[COOKIE] Checking for cookie consent banner")
        try:
            selector = SELECTORS["cookie_accept_button"]
            logger.debug("[COOKIE] Looking for consent button: %s", selector)
            btn = self._page.locator(selector)
            await btn.first.wait_for(state="visible", timeout=5_000)
            await _human_sleep(SLEEP_SHORT, "before cookie accept")
            await btn.first.click()
            logger.info("[COOKIE] Cookie consent banner dismissed")
            await _human_sleep(SLEEP_SHORT, "after cookie accept")
        except Exception:
            logger.debug("[COOKIE] No cookie consent banner detected (timeout or not present)")

    async def is_logged_in(self) -> bool:
        """
        Check whether the current session is already authenticated.

        Strategy: Navigate to /pin-creation-tool/ which requires auth.
        If we land on the creation page (not redirected to login), we're in.
        """
        current_url = self._page.url
        logger.info("[AUTH] Checking login state — current URL: %s", current_url)

        # If we're on a login page, we're definitely not logged in
        if "/login" in current_url:
            logger.info("[AUTH] Currently on login page — NOT logged in")
            return False

        # Strong negative signal: visible "Log in" / "Accedi" link/button
        try:
            login_link = self._page.locator(
                'a[href="/login/"], '
                '[data-test-id="simple-login-button"]'
            )
            link_count = await login_link.count()
            logger.debug("[AUTH] Found %d login link(s) on page", link_count)
            if link_count > 0 and await login_link.first.is_visible(timeout=3_000):
                text = await login_link.first.text_content()
                logger.info("[AUTH] Login link visible ('%s') — NOT logged in", (text or '').strip())
                return False
        except Exception as e:
            logger.debug("[AUTH] Login link check failed: %s", e)

        # Positive signal: check if we can access an auth-required page
        logger.debug("[AUTH] Probing auth by navigating to /pin-creation-tool/")
        try:
            await self._page.goto("https://www.pinterest.com/pin-creation-tool/", wait_until="networkidle")
            await _human_sleep(SLEEP_SHORT, "auth probe")
            probe_url = self._page.url
            probe_title = await self._page.title()
            logger.debug("[AUTH] Probe result — URL: %s, title: '%s'", probe_url, probe_title)
            if "/login" not in probe_url:
                logger.info("[AUTH] Auth probe PASSED — user IS logged in (URL: %s)", probe_url)
                return True
            else:
                logger.info("[AUTH] Auth probe redirected to login — NOT logged in")
                return False
        except Exception as e:
            logger.warning("[AUTH] Auth probe failed with exception: %s", e)

        logger.warning("[AUTH] Could not determine login state — assuming NOT logged in")
        return False

    async def login(self, email: str | None = None, password: str | None = None) -> None:
        """
        Navigate to the login page and authenticate with human-like behavior.

        Raises:
            RuntimeError: if login fails after form submission.
        """
        email = email or PINTEREST_EMAIL
        password = password or PINTEREST_PASSWORD

        if not email or not password:
            raise RuntimeError(
                "Pinterest credentials not configured. "
                "Set GBNXD_API_BROWSER_PINTEREST_EMAIL and GBNXD_API_BROWSER_PINTEREST_PASSWORD in .env"
            )

        logger.info("Navigating to Pinterest login page: %s", PINTEREST_LOGIN_URL)
        await self._page.goto(PINTEREST_LOGIN_URL, wait_until="networkidle")
        await _human_sleep(SLEEP_MEDIUM, "page loaded")

        await self.dismiss_cookie_consent()

        # ── Fill email with human-like typing ────────────────────────────
        logger.debug("Filling email field")
        email_input = self._page.locator(SELECTORS["login_email_input"])
        await email_input.click()
        await _human_sleep(SLEEP_SHORT, "before typing email")
        await email_input.type(email, delay=TYPING_DELAY_MS)
        await _human_sleep(SLEEP_SHORT, "after email")

        # ── Fill password with human-like typing ─────────────────────────
        logger.debug("Filling password field")
        password_input = self._page.locator(SELECTORS["login_password_input"])
        await password_input.click()
        await _human_sleep(SLEEP_SHORT, "before typing password")
        await password_input.type(password, delay=TYPING_DELAY_MS)
        await _human_sleep(SLEEP_MEDIUM, "after password")

        # ── Submit login form ────────────────────────────────────────────
        logger.info("Submitting login form")
        submit_btn = self._page.locator(SELECTORS["login_submit_button"])
        await submit_btn.first.click()

        # Wait for navigation after login
        await _human_sleep(SLEEP_LONG, "waiting for login redirect")
        await self._page.wait_for_load_state("networkidle", timeout=ACTION_TIMEOUT)
        await _human_sleep(SLEEP_MEDIUM, "post-login settle")

        # Verify: if URL is NOT /login, we succeeded
        post_login_url = self._page.url
        if "/login" not in post_login_url:
            logger.info("Pinterest login successful (URL: %s)", post_login_url)
        else:
            await self._save_screenshot("pinterest_login_failed")
            raise RuntimeError(
                "Pinterest login failed — still on login page after form submission. "
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
