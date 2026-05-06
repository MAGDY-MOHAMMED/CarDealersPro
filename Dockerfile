# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create storage directories with write permissions
RUN mkdir -p /app/storage/uploads/images /app/storage/uploads/videos && \
    chmod -R 755 /app/storage

# Expose port (Hugging Face uses 7860, can be overridden by PORT env var)
EXPOSE 7860

# Run the application using uvicorn (standard FastAPI practice)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
