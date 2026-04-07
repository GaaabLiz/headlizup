"""
Page Object for Civitai post/upload page.

Encapsulates all interactions with the image upload and post creation
form so that selector changes only need to be updated in config.py.
"""

import logging
import os
from playwright.async_api import Page

from headlizup.civitai.config import (
    SELECTORS,
    CIVITAI_POSTS_CREATE_URL,
    SCREENSHOTS_DIR,
    ACTION_TIMEOUT,
    UPLOAD_TIMEOUT,
)
logger = logging.getLogger("civitai.upload")


class UploadPage:
    """Handles image upload and post creation on Civitai."""

    def __init__(self, page: Page):
        self._page = page

    async def navigate_to_upload(self) -> None:
        """Open the post-creation page."""
        logger.info("[NAV] Navigating to post creation: %s", CIVITAI_POSTS_CREATE_URL)
        await self._page.goto(CIVITAI_POSTS_CREATE_URL, wait_until="load")
        logger.debug("[NAV] Page loaded — URL: %s", self._page.url)
        await self._dismiss_cookie_consent()
        await self._dismiss_joyride()
        logger.info("[NAV] Post creation page ready")

    async def _dismiss_cookie_consent(self) -> None:
        """Dismiss the GDPR consent banner if it reappears on this page."""
        try:
            btn = self._page.locator(SELECTORS["cookie_accept_button"])
            await btn.wait_for(state="visible", timeout=6_000)
            await btn.click()
            logger.info("[COOKIE] Consent dismissed on upload page")
            await self._page.wait_for_timeout(1_500)
        except Exception:
            logger.debug("[COOKIE] No consent banner on upload page")

    async def _dismiss_joyride(self) -> None:
        """Dismiss the react-joyride onboarding tour overlay if present."""
        # Inject JS to remove the overlay directly — most reliable approach
        try:
            await self._page.evaluate("""
                () => {
                    const portal = document.getElementById('react-joyride-portal');
                    if (portal) portal.remove();
                    const overlay = document.querySelector('[data-test-id="overlay"]');
                    if (overlay) overlay.remove();
                }
            """)
            logger.debug("Joyride overlay removed via JS")
            await self._page.wait_for_timeout(500)
        except Exception as e:
            logger.debug("Joyride dismissal skipped: %s", e)

    async def upload_image(self, file_path: str) -> None:
        """
        Upload an image file via the file input.

        After upload CivitAI transitions to the post editor and begins
        automatic image analysis. Waits for:
          1. The post editor (title field) to appear.
          2. The 'Analyzing image' notice to disappear.
        """
        file_size = os.path.getsize(file_path)
        logger.info("[UPLOAD] Starting image upload: %s (%.2f KB)", file_path, file_size / 1024)
        file_input = self._page.locator(SELECTORS["upload_file_input"])
        file_input_count = await file_input.count()
        logger.debug("[UPLOAD] Found %d file input(s)", file_input_count)
        await file_input.set_input_files(file_path)
        logger.info("[UPLOAD] File set on input — waiting for post editor")

        # Wait for the post editor to appear
        logger.debug("[UPLOAD] Waiting for title field to appear (timeout: %dms)", UPLOAD_TIMEOUT)
        try:
            await self._page.locator(SELECTORS["post_title_input"]).wait_for(
                state="visible", timeout=UPLOAD_TIMEOUT
            )
            logger.info("[UPLOAD] Post editor title field visible")
        except Exception:
            logger.warning("[UPLOAD] Title field not detected after timeout — proceeding anyway")
            await self._page.wait_for_timeout(5_000)

        await self._dismiss_cookie_consent()
        await self._dismiss_joyride()

        # Wait for image analysis to complete before touching the form
        logger.info("[UPLOAD] Waiting for image analysis to complete...")
        try:
            analysis = self._page.locator(SELECTORS["analysis_in_progress"])
            analysis_count = await analysis.count()
            logger.debug("[UPLOAD] Analysis banner count: %d", analysis_count)
            if analysis_count > 0:
                await analysis.wait_for(state="hidden", timeout=UPLOAD_TIMEOUT)
                logger.info("[UPLOAD] Image analysis complete")
            else:
                logger.debug("[UPLOAD] No analysis banner found — image ready immediately")
        except Exception as e:
            logger.warning("[UPLOAD] Timed out waiting for analysis (%dms): %s — proceeding", UPLOAD_TIMEOUT, e)

        logger.debug("[UPLOAD] Current URL after upload: %s", self._page.url)
        logger.info("[UPLOAD] Image upload phase complete")

    async def fill_title(self, title: str) -> None:
        """Fill in the post title."""
        logger.info("[TITLE] Filling title: '%s'", title)
        title_input = self._page.locator(SELECTORS["post_title_input"])
        await title_input.click(force=True)
        await title_input.fill(title)
        logger.debug("[TITLE] Title filled")

    async def fill_description(self, description: str) -> None:
        """Fill in the post description."""
        if not description:
            logger.debug("[DESC] No description provided — skipping")
            return

        logger.info("[DESC] Filling description (%d chars)", len(description))
        desc_input = self._page.locator(SELECTORS["post_description_input"])
        await desc_input.click(force=True)
        await desc_input.fill(description)
        logger.debug("[DESC] Description filled")

    async def add_tags(self, tags: list[str]) -> None:
        """Add tags one by one through the tag input."""
        if not tags:
            logger.debug("[TAGS] No tags provided — skipping")
            return

        logger.info("[TAGS] Adding %d tags: %s", len(tags), tags)

        # The "+ Tag" button has "+" as a CSS pseudo-element; text node is just "Tag".
        # Use JS to find and click it reliably.
        clicked = await self._page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null
                );
                let node;
                while (node = walker.nextNode()) {
                    if (node.textContent.trim() === 'Tag') {
                        const el = node.parentElement;
                        el.click();
                        return el.tagName + '|' + (el.className || '').substring(0, 60);
                    }
                }
                return null;
            }
        """)
        if clicked:
            logger.debug("[TAGS] + Tag element clicked via JS: %s", clicked)
            await self._page.wait_for_timeout(800)
        else:
            logger.warning("[TAGS] Could not find '+ Tag' element via JS")

        # After clicking, find the tag input that appeared
        tag_input = self._page.locator(SELECTORS["tag_input"]).first

        for idx, tag in enumerate(tags):
            logger.debug("[TAGS] Adding tag %d/%d: '%s'", idx + 1, len(tags), tag)
            try:
                await tag_input.click(force=True, timeout=5_000)
                await tag_input.fill(tag)
                await self._page.wait_for_timeout(600)

                try:
                    suggestion = self._page.locator(SELECTORS["tag_suggestion_item"]).first
                    await suggestion.click(timeout=3_000, force=True)
                    logger.debug("[TAGS] Tag '%s' selected from suggestions", tag)
                except Exception:
                    await tag_input.press("Enter")
                    logger.debug("[TAGS] Tag '%s' added via Enter key", tag)

                await self._page.wait_for_timeout(400)
            except Exception as e:
                logger.warning("[TAGS] Failed to add tag '%s': %s — skipping", tag, e)

        logger.info("[TAGS] Tag addition complete")

    async def fill_metadata(self, title: str, description: str, tags: list[str]) -> None:
        """Convenience method to fill all post metadata at once."""
        logger.info("[META] Starting metadata fill — title: '%s', desc_len: %d, tags: %s",
                     title, len(description) if description else 0, tags)
        await self.fill_title(title)
        await self.fill_description(description)
        await self.add_tags(tags)
        logger.info("[META] All metadata filled successfully")

    async def submit(self) -> str | None:
        """
        Click the publish button and wait for confirmation.

        Returns:
            The URL of the published post, or None if the URL could not
            be determined.
        """
        logger.info("[SUBMIT] Clicking publish button")
        publish_btn = self._page.locator(SELECTORS["publish_button"])
        await publish_btn.click()
        logger.info("[SUBMIT] Publish button clicked — waiting for response")

        # Wait for navigation or success indicator
        try:
            await self._page.wait_for_load_state("load", timeout=UPLOAD_TIMEOUT)
            logger.debug("[SUBMIT] Page loaded after publish")
        except Exception:
            logger.warning("[SUBMIT] Timed out waiting for post-publish navigation")

        # Try to detect the published post URL
        current_url = self._page.url
        logger.debug("[SUBMIT] Post-publish URL: %s", current_url)
        if "/posts/" in current_url and "/create" not in current_url:
            logger.info("[SUBMIT] SUCCESS — Post published at: %s", current_url)
            return current_url

        # Fallback: check for success message
        try:
            success = self._page.locator(SELECTORS["post_success_indicator"])
            await success.wait_for(state="visible", timeout=ACTION_TIMEOUT)
            logger.info("[SUBMIT] SUCCESS — Post published (success indicator detected, URL: %s)", self._page.url)
            return self._page.url
        except Exception:
            await self._save_screenshot("publish_result")
            logger.warning(
                "[SUBMIT] Could not confirm publish success. Current URL: %s", current_url
            )
            return current_url

    async def delete_post(self) -> None:
        """Click 'Delete Post' to clean up a failed or partial post."""
        logger.info("[DELETE] Attempting to delete partial/failed post")
        try:
            delete_btn = self._page.locator(SELECTORS["delete_post_button"])
            await delete_btn.wait_for(state="visible", timeout=5_000)
            await delete_btn.click(force=True)
            await self._page.wait_for_timeout(2_000)
            logger.info("[DELETE] Post deleted successfully")
        except Exception as e:
            logger.warning("[DELETE] Could not delete post: %s", e)

    async def _save_screenshot(self, name: str) -> str:
        """Save a screenshot for debugging and return its path."""
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
        try:
            await self._page.screenshot(path=path, full_page=True)
            file_size = os.path.getsize(path)
            logger.debug("[SCREENSHOT] Saved: %s (%.1f KB)", path, file_size / 1024)
        except Exception as e:
            logger.error("[SCREENSHOT] Failed to save '%s': %s", name, e)
        return path
