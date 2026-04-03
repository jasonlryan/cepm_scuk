FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cepm/ cepm/
COPY server.py .
COPY mcp_server.py .
COPY privacy.md .
COPY openapi.json .

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Default: run Flask API via gunicorn
# Override CMD to run MCP server instead:
#   CMD ["python", "mcp_server.py", "--transport", "sse", "--port", "8080"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "300", "--log-level", "info", "server:app"]
