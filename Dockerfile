# ───────────────────────── stage 1: build ─────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ───────────────────────── stage 2: runtime ────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

# sensible default env‑vars (override when docker‑run/docker‑compose)
ENV PORT=5001 \
    LOG_LEVEL=INFO

EXPOSE 5001

CMD ["uvicorn", "app.vehicle_service:app", "--host", "0.0.0.0", "--port", "5001"]