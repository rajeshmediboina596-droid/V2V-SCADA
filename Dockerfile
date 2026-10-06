FROM python:3.10-slim

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user and prepare persistent directories
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/database /app/reports && \
    chown -R appuser:appuser /app

# Copy application source code with non-root ownership
COPY --chown=appuser:appuser backend/ ./backend/
COPY --chown=appuser:appuser ml/ ./ml/
COPY --chown=appuser:appuser frontend/ ./frontend/
COPY --chown=appuser:appuser reports/ ./reports/

USER appuser

EXPOSE 8000

# Zero-dependency container health check using Python standard library
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

