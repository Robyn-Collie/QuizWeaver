FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/generated_images /app/Quiz_Output

# Environment defaults
ENV SECRET_KEY=change-me-in-production
ENV DATABASE_PATH=/app/data/quiz_warehouse.db
ENV LLM_PROVIDER=mock

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "src.web.app:create_app()"]
