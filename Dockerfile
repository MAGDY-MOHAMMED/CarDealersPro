# Optimized Dockerfile for faster builds on Hugging Face
FROM python:3.11-slim

WORKDIR /app

# Set environment variables early
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build argument to enable AI features (default: false for faster builds)
ARG ENABLE_AI=false
ENV ENABLE_AI=${ENABLE_AI}

# Install system dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install AI dependencies only if ENABLE_AI=true
COPY requirements-ai.txt .
RUN if [ "$ENABLE_AI" = "true" ]; then \
    echo "Installing AI dependencies..."; \
    pip install --no-cache-dir -r requirements-ai.txt; \
    else \
    echo "AI dependencies skipped (ENABLE_AI=false)"; \
    fi

# Copy application code
COPY . .

# Create storage directories
RUN mkdir -p /app/storage/uploads/images /app/storage/uploads/videos && \
    chmod -R 755 /app/storage

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start using Gunicorn with our custom config
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]
