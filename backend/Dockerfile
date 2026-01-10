FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt /tmp/requirements_backend.txt
COPY requirements.txt /tmp/requirements_src.txt

# Install dependencies
RUN pip install --no-cache-dir -r /tmp/requirements_backend.txt
RUN pip install --no-cache-dir -r /tmp/requirements_src.txt

# Copy backend application code to /app
COPY backend/ .

# Copy src directory for translation logic to /src
COPY src/ /src

# Expose API port (if needed for API service)
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
