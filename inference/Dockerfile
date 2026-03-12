FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY model_server.py .

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 3001
CMD ["bentoml", "serve", "model_server:InferenceService", "--port", "3001"]