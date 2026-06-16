# ── Stage 1: download model weights ───────────────────────────
# Separate stage so weights are cached in a Docker layer.
# Re-building the app code doesn't re-download models.
FROM python:3.11-slim AS model-downloader

WORKDIR /model-download

RUN pip install --no-cache-dir sentence-transformers==2.7.0

# Download both models into /models at build time.
# They are then COPYed into the final image — weights are baked in,
# no network call at container startup.
ARG EMBEDDING_MODEL=all-MiniLM-L6-v2
ARG RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

RUN python <<EOF

from sentence_transformers import SentenceTransformer, CrossEncoder
import shutil, os

print('Downloading embedding model...')
SentenceTransformer('${EMBEDDING_MODEL}').save('/models')
print('Downloading reranker model...')
model = CrossEncoder('${RERANKER_MODEL}')
model.save('./models/reranker')
hf_cache = os.path.expanduser('~/.cache/huggingface/hub')
if os.path.exists(hf_cache):
    shutil.copytree(hf_cache, '/models/hub', dirs_exist_ok=True)

    print('Models downloaded.')
EOF

# ── Stage 2: runtime image ────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Python dependencies (no torch CUDA — CPU only for this service)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy pre-downloaded model weights from stage 1
COPY --from=model-downloader /models /models

# Copy application code
COPY main.py .

# Model config — can be overridden via docker-compose environment
ENV EMBEDDING_MODEL=all-MiniLM-L6-v2
ENV RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
ENV MODEL_CACHE_DIR=/models
ENV PORT=8080

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app /models
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=20s --timeout=10s --retries=5 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "main.py"]
