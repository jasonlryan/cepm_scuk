FROM --platform=linux/amd64 python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PORT=8080
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/key.json

# Start the Flask application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "--log-level", "debug", "server:app"] 