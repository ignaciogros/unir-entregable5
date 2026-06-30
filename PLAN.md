# Plan de implementación

## Reglas de proceso
- Implementar una fase completa → ejecutar sus pruebas → **pedir confirmación al usuario antes de pasar a la siguiente**.
- Si una prueba falla, corregir en la misma fase antes de preguntar.
- **Cobertura mínima: 80 %**. El gate de cada fase incluye:
  ```bash
  pytest --cov=app --cov-report=term-missing --cov-fail-under=80
  ```
  Los tests se escriben en cada fase junto al código que cubren.
- Las plantillas de fases intermedias son funcionales y accesibles (a11y), no diseño final.
- La UI final (diseño visual) la genera el plugin `/frontend-design` en la Fase 11.

---

### Fase 1 — Scaffolding del proyecto
**Objetivo**: estructura de repo ejecutable sin funcionalidad todavía.

**Tareas**
- [ ] `.gitignore` — incluir: `.env`, `uploads/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`
- [ ] `requirements.txt` con todas las dependencias del stack
- [ ] `.env.example` con placeholders (sin credenciales reales)
- [ ] `app/main.py` mínimo: FastAPI app + ruta `GET /` (redirige a `/login`) + ruta `GET /health` → `{"status": "ok"}`
- [ ] `Dockerfile` — Python 3.11-slim, instala deps, copia `app/`, arranca uvicorn en puerto 8000
- [ ] `docker-compose.yml` con 3 servicios: `app`, `db` (postgres:16-alpine), `qdrant` (qdrant/qdrant:latest)

**Cómo probar**
```bash
# Arrancar en segundo plano (-d) para dejar el terminal libre
docker-compose up --build -d

# Verificar que los 3 contenedores están running
docker ps

# Comprobar endpoint de salud
curl http://localhost:8000/health
# Esperado: {"status":"ok"}

curl -o /dev/null -s -w "%{http_code}" http://localhost:8000/
# Esperado: 307 (redirect a /login)

# Ejecutar tests con cobertura (el contenedor ya está corriendo)
docker-compose exec app pytest --cov=app --cov-report=term-missing --cov-fail-under=80
# Esperado: 2 tests pasados, cobertura ≥ 80 %

# Ver logs si algo falla
docker-compose logs app
```

⛔ **Esperar confirmación antes de iniciar Fase 2.**

---

### Fase 2 — Base de datos y modelos
**Objetivo**: PostgreSQL accesible con tablas creadas y usuario inicial al arrancar.

**Tareas**
- [x] `app/database.py` — SQLAlchemy engine síncrono + `SessionLocal` + `get_db()` + `Base`
- [x] `app/models.py` — tres tablas:
  ```
  users(id SERIAL PK, username TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL)
  config(key TEXT PK, value TEXT NOT NULL)
  uploaded_files(id SERIAL PK, filename TEXT UNIQUE NOT NULL, size_bytes INT,
                 uploaded_at TIMESTAMP DEFAULT now(), processed BOOL DEFAULT false)
  ```
- [x] `app/init_db.py` — `init()`: crea tablas con `Base.metadata.create_all()`, inserta usuario desde `APP_USER`/`APP_PASSWORD` (bcrypt hash) si `users` está vacía
- [x] Llamar `init_db.init()` en el `lifespan` de `main.py`

**Cómo probar**
```bash
docker-compose up --build
# Conectar al contenedor de PostgreSQL:
docker exec -it <nombre_contenedor_db> psql -U raguser -d ragdb
# En psql:
\dt
# Esperado: tablas users, config, uploaded_files
SELECT username FROM users;
# Esperado: una fila con el usuario configurado en .env
\q
```
> Verificar también que `docker-compose up` por segunda vez no duplica el usuario.

⛔ **Esperar confirmación antes de iniciar Fase 3.**

---

### Fase 3 — Autenticación
**Objetivo**: login/logout funcional, todas las rutas protegidas. Plantillas accesibles.

**Tareas**
- [ ] `app/auth.py`:
  - `verify_password(plain, hashed)` con bcrypt
  - `create_session(response, username)` — escribe cookie `session` firmada (itsdangerous), HttpOnly, SameSite=lax
  - `get_current_user(request)` — lee y valida cookie; devuelve username o `None`
  - `require_auth(request)` — dependencia FastAPI; si no hay sesión lanza `RedirectResponse("/login")`
- [ ] Rutas en `main.py`: `GET /login`, `POST /login` (verifica credenciales → crea sesión → redirige a `/chat`), `GET /logout` (borra cookie → redirige a `/login`)
- [ ] `app/templates/base.html` — layout con `<nav>` (enlaces Admin / Chat / Cerrar sesión); roles ARIA, `lang="es"`, `<meta charset="UTF-8">`
- [ ] `app/templates/login.html` — `<form>` con `<label for=...>` explícitos, campo usuario, campo contraseña, botón submit, mensaje de error en `role="alert"`; contraste WCAG AA

**Cómo probar**
```bash
# 1. Sin sesión, acceso a ruta protegida redirige a login
curl -o /dev/null -s -w "%{http_code}" http://localhost:8000/chat
# Esperado: 307

# 2. Login con credenciales incorrectas
curl -s -X POST http://localhost:8000/login \
  -d "username=user1&password=wrong" -c /tmp/cookies.txt
# Esperado: permanece en /login, sin cookie de sesión

# 3. Login correcto
curl -s -X POST http://localhost:8000/login \
  -d "username=${APP_USER}&password=${APP_PASSWORD}" \
  -c /tmp/cookies.txt -L
# Esperado: redirige a /chat (HTTP 200 o 307→200)

# 4. Con cookie válida, acceso a ruta protegida
curl -s -b /tmp/cookies.txt -o /dev/null -w "%{http_code}" http://localhost:8000/chat
# Esperado: 200

# 5. Logout borra acceso
curl -s -b /tmp/cookies.txt http://localhost:8000/logout
curl -s -b /tmp/cookies.txt -o /dev/null -w "%{http_code}" http://localhost:8000/chat
# Esperado: 307 (redirige a login de nuevo)
```
> Verificar también en navegador: teclado solo (Tab/Enter), lectores de pantalla ven la etiqueta de cada campo.

⛔ **Esperar confirmación antes de iniciar Fase 4.**

---

### Fase 4 — Panel admin (sin RAG todavía)
**Objetivo**: subir, listar y borrar PDFs. El botón "Procesar" existe pero no hace nada aún.

**Tareas**
- [ ] Montar `StaticFiles` en `/uploads` apuntando a `./uploads/` (para servir PDFs después)
- [ ] `app/admin.py`:
  - `GET /admin` — lista `uploaded_files`, renderiza `admin.html`
  - `POST /admin/upload` — valida extensión `.pdf` + content-type `application/pdf` + tamaño ≤ 20 MB; guarda en `uploads/`; inserta en `uploaded_files(processed=False)`; redirige a `/admin`
  - `POST /admin/delete/{filename}` — borra archivo físico + fila DB; redirige a `/admin`
  - `POST /admin/process` — placeholder: devuelve `{"status":"not_implemented"}`
- [ ] `app/templates/admin.html` (a11y):
  - Tabla con `<caption>`, `scope="col"` en cabeceras
  - Formulario de subida con `<label>`, `accept=".pdf"`, `aria-describedby` para límite de tamaño
  - Botones de borrado con `aria-label="Eliminar {filename}"`
  - Botón "Procesar" deshabilitado visualmente hasta que haya PDFs

**Cómo probar**
```bash
# 1. Subir un PDF válido
curl -s -b /tmp/cookies.txt \
  -F "file=@ruta/a/test.pdf" \
  http://localhost:8000/admin/upload
# Esperado: redirect a /admin, el PDF aparece en la lista

# 2. Subir un archivo no-PDF (debe rechazarse)
curl -s -b /tmp/cookies.txt \
  -F "file=@ruta/a/archivo.txt" \
  -o /dev/null -w "%{http_code}" http://localhost:8000/admin/upload
# Esperado: 400 o redirect con mensaje de error

# 3. Verificar que el archivo existe en disco
ls uploads/

# 4. Eliminar el PDF
curl -s -b /tmp/cookies.txt \
  -X POST http://localhost:8000/admin/delete/test.pdf
# Esperado: redirect a /admin, lista vacía; archivo borrado de uploads/

# 5. Verificar acceso al panel sin sesión
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin
# Esperado: 307 a /login
```

⛔ **Esperar confirmación antes de iniciar Fase 5.**

---

### Fase 5 — Integración Qdrant
**Objetivo**: operaciones básicas contra Qdrant: colecciones, búsqueda, versionado.

**Tareas**
- [ ] `app/vector_store.py`:
  - `get_client()` — QdrantClient con `QDRANT_URL` + `QDRANT_API_KEY` (opcional)
  - `create_collection(name)` — colección con vector size 1536, distancia Cosine
  - `upsert_points(collection, points)` — recibe lista de `PointStruct`
  - `search(collection, vector, top_k=5)` — devuelve `[{"source", "page", "score", "content"}]`
  - `delete_by_source(collection, filename)` — filtra por `payload["source"] == filename`
  - `get_active_collection(db)` — lee `config` key `active_collection`; devuelve `None` si no existe
  - `swap_collections(db, new_name)` — escribe `previous_collection` ← actual, `active_collection` ← `new_name`; borra colecciones con antigüedad > 2

**Cómo probar**
```bash
# Con docker-compose levantado:
docker-compose exec app python - <<'EOF'
from app.vector_store import get_client, create_collection, upsert_points, search
from qdrant_client.models import PointStruct

client = get_client()
create_collection("test_col")
upsert_points("test_col", [
    PointStruct(id=1, vector=[0.1]*1536, payload={"source":"a.pdf","page":1,"content":"hola"})
])
results = search("test_col", [0.1]*1536, top_k=1)
print(results)
# Esperado: [{"source":"a.pdf","page":1,"score":~1.0,"content":"hola"}]
client.delete_collection("test_col")
EOF
```
> Verificar también que Qdrant UI (http://localhost:6333/dashboard) muestra la colección durante el test y desaparece tras el borrado.

⛔ **Esperar confirmación antes de iniciar Fase 6.**

---

### Fase 6 — Pipeline de ingesta
**Objetivo**: el botón "Procesar" parsea PDFs, genera embeddings y puebla Qdrant.

**Tareas**
- [ ] `app/ingest.py`:
  - `parse_pdf(filepath)` → `[{"text": str, "page": int}]` con `pypdf.PdfReader`
  - `chunk_text(pages, filename)` → `[{"text", "page", "source", "chunk_idx"}]` (chunks ~2000 chars, overlap ~200 chars)
  - `embed_text(text)` → `list[float]` vía Azure OpenAI embeddings
  - `process_all_pdfs(db)`:
    1. Crea colección `knowledge_{int(time.time())}`
    2. Para cada PDF en `uploads/`: parsea → chunka → embede → upsert
    3. Llama `swap_collections(db, nueva)`
    4. Marca `processed=True` en `uploaded_files`
- [ ] `POST /admin/process` — llama `process_all_pdfs(db)` con `BackgroundTasks`; devuelve `{"status":"processing"}` inmediato
- [ ] `POST /admin/delete/{filename}` — si hay colección activa, llama también `delete_by_source(colección, filename)`
- [ ] Añadir en `admin.html`: indicador visual de "Procesando..." mientras corre el background task (polling ligero con HTMX `hx-trigger="every 3s"` a `GET /admin/status`)
- [ ] `GET /admin/status` — devuelve `{"processing": bool, "active_collection": str|null, "total_vectors": int}`

**Cómo probar**
```bash
# 1. Subir un PDF y procesar
# (usar un PDF pequeño con texto, no solo imágenes)
curl -s -b /tmp/cookies.txt -F "file=@test.pdf" http://localhost:8000/admin/upload
curl -s -b /tmp/cookies.txt -X POST http://localhost:8000/admin/process
# Esperado: {"status":"processing"}

# 2. Esperar ~10s y consultar estado
curl -s -b /tmp/cookies.txt http://localhost:8000/admin/status
# Esperado: {"processing":false,"active_collection":"knowledge_XXXX","total_vectors":N}

# 3. Verificar colección en Qdrant
curl -s http://localhost:6333/collections
# Esperado: aparece la colección knowledge_XXXX

# 4. Verificar en DB que processed=true
docker exec -it <db_container> psql -U raguser -d ragdb \
  -c "SELECT filename, processed FROM uploaded_files;"
```

⛔ **Esperar confirmación antes de iniciar Fase 7.**

---

### Fase 7 — Pipeline RAG y chat
**Objetivo**: chatbot funcional con memoria de conversación y citas de fuentes.

**Tareas**
- [ ] `app/rag.py`:
  - `ask(question, history, db)`:
    1. Embed `question` con Azure OpenAI
    2. Buscar top-5 en `get_active_collection(db)`; si no hay colección → error claro
    3. Construir `messages`: system prompt fijo + últimos 6 de `history` + user message con contexto incrustado
    4. Llamar Azure OpenAI chat completions
    5. Devolver `{"answer": str, "sources": [{"source": str, "page": int, "score": float}]}`
- [ ] `app/chat.py`:
  - `GET /chat` — renderiza `chat.html`, historial desde sesión (clave `chat_history`)
  - `POST /chat/ask` — llama `rag.ask()`, añade Q+A a sesión, devuelve fragmento HTML (para HTMX `hx-swap="beforeend"`)
  - `POST /chat/clear` — limpia `chat_history` de la sesión
- [ ] `app/templates/chat.html` (a11y):
  - `<main role="main">`, área de mensajes como `<ol aria-live="polite" aria-label="Historial de conversación">`
  - Cada mensaje: `<li>` con `<article>` diferenciando rol usuario/asistente
  - Formulario: `<label>` para el textarea, botón con texto descriptivo
  - Sección fuentes: `<details><summary>Fuentes ({n})</summary>` con lista de `<a>` al PDF + fiabilidad
  - Aviso de baja confianza (score < 0.75) con `role="status"`

**Cómo probar**
```bash
# Prerequisito: colección Qdrant con datos (Fase 6 completada)

# 1. Pregunta sobre contenido que SÍ está en los PDFs
curl -s -b /tmp/cookies.txt \
  -X POST http://localhost:8000/chat/ask \
  -d "question=¿Qué es X?" \
  -H "Content-Type: application/x-www-form-urlencoded"
# Esperado: HTML con respuesta en español + sección de fuentes con PDF y score

# 2. Pregunta que NO está en los PDFs
curl -s -b /tmp/cookies.txt \
  -X POST http://localhost:8000/chat/ask \
  -d "question=¿Cuál es la capital de Francia?" \
  -H "Content-Type: application/x-www-form-urlencoded"
# Esperado: respuesta con "No encuentro información sobre eso en los documentos disponibles."

# 3. Memoria de contexto
# Primera pregunta sobre un concepto del PDF → responde correctamente
# Segunda pregunta: "¿Y cómo se relaciona con Y?" → usa contexto de la anterior

# 4. En navegador: verificar que el chat funciona con solo teclado (Tab, Enter)
```

⛔ **Esperar confirmación antes de iniciar Fase 8.**

---

### Fase 8 — Tests automatizados
**Objetivo**: suite de tests que pasa en CI sin servicios externos levantados.

**Tareas**
- [ ] `tests/conftest.py` — fixtures: app de test con SQLite en memoria, Qdrant y Azure OpenAI mockeados
- [ ] `tests/test_health.py`:
  - `GET /health` → 200, body tiene keys `status`, `postgres`, `qdrant`
- [ ] `tests/test_auth.py`:
  - Sin sesión → `GET /chat` devuelve 307 hacia `/login`
  - `POST /login` credenciales correctas → cookie de sesión presente
  - `POST /login` credenciales incorrectas → sin cookie, respuesta con mensaje de error
  - `GET /logout` → cookie borrada → acceso protegido redirige a `/login`
- [ ] `tests/test_admin.py`:
  - Subir PDF válido → 200/302, aparece en listado
  - Subir archivo `.txt` → 400
  - Subir PDF > 20 MB → 400
- [ ] `tests/test_rag.py`:
  - `rag.ask()` con Qdrant mockeado que devuelve 2 chunks → respuesta tiene `answer` (str) y `sources` (lista con 2 elementos)
  - Si colección activa es `None` → devuelve error controlado

**Cómo probar**
```bash
# Sin docker-compose levantado:
pip install -r requirements.txt
pytest tests/ -v --tb=short
# Esperado: todos los tests en verde, sin conexiones reales a Postgres/Qdrant/Azure

# Con docker-compose levantado (tests de integración opcionales):
docker-compose exec app pytest tests/ -v
```

⛔ **Esperar confirmación antes de iniciar Fase 9.**

---

### Fase 9 — Dockerfile y compose de producción
**Objetivo**: imagen optimizada y orquestación lista para CI/CD.

**Tareas**
- [ ] `Dockerfile` — build multi-stage: stage `builder` (instala deps) + stage `runtime` (copia solo lo necesario, usuario no-root `appuser`)
- [ ] `docker-compose.yml` final:
  - `db`: healthcheck `pg_isready`, volumen nombrado `postgres_data`
  - `qdrant`: healthcheck `GET :6333/healthz`, volumen nombrado `qdrant_data`
  - `app`: `depends_on: db: {condition: service_healthy}, qdrant: {condition: service_healthy}`
- [ ] `.dockerignore` — excluir: `.env`, `uploads/`, `tests/`, `__pycache__/`, `.git/`
- [ ] Verificar tamaño de imagen: `docker images | grep rag-chatbot`

**Cómo probar**
```bash
# Arranque desde cero (sin imágenes cacheadas)
docker-compose down -v
docker-compose up --build

# 1. Verificar healthchecks
docker ps --format "table {{.Names}}\t{{.Status}}"
# Esperado: los 3 contenedores con status "healthy"

# 2. Verificar que app espera a que db y qdrant estén healthy antes de arrancar

# 3. Flujo completo post-arranque:
# - Login → subir PDF → Procesar → Chat con pregunta → respuesta con fuentes

# 4. Tamaño de imagen razonable (< 500 MB)
docker images | grep rag-chatbot
```

⛔ **Esperar confirmación antes de iniciar Fase 10.**

---

### Fase 10 — CI/CD y despliegue Azure
**Objetivo**: push a main despliega automáticamente en Azure Container Apps.

**Tareas (manual, una sola vez)**
- [ ] Crear Resource Group: `az group create --name rg-entregable5 --location westeurope`
- [ ] Crear ACR: `az acr create --name <acr-name> --resource-group rg-entregable5 --sku Basic`
- [ ] Crear Container Apps environment: `az containerapp env create ...`
- [ ] Crear Container App inicial con imagen placeholder
- [ ] Configurar GitHub Actions secrets y variables (ver lista en CLAUDE.md)
- [ ] Documentar todos los pasos en `doc/azure-setup.md`

**Tareas (automatizadas)**
- [ ] `.github/workflows/deploy.yml`:
  ```
  on: push to main
  jobs:
    test      → pytest (sin servicios externos)
    build     → docker build + push a ACR con tag :$SHA y :latest
    deploy    → az containerapp secret set + az containerapp update --image :$SHA
    smoke     → curl https://<url>/health → {"status":"ok"}
  ```

**Cómo probar**
```bash
# 1. Push a main y observar Actions
git push origin main
# GitHub Actions → todos los jobs en verde

# 2. Smoke test desde fuera
curl https://<container-app-url>/health
# Esperado: {"status":"ok","postgres":"connected","qdrant":"connected",...}

# 3. Abrir la URL en navegador → login → subir PDF → procesar → preguntar

# 4. Logs en Azure
az containerapp logs show \
  --name <container-app-name> \
  --resource-group rg-entregable5 \
  --follow
```

⛔ **Esperar confirmación antes de iniciar Fase 11.**

---

### Fase 11 — UI final (plugin de diseño)
**Objetivo**: aplicar diseño visual definitivo sobre las plantillas funcionales existentes.

**Tareas**
- [ ] Invocar `/frontend-design` con las plantillas actuales como base
- [ ] Aplicar resultado a `base.html`, `login.html`, `admin.html`, `chat.html`
- [ ] Verificar a11y tras el rediseño: contraste, foco visible, `aria-*` intactos
- [ ] Verificar que HTMX sigue funcionando tras cambios de clases/estructura

**Cómo probar**
```bash
docker-compose up --build
# En navegador:
# - Flujo completo: login → admin (subir, procesar) → chat (preguntar)
# - Navegación solo con teclado (Tab, Enter, Escape)
# - Validar con Lighthouse (Chrome DevTools) → Accessibility > 90
```

⛔ **Esperar confirmación antes de iniciar Fase 12.**

---

### Fase 12 — Documentación y validación final de rúbrica
**Objetivo**: documentación completa y verificación de los 6 criterios.

**Tareas**
- [ ] `README.md` en español:
  - Descripción y arquitectura
  - Requisitos previos (Docker, credenciales Azure OpenAI)
  - Guía de ejecución local (paso a paso desde cero)
  - Guía de despliegue → referencia a `doc/azure-setup.md`
  - Variables de entorno documentadas
  - Capturas de pantalla de login, admin y chat
- [ ] `doc/azure-setup.md`:
  - Crear ACR y Container App (comandos exactos)
  - Configurar GitHub Secrets
  - Primer despliegue manual
  - Verificar logs con `az containerapp logs show`
- [ ] Checklist rúbrica:
  - [ ] Criterio 1 — repo GitHub con estructura y `.env.example`
  - [ ] Criterio 2 — `docker-compose up --build` funciona desde cero
  - [ ] Criterio 3 — imagen visible en Azure Portal → ACR
  - [ ] Criterio 4 — URL pública de Container Apps responde
  - [ ] Criterio 5 — workflow de Actions con todos los jobs en verde
  - [ ] Criterio 6 — `/health` con DB+Qdrant, `az containerapp logs show` muestra logs

**Cómo probar**
```bash
# Simular descarga desde cero (otro directorio, sin .env):
git clone <repo-url> /tmp/test-entregable5
cd /tmp/test-entregable5
cp .env.example .env
# Editar .env con credenciales reales
docker-compose up --build
curl http://localhost:8000/health
# Esperado: todo funciona sin pasos adicionales

# Lighthouse en Chrome sobre http://localhost:8000
# → Performance > 80, Accessibility > 90
```

---

## Ampliación futura — Modo quiz
Solo implementar tras completar Fase 12 y con nota 10/10 confirmada.
`GET /quiz` → Azure OpenAI genera 5 preguntas sobre el contenido activo → formulario HTMX → corrección inmediata en cliente. Sin persistencia en DB.
