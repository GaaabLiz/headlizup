import os
import json
from pathlib import Path

# Configurable path for Headliz data, defaults to ~/.headliz
HEADLIZ_PATH = os.getenv("HEADLIZ_PATH", str(Path.home() / ".headliz"))
HEADLIZ_DIR = Path(HEADLIZ_PATH)

CIVITAI_AUTH_PATH = HEADLIZ_DIR / "civitai_auth.json"
PINTEREST_AUTH_PATH = HEADLIZ_DIR / "pinterest_auth.json"

TEMP_DIR = str(HEADLIZ_DIR / "temp")
SCREENSHOTS_DIR = str(HEADLIZ_DIR / "screenshots")

def parse_cookie_string(cookie_string: str, domain: str) -> dict:
    """
    Parses a raw HTTP cookie string (e.g. 'name=value; name2=value2') into
    a Playwright compatible storage state dictionary.
    """
    cookies = []
    if cookie_string:
        cookie_string = cookie_string.strip()
        # Rimuove l'eventuale prefisso "Cookie: " se l'utente lo ha incluso per errore
        if cookie_string.lower().startswith("cookie:"):
            cookie_string = cookie_string[7:].strip()
            
        # Se la stringa non contiene '=' o ';', assumiamo che sia il valore del token principale
        if '=' not in cookie_string and ';' not in cookie_string:
            name = "__Secure-civitai-token" if "civitai" in domain else "_pinterest_sess"
            cookies.append({
                "name": name,
                "value": cookie_string,
                "domain": domain,
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax"
            })
            return {"cookies": cookies, "origins": []}

        for item in cookie_string.split(';'):
            item = item.strip()
            if not item:
                continue
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "expires": -1,
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax"
                })
    return {"cookies": cookies, "origins": []}
