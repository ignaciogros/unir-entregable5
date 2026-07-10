# CLAUDE.md — Entregable 5: RAG Chatbot con CI/CD en Azure

## Descripción
Aplicación RAG con chatbot en español, panel de administración de PDFs y pipeline CI/CD completo.
Entregable académico UNIR — cubre el 100% de la rúbrica del Entregable 5.

## Criterios de rúbrica → cómo se cubren

| Criterio | Peso | Implementación |
|---|---|---|
| Configuración y estructuración | 15% | Repo GitHub, estructura modular Python, `.env` |
| Contenerización | 15% | Dockerfile + `docker-compose.yml` con 3 servicios |
| Registro en Azure | 20% | ACR + push automático en GitHub Actions |
| Despliegue en Azure | 20% | Azure Container Apps vía `az containerapp update` |
| Pipeline CI/CD | 20% | GitHub Actions: tests → build → push ACR → deploy |
| Monitoreo y validación | 10% | `/health` + logs de Container Apps |

## Arquitectura

### Local (Docker Compose)
- **app**: FastAPI + Jinja2/HTMX (puerto 8000)
- **db**: PostgreSQL 16 (puerto 5432) — autenticación, configuración, metadatos de PDFs
- **qdrant**: Qdrant (puerto 6333) — base de datos vectorial

### Azure (producción)
- **Azure Container Registry**: almacena la imagen Docker de `app`
- **Azure Container Apps**: ejecuta `app`
- **Qdrant Cloud** (free tier, 1 GB): base vectorial externa, sin coste adicional
- **Azure Database for PostgreSQL** (Flexible Server, Burstable B1ms): DB de prod, configurable vía `DATABASE_URL`

## Stack técnico
- Python 3.11
- FastAPI + uvicorn
- Jinja2 + HTMX (sin framework JS)
- SQLAlchemy 2.x + psycopg2-binary
- qdrant-client
- openai (SDK oficial, configurado para Azure OpenAI)
- pypdf (parseo de PDFs)
- python-multipart (subida de archivos)
- bcrypt (hash de contraseñas)
- itsdangerous (sesiones firmadas con cookie HttpOnly)
- python-dotenv

**No usar LlamaIndex.** Usar SDKs directos (openai + qdrant-client) para mayor control.

## Estructura de directorios

```
entregable5/
├── app/
│   ├── main.py             # FastAPI app, lifespan, rutas raíz
│   ├── auth.py             # Login/logout, middleware de autenticación
│   ├── admin.py            # Rutas admin: upload/delete PDF, procesar, restaurar
│   ├── chat.py             # Rutas chat: preguntas RAG + historial de sesión
│   ├── rag.py              # Pipeline RAG: embed → retrieve → generate
│   ├── ingest.py           # Procesado de PDFs: parse, chunk, embed, upsert en Qdrant
│   ├── vector_store.py     # Operaciones Qdrant: colecciones, búsqueda, versionado
│   ├── database.py         # Conexión PostgreSQL (SQLAlchemy engine + session)
│   ├── models.py           # Modelos SQLAlchemy: User, Config, UploadedFile
│   ├── templates/
│   │   ├── base.html       # Layout base con nav
│   │   ├── login.html
│   │   ├── admin.html      # Panel admin: lista PDFs, botones, estado ingesta
│   │   └── chat.html       # Chat con HTMX
│   └── static/
│       └── styles.css
├── uploads/                # PDFs subidos (volumen Docker: ./uploads:/app/uploads)
├── tests/
│   ├── conftest.py
│   ├── test_admin.py
│   ├── test_auth.py
│   ├── test_chat.py
│   ├── test_database.py
│   ├── test_health.py
│   ├── test_ingest.py
│   ├── test_rag.py
│   └── test_vector_store.py
├── doc/
│   ├── index.md            # Índice de la documentación
│   ├── tecnica.md          # Componentes, flujo RAG, por qué Qdrant es externo
│   ├── instalacion.md      # Guía de ejecución local
│   ├── azure.md            # Creación de infra, secrets, monitorización, limpieza
│   ├── uso.md              # Guía de uso de la aplicación
│   ├── pipeline.md         # Explicación de cada stage del CI/CD
│   ├── verificacion.md     # Cumplimiento de rúbrica y mejoras por encima
│   └── img/                # Capturas del pipeline (00-deploy.png … 05-smoke-test.png)
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .editorconfig
├── .env.example
├── requirements.txt
├── README.md
├── entrega.md              # Texto del correo que acompaña la entrega
├── LICENSE                 # AGPL-3.0
└── .github/
    └── workflows/
        └── deploy.yml
```

## Variables de entorno (.env.example)

**REGLA: `.env.example` va al repo con placeholders. El `.env` real va en `.gitignore`. Las credenciales reales NUNCA tocan el repositorio.**

```bash
# Azure OpenAI (ya desplegado)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_CHAT_DEPLOYMENT=your-chat-deployment-name
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=your-embedding-deployment-name
AZURE_OPENAI_API_VERSION=2024-10-21

# PostgreSQL
DATABASE_URL=postgresql://raguser:ragpass@db:5432/ragdb

# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=                             # vacío en local, rellenar para Qdrant Cloud

# Aplicación — NUNCA poner valores reales aquí, vienen de GitHub Secrets
SECRET_KEY=changeme-replace-with-random-32-char-string
APP_USER=changeme
APP_PASSWORD=changeme
```

## Flujo de credenciales seguro

```
GitHub Secrets (fuente de verdad)
    APP_USER, APP_PASSWORD, SECRET_KEY, ...
         │
         ▼
GitHub Actions (deploy.yml)
    az containerapp secret set   ← inyecta como secretos en Container Apps
         │
         ▼
Azure Container Apps
    env vars referenciadas como secretref:app-user, secretref:app-password
         │
         ▼
Contenedor en ejecución
    os.getenv("APP_USER"), os.getenv("APP_PASSWORD")
```

En el paso de deploy del workflow:
```yaml
- name: Set app secrets
  run: |
    az containerapp secret set \
      --name ${{ vars.CONTAINER_APP_NAME }} \
      --resource-group ${{ vars.RESOURCE_GROUP }} \
      --secrets \
        "app-user=${{ secrets.APP_USER }}" \
        "app-password=${{ secrets.APP_PASSWORD }}" \
        "secret-key=${{ secrets.SECRET_KEY }}"

- name: Deploy
  run: |
    az containerapp update \
      --name ${{ vars.CONTAINER_APP_NAME }} \
      --resource-group ${{ vars.RESOURCE_GROUP }} \
      --image ${{ vars.ACR_LOGIN_SERVER }}/rag-chatbot:${{ github.sha }} \
      --set-env-vars \
        "APP_USER=secretref:app-user" \
        "APP_PASSWORD=secretref:app-password" \
        "SECRET_KEY=secretref:secret-key"
```

GitHub Actions secrets necesarios (Settings → Secrets and variables → Actions):
- **Secrets**: `APP_USER`, `APP_PASSWORD`, `SECRET_KEY`, `AZURE_CREDENTIALS`, `AZURE_OPENAI_API_KEY`, `QDRANT_API_KEY`, `DATABASE_URL`
- **Variables** (no sensibles): `ACR_NAME`, `ACR_LOGIN_SERVER`, `CONTAINER_APP_NAME`, `RESOURCE_GROUP`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`

## Funcionalidades clave

### Autenticación
- Usuario único: `user1` / `Pass134!` en tabla `users` (contraseña hasheada con bcrypt)
- Sesiones firmadas con `itsdangerous.URLSafeTimedSerializer` (cookie `session`, HttpOnly, SameSite=lax)
- Middleware FastAPI: todas las rutas excepto `GET /login` y `POST /login` redirigen a `/login` si no hay sesión
- Ruta raíz `/` redirige a `/chat` si autenticado, a `/login` si no

### Panel admin (`/admin`)
- Tabla de PDFs: nombre, tamaño, fecha de subida, estado (pendiente/procesado)
- Subir PDF: validar extensión `.pdf` y MIME type `application/pdf`, máx 20 MB, guardar en `uploads/`
- Eliminar PDF: borra el archivo físico + sus puntos de la colección Qdrant activa (filtro por `source`)
- Botón **"Procesar"**: lanza `ingest.process_all_pdfs()` en background → crea nueva colección Qdrant → swap
- Botón **"Restaurar versión anterior"**: visible solo si existe `previous_collection` en tabla `config`

### Versionado de base vectorial (Qdrant)
- Colecciones nombradas `knowledge_{unix_timestamp_entero}`
- Tabla PostgreSQL `config(key TEXT PRIMARY KEY, value TEXT)`:
  - `active_collection` → nombre de la colección en uso
  - `previous_collection` → colección anterior (para restaurar)
- Al "Procesar": nueva colección → ingestar todo → actualizar `config` → borrar la más antigua si hay más de 2
- Al "Restaurar": swap `active_collection` ↔ `previous_collection` en `config`
- La colección a consultar se lee de `config` en cada petición de chat (no se cachea en memoria)

### Chat (`/chat`)
- Interfaz HTMX: formulario POST a `/chat/ask`, respuesta HTML parcial `<div>`, sin recarga
- Historial de conversación en sesión del servidor (clave `history` en cookie, últimos 6 intercambios)
- Flujo RAG por pregunta:
  1. Embed pregunta → Azure OpenAI embedding
  2. Buscar top-5 en colección Qdrant activa
  3. Recuperar `previous_messages` de sesión
  4. Construir prompt con contexto + historial
  5. Llamar Azure OpenAI chat
  6. Guardar Q+A en sesión
- **Prompt de sistema (no modificar sin revisar rúbrica)**:
  ```
  Eres un asistente que responde EXCLUSIVAMENTE en español usando SOLO la información
  proporcionada en el CONTEXTO. No uses conocimiento externo bajo ninguna circunstancia.
  Si la información no está en el contexto, responde exactamente:
  "No encuentro información sobre eso en los documentos disponibles."
  ```

### Citas y fiabilidad en las respuestas de chat

Cada respuesta muestra debajo del texto las fuentes usadas:

```
Respuesta del asistente...

Fuentes:
  📄 tema1.pdf  •  pág. 12  •  Fiabilidad: 92%   [ver PDF]
  📄 tema1.pdf  •  pág. 14  •  Fiabilidad: 87%   [ver PDF]
  📄 tema3.pdf  •  pág. 3   •  Fiabilidad: 81%   [ver PDF]
```

- **Fiabilidad**: score de similitud coseno de Qdrant × 100, redondeado a entero
- **Nombre del PDF**: campo `source` del payload de Qdrant (nombre del archivo)
- **Página**: campo `page` del payload de Qdrant
- **Enlace al PDF**: el nombre del fichero enlaza a `/uploads/{nombre_archivo}` — los PDFs se sirven como archivos estáticos con `StaticFiles`
  - En local siempre funciona
  - En Azure Container Apps: funciona mientras el contenedor tenga los archivos (sin volumen persistente los pierde al reiniciar — aceptable para demo académica)
- La respuesta de `rag.py` devuelve `{"answer": str, "sources": [{"source": str, "page": int, "score": float}]}`
- Si ningún chunk supera score 0.75, añadir nota visual: "⚠️ Baja confianza — respuesta puede no estar en los documentos"

### Grounding by design

El sistema está diseñado para que toda respuesta esté **anclada a las fuentes recuperadas**, no al conocimiento paramétrico del modelo. Principio transversal, materializado en cuatro mecanismos ya descritos arriba:

1. **System prompt restrictivo** — responde EXCLUSIVAMENTE con el CONTEXTO; prohíbe conocimiento externo.
2. **Rechazo explícito** — si la información no está en el contexto: «No encuentro información sobre eso en los documentos disponibles.»
3. **Umbral de confianza** — si ningún chunk supera score 0.75, aviso visual «⚠️ Baja confianza».
4. **Citas obligatorias** — cada respuesta muestra fuente + página + fiabilidad (score coseno × 100).

Cualquier cambio en `rag.py` o en el prompt debe preservar estos cuatro puntos.

### Chunking de PDFs (ingest.py)
- Parsear con `pypdf.PdfReader`
- Dividir en chunks de 500 tokens con 50 tokens de solapamiento (aproximar por caracteres: 500 tokens ≈ 2000 chars)
- Metadata de cada punto Qdrant: `{"source": "nombre_archivo.pdf", "page": N, "chunk_idx": K}`
- Tamaño de vector: 1536 (text-embedding-3-small)

### Endpoint de salud (`/health`)
```json
{
  "status": "ok",
  "postgres": "connected",
  "qdrant": "connected",
  "active_collection": "knowledge_1234567890",
  "total_vectors": 142
}
```

## Pipeline CI/CD — `.github/workflows/deploy.yml`

Disparador: `push` a rama `main`

Organizado en *stages* (jobs de GitHub Actions encadenados con `needs:`, cada uno arranca solo
si el anterior pasa). Estructura tomada del pipeline de ejemplo en Azure DevOps, añadiendo `lint`:

```
jobs:
  lint            → pip install ruff · ruff check . && ruff format --check .
  test            → needs: lint            · pytest --cov=app --cov-fail-under=80
  build-and-push  → needs: test            · az acr login · docker build
                                           · smoke test de la imagen (ver abajo)
                                           · push :$SHA y :latest
  deploy          → needs: build-and-push  · az containerapp secret set · update --image :$SHA
  smoke-test      → needs: deploy          · curl https://<app-url>/health → 200 {"status":"ok"}
```

**Smoke test de la imagen** (dentro de `build-and-push`, entre `docker build` y `docker push`):
levanta `postgres:16-alpine` y `qdrant/qdrant` en una red de Docker del runner, arranca la imagen
recién construida contra ellos y exige que `/health` devuelva `200` con `"status":"ok"` — no
`"degraded"`. Si falla, vuelca los logs del contenedor y **la imagen no se publica en ACR**. Un
`docker run` suelto no valdría: `init_db.init()` crea las tablas al arrancar y el proceso muere si
no alcanza Postgres.

El job `lint` instala **solo `ruff`**, no el `requirements.txt` completo: el análisis estático no
necesita FastAPI ni el SDK de Azure OpenAI.

Variables necesarias en GitHub Actions secrets:
`AZURE_CREDENTIALS`, `ACR_NAME`, `ACR_LOGIN_SERVER`, `CONTAINER_APP_NAME`, `RESOURCE_GROUP`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `DATABASE_URL` (prod), `QDRANT_URL` (Qdrant Cloud), `QDRANT_API_KEY`, `SECRET_KEY`, `APP_USER`, `APP_PASSWORD`

## Comandos de desarrollo

```bash
# Arrancar todo localmente
docker-compose up --build

# Solo tests (sin levantar los servicios de infra)
docker-compose run --rm app pytest tests/ -v

# Ver logs en tiempo real
docker-compose logs -f app

# Reiniciar solo la app (sin tocar db/qdrant)
docker-compose up --build app

# Lint + formato (mismo gate que el stage `lint` del pipeline)
# --no-deps evita esperar a los healthchecks de db/qdrant
docker-compose run --rm --no-deps app ruff check .
docker-compose run --rm --no-deps app ruff format --check .

# Autoarreglo local (lint + formato)
docker-compose run --rm --no-deps app ruff check . --fix
docker-compose run --rm --no-deps app ruff format .
```

### Ejecutar ruff fuera del contenedor (en el host)

`ruff` es análisis estático: no necesita `.env`, ni la base de datos, ni levantar servicios. Se puede
instalar en el host y ejecutar directamente sobre la carpeta del repo. Útil para lintar rápido sin
Docker.

```powershell
# Instalar ruff (una vez). Opción A: instalador oficial, sin Python
powershell -c "irm https://astral.sh/ruff/install.ps1 | iex"
# Opción B: con pip (paridad con el CI, que usa ruff>=0.6.0)
pip install "ruff>=0.6.0"

# Abrir una terminal nueva (para refrescar el PATH) y verificar
ruff --version

# Ejecutar desde la RAÍZ del repo (donde está pyproject.toml)
ruff check .
ruff format --check .

# Autoarreglo
ruff check . --fix
ruff format .
```

> Nota: `ruff` se ejecuta dentro del contenedor (está en `requirements.txt`) y corre con sus
> **defaults** (línea 88, reglas `E4/E7/E9/F`): no hay sección `[tool.ruff]` en `pyproject.toml`,
> y es deliberado — activar `E501`, `I` o `B` obligaría a un refactor de alcance desconocido a
> cambio de cero puntos de rúbrica. El gate del pipeline usa los comandos de arriba.

## Reglas de trabajo (leer antes de implementar)

- **Fases**: implementar una fase completa, luego ejecutar sus pruebas, luego preguntar al usuario antes de pasar a la siguiente. No se salta ningún gate.
- **Cobertura de tests**: mínimo **80 %** medido con `pytest-cov`. Los tests se escriben en cada fase junto al código. El gate de cada fase incluye pasar `pytest --cov=app --cov-report=term-missing --cov-fail-under=80`. El pipeline CI/CD también lo aplica.
- **Guía de estilo (obligado cumplimiento)**: **4 espacios por defecto**; **2 espacios por consenso** en `.yml`/`.yaml`, `.html`/Jinja2, `.css`, `.js`. Nunca tabuladores. Regla codificada en `.editorconfig`. Linter y formateador: **`ruff`**, con sus reglas por defecto. Comando de lint: `ruff check . && ruff format --check .`. El gate de cada fase y el *stage* `lint` del pipeline deben pasar sin errores.
- **UI**: diseñar con a11y en mente desde el principio (roles ARIA, etiquetas `<label>`, contraste suficiente, navegación por teclado, atributos `alt`). La UI final (diseño visual, tipografía, paleta) la genera el plugin `/frontend-design` — las plantillas de las fases intermedias son funcionales y accesibles, no necesariamente bonitas.
- **Documentación** (toda en español; escrita/actualizada en la Fase 12):
  - `README.md`: aviso de proyecto académico, descripción del producto, instalación rápida, enlace destacado a `doc/index.md`, stack tecnológico, enlace a `doc/verificacion.md` y licencia AGPL.
  - `doc/index.md`: índice con descripción general y enlaces al resto de apartados.
  - `doc/tecnica.md`, `doc/instalacion.md`, `doc/azure.md`, `doc/uso.md`, `doc/pipeline.md`, `doc/verificacion.md`.
  - `entrega.md`: texto breve del correo de entrega (qué cumple de la rúbrica, qué aporta por encima).
  - Textos breves y comprensibles: solo lo necesario para que el docente evalúe la práctica.
- **Sin Makefile**: descartado. El objetivo del entregable es demostrar CI/CD, y los comandos reales
  ya están documentados. Tampoco `scripts/lint.ps1`.

## Decisiones de diseño

- **Sin LlamaIndex**: los pipelines RAG directos con openai + qdrant-client son suficientes y más fáciles de depurar en un proyecto académico.
- **HTMX en lugar de React**: el `docker-compose.yml` queda con 3 servicios limpios (no 4), el Dockerfile es uno solo, y la experiencia de usuario es buena para el alcance del proyecto.
- **itsdangerous para sesiones**: evita dependencia de Redis o almacenamiento de sesión en DB. La cookie firmada guarda el user_id y el historial de chat (< 4 KB).
- **Qdrant Cloud gratuito en prod**: evita coste de volúmenes persistentes en Azure Container Apps y simplifica la arquitectura cloud.
- **Azure Database for PostgreSQL en prod**: Postgres gestionado dentro de Azure (Flexible Server B1ms). A diferencia de Qdrant, Azure ofrece Postgres gestionado de primera clase, así que la BD relacional se mantiene en Azure por coherencia con el entregable. Configurable vía `DATABASE_URL` (la rúbrica no exige la BD en Azure, pero se elige así con suscripción de pago).
- **Dos colecciones máximo**: suficiente para la funcionalidad de restauración pedida. Más copias no aportan valor en un proyecto académico.

## Ampliación futura (modo quiz)
No implementar en fase inicial. El modelo generará preguntas breves de respuesta única basadas en los PDFs activos. No requiere persistencia de resultados en BD. Ruta propuesta: `GET /quiz` → 5 preguntas generadas con Azure OpenAI → formulario HTMX → corrección en cliente.
