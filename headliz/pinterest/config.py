"""
Centralized configuration for Pinterest browser automation.

This is the SINGLE SOURCE OF TRUTH for all URLs and CSS selectors used
to interact with Pinterest's web UI. When Pinterest changes their frontend,
update ONLY this file to restore functionality.
"""

import os

# ── URLs ─────────────────────────────────────────────────────────────────────

PINTEREST_BASE_URL = "https://www.pinterest.com"
PINTEREST_LOGIN_URL = f"{PINTEREST_BASE_URL}/login/"
PINTEREST_PIN_CREATION_URL = f"{PINTEREST_BASE_URL}/pin-creation-tool/"

# ── Environment ──────────────────────────────────────────────────────────────

PINTEREST_EMAIL = os.getenv("GBNXD_API_BROWSER_PINTEREST_EMAIL", "")
PINTEREST_PASSWORD = os.getenv("GBNXD_API_BROWSER_PINTEREST_PASSWORD", "")
PINTEREST_HEADLESS = os.getenv("GBNXD_API_BROWSER_PINTEREST_HEADLESS", "true").lower() == "true"

# ── Paths ────────────────────────────────────────────────────────────────────


from headliz.config import TEMP_DIR, SCREENSHOTS_DIR

# ── Timeouts (ms) ───────────────────────────────────────────────────────────

NAVIGATION_TIMEOUT = 60_000
ACTION_TIMEOUT = 30_000
UPLOAD_TIMEOUT = 120_000

# ── Anti-bot sleep ranges (seconds) ─────────────────────────────────────────
# Used with random.uniform(min, max) between actions to mimic human behavior.

SLEEP_MICRO = (0.3, 0.8)       # Between keystrokes / tiny pauses
SLEEP_SHORT = (1.0, 2.5)       # Between form field interactions
SLEEP_MEDIUM = (2.5, 4.5)      # After page navigations / major actions
SLEEP_LONG = (4.0, 7.0)        # After login / before critical actions

# Typing delay per character (ms) — used with page.type(delay=...)
TYPING_DELAY_MS = 80

# ── CSS / XPath Selectors ───────────────────────────────────────────────────
#
# HOW TO MAINTAIN:
#   1. Open Pinterest in a browser, right-click the element → Inspect
#   2. Copy the most stable selector (prefer data-test-id, aria labels, roles)
#   3. Update the corresponding key below
#   4. Re-test the uploadToPinterest endpoint
#
# Selectors are grouped by page. Each selector has a comment describing
# what element it targets so you can locate it visually on the page.
#
# NOTE: The UI may be localized (IT, EN, etc.). Prefer structural selectors
# (data-test-id, input IDs, ARIA roles) over text-based ones.

SELECTORS = {
    # ── Login Page ───────────────────────────────────────────────────────
    # Email input field on the login form
    "login_email_input": '#email',
    # Password input field on the login form
    "login_password_input": '#password',
    # Login submit button (red "Log in" / "Accedi" button)
    "login_submit_button": 'button[type="submit"], div[data-test-id="registerFormSubmitButton"]',

    # ── Pin Creation Tool ────────────────────────────────────────────────
    # File input for image upload (hidden, Playwright handles it)
    "upload_file_input": 'input[type="file"]',

    # ── Cookie consent popup ─────────────────────────────────────────────
    # Accept cookies button (Pinterest GDPR banner)
    "cookie_accept_button": 'button[data-test-id="cookie-policy-banner-accept"]',

    # ── Misc ─────────────────────────────────────────────────────────────
    # Close button for any popup/modal overlay
    "modal_close_button": 'button[aria-label="close"], button[aria-label="Close"], button[aria-label="chiudi"], button[aria-label="Chiudi"]',
}
