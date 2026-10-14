# syntax=docker/dockerfile:1.6

# =============================================================================
# Stage 1 — Builder
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time toolchain (only needed to compile native wheels).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Fast pip replacement.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Requirements are copied separately for better layer caching.
COPY requirements.txt requirements-ml.txt requirements-ai.txt ./

# `ENABLE_AI` gates ONLY the extra LLM/client packages (litellm, openai, ...).
# The ML stack (torch, numpy, pandas, sklearn) is ALWAYS installed because
# app.main imports the AI router which imports the ML services.
ARG ENABLE_AI=false
RUN if [ "$ENABLE_AI" = "true" ]; then \
        uv pip install --system --no-cache \
            -r requirements.txt \
            -r requirements-ml.txt \
            -r requirements-ai.txt ; \
    else \
        uv pip install --system --no-cache \
            -r requirements.txt \
            -r requirements-ml.txt ; \
    fi


# =============================================================================
# Stage 2 — Runtime
# =============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    MPLBACKEND=Agg

# Runtime-only shared libraries.
#
# IMPORTANT — `libgl1-mesa-glx` is DEPRECATED on Debian Bookworm and no longer
# installable. The correct split is `libgl1` + `libglx-mesa0`. Adding the
# X11 stubs (libsm6/libxext6/libxrender1) prevents cryptic "libGL.so.1:
# cannot open shared object file" errors from OpenCV in Pillow/torchvision.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        libgl1 \
        libglx-mesa0 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Bring in everything built in stage 1.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

# Pre-create runtime directories with correct ownership.
RUN mkdir -p /app/storage/uploads/images \
             /app/storage/uploads/videos \
             /app/ai_models/ai_artifacts \
             /app/data/optimized

EXPOSE 8000

# start-period covers torch cold-import (~10-20s on slow disks).
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]