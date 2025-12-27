# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies including C++ for PyMuPDF
# This layer is cached unless system dependencies change
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    build-essential \
    libmupdf-dev \
    mupdf-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first for better caching
# This layer is cached unless requirements.txt changes
COPY requirements.txt .

# Install Python dependencies using pip
# This layer is cached unless requirements.txt changes
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Development runtime
FROM python:3.11-slim AS dev

WORKDIR /app

# Install only runtime dependencies (smaller image)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (this invalidates cache only when code changes)
COPY . .

# Create uploads and data directories
RUN mkdir -p /app/uploads /app/data/dvf /app/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
