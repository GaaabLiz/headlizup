# Headliz

Headliz is a Python library that allows you to easily automate image uploads to **Civitai** and **Pinterest** using Playwright. 

Instead of configuring complex browser integrations or dealing with manual logins every time, Headliz uses your existing browser sessions (cookies) to securely log in and upload your images in the background.

## Features
- 🚀 **Automated Uploads**: Upload directly to Civitai posts and Pinterest boards without manual intervention.
- 🍪 **Environment Variable Cookies**: Simply provide your browser cookies via environment variables, and Headliz will automatically configure Playwright's authentication state.
- ⚙️ **Configurable Paths**: Customize where authentication files are stored.
- 🐍 **Simple Python API**: A unified `Headliz` class to handle your uploads seamlessly.

---

## Getting Started

### 1. Installation

As this package requires Playwright, make sure you install it and its browser dependencies:

```bash
pip install headlizup
playwright install chromium
```

### 2. Getting Your Authentication Cookies

To allow Headliz to upload on your behalf, you need to provide your session cookies from Civitai and Pinterest.

**Which specific cookies are required?**
When you log in to these platforms, they store specific authentication keys in your browser. These are the "digital keys" that prove you are logged in:
* **Pinterest**: The primary authentication cookies are `_pinterest_sess` and `_auth`. 
* **CivitAI**: The primary authentication cookie is `__Secure-next-auth.session-token` (or just `next-auth.session-token`).

**How to extract them (The easiest and most reliable method):**

Because websites use strict security architectures (like CSRF tokens), the most reliable way to authenticate Playwright is to provide the **entire raw `Cookie` header string**, which automatically bundles all necessary authentication keys (like `_pinterest_sess` and `next-auth.session-token`) formatted perfectly for our script. 

Here is the exact step-by-step process:

1. **Open Google Chrome** (or Edge/Brave) in normal mode (not incognito).
2. **Log into** [Civitai.com](https://civitai.com) (or [Pinterest.com](https://www.pinterest.com)).
3. Press **F12** on your keyboard (or right-click anywhere and select **Inspect**) to open Developer Tools.
4. Click on the **Network** tab at the top.
5. **Refresh the page** (F5) so the network requests appear.
6. Click on the very first request in the list at the top (usually named `civitai.com`, `www.pinterest.com` or `/`).
7. A panel will open on the right. Make sure you are in the **Headers** tab within that panel.
8. Scroll down until you find the section named **Request Headers**.
9. Look for the label named exactly **`Cookie:`**.
10. Right-click the **extremely long text value** next to it, and select **Copy Value**.

This long text is your raw cookie string, containing `__Secure-next-auth.session-token` (for Civitai) or `_pinterest_sess` (for Pinterest) properly formatted as `name=value;`.

### 3. Setting Environment Variables

Set the copied cookie strings as environment variables on your system:

**On Linux / macOS:**
```bash
export HEADLIZ_CIVITAI_COOKIE="<paste your civitai cookie string here>"
export HEADLIZ_PINTEREST_COOKIE="<paste your pinterest cookie string here>"
```

**On Windows (Command Prompt):**
```cmd
set HEADLIZ_CIVITAI_COOKIE="<paste your civitai cookie string here>"
set HEADLIZ_PINTEREST_COOKIE="<paste your pinterest cookie string here>"
```

*Optional*: By default, Headliz saves the parsed authentication JSON files in `~/.headliz` (in your user home directory). You can change this by setting:
```bash
export HEADLIZ_PATH="/custom/path/to/folder"
```

### 4. Basic Usage

Once your environment variables are set, you can use the library in your Python code:

```python
import asyncio
from headlizup import Headliz, UploadToCivitaiRequest, UploadToPinterestRequest

async def main():
    # Calling the class automatically reads the environment variables 
    # and generates the authentication JSON files!
    client = Headliz()
    
    # Let's say you have an image in base64 format
    img_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    # ── Upload to Civitai ──
    civitai_req = UploadToCivitaiRequest(
        image_base64=img_b64,
        title="My Awesome Creation",
        description="Created with Stable Diffusion",
        tags=["art", "ai", "portrait"]
    )
    
    print("Uploading to Civitai...")
    civitai_response = await client.upload_to_civitai(civitai_req)
    
    if civitai_response.success:
        print(f"Success! Post URL: {civitai_response.post_url}")
    else:
        print(f"Failed: {civitai_response.message}")
        
    # ── Upload to Pinterest ──
    pinterest_req = UploadToPinterestRequest(
        image_base64=img_b64,
        title="My Awesome Creation",
        description="Created with Stable Diffusion",
        board_name="AI Art", # Ensure this board exists on your profile!
        tags=["art", "ai"]
    )

    print("Uploading to Pinterest...")
    pinterest_response = await client.upload_to_pinterest(pinterest_req)
    
    if pinterest_response.success:
        print(f"Success! Pin URL: {pinterest_response.pin_url}")
    else:
        print(f"Failed: {pinterest_response.message}")

# Run the async code
asyncio.run(main())
```

### Troubleshooting
- **Authentication fails**: Your session cookies might have expired. When you log out and log back in, cookies change. Simply repeat *Step 2* to grab the new `Cookie` string and update your environment variables.
- **Missing Browser**: If you get an error from Playwright about a missing browser, ensure you ran `playwright install chromium`.
