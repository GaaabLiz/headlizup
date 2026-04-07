import os
import base64
import asyncio
import httpx
from dotenv import load_dotenv
from headlizup import Headliz, UploadToCivitaiRequest

# Carica le variabili d'ambiente dal file .env nella root del progetto
# Cerchiamo il file .env partendo dalla cartella corrente e risalendo se necessario (comportamento standard di load_dotenv)
load_dotenv()

async def get_test_image_base64():
    """Scarica un'immagine di test da Unsplash e la restituisce codificata in base64."""
    # Un'immagine di esempio generata da Picsum
    url = "https://picsum.photos/500/500"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print(f"[TEST] Download immagine da: {url}")
        response = await client.get(url)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")
        else:
            raise Exception(f"Errore durante il download dell'immagine: {response.status_code}")

async def test_civitai_upload():
    print("[TEST] Inizio test di upload su Civitai...")
    
    # Verifica che il cookie sia presente
    civitai_cookie = os.getenv("HEADLIZ_CIVITAI_COOKIE")
    if not civitai_cookie:
        print("[ERRORE] HEADLIZ_CIVITAI_COOKIE non trovato nel file .env!")
        return

    try:
        # 1. Download immagine
        img_b64 = await get_test_image_base64()
        
        # 2. Inizializzazione libreria
        client = Headliz()
        
        # 3. Creazione della richiesta di upload
        request = UploadToCivitaiRequest(
            image_base64=img_b64,
            title="Headliz Automated Test",
            description="Caricamento di test eseguito automaticamente dalla libreria Headliz.",
            tags=["automation", "test", "headliz"]
        )
        
        # 4. Esecuzione upload
        print("[TEST] Avvio procedura di upload (richiede Playwright)...")
        response = await client.upload_to_civitai(request)
        
        if response.success:
            print(f"[SUCCESS] Upload completato con successo!")
            print(f"[SUCCESS] URL del post: {response.post_url}")
        else:
            print(f"[FAILED] Caricamento fallito: {response.message}")
            if "login" in response.message.lower() or "auth" in response.message.lower():
                print("[INFO] Sembra esserci un problema di autenticazione. Verificare il cookie.")
                
    except Exception as e:
        print(f"[ERROR] Eccezione durante il test: {e}")

if __name__ == "__main__":
    asyncio.run(test_civitai_upload())
