# AloSM Zipformer ASR Server — CPU Image
# GPU: change base image to nvidia/cuda:12.x-runtime-ubuntu22.04
#       and set SHERPA_PROVIDER=cuda in .env

FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 wget curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements-asr.txt .
RUN pip install --no-cache-dir -r requirements-asr.txt

# Copy server code
COPY asr_server/ ./asr_server/
COPY src/voice/asr/zipformer/ ./src/voice/asr/zipformer/
COPY src/__init__.py ./src/

# Model directory (mount at runtime or bake in)
RUN mkdir -p data/models/asr

ENV SHERPA_PROVIDER=cpu
ENV ASR_SERVER_HOST=0.0.0.0
ENV ASR_SERVER_PORT=9000

EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:9000/ready || exit 1

CMD ["python", "-m", "uvicorn", "asr_server.server:app", "--host", "0.0.0.0", "--port", "9000"]
