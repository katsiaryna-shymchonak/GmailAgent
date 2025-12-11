# Dockerfile (корень репозитория)
FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/katsiarynashymchonak-trainee/GmailAgent"

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc zip unzip curl \
    && rm -rf /var/lib/apt/lists/*

# Create venv
RUN python -m venv /opt/venv

# Install server dependencies
COPY server/requirements.txt /app/server/requirements.txt
RUN /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/server/requirements.txt

# Copy server code
COPY server/ /app/server/

# Prepare extension folders
RUN mkdir -p /app/extension_root /app/server/static/extension

# Copy ONLY manifest.json (the only extension file in root)
COPY manifest.json /app/extension_root/manifest.json
COPY manifest.json /app/server/static/extension/manifest.json

# Create zip archive (contains only manifest.json)
RUN cd /app/server/static && (zip -r extension.zip extension || true)

# Runtime env vars (empty defaults)
ENV GEMINI_API_KEY="" \
    PG_DSN="" \
    GEMINI_MODEL="models/gemini-2.5-flash" \
    EMBEDDING_MODEL="text-embedding-004"

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

WORKDIR /app

EXPOSE 8000

CMD ["/opt/venv/bin/uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

