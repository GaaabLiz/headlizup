import os
import base64
import asyncio
import httpx
from dotenv import load_dotenv
from headliz import Headliz, UploadToPinterestRequest

# Carica le variabili d'ambiente
load_dotenv()

async def get_test_image_base64():
    """Scarica un'immagine di test da Picsum e la restituisce codificata in base64."""
    url = "https://picsum.photos/600/900"  # Pinterest preferisce immagini verticali
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print(f"[TEST] Download immagine da: {url}")
        response = await client.get(url)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")
        else:
            raise Exception(f"Errore durante il download dell'immagine: {response.status_code}")

async def test_pinterest_upload():
    print("[TEST] Inizio test di upload su Pinterest...")
    
    # Verifica che il cookie sia presente
    pinterest_cookie = os.getenv("HEADLIZ_PINTEREST_COOKIE")
    if not pinterest_cookie:
        print("[ERRORE] HEADLIZ_PINTEREST_COOKIE non trovato nel file .env!")
        return

    try:
        # 1. Download immagine
        img_b64 = await get_test_image_base64()
        
        # 2. Inizializzazione libreria
        client = Headliz()
        
        # 3. Creazione della richiesta di upload
        request = UploadToPinterestRequest(
            image_base64=img_b64,
            title="Headliz Pinterest Test",
            description="Questo è un Pin di test creato automaticamente con Headliz.",
            link="https://github.com/gabliz/headliz"
        )
        
        # 4. Esecuzione upload
        print("[TEST] Avvio procedura di upload (richiede Playwright)...")
        response = await client.upload_to_pinterest(request)
        
        if response.success:
            print(f"[SUCCESS] Upload Pinterest completato!")
            print(f"[SUCCESS] URL del Pin: {response.pin_url}")
        else:
            print(f"[FAILED] Caricamento Pinterest fallito: {response.message}")
            if "login" in response.message.lower() or "auth" in response.message.lower():
                print("[INFO] Problema di autenticazione Pinterest. Controlla il cookie _pinterest_sess.")
                
    except Exception as e:
        print(f"[ERROR] Eccezione durante il test Pinterest: {e}")

if __name__ == "__main__":
    asyncio.run(test_pinterest_upload())
