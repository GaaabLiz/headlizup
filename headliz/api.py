import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from headliz.core import Headliz
from headliz.civitai.models import UploadToCivitaiRequest, UploadToCivitaiResponse
from headliz.pinterest.models import UploadToPinterestRequest, UploadToPinterestResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("headliz.api")

app = FastAPI(
    title="Headliz Web API",
    description="REST API per interagire con la libreria di browser automation per Pinterest e CivitAI",
    version="1.0.0"
)

# Inizializziamo il client della libreria (si occuperà anche di fare il parsing dei cookie dall'ambiente)
headliz_client = Headliz()

@app.post(
    "/civitai/upload",
    response_model=UploadToCivitaiResponse,
    description="Esegue l'upload di un'immagine su CivitAI utilizzando l'automazione del browser."
)
async def upload_to_civitai(request: UploadToCivitaiRequest):
    logger.info("Ricevuta richiesta di upload per CivitAI (Titolo: '%s')", request.title)
    try:
        response = await headliz_client.upload_to_civitai(request)
        if not response.success:
            logger.warning("Upload CivitAI fallito: %s", response.message)
            raise HTTPException(status_code=400, detail=response.message)
        return response
    except Exception as e:
        logger.error("Errore imprevisto durante l'upload su CivitAI: %s", str(e), exc_info=True)
        # Rilanciamo come HTTPException 500 se non è stata già sollevata una da noi
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/pinterest/upload",
    response_model=UploadToPinterestResponse,
    description="Esegue l'upload di un'immagine (pin) su Pinterest utilizzando l'automazione del browser."
)
async def upload_to_pinterest(request: UploadToPinterestRequest):
    logger.info("Ricevuta richiesta di upload per Pinterest (Titolo: '%s')", request.title)
    try:
        response = await headliz_client.upload_to_pinterest(request)
        if not response.success:
            logger.warning("Upload Pinterest fallito: %s", response.message)
            raise HTTPException(status_code=400, detail=response.message)
        return response
    except Exception as e:
        logger.error("Errore imprevisto durante l'upload su Pinterest: %s", str(e), exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    # Ottimo per il debug diretto se lanciato come script python api.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
