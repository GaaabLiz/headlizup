"""
Centralized configuration for Civitai browser automation.

This is the SINGLE SOURCE OF TRUTH for all URLs and CSS selectors used
to interact with Civitai's web UI. When Civitai changes their frontend,
update ONLY this file to restore functionality.
"""

import os

# ── URLs ─────────────────────────────────────────────────────────────────────

CIVITAI_BASE_URL = "https://civitai.com"
CIVITAI_LOGIN_URL = f"{CIVITAI_BASE_URL}/login"
CIVITAI_POSTS_CREATE_URL = f"{CIVITAI_BASE_URL}/posts/create"

# ── Environment ──────────────────────────────────────────────────────────────

GBNXD_API_BROWSER_CIVITAI_EMAIL = os.getenv("GBNXD_API_BROWSER_CIVITAI_EMAIL", "")
GBNXD_API_BROWSER_CIVITAI_PASSWORD = os.getenv("GBNXD_API_BROWSER_CIVITAI_PASSWORD", "")
GBNXD_API_BROWSER_CIVITAI_HEADLESS = os.getenv("GBNXD_API_BROWSER_CIVITAI_HEADLESS", "true").lower() == "true"

# ── Paths ────────────────────────────────────────────────────────────────────


from headlizup.config import TEMP_DIR, SCREENSHOTS_DIR

# ── Timeouts (ms) ───────────────────────────────────────────────────────────

NAVIGATION_TIMEOUT = 60_000
ACTION_TIMEOUT = 30_000
UPLOAD_TIMEOUT = 120_000

# ── CSS / XPath Selectors ───────────────────────────────────────────────────
#
# HOW TO MAINTAIN:
#   1. Open Civitai in a browser, right-click the element → Inspect
#   2. Copy the most stable selector (prefer data-* attrs, aria labels, roles)
#   3. Update the corresponding key below
#   4. Re-test the uploadToCivitai endpoint
#
# Selectors are grouped by page. Each selector has a comment describing
# what element it targets so you can locate it visually on the page.

SELECTORS = {
    # ── Cookie consent popup (GDPR) ─────────────────────────────────────
    # "Accept all & visit the site" — is a <div>, NOT a <button>
    "cookie_accept_button": '#accept-choices',
    "cookie_accept_iframe": 'iframe[id^="sp_message_iframe"], iframe[title*="privacy"], iframe[title*="Privacy"]',

    # ── Login Page ───────────────────────────────────────────────────────
    # Email input field on the login form
    "login_email_input": 'input[name="email"]',
    # Continue button shown after entering email (step 1 of two-step login)
    "login_continue_button": 'button:has-text("Continue"), button:has-text("Next")',
    # Password input field on the login form (step 2)
    "login_password_input": 'input[name="password"]',
    # Submit button on the login form
    "login_submit_button": 'button[type="submit"]',

    # ── Logged-in state detection ────────────────────────────────────────
    # Element visible only when the user is logged in (e.g. user menu avatar)
    "user_avatar": 'button[aria-label="Account menu"]',

    # ── Joyride onboarding tour overlay ──────────────────────────────────
    # Dismiss button for the react-joyride guided tour (appears on first visit)
    "joyride_close_button": 'button[data-action="close"], button[aria-label="Close"], [data-test-id="button-skip"]',
    "joyride_skip_button": 'button:has-text("Skip"), button:has-text("×"), button:has-text("✕")',
    "joyride_spotlight": '[data-test-id="spotlight"]',

    # File input element for uploading images (may be hidden, Playwright handles it)
    "upload_file_input": 'input[type="file"]',
    # Title input field for the post
    "post_title_input": '[placeholder="Add a title..."]',
    # Description / body text area (contenteditable or textarea)
    "post_description_input": '[contenteditable="true"], textarea[placeholder*="description"], textarea[placeholder*="Description"]',
    # "+ Tag" button that reveals the tag input
    "tag_add_button": 'button:has-text("Tag")',
    # Tag input field (revealed after clicking + Tag)
    "tag_input": 'input[placeholder*="tag"], input[placeholder*="Tag"], input[id*="tag"], input[name*="tag"]',
    # Tag suggestion / dropdown item (used after typing a tag to select it)
    "tag_suggestion_item": '[role="option"], .mantine-Autocomplete-item',
    # Publish / Submit button
    "publish_button": '[data-tour="post:publish"], button:has-text("Publish")',
    # Delete Post button (used for cleanup on error)
    "delete_post_button": 'button:has-text("Delete Post")',

    # ── Post-upload confirmation ─────────────────────────────────────────
    # Element or URL pattern that confirms the post was published
    "post_success_indicator": 'text="Your post has been published"',
    # Image analysis in progress notice — wait for this to disappear before publishing
    "analysis_in_progress": 'text="Analyzing image"',
}
