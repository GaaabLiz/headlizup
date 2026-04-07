"""
Orchestration service for uploading images to Pinterest.

Full upload flow (with automatic retry on failure):
  1. Decode base64 image → save to temp file
  2. Open browser context (with auth state if available)
  3. Login if necessary
  4. Navigate to pin creation tool
  5. Upload image
  6. Fill metadata (title, description, tags as hashtags)
  7. Select board
  8. Publish
  9. Save auth state for next request
  10. Cleanup temp file
"""

import base64
import logging
import os
import uuid

from headlizup.pinterest.browser import PinterestBrowserManager
from headlizup.pinterest.config import (
    PINTEREST_BASE_URL,
    TEMP_DIR,
    SCREENSHOTS_DIR,
)
from headlizup.pinterest.models import UploadToPinterestRequest, UploadToPinterestResponse
from headlizup.pinterest.pages.login_page import PinterestLoginPage
from headlizup.pinterest.pages.upload_page import PinterestUploadPage

logger = logging.getLogger("pinterest.service")

MAX_RETRIES = 2


def _decode_and_save_image(image_base64: str) -> str:
    """
    Decode a base64 string and write it to a temp file.

    Returns:
        Absolute path to the saved image file.

    Raises:
        ValueError: if the base64 payload is invalid.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    file_name = f"pinterest_{uuid.uuid4().hex}.png"
    file_path = os.path.join(TEMP_DIR, file_name)

    logger.debug("[DECODE] Decoding base64 payload (%d chars)", len(image_base64))
    try:
        image_data = base64.b64decode(image_base64)
    except Exception as exc:
        logger.error("[DECODE] Invalid base64 data: %s", exc)
        raise ValueError(f"Invalid base64 image data: {exc}") from exc

    with open(file_path, "wb") as f:
        f.write(image_data)

    logger.info("[DECODE] Image saved: %s (%d bytes / %.2f KB)", file_path, len(image_data), len(image_data) / 1024)
    return file_path


def _cleanup_file(path: str) -> None:
    """Remove a temp file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info("[CLEANUP] Removed temp file: %s", path)
        else:
            logger.debug("[CLEANUP] File already gone: %s", path)
    except OSError as exc:
        logger.warning("[CLEANUP] Failed to remove %s: %s", path, exc)


async def _do_upload_attempt(
    page,
    temp_file: str,
    request: UploadToPinterestRequest,
    attempt: int,
) -> str | None:
    """
    Single upload attempt: navigate → upload image → fill metadata →
    select board → publish.
    """
    upload_page = PinterestUploadPage(page)

    try:
        # ── Navigate to pin creation tool ────────────────────────────────
        logger.info("[ATTEMPT %d] Step 1/4: Navigating to pin creation tool", attempt)
        await upload_page.navigate_to_pin_creation()

        # ── Upload image ─────────────────────────────────────────────────
        logger.info("[ATTEMPT %d] Step 2/4: Uploading image", attempt)
        await upload_page.upload_image(temp_file)

        # ── Fill title, description, tags ────────────────────────────────
        logger.info("[ATTEMPT %d] Step 3/4: Filling metadata (title='%s', %d tags)",
                     attempt, request.title, len(request.tags) if request.tags else 0)
        await upload_page.fill_metadata(
            title=request.title,
            description=request.description,
            tags=request.tags,
        )

        # ── Select board ─────────────────────────────────────────────────
        logger.info("[ATTEMPT %d] Step 3.5/4: Selecting board '%s'", attempt, request.board_name or 'default')
        await upload_page.select_board(request.board_name)

        # ── Publish ──────────────────────────────────────────────────────
        logger.info("[ATTEMPT %d] Step 4/4: Publishing pin", attempt)
        pin_url = await upload_page.submit()
        logger.info("[ATTEMPT %d] Upload attempt SUCCEEDED — pin_url: %s", attempt, pin_url)
        return pin_url

    except Exception as exc:
        logger.error("[ATTEMPT %d] FAILED: %s", attempt, exc, exc_info=True)
        # Save screenshot for debugging
        try:
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            screenshot_path = os.path.join(SCREENSHOTS_DIR, f"pinterest_error_attempt_{attempt}.png")
            await page.screenshot(
                path=screenshot_path,
                full_page=True,
            )
            logger.info("[ATTEMPT %d] Error screenshot saved: %s", attempt, screenshot_path)
        except Exception as ss_exc:
            logger.warning("[ATTEMPT %d] Could not save error screenshot: %s", attempt, ss_exc)
        raise


async def upload_to_pinterest(
    request: UploadToPinterestRequest,
    browser_manager: PinterestBrowserManager,
) -> UploadToPinterestResponse:
    """
    Full upload flow with retry.
    """
    temp_file: str | None = None
    context = None

    try:
        # ── Step 1: Decode image ─────────────────────────────────────────
        logger.info("[FLOW] ═══ Starting Pinterest upload flow ═══")
        logger.info("[FLOW] Request: title='%s', description='%s...', tags=%s, board='%s'",
                     request.title, (request.description or '')[:50], request.tags, request.board_name or 'default')
        logger.info("[FLOW] Step 1: Decoding base64 image (%d chars)", len(request.image_base64))
        temp_file = _decode_and_save_image(request.image_base64)

        # ── Step 2: Open browser context ─────────────────────────────────
        logger.info("[FLOW] Step 2: Creating Pinterest browser context")
        context = await browser_manager.new_context()
        page = await context.new_page()
        logger.debug("[FLOW] Browser context created, new page opened")

        # ── Step 3: Auth check ───────────────────────────────────────────
        logger.info("[FLOW] Step 3: Navigating to Pinterest for auth check")
        await page.goto(PINTEREST_BASE_URL, wait_until="networkidle")
        logger.debug("[FLOW] Pinterest home loaded — URL: %s", page.url)

        login_page = PinterestLoginPage(page)
        await login_page.dismiss_cookie_consent()

        if not await login_page.is_logged_in():
            # is_logged_in navigated to /pin-creation-tool/ which redirected to login
            logger.info("[FLOW] Not logged in — performing Pinterest login")
            await login_page.login()
            # Save auth state after successful login
            logger.info("[FLOW] Saving auth state after login")
            await browser_manager.save_auth_state(context)
        else:
            # is_logged_in already navigated to /pin-creation-tool/ successfully
            logger.info("[FLOW] Already logged in to Pinterest (skipping login step)")

        # ── Steps 4–8: Upload with retry ─────────────────────────────────
        logger.info("[FLOW] Step 4: Starting upload (max %d attempts)", MAX_RETRIES)
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("[FLOW] ─── Upload attempt %d/%d ───", attempt, MAX_RETRIES)
                pin_url = await _do_upload_attempt(page, temp_file, request, attempt)

                # ── Success ───────────────────────────────────────────────
                logger.info("[FLOW] ═══ Upload SUCCEEDED ═══ Pin URL: %s", pin_url)
                # Update auth state
                logger.debug("[FLOW] Updating auth state after successful upload")
                await browser_manager.save_auth_state(context)

                return UploadToPinterestResponse(
                    success=True,
                    message="Image uploaded to Pinterest successfully",
                    pin_url=pin_url,
                )
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    logger.warning("[FLOW] Attempt %d failed — retrying (%d/%d)…", attempt, attempt + 1, MAX_RETRIES)
                else:
                    logger.error("[FLOW] ═══ All %d attempts FAILED ═══", MAX_RETRIES)

        return UploadToPinterestResponse(
            success=False,
            message=f"Upload failed after {MAX_RETRIES} attempts: {last_exc}",
        )

    except ValueError as exc:
        logger.error("[FLOW] Validation error: %s", exc)
        return UploadToPinterestResponse(success=False, message=str(exc))

    except Exception as exc:
        logger.exception("[FLOW] ═══ UNEXPECTED ERROR during Pinterest upload ═══")
        return UploadToPinterestResponse(
            success=False,
            message=f"Unexpected error: {exc}",
        )

    finally:
        logger.info("[FLOW] Cleanup phase")
        if temp_file:
            _cleanup_file(temp_file)
        if context:
            logger.debug("[FLOW] Closing browser context")
            await context.close()
        logger.info("[FLOW] ═══ Pinterest upload flow ended ═══")
