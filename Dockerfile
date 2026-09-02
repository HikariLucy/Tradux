FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies needed at runtime if any (clean apt cache afterwards)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy build files and application code
COPY pyproject.toml README.md /app/
COPY app /app/app
RUN pip install --no-cache-dir .

# Create non-privileged user and create runtime directories
RUN useradd -m -u 1000 tradux && \
    mkdir -p /app/temp /app/output && \
    chown -R tradux:tradux /app

USER tradux

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
