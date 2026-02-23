# ─── Stage 1: Builder ────────────────────────────────────────────────────────
# Install dependencies in an isolated layer so the final image only
# contains what it needs (no build tools, no pip cache).
FROM python:3.12-slim AS builder

WORKDIR /build

# System dependencies required to compile some Python packages (e.g. pymongo).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Python best-practices for containers:
#   PYTHONDONTWRITEBYTECODE – avoids .pyc clutter.
#   PYTHONUNBUFFERED        – ensures stdout/stderr reach container logs immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only the installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy application source.
COPY app/ ./app/

# Azure Container Apps injects PORT env var; default to 8000.
ENV PORT=8000
EXPOSE ${PORT}

# Non-root user for security (principle of least privilege).
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# ── Startup command ───────────────────────────────────────────────────────────
# --workers 2: sensible default for a Container App with 1 vCPU.
#              Increase via the WORKERS env var in the Container App config.
CMD uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers ${WORKERS:-2} \
    --log-level ${LOG_LEVEL:-info}
