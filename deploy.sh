#!/bin/bash

# Exit on any error
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function for logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Check for required tools
command -v docker >/dev/null 2>&1 || error "Docker is not installed"
command -v gcloud >/dev/null 2>&1 || error "Google Cloud SDK is not installed"

# Check if user is authenticated with gcloud
if ! gcloud auth print-identity-token >/dev/null 2>&1; then
    error "Not authenticated with Google Cloud. Please run 'gcloud auth login' first"
fi

# Get the project ID
export PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    error "Could not determine Google Cloud project ID"
fi
log "Using Google Cloud Project: $PROJECT_ID"

# Enable required APIs
log "Enabling required APIs..."
gcloud services enable run.googleapis.com containerregistry.googleapis.com --quiet || \
    error "Failed to enable required APIs"

# Verify Docker authentication
log "Verifying Docker authentication..."
if ! gcloud auth configure-docker --quiet; then
    error "Failed to configure Docker authentication"
fi

# Build the Docker image
log "Building Docker image..."
if ! docker build --platform linux/amd64 \
    -t gcr.io/$PROJECT_ID/flask-addition-service .; then
    error "Docker build failed"
fi

# Push to Google Container Registry
log "Pushing to Google Container Registry..."
if ! docker push gcr.io/$PROJECT_ID/flask-addition-service; then
    error "Failed to push image to Google Container Registry"
fi

# Deploy to Cloud Run
log "Deploying to Cloud Run..."
if ! gcloud run deploy flask-addition-service \
    --image gcr.io/$PROJECT_ID/flask-addition-service \
    --platform managed \
    --region europe-west1 \
    --allow-unauthenticated \
    --timeout 300 \
    --service-account flask-addition-service@scuk-test.iam.gserviceaccount.com \
    --quiet; then
    error "Failed to deploy to Cloud Run"
fi

# Verify deployment
SERVICE_URL=$(gcloud run services describe flask-addition-service \
    --platform managed \
    --region europe-west1 \
    --format 'value(status.url)' 2>/dev/null)

if [ -n "$SERVICE_URL" ]; then
    log "Service deployed successfully!"
    log "Service URL: $SERVICE_URL"
    
    # Test the health check endpoint
    log "Testing health check endpoint..."
    if curl -s "$SERVICE_URL" | grep -q "healthy"; then
        log "Health check passed ✅"
    else
        warning "Health check failed. Please check the logs in Cloud Console"
    fi
else
    error "Could not retrieve service URL"
fi

# Print helpful next steps
cat << EOF

${GREEN}Deployment completed successfully!${NC}

Next steps:
1. View your service: $SERVICE_URL
2. Monitor logs: gcloud logs tail --project=$PROJECT_ID --service=flask-addition-service
3. Update configuration: gcloud run services update flask-addition-service --help

For troubleshooting, visit the Cloud Run console:
https://console.cloud.google.com/run/detail/europe-west1/flask-addition-service?project=$PROJECT_ID
EOF 