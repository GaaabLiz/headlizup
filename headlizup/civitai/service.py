"""
Orchestration service for uploading images to Civitai.

Full upload flow (with automatic retry on failure):
  1. Decode base64 image → save to temp file
  2. Open browser context (with auth state if available)
  3. Login if necessary
  4. Navigate to upload page
  5. Upload image + wait for analysis to complete
  6. Fill metadata (title, description, tags)
  7. Publish
  8. On any error after post creation → Delete Post + retry from scratch (up to MAX_RETRIES)
  9. Save auth state for next request
  10. Cleanup temp file
"""

import base64
import logging
import os
import uuid

from headlizup.civitai.browser import BrowserManager
from headlizup.civitai.config import CIVITAI_BASE_URL, TEMP_DIR, SCREENSHOTS_DIR
from headlizup.config import CIVITAI_AUTH_PATH
from headlizup.civitai.models import UploadToCivitaiRequest, UploadToCivitaiResponse
from headlizup.civitai.pages.login_page import LoginPage
from headlizup.civitai.pages.upload_page import UploadPage

logger = logging.getLogger("civitai.service")

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
    file_name = f"{uuid.uuid4().hex}.png"
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
    request: UploadToCivitaiRequest,
    attempt: int,
) -> str | None:
    """
    Single upload attempt: navigate → upload image → wait for analysis →
    fill metadata → publish.

    On failure, tries to delete the post before raising so the caller
    can retry cleanly.
    """
    upload_page = UploadPage(page)

    try:
        # ── Navigate to a fresh upload page ──────────────────────────────
        logger.info("Attempt %d: navigating to upload page", attempt)
        await upload_page.navigate_to_upload()

        # ── Upload image and wait for analysis to complete ────────────────
        await upload_page.upload_image(temp_file)

        # ── Fill title, description, tags ─────────────────────────────────
        await upload_page.fill_metadata(
            title=request.title,
            description=request.description,
            tags=request.tags,
        )

        # ── Publish ───────────────────────────────────────────────────────
        post_url = await upload_page.submit()
        return post_url

    except Exception as exc:
        logger.error("Attempt %d failed: %s — trying to delete post", attempt, exc)
        # Save screenshot for debugging
        try:
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            await page.screenshot(
                path=os.path.join(SCREENSHOTS_DIR, f"error_attempt_{attempt}.png"),
                full_page=False,
            )
        except Exception:
            pass
        # Delete the partial/broken post before retrying
        await upload_page.delete_post()
        raise


async def upload_to_civitai(
    request: UploadToCivitaiRequest,
    browser_manager: BrowserManager,
) -> UploadToCivitaiResponse:
    """
    Full upload flow with retry. On each failed attempt the partial post
    is deleted and the flow restarts from the upload page.
    """
    temp_file: str | None = None
    context = None

    try:
        # ── Step 0: Auth state required ──────────────────────────────────────
        if not os.path.exists(CIVITAI_AUTH_PATH):
            logger.error("Auth state file not found at %s", CIVITAI_AUTH_PATH)
            return UploadToCivitaiResponse(
                success=False,
                message=f"Auth state file not found at {CIVITAI_AUTH_PATH}. "
                    "Please provide a valid civitai_auth.json to authenticate with Civitai.",
            )

        # ── Step 1: Decode image ─────────────────────────────────────────
        logger.info("Decoding base64 image")
        temp_file = _decode_and_save_image(request.image_base64)

        # ── Step 2: Open browser context ─────────────────────────────────
        logger.info("Creating browser context")
        context = await browser_manager.new_context()
        page = await context.new_page()

        # ── Step 3: Auth check ───────────────────────────────────────────
        logger.info("Navigating to Civitai")
        await page.goto(CIVITAI_BASE_URL, wait_until="load")

        login_page = LoginPage(page)
        await login_page.dismiss_cookie_consent()

        if os.path.exists(CIVITAI_AUTH_PATH):
            logger.info("Auth state found — trusting saved session")
        elif not await login_page.is_logged_in():
            logger.info("Not logged in — performing login")
            await login_page.login()
        else:
            logger.info("Already logged in")

        # ── Steps 4–7: Upload with retry ─────────────────────────────────
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                post_url = await _do_upload_attempt(page, temp_file, request, attempt)

                # ── Success ───────────────────────────────────────────────────
                logger.info("Upload completed. Post URL: %s", post_url)
                return UploadToCivitaiResponse(
                    success=True,
                    message="Image uploaded to Civitai successfully",
                    post_url=post_url,
                )
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    logger.warning("Retrying upload (attempt %d/%d)…", attempt + 1, MAX_RETRIES)
                else:
                    logger.error("All %d attempts failed", MAX_RETRIES)

        return UploadToCivitaiResponse(
            success=False,
            message=f"Upload failed after {MAX_RETRIES} attempts: {last_exc}",
        )

    except ValueError as exc:
        logger.error("Validation error: %s", exc)
        return UploadToCivitaiResponse(success=False, message=str(exc))

    except Exception as exc:
        logger.exception("Unexpected error during Civitai upload")
        return UploadToCivitaiResponse(
            success=False,
            message=f"Unexpected error: {exc}",
        )

    finally:
        if temp_file:
            _cleanup_file(temp_file)
        if context:
            await context.close()
