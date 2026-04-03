#!/bin/bash

# CEPM Deployment Script — Flask API + MCP Server to Google Cloud Run
# Usage:
#   ./deploy.sh          Deploy Flask API only (default)
#   ./deploy.sh --mcp    Deploy MCP server only
#   ./deploy.sh --all    Deploy both

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()     { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error()   { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"; exit 1; }
warning() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"; }

# Parse arguments
DEPLOY_API=false
DEPLOY_MCP=false

case "${1:-api}" in
    --mcp)  DEPLOY_MCP=true ;;
    --all)  DEPLOY_API=true; DEPLOY_MCP=true ;;
    *)      DEPLOY_API=true ;;
esac

# Check prerequisites
command -v docker >/dev/null 2>&1 || error "Docker is not installed"
command -v gcloud >/dev/null 2>&1 || error "Google Cloud SDK is not installed"

if ! gcloud auth print-identity-token >/dev/null 2>&1; then
    error "Not authenticated with Google Cloud. Run 'gcloud auth login' first"
fi

export PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
[ -z "$PROJECT_ID" ] && error "Could not determine Google Cloud project ID"
log "Project: $PROJECT_ID"

# Enable required APIs
log "Enabling required APIs..."
gcloud services enable run.googleapis.com containerregistry.googleapis.com firestore.googleapis.com --quiet || \
    error "Failed to enable required APIs"

gcloud auth configure-docker --quiet || error "Failed to configure Docker auth"

# ============================================================
# Deploy Flask API (ChatGPT plugin)
# ============================================================
deploy_api() {
    local SERVICE="cepm-api"
    local IMAGE="gcr.io/$PROJECT_ID/$SERVICE"

    log "Building Flask API image..."
    docker build --platform linux/amd64 -t "$IMAGE" . || error "Docker build failed"

    log "Pushing to Container Registry..."
    docker push "$IMAGE" || error "Failed to push image"

    log "Deploying Flask API to Cloud Run..."
    gcloud run deploy "$SERVICE" \
        --image "$IMAGE" \
        --platform managed \
        --region europe-west1 \
        --allow-unauthenticated \
        --timeout 300 \
        --service-account flask-addition-service@scuk-test.iam.gserviceaccount.com \
        --quiet || error "Failed to deploy Flask API"

    local URL=$(gcloud run services describe "$SERVICE" \
        --platform managed --region europe-west1 \
        --format 'value(status.url)' 2>/dev/null)

    if [ -n "$URL" ]; then
        log "Flask API deployed: $URL"
        if curl -s "$URL" | grep -q "healthy"; then
            log "Health check passed"
        else
            warning "Health check failed — check logs"
        fi
    else
        error "Could not retrieve service URL"
    fi
}

# ============================================================
# Deploy MCP Server (Claude plugin — SSE transport)
# ============================================================
deploy_mcp() {
    local SERVICE="cepm-mcp"
    local IMAGE="gcr.io/$PROJECT_ID/$SERVICE"

    log "Building MCP server image..."
    docker build --platform linux/amd64 -f Dockerfile.mcp -t "$IMAGE" . || error "Docker build failed"

    log "Pushing to Container Registry..."
    docker push "$IMAGE" || error "Failed to push image"

    log "Deploying MCP server to Cloud Run..."
    gcloud run deploy "$SERVICE" \
        --image "$IMAGE" \
        --platform managed \
        --region europe-west1 \
        --allow-unauthenticated \
        --port 8443 \
        --timeout 300 \
        --service-account flask-addition-service@scuk-test.iam.gserviceaccount.com \
        --quiet || error "Failed to deploy MCP server"

    local URL=$(gcloud run services describe "$SERVICE" \
        --platform managed --region europe-west1 \
        --format 'value(status.url)' 2>/dev/null)

    if [ -n "$URL" ]; then
        log "MCP server deployed: $URL"
        log ""
        log "To connect from Claude Code, add to .mcp.json:"
        log "  {\"mcpServers\": {\"cepm\": {\"type\": \"sse\", \"url\": \"$URL/sse\"}}}"
        log ""
        log "To connect from Claude Desktop, add to claude_desktop_config.json:"
        log "  {\"mcpServers\": {\"cepm\": {\"type\": \"sse\", \"url\": \"$URL/sse\"}}}"
    else
        error "Could not retrieve service URL"
    fi
}

# Run deployments
$DEPLOY_API && deploy_api
$DEPLOY_MCP && deploy_mcp

cat << EOF

${GREEN}Deployment complete!${NC}

Monitor logs:
  gcloud logs tail --project=$PROJECT_ID

Cloud Run console:
  https://console.cloud.google.com/run?project=$PROJECT_ID

Local development:
  Flask API:   python server.py
  MCP (stdio): python mcp_server.py
  MCP (SSE):   python mcp_server.py --transport sse --port 8443
EOF
