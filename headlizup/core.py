import os
import json
from headlizup.config import (
    HEADLIZ_DIR,
    CIVITAI_AUTH_PATH,
    PINTEREST_AUTH_PATH,
    parse_cookie_string
)
from headlizup.civitai.service import upload_to_civitai
from headlizup.civitai.models import UploadToCivitaiRequest, UploadToCivitaiResponse
from headlizup.civitai.browser import BrowserManager

from headlizup.pinterest.service import upload_to_pinterest
from headlizup.pinterest.models import UploadToPinterestRequest, UploadToPinterestResponse
from headlizup.pinterest.browser import PinterestBrowserManager

class Headliz:
    def __init__(self):
        """
        Initializes the Headliz library. 
        It looks for HEADLIZ_CIVITAI_COOKIE and HEADLIZ_PINTEREST_COOKIE
        environment variables to build the necessary session files.
        """
        self._setup_auth()

    def _setup_auth(self):
        civitai_cookie = os.getenv("HEADLIZ_CIVITAI_COOKIE")
        if civitai_cookie:
            HEADLIZ_DIR.mkdir(parents=True, exist_ok=True)
            # Aggiungiamo sia il dominio con punto che senza per massimizzare la probabilità che Playwright lo invii
            state_dot = parse_cookie_string(civitai_cookie, ".civitai.com")
            state_bare = parse_cookie_string(civitai_cookie, "civitai.com")
            
            combined_cookies = state_dot["cookies"] + state_bare["cookies"]
            state = {"cookies": combined_cookies, "origins": []}
            CIVITAI_AUTH_PATH.write_text(json.dumps(state, indent=2))

        pinterest_cookie = os.getenv("HEADLIZ_PINTEREST_COOKIE")
        if pinterest_cookie:
            HEADLIZ_DIR.mkdir(parents=True, exist_ok=True)
            # Aggiungiamo sia il dominio con punto che senza per massimizzare la probabilità che Playwright lo invii
            state_dot = parse_cookie_string(pinterest_cookie, ".pinterest.com")
            state_bare = parse_cookie_string(pinterest_cookie, "pinterest.com")
            
            combined_cookies = state_dot["cookies"] + state_bare["cookies"]
            state = {"cookies": combined_cookies, "origins": []}
            PINTEREST_AUTH_PATH.write_text(json.dumps(state, indent=2))

    async def upload_to_civitai(self, request: UploadToCivitaiRequest) -> UploadToCivitaiResponse:
        """Uploads an image to Civitai."""
        browser_manager = BrowserManager()
        try:
            return await upload_to_civitai(request, browser_manager)
        finally:
            await browser_manager.close()

    async def upload_to_pinterest(self, request: UploadToPinterestRequest) -> UploadToPinterestResponse:
        """Uploads a pin to Pinterest."""
        browser_manager = PinterestBrowserManager()
        try:
            return await upload_to_pinterest(request, browser_manager)
        finally:
            await browser_manager.close()
