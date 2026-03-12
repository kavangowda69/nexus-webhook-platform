# ================================
# Stage 1: Builder
# ================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ================================
# Stage 2: Runtime
# ================================
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependency (libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser
USER appuser