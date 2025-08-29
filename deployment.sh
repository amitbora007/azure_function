#!/bin/bash

# Payliance Azure Function Deployment Script

set -e

echo "🚀 Deploying Payliance Azure Function to Azure"
echo "=============================================="

# Configuration
RESOURCE_GROUP="payliance-rg"
LOCATION="eastus"
# Use a more unique storage account name
STORAGE_ACCOUNT="learningstorage29082025"
FUNCTION_APP_NAME="payliance-function-app-$(date +%s)"

# Check if logged in to Azure and validate subscription
echo "🔐 Checking Azure authentication..."
if ! az account show &> /dev/null; then
    echo "Not logged in to Azure. Please login..."
    az login
fi

# List available subscriptions
echo "📋 Available subscriptions:"
az account list --output table

# Get current subscription info using Azure CLI's built-in query options
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
SUBSCRIPTION_STATE=$(az account show --query state -o tsv)

echo "📋 Current subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"
echo "📋 Subscription state: $SUBSCRIPTION_STATE"

# Validate subscription state
if [ "$SUBSCRIPTION_STATE" != "Enabled" ]; then
    echo "❌ Error: Current subscription is not enabled. Please select a valid subscription:"
    az account list --output table
    echo ""
    echo "To set a different subscription, run:"
    echo "az account set --subscription \"your-subscription-id\""
    exit 1
fi

# Verify subscription access by testing a simple command
echo "🔍 Verifying subscription access..."
if ! az group list --output none 2>/dev/null; then
    echo "❌ Error: Cannot access subscription. Please check your permissions or try a different subscription."
    echo "Available subscriptions:"
    az account list --output table
    exit 1
fi

echo "✅ Subscription access verified"

# Check if resource group already exists
if az group show --name $RESOURCE_GROUP &> /dev/null; then
    echo "📦 Resource group $RESOURCE_GROUP already exists"
else
    echo "📦 Creating resource group: $RESOURCE_GROUP"
    az group create --name $RESOURCE_GROUP --location $LOCATION
fi

# List existing storage accounts
az storage account list --output table

# Create function app
echo "⚡ Creating function app: $FUNCTION_APP_NAME in $LOCATION"
az functionapp create \
    --resource-group $RESOURCE_GROUP \
    --consumption-plan-location $LOCATION \
    --runtime python \
    --runtime-version 3.10 \
    --functions-version 4 \
    --name $FUNCTION_APP_NAME \
    --storage-account $STORAGE_ACCOUNT \
    --os-type linux

# Wait a moment for the function app to be ready
echo "⏳ Waiting for function app to be ready..."
sleep 30

# Configure application settings
echo "⚙️ Configuring application settings..."
if [ -z "$PAYLIANCE_BASE_URL" ] || [ -z "$PAYLIANCE_AUTH_TOKEN" ]; then
    echo "⚠️  Warning: Environment variables not set. Please set them manually in Azure Portal:"
    echo "   - PAYLIANCE_BASE_URL"
    echo "   - PAYLIANCE_AUTH_TOKEN"
    echo "   - MSSQL_SERVER, MSSQL_DATABASE, MSSQL_USERNAME, MSSQL_PASSWORD, MSSQL_PORT"
else
    az functionapp config appsettings set \
        --name $FUNCTION_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --settings \
        "PAYLIANCE_BASE_URL=$PAYLIANCE_BASE_URL" \
        "PAYLIANCE_AUTH_TOKEN=$PAYLIANCE_AUTH_TOKEN" \
        "MSSQL_SERVER=$MSSQL_SERVER" \
        "MSSQL_DATABASE=$MSSQL_DATABASE" \
        "MSSQL_USERNAME=$MSSQL_USERNAME" \
        "MSSQL_PASSWORD=$MSSQL_PASSWORD" \
        "MSSQL_PORT=$MSSQL_PORT" \
        "MSSQL_DRIVER=ODBC Driver 18 for SQL Server"
fi

# Check if func CLI is available
if ! command -v func &> /dev/null; then
    echo "❌ Error: Azure Functions Core Tools (func) not found."
    echo "Please install it with: npm install -g azure-functions-core-tools@4 --unsafe-perm true"
    exit 1
fi

# Deploy the function
echo "🚀 Deploying function code..."
func azure functionapp publish $FUNCTION_APP_NAME

# Get function keys
echo "🔑 Retrieving function keys..."
sleep 10  # Wait for deployment to complete
FUNCTION_KEY=$(az functionapp function keys list \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --function-name PaylianceDebitFunction \
    --query "default" -o tsv 2>/dev/null || echo "Failed to retrieve")

# Get function URL
FUNCTION_URL=$(az functionapp function show \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --function-name PaylianceDebitFunction \
    --query invokeUrlTemplate -o tsv 2>/dev/null || echo "Failed to retrieve")

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Deployment Details:"
echo "   Subscription: $SUBSCRIPTION_NAME"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   Function App: $FUNCTION_APP_NAME"
echo "   Storage Account: $STORAGE_ACCOUNT"
echo "   Location: $LOCATION"
echo "   Function URL: $FUNCTION_URL"
echo "   Function Key: $FUNCTION_KEY"
echo ""
echo "🧪 Test your function:"
if [ "$FUNCTION_KEY" != "Failed to retrieve" ]; then
    echo "   curl -X POST \"$FUNCTION_URL&code=$FUNCTION_KEY\" \\"
    echo "        -H \"Content-Type: application/json\" \\"
    echo "        -d '{\"transaction_id\": \"test123\"}'"
fi
echo ""
echo "🔗 Useful commands:"
echo "   View logs: az functionapp logs tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP"
echo "   Function keys: az functionapp function keys list --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP --function-name PaylianceDebitFunction"
echo "   Azure Portal: https://portal.azure.com"
echo ""