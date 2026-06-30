# Configuración de Azure

Todos los comandos utilizan **PowerShell** y **Azure CLI**.

## Iniciar sesión

```powershell
az login
az account show --output table
```

---

## 1. Azure OpenAI

### Definir variables

```powershell
$RG           = "rg-entregable5"
$LOCATION     = "swedencentral"
$OPENAI_NAME  = "openai-entregable5"
$CHAT_DEP     = "chat"
$EMBED_DEP    = "embedding"

Write-Host "Recurso OpenAI : $OPENAI_NAME"
Write-Host "Región         : $LOCATION"
```

### Crear grupo de recursos

```powershell
az group create `
  --name $RG `
  --location $LOCATION
```

### Crear recurso Azure OpenAI

```powershell
az cognitiveservices account create `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --kind OpenAI `
  --sku S0 `
  --location $LOCATION
```

### Obtener AZURE_OPENAI_ENDPOINT

```powershell
az cognitiveservices account show `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --query properties.endpoint `
  --output tsv
```

### Obtener AZURE_OPENAI_API_KEY

```powershell
az cognitiveservices account keys list `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --query key1 `
  --output tsv
```

### Crear deployment de chat (AZURE_OPENAI_CHAT_DEPLOYMENT)

```powershell
az cognitiveservices account deployment create `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --deployment-name $CHAT_DEP `
  --model-name gpt-4o-mini `
  --model-version "2024-07-18" `
  --model-format OpenAI `
  --sku-name Standard `
  --sku-capacity 10
```

### Crear deployment de embeddings (AZURE_OPENAI_EMBEDDING_DEPLOYMENT)

```powershell
az cognitiveservices account deployment create `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --deployment-name $EMBED_DEP `
  --model-name text-embedding-ada-002 `
  --model-version "2" `
  --model-format OpenAI `
  --sku-name Standard `
  --sku-capacity 10
```

### Verificar deployments

```powershell
az cognitiveservices account deployment list `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --output table
```

Esperado: dos filas con `ProvisioningState = Succeeded`, una para `chat` y otra para `embedding`.

### Actualizar .env con los valores obtenidos

```bash
AZURE_OPENAI_ENDPOINT=<salida del comando show>
AZURE_OPENAI_API_KEY=<salida del comando keys list>
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_CHAT_DEPLOYMENT=chat
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding
```

```powershell
docker-compose restart app
```

---

## 2. Azure Container Registry — Fase 10

```powershell
$ACR_NAME = "acrentregable5"

az acr create `
  --resource-group $RG `
  --name $ACR_NAME `
  --sku Basic `
  --admin-enabled true

az acr show `
  --name $ACR_NAME `
  --query loginServer `
  --output tsv
```

---

## 3. Azure Container Apps — Fase 10

```powershell
$APP_ENV  = "env-entregable5"
$APP_NAME = "rag-chatbot"

az containerapp env create `
  --name $APP_ENV `
  --resource-group $RG `
  --location $LOCATION

az containerapp create `
  --name $APP_NAME `
  --resource-group $RG `
  --environment $APP_ENV `
  --image mcr.microsoft.com/azuredocs/containerapps-helloworld:latest `
  --target-port 8000 `
  --ingress external
```

---

## 4. Service principal para GitHub Actions — Fase 10

```powershell
$SUBSCRIPTION_ID = az account show --query id --output tsv

az ad sp create-for-rbac `
  --name "sp-github-entregable5" `
  --role contributor `
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG" `
  --json-auth
```

Copiar el JSON completo → GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret              | Valor                        |
|---------------------|------------------------------|
| `AZURE_CREDENTIALS` | JSON completo del comando anterior |

---

## 5. Secrets y variables de GitHub Actions — Fase 10

**Secrets** (Settings → Secrets):

| Nombre                  | Fuente                              |
|-------------------------|-------------------------------------|
| `AZURE_CREDENTIALS`     | JSON del service principal          |
| `AZURE_OPENAI_API_KEY`  | Paso 1 (keys list)                  |
| `QDRANT_API_KEY`        | Qdrant Cloud → cluster → API Keys   |
| `DATABASE_URL`          | Neon.tech → connection string       |
| `SECRET_KEY`            | cadena aleatoria ≥ 32 caracteres    |
| `APP_USER`              | usuario del chatbot en producción   |
| `APP_PASSWORD`          | contraseña del chatbot en producción|

**Variables** (Settings → Variables):

| Nombre                            | Valor                          |
|-----------------------------------|--------------------------------|
| `ACR_NAME`                        | `acrentregable5`               |
| `ACR_LOGIN_SERVER`                | salida de `az acr show`        |
| `CONTAINER_APP_NAME`              | `rag-chatbot`                  |
| `RESOURCE_GROUP`                  | `rg-entregable5`               |
| `AZURE_OPENAI_ENDPOINT`           | salida de `az cognitiveservices account show` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT`    | `chat`                         |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `embedding`                  |
