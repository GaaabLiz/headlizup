import base64
import httpx
import asyncio
import json

async def test_docker_api():
    base_url = "http://localhost:8000"
    
    # 1. Download image
    image_url = "https://picsum.photos/800/600"
    print(f"Downloading image from {image_url}...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(image_url)
        if response.status_code != 200:
            print(f"Failed to download image: {response.status_code}")
            return
        image_base64 = base64.b64encode(response.content).decode('utf-8')

    # 2. Test Civitai Upload
    civitai_payload = {
        "image_base64": image_base64,
        "title": "Docker API Test - Civitai",
        "tags": ["docker", "api", "test"],
        "description": "This was uploaded via the Headliz Docker API"
    }
    
    print("\nTesting Civitai Upload via API...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(f"{base_url}/civitai/upload", json=civitai_payload)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error calling Civitai API: {e}")

    # 3. Test Pinterest Upload
    pinterest_payload = {
        "image_base64": image_base64,
        "title": "Docker API Test - Pinterest",
        "description": "This was uploaded via the Headliz Docker API",
        "tags": ["docker", "api", "test"],
        "board_name": "" # Use default board
    }
    
    print("\nTesting Pinterest Upload via API...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(f"{base_url}/pinterest/upload", json=pinterest_payload)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error calling Pinterest API: {e}")

if __name__ == "__main__":
    asyncio.run(test_docker_api())
