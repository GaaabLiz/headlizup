"""
Page Object for Pinterest pin creation/upload page.

Encapsulates all interactions with the pin creation tool so that selector
changes only need to be updated in config.py.

STRATEGY: Pinterest's pin-creation-tool form uses dynamic React components
whose selectors change across versions and locales. This module uses a
multi-strategy approach:
  1. Look for stable data-test-id attributes first
  2. Fall back to structural selectors (nth field in the form)
  3. Use page.evaluate() to inspect the DOM when needed
"""

import asyncio
import logging
import os
import random
from playwright.async_api import Page, Locator

from headlizup.pinterest.config import (
    SELECTORS,
    PINTEREST_PIN_CREATION_URL,
    SCREENSHOTS_DIR,
    ACTION_TIMEOUT,
    UPLOAD_TIMEOUT,
    SLEEP_MICRO,
    SLEEP_SHORT,
    SLEEP_MEDIUM,
    SLEEP_LONG,
    TYPING_DELAY_MS,
)

logger = logging.getLogger("pinterest.upload")


async def _human_sleep(sleep_range: tuple[float, float], label: str = "") -> None:
    """Sleep for a random duration within the given range to mimic human behavior."""
    duration = random.uniform(*sleep_range)
    if label:
        logger.debug("Sleeping %.1fs (%s)", duration, label)
    await asyncio.sleep(duration)


class PinterestUploadPage:
    """Handles pin creation and image upload on Pinterest."""

    def __init__(self, page: Page):
        self._page = page

    # ── Navigation ───────────────────────────────────────────────────────

    async def navigate_to_pin_creation(self) -> None:
        """Open the pin creation tool page directly."""
        logger.info("[NAV] Navigating to pin creation tool: %s", PINTEREST_PIN_CREATION_URL)
        logger.debug("[NAV] Current URL before navigation: %s", self._page.url)
        await self._page.goto(PINTEREST_PIN_CREATION_URL, wait_until="networkidle")
        logger.info("[NAV] Page loaded — final URL: %s", self._page.url)
        logger.debug("[NAV] Page title: %s", await self._page.title())
        await _human_sleep(SLEEP_MEDIUM, "pin creation page loaded")

        # Dismiss any overlay/joyride popups
        await self._dismiss_overlays()

        # Take diagnostic screenshot of initial state
        await self._save_screenshot("diag_pin_creation_loaded")
        logger.info("[NAV] Pin creation page ready")

    async def _dismiss_overlays(self) -> None:
        """Dismiss tutorial/joyride/popup overlays if present."""
        logger.debug("[OVERLAY] Checking for popup overlays to dismiss")
        dismissed_count = 0
        for attempt in range(3):
            try:
                close_btn = self._page.locator(
                    'button[aria-label="close"], button[aria-label="Close"], '
                    'button[aria-label="chiudi"], button[aria-label="Chiudi"], '
                    'div[data-test-id="joyride-close-button"]'
                )
                if await close_btn.first.is_visible(timeout=2_000):
                    await close_btn.first.click()
                    dismissed_count += 1
                    logger.info("[OVERLAY] Dismissed overlay #%d (attempt %d)", dismissed_count, attempt + 1)
                    await _human_sleep(SLEEP_SHORT, "dismissed overlay")
                else:
                    logger.debug("[OVERLAY] No more overlays visible")
                    break
            except Exception:
                logger.debug("[OVERLAY] No overlay found on attempt %d", attempt + 1)
                break
        if dismissed_count == 0:
            logger.debug("[OVERLAY] No overlays needed dismissing")
        else:
            logger.info("[OVERLAY] Total overlays dismissed: %d", dismissed_count)

    # ── Image Upload ─────────────────────────────────────────────────────

    async def upload_image(self, file_path: str) -> None:
        """Upload an image file via the hidden file input."""
        file_size = os.path.getsize(file_path)
        logger.info("[UPLOAD] Starting image upload: %s (%.2f KB)", file_path, file_size / 1024)
        await _human_sleep(SLEEP_SHORT, "before upload")

        selector = SELECTORS["upload_file_input"]
        logger.debug("[UPLOAD] Looking for file input with selector: %s", selector)
        file_input = self._page.locator(selector)
        file_input_count = await file_input.count()
        logger.debug("[UPLOAD] Found %d file input(s)", file_input_count)

        await file_input.set_input_files(file_path)
        logger.info("[UPLOAD] File set on input — waiting for editor form to appear")
        await _human_sleep(SLEEP_LONG, "image processing")

        # Wait for the form to stabilize — look for any input/textarea/contenteditable
        try:
            await self._page.wait_for_selector(
                'input, textarea, [contenteditable="true"]',
                state="visible",
                timeout=UPLOAD_TIMEOUT,
            )
            logger.info("[UPLOAD] Pin editor form detected after image upload")
        except Exception:
            logger.warning("[UPLOAD] Form fields not detected after upload timeout (%dms) — continuing anyway", UPLOAD_TIMEOUT)

        logger.debug("[UPLOAD] Current URL after upload: %s", self._page.url)
        await self._save_screenshot("diag_after_upload")
        logger.info("[UPLOAD] Image upload phase complete")

    # ── Field Interaction Helpers ────────────────────────────────────────

    async def _find_title_field(self) -> Locator:
        """
        Find the title input field using multiple strategies.
        Pinterest uses either a plain <input> or a contenteditable div.
        """
        strategies = [
            ("#pin-draft-title (by ID)", lambda: self._page.locator('#pin-draft-title')),
            ('[data-test-id="pin-draft-title"]', lambda: self._page.locator('[data-test-id="pin-draft-title"]')),
            ('placeholder*="titolo|title"', lambda: self._page.locator(
                'input[placeholder*="titolo"], input[placeholder*="title"], '
                'input[placeholder*="Title"]'
            )),
            ('generic visible input (not file/hidden)', lambda: self._page.locator(
                'input:not([type="file"]):not([type="hidden"]):not([type="checkbox"])'
                ':not([type="radio"]):not([role="combobox"])'
            )),
        ]

        for label, strategy in strategies:
            try:
                loc = strategy()
                count = await loc.count()
                logger.debug("[TITLE] Strategy '%s' → %d match(es)", label, count)
                if count > 0 and await loc.first.is_visible(timeout=3_000):
                    tag_name = await loc.first.evaluate("el => el.tagName")
                    logger.info("[TITLE] Field found via '%s' — element: <%s>", label, tag_name)
                    return loc.first
            except Exception as e:
                logger.debug("[TITLE] Strategy '%s' failed: %s", label, e)
                continue

        # Dump DOM summary for debugging
        try:
            inputs = await self._page.evaluate(
                """() => Array.from(document.querySelectorAll('input, textarea, [contenteditable]')).map(
                    el => ({tag: el.tagName, id: el.id, type: el.type, placeholder: el.placeholder, visible: el.offsetParent !== null})
                ).slice(0, 20)"""
            )
            logger.error("[TITLE] DOM input elements dump: %s", inputs)
        except Exception:
            pass
        raise RuntimeError("Could not find title field on pin creation page")

    async def _find_description_field(self) -> Locator:
        """
        Find the description field. Pinterest uses a contenteditable div
        or a textarea inside the pin creation form.
        """
        strategies = [
            ('data-test-id="pin-draft-description-field" contenteditable/textbox', lambda: self._page.locator(
                '[data-test-id="pin-draft-description-field"] [contenteditable="true"], '
                '[data-test-id="pin-draft-description-field"] [role="textbox"]'
            )),
            ('[role="textbox"][contenteditable]', lambda: self._page.locator('[role="textbox"][contenteditable="true"]')),
            ('div[contenteditable]', lambda: self._page.locator(
                'div[contenteditable="true"], '
                'div[contenteditable="plaintext-only"]'
            )),
            ('textarea fallback', lambda: self._page.locator('textarea')),
        ]

        for label, strategy in strategies:
            try:
                loc = strategy()
                count = await loc.count()
                logger.debug("[DESC] Strategy '%s' → %d match(es)", label, count)
                if count > 0 and await loc.first.is_visible(timeout=3_000):
                    tag_name = await loc.first.evaluate("el => el.tagName")
                    logger.info("[DESC] Field found via '%s' — element: <%s>", label, tag_name)
                    return loc.first
            except Exception as e:
                logger.debug("[DESC] Strategy '%s' failed: %s", label, e)
                continue

        # Dump DOM summary for debugging
        try:
            editables = await self._page.evaluate(
                """() => Array.from(document.querySelectorAll('[contenteditable], textarea, [role="textbox"]')).map(
                    el => ({tag: el.tagName, role: el.getAttribute('role'), ce: el.contentEditable, visible: el.offsetParent !== null})
                ).slice(0, 20)"""
            )
            logger.error("[DESC] DOM editable elements dump: %s", editables)
        except Exception:
            pass
        raise RuntimeError("Could not find description field on pin creation page")

    async def _find_tag_field(self) -> Locator | None:
        """
        Find the tag input field. Pinterest's tag input is usually inside
        a specific section of the form (below description), NOT the global
        search bar at the top.
        Returns None if not found (tags will be added as hashtags).
        """
        logger.debug("[TAGS] Searching for dedicated tag input field")
        strategies = [
            ('data-test-id="pin-draft-tags-input"', lambda: self._page.locator('[data-test-id="pin-draft-tags-input"]')),
            ('placeholder*="tag" (not search-input)', lambda: self._page.locator(
                'input[placeholder*="tag"]:not([data-test-id="search-input"]), '
                'input[placeholder*="Tag"]:not([data-test-id="search-input"])'
            )),
            ('id*="tag"', lambda: self._page.locator('input[id*="tag"], input[id*="Tag"]')),
        ]

        for label, strategy in strategies:
            try:
                loc = strategy()
                count = await loc.count()
                logger.debug("[TAGS] Strategy '%s' → %d match(es)", label, count)
                if count > 0 and await loc.first.is_visible(timeout=3_000):
                    logger.info("[TAGS] Dedicated tag field found via '%s'", label)
                    return loc.first
            except Exception as e:
                logger.debug("[TAGS] Strategy '%s' failed: %s", label, e)
                continue

        # Try clicking the tag section to expand it (it might be a dropdown)
        logger.debug("[TAGS] Trying to expand tag section by clicking on 'argomenti taggati'/'tagged topics'")
        try:
            tag_section = self._page.locator(
                'div:has-text("argomenti taggati"), div:has-text("tagged topics")'
            ).last
            if await tag_section.is_visible(timeout=3_000):
                logger.debug("[TAGS] Tag section found — clicking to expand")
                await tag_section.click()
                await _human_sleep(SLEEP_SHORT, "expand tag section")
                # Now try to find the input again
                tag_input = self._page.locator(
                    'input[placeholder*="tag"], input[placeholder*="Tag"]'
                )
                if await tag_input.first.is_visible(timeout=3_000):
                    logger.info("[TAGS] Tag field found after expanding section")
                    return tag_input.first
                else:
                    logger.debug("[TAGS] Tag input still not visible after expanding section")
        except Exception as e:
            logger.debug("[TAGS] Tag section expand attempt failed: %s", e)

        logger.warning("[TAGS] Dedicated tag field not found — tags will be added as hashtags in description")
        return None

    async def _find_board_dropdown(self) -> Locator | None:
        """
        Find the board selection dropdown. It typically contains text like
        "Scegli una bacheca" (IT) / "Choose a board" (EN).
        """
        logger.debug("[BOARD] Searching for board dropdown")
        strategies = [
            ('data-test-id="board-dropdown-select-button"', lambda: self._page.locator(
                'button[data-test-id="board-dropdown-select-button"], '
                'button[data-test-id="boardDropdownSelectButton"]'
            )),
            ('button:has-text("bacheca"/"board")', lambda: self._page.locator(
                'button:has-text("bacheca"), button:has-text("board"), '
                'button:has-text("Board"), button:has-text("Bacheca")'
            )),
            ('div > span:text-is("Bacheca"/"Board") button', lambda: self._page.locator(
                'div:has(> span:text-is("Bacheca")) button, '
                'div:has(> span:text-is("Board")) button'
            )),
        ]

        for label, strategy in strategies:
            try:
                loc = strategy()
                count = await loc.count()
                logger.debug("[BOARD] Strategy '%s' → %d match(es)", label, count)
                if count > 0 and await loc.first.is_visible(timeout=3_000):
                    text = await loc.first.text_content()
                    logger.info("[BOARD] Dropdown found via '%s' — text: '%s'", label, (text or '').strip()[:50])
                    return loc.first
            except Exception as e:
                logger.debug("[BOARD] Strategy '%s' failed: %s", label, e)
                continue

        logger.warning("[BOARD] Board dropdown not found — dumping buttons on page")
        try:
            buttons = await self._page.evaluate(
                """() => Array.from(document.querySelectorAll('button')).map(
                    el => ({text: el.textContent.trim().substring(0, 40), visible: el.offsetParent !== null, testId: el.dataset.testId || ''})
                ).filter(b => b.visible).slice(0, 15)"""
            )
            logger.debug("[BOARD] Visible buttons dump: %s", buttons)
        except Exception:
            pass
        return None

    async def _find_publish_button(self) -> Locator:
        """
        Find the Publish/Pubblica button. Usually a red button in the header.
        """
        logger.debug("[PUBLISH] Searching for Publish/Pubblica button")
        strategies = [
            ('data-test-id="board-dropdown-save-button" / "create-new-pin-button"', lambda: self._page.locator(
                'button[data-test-id="board-dropdown-save-button"], '
                'button[data-test-id="create-new-pin-button"]'
            )),
            ('button:has-text("Pubblica"/"Publish")', lambda: self._page.locator(
                'button:has-text("Pubblica"), button:has-text("Publish")'
            )),
            ('div[data-test-id="pin-draft-save-button"] button', lambda: self._page.locator(
                'div[data-test-id="pin-draft-save-button"] button'
            )),
        ]

        for label, strategy in strategies:
            try:
                loc = strategy()
                count = await loc.count()
                logger.debug("[PUBLISH] Strategy '%s' → %d match(es)", label, count)
                if count > 0 and await loc.first.is_visible(timeout=3_000):
                    text = await loc.first.text_content()
                    logger.info("[PUBLISH] Button found via '%s' — text: '%s'", label, (text or '').strip())
                    return loc.first
            except Exception as e:
                logger.debug("[PUBLISH] Strategy '%s' failed: %s", label, e)
                continue

        # Dump all visible buttons for debugging
        try:
            buttons = await self._page.evaluate(
                """() => Array.from(document.querySelectorAll('button')).map(
                    el => ({text: el.textContent.trim().substring(0, 40), visible: el.offsetParent !== null, testId: el.dataset.testId || ''})
                ).filter(b => b.visible).slice(0, 15)"""
            )
            logger.error("[PUBLISH] Visible buttons dump: %s", buttons)
        except Exception:
            pass
        raise RuntimeError("Could not find Publish/Pubblica button")

    # ── Form Fill Methods ────────────────────────────────────────────────

    async def fill_title(self, title: str) -> None:
        """Fill in the pin title with human-like typing."""
        if not title:
            logger.debug("[TITLE] No title provided — skipping")
            return

        logger.info("[TITLE] Filling title: '%s' (%d chars)", title, len(title))
        await _human_sleep(SLEEP_SHORT, "before title")

        title_field = await self._find_title_field()
        logger.debug("[TITLE] Clicking title field")
        await title_field.click()
        await _human_sleep(SLEEP_MICRO, "focus title")

        # Clear any existing content
        logger.debug("[TITLE] Clearing existing content (Ctrl+A)")
        await self._page.keyboard.press("Meta+a")
        await _human_sleep(SLEEP_MICRO, "select all")

        logger.debug("[TITLE] Typing title with %dms delay per char", TYPING_DELAY_MS)
        await title_field.type(title, delay=TYPING_DELAY_MS)
        await _human_sleep(SLEEP_SHORT, "after title")
        logger.info("[TITLE] Title filled successfully")

    async def fill_description(self, description: str) -> None:
        """Fill in the pin description with human-like typing."""
        if not description:
            logger.debug("[DESC] No description provided — skipping")
            return

        logger.info("[DESC] Filling description (%d chars, preview: '%s...')", len(description), description[:80])
        await _human_sleep(SLEEP_SHORT, "before description")

        desc_field = await self._find_description_field()
        logger.debug("[DESC] Clicking description field")
        await desc_field.click()
        await _human_sleep(SLEEP_MICRO, "focus description")

        logger.debug("[DESC] Typing description with %dms delay per char", TYPING_DELAY_MS)
        await desc_field.type(description, delay=TYPING_DELAY_MS)
        await _human_sleep(SLEEP_SHORT, "after description")
        logger.info("[DESC] Description filled successfully")

    async def add_tags(self, tags: list[str]) -> None:
        """
        Add tags via the dedicated tag field if available, otherwise
        append as #hashtags in the description.
        """
        if not tags:
            logger.debug("[TAGS] No tags provided — skipping")
            return

        logger.info("[TAGS] Adding %d tags: %s", len(tags), tags)
        await _human_sleep(SLEEP_SHORT, "before tags")

        tag_field = await self._find_tag_field()

        if tag_field is not None:
            # Use the dedicated tag field
            logger.info("[TAGS] Using dedicated tag field")
            for idx, tag in enumerate(tags):
                tag_text = tag.strip()
                if not tag_text:
                    continue
                logger.debug("[TAGS] Typing tag %d/%d: '%s'", idx + 1, len(tags), tag_text)
                await tag_field.click()
                await _human_sleep(SLEEP_MICRO, "focus tag field")
                await tag_field.type(tag_text, delay=TYPING_DELAY_MS)
                await _human_sleep(SLEEP_SHORT, "wait for suggestions")

                # Try pressing Enter to confirm the tag
                await self._page.keyboard.press("Enter")
                logger.debug("[TAGS] Tag '%s' submitted via Enter", tag_text)
                await _human_sleep(SLEEP_SHORT, f"tag '{tag_text}' submitted")

            await self._save_screenshot("diag_after_tags")
            logger.info("[TAGS] All %d tags added via tag field", len(tags))
        else:
            # Fallback: append hashtags to description
            logger.info("[TAGS] Falling back to hashtags in description")
            desc_field = await self._find_description_field()
            await desc_field.click()
            await _human_sleep(SLEEP_MICRO, "focus desc for hashtags")

            await self._page.keyboard.press("End")
            await self._page.keyboard.press("Enter")
            await _human_sleep(SLEEP_MICRO, "newline")

            hashtag_text = " ".join(f"#{t.strip().replace(' ', '')}" for t in tags if t.strip())
            logger.debug("[TAGS] Typing hashtag string: '%s'", hashtag_text)
            await desc_field.type(hashtag_text, delay=TYPING_DELAY_MS)
            await _human_sleep(SLEEP_SHORT, "after hashtags")
            logger.info("[TAGS] Hashtags appended to description: %s", hashtag_text)

    async def select_board(self, board_name: str = "") -> None:
        """Select a board for the pin. Scrolls the form to find the dropdown."""
        logger.info("[BOARD] Selecting board (requested: '%s')", board_name or "first available")
        await _human_sleep(SLEEP_SHORT, "before board selection")

        # Scroll down to reveal board dropdown (it's below description)
        logger.debug("[BOARD] Scrolling down 400px to reveal board dropdown")
        await self._page.evaluate("window.scrollBy(0, 400)")
        await _human_sleep(SLEEP_SHORT, "scrolled down for board")
        await self._save_screenshot("diag_board_area")

        dropdown = await self._find_board_dropdown()
        if dropdown is None:
            logger.warning("[BOARD] Board dropdown not found — skipping board selection")
            return

        try:
            logger.debug("[BOARD] Clicking board dropdown")
            await dropdown.click()
            await _human_sleep(SLEEP_MEDIUM, "board dropdown opened")
            await self._save_screenshot("diag_board_dropdown")

            if board_name:
                # Try to search for specific board
                logger.debug("[BOARD] Searching for board: '%s'", board_name)
                search = self._page.locator('input[placeholder*="Cerca"], input[placeholder*="Search"]')
                try:
                    await search.first.click(timeout=3_000)
                    await search.first.type(board_name, delay=TYPING_DELAY_MS)
                    await _human_sleep(SLEEP_MEDIUM, "board search")
                    logger.debug("[BOARD] Board search text entered")
                except Exception:
                    logger.debug("[BOARD] No board search input found")

            # Click the first board option available
            board_options = self._page.locator(
                'div[data-test-id="board-row"], '
                '[role="option"], '
                '[data-test-id="boardWithoutSection"]'
            )
            try:
                count = await board_options.count()
                logger.debug("[BOARD] Found %d board option(s)", count)
                await board_options.first.click(timeout=ACTION_TIMEOUT)
                await _human_sleep(SLEEP_SHORT, "board selected")
                logger.info("[BOARD] Board selected successfully")
            except Exception as e1:
                logger.debug("[BOARD] Primary board option click failed: %s — trying fallback", e1)
                # Try clicking any list item in the dropdown
                list_items = self._page.locator('[role="listbox"] [role="option"], ul li')
                fallback_count = await list_items.count()
                logger.debug("[BOARD] Fallback: found %d list items", fallback_count)
                await list_items.first.click(timeout=5_000)
                await _human_sleep(SLEEP_SHORT, "board selected (fallback)")
                logger.info("[BOARD] Board selected via fallback")

        except Exception as e:
            logger.warning("[BOARD] Board selection failed: %s — will try to publish anyway", e)
            await self._save_screenshot("board_selection_failed")
            # Press Escape to close any open dropdown
            logger.debug("[BOARD] Pressing Escape to close any open dropdown")
            await self._page.keyboard.press("Escape")
            await _human_sleep(SLEEP_SHORT, "escape dropdown")

    async def fill_metadata(self, title: str, description: str, tags: list[str]) -> None:
        """
        Fill all pin metadata.
        Tags are appended as #hashtags at the end of the description to avoid
        accidentally typing into the global search bar.
        """
        logger.info("[META] Starting metadata fill — title: '%s', desc length: %d, tags: %s",
                     title, len(description) if description else 0, tags)

        await self.fill_title(title)

        # Build description with hashtags appended
        full_description = description
        if tags:
            hashtags = " ".join(
                f"#{t.strip().replace(' ', '')}" for t in tags if t.strip()
            )
            full_description = f"{description}\n\n{hashtags}" if description else hashtags
            logger.debug("[META] Description with hashtags (%d chars total): '%s...'",
                         len(full_description), full_description[:100])

        await self.fill_description(full_description)
        await self._save_screenshot("diag_after_metadata")
        logger.info("[META] All metadata filled successfully (tags appended as hashtags in description)")

    # ── Publish ──────────────────────────────────────────────────────────

    async def submit(self) -> str | None:
        """Click Publish and wait for confirmation. Returns the URL."""
        logger.info("[SUBMIT] Starting pin publish sequence")
        logger.debug("[SUBMIT] Current URL before publish: %s", self._page.url)
        await _human_sleep(SLEEP_LONG, "before publish")

        # Scroll to top — the "Pubblica" button is in the page header
        logger.debug("[SUBMIT] Scrolling to top of page for publish button")
        await self._page.evaluate("window.scrollTo(0, 0)")
        await _human_sleep(SLEEP_SHORT, "scrolled to top for publish button")

        await self._save_screenshot("diag_before_publish")

        publish_btn = await self._find_publish_button()
        logger.info("[SUBMIT] Clicking publish button")
        await publish_btn.click()
        logger.info("[SUBMIT] Publish button clicked — waiting for response")

        # Pinterest may show a board selection popup after pressing Pubblica
        await self._handle_board_popup()

        # Wait for post-publish navigation
        logger.debug("[SUBMIT] Waiting for post-publish navigation/confirmation")
        await _human_sleep(SLEEP_LONG, "waiting for publish confirmation")

        try:
            await self._page.wait_for_load_state("networkidle", timeout=UPLOAD_TIMEOUT)
            logger.debug("[SUBMIT] Page reached networkidle state")
        except Exception:
            logger.warning("[SUBMIT] Timed out waiting for post-publish networkidle (%dms)", UPLOAD_TIMEOUT)

        await _human_sleep(SLEEP_SHORT, "post-publish settle")
        await self._save_screenshot("diag_after_publish")

        current_url = self._page.url
        logger.info("[SUBMIT] Post-publish URL: %s", current_url)

        if "/pin/" in current_url:
            logger.info("[SUBMIT] SUCCESS — Pin published at: %s", current_url)
            return current_url

        if "/pin-creation-tool/" in current_url or "/pin-builder/" in current_url:
            logger.info("[SUBMIT] SUCCESS — Pin published (redirected back to creation tool)")
            return current_url

        logger.warning("[SUBMIT] Unexpected post-publish URL: %s", current_url)
        return current_url

    # ── Board Popup After Publish ───────────────────────────────────────

    async def _handle_board_popup(self) -> None:
        """
        After clicking 'Pubblica', Pinterest may prompt the user to select
        a board. This method detects and handles that popup.
        """
        logger.debug("[BOARD-POPUP] Checking for post-publish board selection popup")
        await _human_sleep(SLEEP_MEDIUM, "waiting for board popup")
        await self._save_screenshot("diag_after_publish_click")

        try:
            # Look for a board selection list/popup
            board_option = self._page.locator(
                '[data-test-id="board-row"], '
                '[data-test-id="boardWithoutSection"], '
                '[role="listbox"] [role="option"]'
            )
            count = await board_option.count()
            logger.debug("[BOARD-POPUP] Found %d board option(s) in popup", count)
            if count > 0 and await board_option.first.is_visible(timeout=5_000):
                text = await board_option.first.text_content()
                logger.info("[BOARD-POPUP] Selecting first board from popup: '%s'", (text or '').strip()[:40])
                await board_option.first.click()
                logger.info("[BOARD-POPUP] Board selected from post-publish popup")
                await _human_sleep(SLEEP_SHORT, "after board popup selection")
                await self._save_screenshot("diag_board_popup_selected")
                return
        except Exception as e:
            logger.debug("[BOARD-POPUP] Board option check failed: %s", e)

        # Try: maybe it shows a "Create board" or board name list as simple divs
        try:
            board_items = self._page.locator(
                'div[role="list"] div[role="listitem"], '
                'ul[role="list"] li'
            )
            count = await board_items.count()
            logger.debug("[BOARD-POPUP] Found %d list item(s) as fallback", count)
            if count > 0 and await board_items.first.is_visible(timeout=3_000):
                await board_items.first.click()
                logger.info("[BOARD-POPUP] Board selected from list items")
                await _human_sleep(SLEEP_SHORT, "after board list selection")
                return
        except Exception as e:
            logger.debug("[BOARD-POPUP] List items fallback failed: %s", e)

        logger.debug("[BOARD-POPUP] No board popup appeared — continuing")

    # ── Diagnostics ──────────────────────────────────────────────────────

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
