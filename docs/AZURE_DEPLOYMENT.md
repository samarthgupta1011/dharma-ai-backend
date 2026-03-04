# Azure Deployment — End-to-End Setup

Complete Azure CLI commands to set up the Dharma AI backend infrastructure from scratch.

---

## Prerequisites

```bash
brew install azure-cli          # macOS
az login
az extension add --name containerapp
```

## Variables

```bash
RESOURCE_GROUP="dharma-rg"
LOCATION="eastus"
ACR_NAME="dharmacr"
CONTAINER_APP_ENV="dharma-env"
CONTAINER_APP_NAME="dharma-api"
KEYVAULT_NAME="dharma-kv"
COSMOS_ACCOUNT="dharma-cosmos"
STORAGE_ACCOUNT="dharmastorageacc"
MANAGED_IDENTITY="dharma-env-umsi"
```

---

## Step 1 — Create Resource Group

```bash
az group create --name $RESOURCE_GROUP --location $LOCATION
```

## Step 2 — Azure Container Registry

```bash
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled false
```

## Step 3 — Azure Key Vault

```bash
az keyvault create \
  --resource-group $RESOURCE_GROUP \
  --name $KEYVAULT_NAME \
  --location $LOCATION
```

## Step 4 — Azure Cosmos DB (MongoDB API)

```bash
az cosmosdb create \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT \
  --kind MongoDB \
  --server-version 7.0 \
  --default-consistency-level Session

# Store connection string in Key Vault
COSMOS_CONN=$(az cosmosdb keys list \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv)

az keyvault secret set \
  --vault-name $KEYVAULT_NAME \
  --name "cosmos-db-connection-string" \
  --value "$COSMOS_CONN"
```

## Step 5 — Store JWT Secret in Key Vault

```bash
JWT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

az keyvault secret set \
  --vault-name $KEYVAULT_NAME \
  --name "jwt-secret-key" \
  --value "$JWT_KEY"
```

## Step 6 — Store OpenAI API Key in Key Vault

```bash
# Get your key from https://platform.openai.com/api-keys
OPENAI_KEY="sk-..."

az keyvault secret set \
  --vault-name $KEYVAULT_NAME \
  --name "openai-api-key" \
  --value "$OPENAI_KEY"
```

## Step 7 — Azure Blob Storage

```bash
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

az storage container create \
  --name dharma-content \
  --account-name $STORAGE_ACCOUNT
```

## Step 8 — Container Apps Environment

```bash
az containerapp env create \
  --resource-group $RESOURCE_GROUP \
  --name $CONTAINER_APP_ENV \
  --location $LOCATION
```

## Step 9 — Build and Push Docker Image

```bash
az acr build \
  --registry $ACR_NAME \
  --image dharma-api:latest \
  .
```

## Step 10 — Create Managed Identity (UMSI)

```bash
az identity create \
  --name $MANAGED_IDENTITY \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

UMSI_CLIENT_ID=$(az identity show \
  --name $MANAGED_IDENTITY \
  --resource-group $RESOURCE_GROUP \
  --query clientId -o tsv)

echo "UMSI Client ID: $UMSI_CLIENT_ID"
```

## Step 11 — Deploy Container App

```bash
az containerapp create \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $CONTAINER_APP_ENV \
  --image "$ACR_NAME.azurecr.io/dharma-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 10 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --user-assigned $MANAGED_IDENTITY \
  --env-vars-from-file app/config/prod.env \
  --set-env-vars AZURE_CLIENT_ID="$UMSI_CLIENT_ID"
```

## Step 12 — Configure RBAC

```bash
PRINCIPAL_ID=$(az identity show \
  --name $MANAGED_IDENTITY \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# Key Vault — read secrets
KEYVAULT_ID=$(az keyvault show \
  --name $KEYVAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $KEYVAULT_ID

# Cosmos DB — read access
COSMOS_ID=$(az cosmosdb show \
  --name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Cosmos DB Account Reader Role" \
  --scope $COSMOS_ID

# Storage — SAS URL generation
STORAGE_ID=$(az storage account show \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Storage Blob Delegator" \
  --scope $STORAGE_ID

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Storage Blob Data Reader" \
  --scope "$STORAGE_ID/blobServices/default/containers/dharma-content"
```

## Step 13 — Verify

```bash
APP_URL=$(az containerapp show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "properties.configuration.ingress.fqdn" -o tsv)

curl "https://$APP_URL/health"
```

---

## Updating an Existing Deployment

```bash
# Build with unique tag
IMAGE_TAG=$(git rev-parse --short HEAD)-$(date +%s)
az acr build --registry $ACR_NAME --platform linux/amd64 --image dharma-api:${IMAGE_TAG} .

# Deploy
ENV_VARS=$(grep -v '^#' app/config/prod.env | grep -v '^$')
UMSI_CLIENT_ID=$(az identity show --name $MANAGED_IDENTITY --resource-group $RESOURCE_GROUP --query clientId -o tsv)

az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image $ACR_NAME.azurecr.io/dharma-api:${IMAGE_TAG} \
  --set-env-vars $(echo "${ENV_VARS}" | tr '\n' ' ') AZURE_CLIENT_ID=${UMSI_CLIENT_ID}
```

## Troubleshooting

```bash
# View Container App logs
az containerapp logs show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --follow

# Check env vars
az containerapp show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "properties.template.containers[0].env"

# Rollback to previous image
az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image $ACR_NAME.azurecr.io/dharma-api:<previous-tag>
```
