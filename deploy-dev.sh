#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get version from argument or use latest from version.txt
VERSION=${1:-$(cat ../doc2-api/version.txt)}

echo -e "${GREEN}🚀 Deploying DocBits API Services to DEV - Version: $VERSION${NC}"
echo "=================================================="

# Ensure we're on the correct context
kubectl config use-context do-fra1-dev-stage

# Function to deploy a service
deploy_service() {
    local SERVICE_NAME=$1
    local VALUES_FILE=$2
    local DEPLOYMENT_NAME=${3:-$SERVICE_NAME}

    echo -e "\n${YELLOW}📦 Deploying $SERVICE_NAME...${NC}"

    # Check if values file exists
    if [ ! -f "$VALUES_FILE" ]; then
        echo -e "${RED}❌ Values file not found: $VALUES_FILE${NC}"
        exit 1
    fi

    # Deploy with Helm
    helm upgrade $SERVICE_NAME ./base \
        --install \
        --namespace dev \
        --values $VALUES_FILE \
        --set image.tag=$VERSION \
        --set fullnameOverride=$DEPLOYMENT_NAME \
        --wait --timeout 5m

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $SERVICE_NAME deployed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to deploy $SERVICE_NAME${NC}"
        exit 1
    fi
}

# Deploy all services in correct order
echo -e "${YELLOW}🔄 Starting deployments...${NC}"

# API Service
deploy_service "api" "values-dev-api.yaml" "api-service"

# Celery Worker
deploy_service "api-celery" "values-dev-api-celery.yaml" "api-celery"

# Beats Scheduler
deploy_service "api-beats" "values-dev-api-beats.yaml" "api-beats"

# Beats Worker
deploy_service "api-beats-worker" "values-dev-api-beats-worker.yaml" "api-beats-tasks"

# Flower UI
deploy_service "api-flower" "values-dev-api-flower.yaml" "flower-service"

echo -e "\n${GREEN}🎉 All services deployed successfully!${NC}"
echo "=================================================="

# Verify deployments
echo -e "\n${YELLOW}🔍 Verifying deployments...${NC}"
kubectl get deployments -n dev | grep -E "(api-service|api-celery|api-beats|api-beats-tasks|flower-service)"

# Check pod status
echo -e "\n${YELLOW}📊 Pod Status:${NC}"
kubectl get pods -n dev | grep -E "(api-service|api-celery|api-beats|api-beats-tasks|flower-service)" | head -10

echo -e "\n${GREEN}✨ Deployment complete!${NC}"
echo "=================================================="
echo "API: https://dev.api.docbits.com"
echo "Flower UI: https://dev.worker.api.docbits.com"