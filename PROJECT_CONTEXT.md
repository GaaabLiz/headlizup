# Project Context: Headlizup

Questo progetto è un script/libreria Python progettata per automatizzare l'upload (e altre possibili interazioni future) su varie piattaforme (Civitai, Pinterest, ecc.) sfruttando un approccio "headless browser" basato su **Playwright**.

## Struttura del Progetto
Attualmente il progetto si compone dei seguenti moduli principali (situati all'interno della cartella `src`):
- `uploadToCivitai`: Logica e metodi per interagire tramite browser con Civitai.
- `uploadToPinterest`: Logica e metodi per interagire tramite browser con Pinterest.

In radice sono presenti:
- `main.py`: Punto di ingresso, originariamente pensato come API FastAPI (ma usabile potenzialmente anche per operazioni batch/CLI un domani).
- `logger.py`: Gestione unificata dei log.

## Gestione Autenticazione (Cookie)
In precedenti iterazioni, i cookie o lo state di autenticazione per i browser (salvati tipicamente come `.json`) erano gestiti staticamente.
**Attualmente:** Nessun file di credenziale o JSON viene (e non deve essere) pushato o salvato a livello di repository principale per evitare leak di sicurezza. 
La logica per caricare i file di cookie (se prevista dai costruttori dei browser playwright in `src/<piattaforma>/browser.py`) andrà parametrizzata ed esposta in modo flessibile affinché l'utilizzatore finale della libreria possa iniettare le credenziali esternamente (es. dal file system locale non tracciato o tramite variabili d'ambiente protette).

## Sviluppi Futuri
- Nuove piattaforme verranno aggiunte sotto `src/`.
- Graduale astrazione della porzione "server" (es. interfacce standardizzate usufruibili sia internamente come API che importate come libreria installabile in altri progetti via `uv`).
