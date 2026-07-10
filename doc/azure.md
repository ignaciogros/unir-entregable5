# Configuración de Azure

Guía paso a paso para crear la infraestructura desde cero y dejar el pipeline CI/CD operativo.
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
  --model-name gpt-5.4-mini `
  --model-version "2026-03-17" `
  --model-format OpenAI `
  --sku-name GlobalStandard `
  --sku-capacity 10
```

> Nota: `gpt-4o-mini`/`gpt-4o` fueron retirados (03/2026). Se usa `gpt-5.4-mini` (ligero, GA).
> La familia gpt-5 **solo admite `--sku-name GlobalStandard`** (con `Standard` da
> `InvalidResourceProperties`). Requiere `AZURE_OPENAI_API_VERSION` reciente (≥ `2024-10-21`);
> la `2024-02-01` no sirve para la familia gpt-5.

### Crear deployment de embeddings (AZURE_OPENAI_EMBEDDING_DEPLOYMENT)

```powershell
az cognitiveservices account deployment create `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --deployment-name $EMBED_DEP `
  --model-name text-embedding-3-small `
  --model-version "1" `
  --model-format OpenAI `
  --sku-name GlobalStandard `
  --sku-capacity 10
```

> Nota: en `swedencentral`, `text-embedding-3-small` tampoco admite `Standard`; usar
> `GlobalStandard`.

### Verificar deployments

```powershell
az cognitiveservices account deployment list `
  --name $OPENAI_NAME `
  --resource-group $RG `
  --query "[].{name:name, model:properties.model.name, version:properties.model.version, state:properties.provisioningState}" `
  --output table
```

Esperado: dos filas con `state = Succeeded` — `chat` (`gpt-5.4-mini`) y `embedding`
(`text-embedding-3-small`). La tabla por defecto (`--output table` sin `--query`) solo muestra
`Name` y `ResourceGroup`; el `--query` de arriba añade modelo, versión y estado.

### Actualizar .env con los valores obtenidos

```bash
AZURE_OPENAI_ENDPOINT=<salida del comando show>
AZURE_OPENAI_API_KEY=<salida del comando keys list>
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_CHAT_DEPLOYMENT=chat
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding
```

```powershell
docker-compose restart app
```

---

## 2. Azure Container Registry

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

### Subida manual de la imagen (opcional)

En el funcionamiento normal, el *job* `build-and-push` del pipeline construye y publica la imagen en
cada `push` a `main`. Si necesitas subirla a mano —por ejemplo, para el primer despliegue antes de
configurar GitHub Actions—, estos son los comandos:

```powershell
az acr login --name $ACR_NAME

docker build -t rag-chatbot:v1 .

docker tag rag-chatbot:v1 "$ACR_NAME.azurecr.io/rag-chatbot:v1"

docker push "$ACR_NAME.azurecr.io/rag-chatbot:v1"
```

Verificar que la imagen está en el registro:

```powershell
az acr repository show-tags --name $ACR_NAME --repository rag-chatbot --output table
```

---

## 3. Azure Container Apps

### Registrar proveedores requeridos (una vez por suscripción)

Container Apps necesita un backend de Log Analytics (`Microsoft.OperationalInsights`) y el proveedor
`Microsoft.App`. Si no están registrados, `az containerapp env create` fallará pidiéndolos.
Regístralos antes (idempotente, `--wait` bloquea hasta terminar, ~1‑2 min):

```powershell
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.ContainerService --wait
```

### Crear entorno y app

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

> Este paso es **obligatorio antes del primer push**. El job `deploy` ejecuta
> `az containerapp update`, que falla con `containerapp 'rag-chatbot' does not exist` si la
> Container App no se ha creado antes con una imagen placeholder.

### Obtener la URL pública

```powershell
az containerapp show --name $APP_NAME --resource-group $RG --query properties.configuration.ingress.fqdn --output tsv
```

Devuelve el FQDN sin esquema. La URL pública es `https://` + ese valor.

---

## 4. Service principal para GitHub Actions

```powershell
$SUBSCRIPTION_ID = az account show --query id --output tsv

az ad sp create-for-rbac `
  --name "sp-github-entregable5" `
  --role contributor `
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG" `
  --json-auth
```

Copiar el JSON completo → GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret              | Valor                              |
|---------------------|------------------------------------|
| `AZURE_CREDENTIALS` | JSON completo del comando anterior |

> **Cuentas Azure for Students:** `az ad sp create-for-rbac` requiere permisos de creación de
> aplicaciones en Microsoft Entra ID, que algunas suscripciones educativas tienen bloqueados. Este
> proyecto se ha desplegado sobre una **suscripción de pago**, donde la operación está permitida.
> Si tu suscripción lo bloquea, la alternativa es autenticar el pipeline con las credenciales de
> ACR y un *bearer token* contra la API REST de Azure.

---

## Servicios externos de producción: Qdrant Cloud

La base vectorial de producción **no** es un contenedor: se usa **Qdrant Cloud** (free tier, 1 GB) para
evitar volúmenes persistentes en Azure Container Apps. De aquí salen los secrets `QDRANT_URL` y
`QDRANT_API_KEY`.

### Obtener `QDRANT_URL`

1. Entrar en **https://cloud.qdrant.io** e iniciar sesión (se puede con la cuenta de GitHub/Google).
2. **Create Cluster** → seleccionar **Free tier** (1 GB), elegir proveedor/región (p. ej. AWS
   `eu-central-1`). Esperar a que el clúster quede en estado **Healthy** (~1‑2 min).
3. Abrir el clúster → pestaña **Overview / Cluster Details**. Copiar el **Endpoint**, con esta forma:
   ```
   https://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.eu-central-1-0.aws.cloud.qdrant.io
   ```
4. El valor del secret `QDRANT_URL` es ese endpoint **con el puerto REST `:6333`**:
   ```
   QDRANT_URL=https://xxxxxxxx-....aws.cloud.qdrant.io:6333
   ```
   > El `qdrant-client` de la app usa la API REST en el **6333**. El 6334 (gRPC) no se usa aquí.

### Obtener `QDRANT_API_KEY`

En el mismo clúster → **Data Access Control** (o **API Keys**) → **Create** → copiar la clave generada.
Ese valor es el secret `QDRANT_API_KEY`.

### Verificar (opcional)

```powershell
curl.exe -s "https://TU-ENDPOINT:6333/healthz" -H "api-key: TU_API_KEY"
```

Debe devolver `healthz check passed`.

> **Local vs producción:** en el `.env` local `QDRANT_URL=http://qdrant:6333` (nombre del servicio de
> Docker Compose) y `QDRANT_API_KEY` vacío. Los valores de Qdrant Cloud van **solo** en los secrets de
> GitHub; no se tocan en el `.env` local.

---

## Base de datos de producción: Azure Database for PostgreSQL

A diferencia de Qdrant, Azure sí ofrece Postgres gestionado (**Flexible Server**), así que la BD
relacional de producción se mantiene **dentro de Azure**. De aquí sale el secret `DATABASE_URL`.

### Registrar el proveedor (una vez por suscripción)

Si la suscripción no lo tiene registrado, `flexible-server create` falla con
`MissingSubscriptionRegistration`. Regístralo antes:

```powershell
az provider register -n Microsoft.DBforPostgreSQL --wait
```

### Definir variables

```powershell
$PG_SERVER   = "pg-entregable5"          # nombre global único, en minúsculas
$PG_ADMIN    = "ragadmin"
$PG_PASSWORD = "<contraseña-fuerte>"      # sin caracteres @ : / # ? (o habrá que URL-encodearlos)
$PG_DB       = "ragdb"
```

### Crear el servidor Flexible Server

```powershell
az postgres flexible-server create `
  --resource-group $RG `
  --name $PG_SERVER `
  --location $LOCATION `
  --admin-user $PG_ADMIN `
  --admin-password $PG_PASSWORD `
  --tier Burstable `
  --sku-name Standard_B1ms `
  --storage-size 32 `
  --version 16 `
  --public-access 0.0.0.0 `
  --yes
```

> `--public-access 0.0.0.0` crea la regla especial que **permite el acceso desde servicios de Azure**
> (necesario para que Container Apps alcance la BD). No abre el servidor a Internet.
> `Standard_B1ms` (Burstable) es el SKU más barato (~12‑15 €/mes); ajústalo si necesitas más.

### Crear la base de datos

```powershell
az postgres flexible-server db create `
  --resource-group $RG `
  --server-name $PG_SERVER `
  --name $PG_DB
```

### Construir `DATABASE_URL`

El host es `<PG_SERVER>.postgres.database.azure.com`. El valor del secret es:

```
DATABASE_URL=postgresql://ragadmin:<PG_PASSWORD>@pg-entregable5.postgres.database.azure.com:5432/ragdb?sslmode=require
```

Notas:
- Flexible Server usa **usuario plano** (`ragadmin`), no el `usuario@servidor` del antiguo Single Server.
- **`?sslmode=require`** obligatorio (Flexible Server exige TLS).
- Si la contraseña lleva caracteres reservados de URL (`@ : / # ? %`), URL-encódéalos en la cadena.
- No hace falta migración: al arrancar, `init_db.init()` crea las tablas y siembra el usuario.

### (Opcional) Abrir tu IP para probar con psql

Crea una regla de firewall que permite conectar tu IP pública al Postgres de Azure, solo para
inspeccionar la BD desde tu máquina (psql/DBeaver). **Si no vas a conectarte tú directamente a la BD
de Azure, puedes saltarte este paso.**

Obtén tu IP pública y créala como regla (el servidor va en `--server-name`; el nombre de la regla
en `--name`):

```powershell
$MYIP = Invoke-RestMethod -Uri https://api.ipify.org

az postgres flexible-server firewall-rule create `
  --resource-group $RG `
  --server-name $PG_SERVER `
  --name allow-mi-ip `
  --start-ip-address $MYIP `
  --end-ip-address $MYIP
```

> El `.env` local **no** cambia: sigue con `postgresql://raguser:ragpass@db:5432/ragdb` (contenedor).

---

## Generar `SECRET_KEY`

Firma las cookies de sesión (`itsdangerous`). Aleatoria, ≥ 32 caracteres, **estable** (si cambia,
invalida las sesiones activas). Generarla con un RNG criptográfico:

```powershell
$b = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
[Convert]::ToBase64String($b)
```

Alternativa con Python del contenedor:

```powershell
docker-compose run --rm --no-deps app python -c "import secrets; print(secrets.token_urlsafe(48))"
```

La salida es el valor del secret `SECRET_KEY`. Solo para producción; en local ya hay un valor en `.env`.

---

## 5. Secrets y variables de GitHub Actions

**Secrets** (Settings → Secrets):

| Nombre                  | Fuente                              |
|-------------------------|-------------------------------------|
| `AZURE_CREDENTIALS`     | JSON del service principal          |
| `AZURE_OPENAI_API_KEY`  | Paso 1 (keys list)                  |
| `QDRANT_URL`            | Qdrant Cloud → cluster → endpoint (https://xxx.cloud.qdrant.io:6333) |
| `QDRANT_API_KEY`        | Qdrant Cloud → cluster → API Keys   |
| `DATABASE_URL`          | Azure Database for PostgreSQL → connection string (ver sección arriba) |
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

---

## 6. Pipeline CI/CD y primer despliegue

El workflow `.github/workflows/deploy.yml` se dispara con cada `push` a `main`
(también manualmente desde **Actions → Run workflow**, gracias a `workflow_dispatch`).
La explicación detallada de cada stage está en [pipeline.md](pipeline.md).

**Requisitos previos al primer push exitoso:**

1. Los recursos de los pasos 1–4 creados (RG, OpenAI + deployments, ACR, Container App, service principal).
2. **Qdrant Cloud** y **Azure Database for PostgreSQL** creados, con sus valores en los secrets `QDRANT_URL`, `QDRANT_API_KEY`, `DATABASE_URL`.
3. Todos los **secrets** y **variables** del paso 5 configurados en GitHub.

> El `smoke-test` exige `"status":"ok"`, lo que implica que **Postgres y Qdrant de producción
> respondan**. Si aún no existen, el pipeline llegará hasta `deploy` pero fallará en `smoke-test`
> (respuesta `"status":"degraded"`). Es el comportamiento esperado hasta completar el punto 2.

**Nota sobre el pull de imagen:** el paso `deploy` ejecuta `az containerapp registry set` con las
credenciales admin del ACR (`admin-enabled true` en el paso 2) para que Container Apps pueda
descargar la imagen privada. La Container App del paso 3 se crea con una imagen *helloworld*
temporal; el primer `deploy` la sustituye por `rag-chatbot:$SHA`.

---

## 7. Monitorización

### Logs de la aplicación

```powershell
az containerapp logs show --name rag-chatbot --resource-group rg-entregable5 --follow
```

### Últimas 50 líneas, sin seguir

```powershell
az containerapp logs show --name rag-chatbot --resource-group rg-entregable5 --tail 50
```

### Estado de las revisiones

```powershell
az containerapp revision list --name rag-chatbot --resource-group rg-entregable5 --output table
```

### Endpoint de salud

```powershell
curl.exe -s "https://<fqdn>/health"
```

Respuesta esperada:

```json
{"status":"ok","postgres":"connected","qdrant":"connected","active_collection":"knowledge_1234567890","total_vectors":142}
```

---

## 8. Limpieza de recursos

Al terminar la práctica conviene eliminar los recursos para no incurrir en costes. El Postgres
Flexible Server (~12‑15 €/mes) y el ACR (~4 €/mes) siguen facturando aunque no se usen.

### Opción A — eliminar todo el grupo de recursos (recomendado)

Borra en una sola operación la Container App, el entorno, el ACR, el Postgres y el recurso de
Azure OpenAI. Es **irreversible**.

```powershell
az group delete --name rg-entregable5 --yes --no-wait
```

Comprobar que ha desaparecido:

```powershell
az group exists --name rg-entregable5
```

### Opción B — eliminar recursos concretos

Útil si quieres conservar el recurso de Azure OpenAI (los deployments tardan en aprobarse) y borrar
solo lo demás.

```powershell
az containerapp delete --name rag-chatbot --resource-group rg-entregable5 --yes
az containerapp env delete --name env-entregable5 --resource-group rg-entregable5 --yes
az acr delete --name acrentregable5 --resource-group rg-entregable5 --yes
az postgres flexible-server delete --name pg-entregable5 --resource-group rg-entregable5 --yes
```

### Recursos fuera de Azure

- **Service principal**: `az ad sp delete --id <appId del JSON de AZURE_CREDENTIALS>`
- **Qdrant Cloud**: eliminar el clúster desde https://cloud.qdrant.io (el free tier no factura,
  pero conviene dejarlo limpio).
- **GitHub**: eliminar los secrets y variables del repositorio si ya no se van a usar.
