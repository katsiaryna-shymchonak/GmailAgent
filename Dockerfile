# Dockerfile
FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/katsiarynashymchonak-trainee/GmailAgent"

# Set environment variables for Python and virtual environment
ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Create and configure virtual environment
RUN python -m venv /opt/venv

# Install server dependencies (ensure langchain-groq is in requirements.txt)
COPY server/requirements.txt /app/server/requirements.txt
RUN /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/server/requirements.txt

# Copy only server application code
COPY server/ /app/server/

# Runtime environment variables
ENV GROQ_API_KEY="" \
    GROQ_MODEL="llama-3.3-70b-versatile" \
    PG_DSN="" \
    GEMINI_API_KEY=""

# Configure non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

WORKDIR /app

EXPOSE 8000

# Launch application using uvicorn
CMD ["/opt/venv/bin/uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]