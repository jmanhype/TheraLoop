# Multi-stage Docker build for TheraLoop production deployment
# Stage 1: Builder for Python dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Node.js builder for UI
FROM node:20-alpine as ui-builder

WORKDIR /ui

# Copy package files
COPY ui/package*.json ./
RUN npm ci --only=production

# Copy UI source and build
COPY ui/ ./
RUN npm run build

# Stage 3: Final production image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Security: Run as non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /data /logs && \
    chown -R appuser:appuser /app /data /logs

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . /app

# Copy built UI from ui-builder
COPY --from=ui-builder --chown=appuser:appuser /ui/build ./ui/build

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app:$PYTHONPATH \
    THERALOOP_PROMPT_PATH=outputs/best_prompt.txt \
    THERALOOP_USE_GEPA=true \
    PORT=8080

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE 8080
CMD ["uvicorn", "theraloop.serving.production_app_secure:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]