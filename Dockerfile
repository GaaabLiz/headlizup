FROM python:3.13-slim

# Imposta variabili d'ambiente per Python e uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Imposta dove salvare i dati di headliz (cookie, temp, screenshots)
ENV HEADLIZ_PATH=/data

WORKDIR /app

# Installa 'uv'
ENV PATH="/root/.cargo/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia i file per l'installazione delle dipendenze
COPY pyproject.toml uv.lock ./

# Installa le dipendenze Python tramite uv, nella cartella di sistema (usando --system)
RUN uv pip install --system -r pyproject.toml

# Installa i browser Playwright e le loro dipendenze di sistema
RUN playwright install chromium --with-deps

# Crea la directory per i dati, così evitiamo problemi di permessi con i volumi successivi pre-creandola
RUN mkdir -p /data

# Copia tutto il resto dell'applicazione
COPY README.md ./
COPY headliz/ ./headliz/

# Esponi la porta 8000 utilizzata da FastAPI/Uvicorn
EXPOSE 8000

# Avvia l'app FastAPI di default
CMD ["uvicorn", "headliz.api:app", "--host", "0.0.0.0", "--port", "8000"]
