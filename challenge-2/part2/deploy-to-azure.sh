#!/bin/bash

# Azure Container Apps Deployment Script for Frau# Configuration variables - derived from .env file and existing resources
RESOURCE_GROUP="rgv1"  # Using existing resource group from previous challenges
LOCATION="swedencentral"  # Location of existing resources
CONTAINER_APP_ENV="fraud-api-env-${UNIQUE_SUFFIX}"
CONTAINER_APP_NAME="fraud-api-${UNIQUE_SUFFIX}"ection API
# This script deploys the containerized fraud detection orchestration system
# 
# Prerequisites:
# - Run challenge-0 setup first to create the base Azure resources (Resource Group, ACR, etc.)
# - Ensure the .env file exists with all required environment variables
# - Azure CLI must be installed and logged in

set -e  # Exit on any error

# Load environment variables from .env file
ENV_FILE="../../.env"
if [ -f "$ENV_FILE" ]; then
    echo "📋 Loading environment variables from $ENV_FILE"
    # Source the .env file, handling quoted values properly
    export $(grep -v '^#' "$ENV_FILE" | sed 's/^/export /' | sed 's/"//g' | xargs)
    echo "✅ Environment variables loaded successfully"
else
    echo "❌ .env file not found at $ENV_FILE"
    echo "Please ensure you have run the get-keys.sh script from challenge-0 to generate the .env file"
    exit 1
fi

# Validate required environment variables are set
REQUIRED_VARS=(
    "ACR_NAME"
    "ACR_LOGIN_SERVER"
    "ACR_USERNAME"
    "ACR_PASSWORD"
    "AZURE_OPENAI_ENDPOINT"
    "AZURE_OPENAI_KEY"
    "AZURE_OPENAI_DEPLOYMENT_NAME"
    "COSMOS_ENDPOINT"
    "COSMOS_KEY"
    "SEARCH_SERVICE_ENDPOINT"
    "SEARCH_ADMIN_KEY"
)

echo "🔍 Validating required environment variables..."
MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo "Please ensure your .env file contains all required values."
    exit 1
fi

echo "✅ All required environment variables are set"

# Extract the unique suffix from existing resource names (e.g., "wuo2agocdyhaa" from "msagthack-search-wuo2agocdyhaa")
UNIQUE_SUFFIX=$(echo "$SEARCH_SERVICE_NAME" | sed 's/.*-//')

# Configuration variables - derived from .env file and existing resources
RESOURCE_GROUP="rgv1"  # Using existing resource group from previous challenges
LOCATION="swedencentral"  # Location of existing resources
CONTAINER_APP_ENV="msagthack-containerapp-env2-${UNIQUE_SUFFIX}"
CONTAINER_APP_NAME="fraud-api-${UNIQUE_SUFFIX}"
# ACR_NAME is already defined in .env file
IMAGE_NAME="fraud-detection-api"
IMAGE_TAG="latest"

echo "🚀 Starting Azure Container Apps deployment for Fraud Detection API"
echo ""
echo "📋 Using the following existing resources from previous challenges:"
echo "   Resource Group: $RESOURCE_GROUP (existing from challenge-0)"
echo "   Container App Environment: $CONTAINER_APP_ENV (will create if needed)"
echo "   Container App Name: $CONTAINER_APP_NAME (will create/update)"
echo "   ACR Name: $ACR_NAME (existing from challenge-0)"
echo "   ACR Login Server: $ACR_LOGIN_SERVER (existing from challenge-0)"
echo "   Location: $LOCATION"
echo ""

# Check if Azure CLI is installed and logged in
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install Azure CLI first."
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo "🔐 Please log in to Azure CLI first:"
    az login
fi

echo "✅ Azure CLI authenticated successfully"

# Verify existing Resource Group
echo "📦 Verifying existing resource group: $RESOURCE_GROUP"
if ! az group show --name $RESOURCE_GROUP &> /dev/null; then
    echo "❌ Resource group '$RESOURCE_GROUP' not found. Please run challenge-0 setup first."
    exit 1
fi
echo "✅ Resource group '$RESOURCE_GROUP' exists"

# Verify existing Azure Container Registry
echo "🏗️  Verifying existing Azure Container Registry: $ACR_NAME"
if ! az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo "❌ Azure Container Registry '$ACR_NAME' not found. Please run challenge-0 setup first."
    exit 1
fi
echo "✅ Azure Container Registry '$ACR_NAME' exists"

# Ensure admin access is enabled for ACR (may already be enabled)
echo "🔓 Ensuring ACR admin access is enabled"
az acr update \
    --name $ACR_NAME \
    --resource-group $RESOURCE_GROUP \
    --admin-enabled true \
    --output table

# Build and push Docker image to ACR
echo "🔨 Building and pushing Docker image"
az acr build \
    --registry $ACR_NAME \
    --resource-group $RESOURCE_GROUP \
    --image $IMAGE_NAME:$IMAGE_TAG \
    .

# Create Container Apps Environment (if it doesn't exist)
echo "🌐 Creating Container Apps Environment: $CONTAINER_APP_ENV"
if ! az containerapp env show --name $CONTAINER_APP_ENV --resource-group $RESOURCE_GROUP &> /dev/null; then
    az containerapp env create \
        --name $CONTAINER_APP_ENV \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --output table
    echo "✅ Container Apps Environment '$CONTAINER_APP_ENV' created"
else
    echo "✅ Container Apps Environment '$CONTAINER_APP_ENV' already exists"
fi

# Use ACR credentials from .env file (already populated by get-keys.sh)
echo "🔗 Using ACR credentials from .env file"
echo "🔗 ACR Login Server: $ACR_LOGIN_SERVER"
echo "🔗 ACR Username: $ACR_USERNAME"

# Deploy Container App
echo "🚀 Deploying Container App: $CONTAINER_APP_NAME"
az containerapp create \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --environment $CONTAINER_APP_ENV \
    --image "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG" \
    --registry-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 10 \
    --cpu 1.0 \
    --memory 2.0Gi \
    --output table

# Set environment variables using values from .env file
echo "⚙️  Setting environment variables from .env file..."

# Build environment variables array from .env file
ENV_VARS=()
ENV_VARS+=("PORT=8000")
ENV_VARS+=("LOG_LEVEL=info")

# Read all variables from .env file and add them to the array
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    
    # Remove any quotes around the value
    value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/')
    
    # Add to environment variables array
    ENV_VARS+=("${key}=${value}")
    echo "📝 Adding: ${key}=${value:0:20}..."
done < ../../.env

# Update container app with all environment variables
echo "🔧 Updating container app with ${#ENV_VARS[@]} environment variables..."
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --set-env-vars "${ENV_VARS[@]}" \
    --output table

echo "✅ Environment variables configured successfully"

# Get the application URL
echo "🌍 Getting application URL..."
APP_URL=$(az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query properties.configuration.ingress.fqdn \
    --output tsv)

echo ""
echo "✅ Deployment completed successfully!"
echo "🌐 Application URL: https://$APP_URL"
echo "📊 API Documentation: https://$APP_URL/docs"
echo "💚 Health Check: https://$APP_URL/health"
echo ""
echo "🔧 Next steps:"
echo "1. Set the environment variables using the az containerapp update command above"
echo "2. Test the API using the /health endpoint"
echo "3. Use the /analyze endpoint to perform fraud detection"

# Optional: Open the application in browser (uncomment if desired)
# echo "🌐 Opening application in browser..."
# open "https://$APP_URL/docs"