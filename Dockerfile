FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY etl/ ./etl/

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chmod 755 /app/logs

# Create a non-root user
RUN useradd --create-home --shell /bin/bash etl_user
RUN chown -R etl_user:etl_user /app
USER etl_user

# Set Python path
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Healthcheck for container
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import psycopg2; print('Health check passed')" || exit 1

# Run the ETL script
CMD ["python", "etl/etl.py"]
