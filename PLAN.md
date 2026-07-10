# Plan de implementación

## Estado actual — 2026-07-10

**Fases completadas y confirmadas:** 1‑11.

**Fase 10 (CI/CD + Azure): ✅ COMPLETADA.** Pipeline en verde (lint→test→build→deploy→smoke-test),
app desplegada en Azure Container Apps, `/health` responde `"status":"ok"`. Recursos: RG
`rg-entregable5`, ACR `acrentregable5`, Container App `rag-chatbot` en `env-entregable5`
(swedencentral), SP `sp-github-entregable5`, **Azure Database for PostgreSQL Flexible Server**,
**Qdrant Cloud**. Secrets/variables cargados en GitHub.

**Fase 11 (UI final): ✅ COMPLETADA.**

**Fase 12 (documentación y validación): ✅ COMPLETADA.** Capturas en `doc/img/`, pipeline en verde
con el smoke test de la imagen.

**Fase 13 (comprobación final): 🟡 EN CURSO.** Ver el punto 1 de abajo: falta el informe PDF/Word.

### 👉 Retomar aquí en la próxima sesión
1. **Bloqueante para la entrega:** maquetar `informe.md` a PDF/Word (Arial o Calibri 12, interlineado
   1,5), insertar las 6 figuras de `doc/img/` en sus marcadores `[FIGURA n]`, rellenar los campos
   `⟨ ⟩` y borrar el bloque de instrucciones. Es el artefacto que califica el docente; el repositorio
   es el trabajo técnico que lo respalda.
2. Rellenar los campos `⟨ ⟩` de `entrega.md` (URL pública, usuario, contraseña).
3. **Commitear y pushear** (lo ejecuta el usuario). Los cambios de documentación admiten `[skip ci]`.
4. MkDocs + GitHub Pages: **descartado** por el usuario (2026-07-10).

**Notas de estado:**
- Git: el asistente NO ejecuta comandos de Git ni de shell; los ejecuta el usuario. Comandos de prueba
  en PowerShell, una línea, `Invoke-RestMethod`/`curl.exe`.
- Infra prod: Azure DB for PostgreSQL (no Neon) + Qdrant Cloud. Razonado en CLAUDE.md; sin referencias
  a Neon en el repo.
- Tooling de calidad: `ruff` en `requirements.txt` (>=0.6.0); gate `ruff check .` + `ruff format --check .`
  pasa. Existe `.editorconfig`. **No** hay `[tool.ruff]` en pyproject, ni `doc/style-guide.md`, ni
  `scripts/lint.ps1`, ni `Makefile`: descartados a propósito (ruff usa defaults, línea 88).
- Azure OpenAI (`chat` + `embedding`) operativo; ingesta real validada; grounding del chat verificado.

---

## Reglas de proceso
- Implementar una fase completa → ejecutar sus pruebas → **pedir confirmación al usuario antes de pasar a la siguiente**.
- Si una prueba falla, corregir en la misma fase antes de preguntar.
- **Cobertura mínima: 80 %**. El gate de cada fase incluye:
  ```bash
  pytest --cov=app --cov-report=term-missing --cov-fail-under=80
  ```
  Los tests se escriben en cada fase junto al código que cubren.
- **Lint sin errores**. El gate de cada fase incluye también:
  ```bash
  ruff check . && ruff format --check .
  ```
- Las plantillas de fases intermedias son funcionales y accesibles (a11y), no diseño final.
- La UI final (diseño visual) la genera el plugin `/frontend-design` en la Fase 11.

---

## Guía de estilo y linter (obligado cumplimiento)

- **Indentación**: **4 espacios por defecto** (Python, Dockerfile, Markdown anidado).
  **2 espacios por consenso** en: `.yml`/`.yaml`, `.html`/plantillas Jinja2, `.css`, `.js`.
  Nunca tabuladores. Codificado en `.editorconfig`.
- **Reglas comunes**: sin espacios al final de línea, salto de línea final, codificación UTF-8.
- **Python**: `ruff` como linter y formateador, **con sus reglas por defecto** (línea 88,
  `E4/E7/E9/F`). No hay `[tool.ruff]` en `pyproject.toml`: activar `E501`, `I`, `UP` o `B` obligaría a
  un refactor de alcance desconocido a cambio de cero puntos de rúbrica.
  `snake_case` para funciones/variables, `PascalCase` para clases.

**Comando de lint** (debe pasar en cada fase y en el pipeline):

```powershell
ruff check . ; if ($?) { ruff format --check . }
```

Autoarreglo local: `ruff check --fix . ; ruff format .`

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
- [x] `app/auth.py`:
  - `verify_password(plain, hashed)` con bcrypt
  - `create_session(response, username)` — escribe cookie `session` firmada (itsdangerous), HttpOnly, SameSite=lax
  - `get_current_user(request)` — lee y valida cookie; devuelve username o `None`
  - Protección via `AuthMiddleware` (BaseHTTPMiddleware) en lugar de dependencia por ruta
- [x] Rutas en `main.py`: `GET /login`, `POST /login` (303 → `/chat`), `GET /logout` (302 → `/login`)
- [x] `app/templates/base.html` — layout con `<nav>` (enlaces Admin / Chat / Cerrar sesión); roles ARIA, `lang="es"`, `<meta charset="UTF-8">`
- [x] `app/templates/login.html` — `<form>` con `<label for=...>` explícitos, campo usuario, campo contraseña, botón submit, mensaje de error en `role="alert"`; contraste WCAG AA

**Cómo probar**
```powershell
# Tests automatizados con cobertura
docker-compose exec app pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# 1. Sin sesión → redirige a login
curl.exe -s -o NUL -w "%{http_code}" "http://localhost:8000/chat"
# Esperado: 307

# 2. Credenciales incorrectas → 401, sin cookie
curl.exe -s -X POST "http://localhost:8000/login" -d "username=user1&password=wrong" -c "$env:TEMP\cookies.txt" -w "%{http_code}"
# Esperado: 401

# 3. Login correcto → 303 (NO usar -L: curl.exe en Windows no convierte POST→GET en 303)
curl.exe -s -X POST "http://localhost:8000/login" -d "username=user1&password=Pass134!" -c "$env:TEMP\cookies.txt" -w "%{http_code}"
# Esperado: 303

# 4. Acceder con cookie guardada
curl.exe -s -b "$env:TEMP\cookies.txt" -o NUL -w "%{http_code}" "http://localhost:8000/chat"
# Esperado: 200

# 5. Logout (-c necesario para actualizar fichero con Max-Age=0)
curl.exe -s -b "$env:TEMP\cookies.txt" -c "$env:TEMP\cookies.txt" "http://localhost:8000/logout" -w "%{http_code}"
# Esperado: 302

# 6. Tras logout → acceso denegado
curl.exe -s -b "$env:TEMP\cookies.txt" -o NUL -w "%{http_code}" "http://localhost:8000/chat"
# Esperado: 307
```
> Verificar también en navegador: Tab navega entre campos, Enter envía el formulario.

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
```powershell
# Tests automatizados con cobertura
docker-compose exec app pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# 0. Login para obtener cookie (prerequisito de los pasos siguientes)
curl.exe -s -X POST "http://localhost:8000/login" -d "username=user1&password=Pass134!" -c "$env:TEMP\cookies.txt" -w "%{http_code}"
# Esperado: 303

# 1. Panel admin accesible con sesión → 200
curl.exe -s -b "$env:TEMP\cookies.txt" -o NUL -w "%{http_code}" "http://localhost:8000/admin"
# Esperado: 200

# 2. Sin sesión → redirige a login
curl.exe -s -o NUL -w "%{http_code}" "http://localhost:8000/admin"
# Esperado: 307

# 3. Subir un PDF válido → 303
# (crear un PDF mínimo primero: el fichero debe empezar por %PDF)
curl.exe -s -b "$env:TEMP\cookies.txt" -X POST "http://localhost:8000/admin/upload" -F "file=@ruta\a\documento.pdf" -w "%{http_code}"
# Esperado: 303

# 4. Ver el PDF en el listado
curl.exe -s -b "$env:TEMP\cookies.txt" "http://localhost:8000/admin"
# Esperado: HTML que contiene el nombre del fichero subido

# 5. Subir archivo .txt → 400
curl.exe -s -b "$env:TEMP\cookies.txt" -X POST "http://localhost:8000/admin/upload" -F "file=@ruta\a\texto.txt" -w "%{http_code}"
# Esperado: 400

# 6. Eliminar el PDF → 303
curl.exe -s -b "$env:TEMP\cookies.txt" -X POST "http://localhost:8000/admin/delete/documento.pdf" -w "%{http_code}"
# Esperado: 303

# 7. Panel vacío tras borrar
curl.exe -s -b "$env:TEMP\cookies.txt" "http://localhost:8000/admin"
# Esperado: HTML con "No hay documentos cargados todavía."

# 8. Botón Procesar (placeholder)
curl.exe -s -b "$env:TEMP\cookies.txt" -X POST "http://localhost:8000/admin/process"
# Esperado: {"status":"not_implemented"}
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
```powershell
# Tests automatizados con cobertura (Qdrant mockeado, sin servicios externos)
docker-compose exec app pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# Prueba de integración manual (opcional, requiere docker-compose levantado)
docker-compose exec app python -c "from app.vector_store import get_client, create_collection, upsert_points, search; from qdrant_client.models import PointStruct; c=get_client(); c.delete_collection('test_col') if c.collection_exists('test_col') else None; create_collection('test_col'); upsert_points('test_col',[PointStruct(id=1,vector=[0.1]*1536,payload={'source':'a.pdf','page':1,'content':'hola'})]); print(search('test_col',[0.1]*1536,top_k=1)); c.delete_collection('test_col')"
# Esperado: [{'source': 'a.pdf', 'page': 1, 'score': ~1.0, 'content': 'hola'}]
```
> Verificar también que Qdrant UI (http://localhost:6333/dashboard) muestra la colección durante la prueba manual y desaparece tras el borrado.

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
```powershell
# Tests automatizados con cobertura
docker-compose exec app pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# 0. Login
curl.exe -s -X POST "http://localhost:8000/login" -d "username=user1&password=Pass134!" -c "$env:TEMP\cookies.txt" -w "%{http_code}"
# Esperado: 303

# 1. Subir un PDF con texto real (no solo imágenes) y procesar
curl.exe -s -b "$env:TEMP\cookies.txt" -X POST "http://localhost:8000/admin/upload" -F "file=@ruta\documento.pdf" -w "%{http_code}"
# Esperado: 303
curl.exe -s -b "$env:TEMP\cookies.txt" -X POST "http://localhost:8000/admin/process" -w "%{http_code}"
# Esperado: 303 (la ingesta corre en background)

# 2. Esperar ~10s y consultar estado
curl.exe -s -b "$env:TEMP\cookies.txt" "http://localhost:8000/admin/status"
# Esperado: {"processing":false,"active_collection":"knowledge_XXXX","total_vectors":N}

# 3. Verificar colección en Qdrant
curl.exe -s "http://localhost:6333/collections"
# Esperado: aparece knowledge_XXXX

# 4. Verificar en DB que processed=true
docker-compose exec db psql -U raguser -d ragdb -c "SELECT filename, processed FROM uploaded_files;"

# 5. Restaurar versión anterior (solo visible en UI si hay previous_collection)
curl.exe -s -b "$env:TEMP\cookies.txt" -X POST "http://localhost:8000/admin/restore" -w "%{http_code}"
# Esperado: 303
```

⛔ **Esperar confirmación antes de iniciar Fase 7.**

---

### Fase 7 — Pipeline RAG y chat  ✅ COMPLETADA (2026-07-09, confirmada)
**Objetivo**: chatbot funcional con memoria de conversación y citas de fuentes.

> **Desviaciones respecto al plan:**
> - Historial en **cookie firmada dedicada** `chat_history` (itsdangerous), no dentro de la sesión de auth — funcionalmente equivalente, mantiene la cookie de sesión intacta.
> - **No** se implementó `POST /chat/clear` (no imprescindible; el historial caduca con la cookie). Pendiente si se quiere botón de "limpiar conversación".
> - La lista de mensajes usa `<div role="log" aria-live="polite">` en vez de `<ol><li>`; a11y equivalente.
> - `rag.py` expone `answer_question(db, question, history)` (no `ask(...)`); devuelve además `low_confidence`.

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

### Fase 8 — Tests automatizados  ✅ COMPLETADA (2026-07-09, confirmada)
**Objetivo**: suite de tests que pasa en CI sin servicios externos levantados.

> **Nota:** el endpoint `/health` se enriqueció (status `ok`/`degraded`, `postgres`, `qdrant`,
> `active_collection`, `total_vectors`, con degradación elegante) y `test_health.py` se reescribió con
> Qdrant mockeado. La suite completa (auth, admin, rag, chat, ingest, vector_store, database, health)
> pasa con cobertura ≥ 80 %.

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

### Fase 9 — Dockerfile y compose de producción  ✅ COMPLETADA (2026-07-09, confirmada)
**Objetivo**: imagen optimizada y orquestación lista para CI/CD.

> **Verificado:** Dockerfile multi-stage (builder venv `/opt/venv` + runtime slim, usuario no-root
> `appuser`), `.dockerignore` creado, compose con healthchecks (db `pg_isready`, qdrant TCP 6333) y
> `depends_on: condition: service_healthy`. Los 3 contenedores arrancan *healthy*; imagen **380 MB**
> (< 500 MB).

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

### Fase 10 — CI/CD y despliegue Azure  ✅ COMPLETADA (2026-07-09, verificada)
**Objetivo**: push a main despliega automáticamente en Azure Container Apps.

> **Estado:** pipeline completo en verde (lint→test→build-and-push→deploy→smoke-test) y app desplegada
> en Azure Container Apps. `/health` responde `"status":"ok"` (postgres + qdrant `connected`).
> - Recursos: RG `rg-entregable5`, ACR `acrentregable5`, Container App `rag-chatbot` en
>   `env-entregable5` (swedencentral), SP `sp-github-entregable5`, Azure DB for PostgreSQL Flexible
>   Server, Qdrant Cloud. Secrets+variables en GitHub cargados.
> - `.github/workflows/deploy.yml` con `az containerapp registry set` (creds admin ACR) para el pull.
> - Gotcha: el `deploy` fallaba con `containerapp 'rag-chatbot' does not exist` hasta ejecutar el paso
>   manual 3 de `azure.md` (crear entorno + Container App con imagen placeholder).

**Tareas (manual, una sola vez)**
- [ ] Crear Resource Group: `az group create --name rg-entregable5 --location westeurope`
- [ ] Crear ACR: `az acr create --name <acr-name> --resource-group rg-entregable5 --sku Basic`
- [ ] Crear Container Apps environment: `az containerapp env create ...`
- [ ] Crear Container App inicial con imagen placeholder
- [ ] Configurar GitHub Actions secrets y variables (ver lista en CLAUDE.md)
- [x] Documentar todos los pasos en `doc/azure.md`

**Tareas (automatizadas)**
- [x] `.github/workflows/deploy.yml` — *stages* encadenados con `needs:` (equivalente
  GitHub Actions a los *stages* de Azure DevOps del proyecto de ejemplo). Cada *job* solo
  arranca si el anterior termina en verde:
  ```
  on: push to main

  jobs:
    lint            → ruff check . && ruff format --check .
    test            → needs: lint    · pytest --cov=app --cov-fail-under=80
    build-and-push  → needs: test    · docker build
                                     · smoke test de la imagen (postgres+qdrant efímeros)
                                     · push a ACR (:$SHA y :latest)
    deploy          → needs: build-and-push
                        · az containerapp secret set  (APP_USER, APP_PASSWORD, SECRET_KEY, ...)
                        · az containerapp update --image :$SHA
    smoke-test      → needs: deploy  · curl https://<url>/health con reintentos → {"status":"ok"}
  ```
  - Orden y responsabilidad de cada *stage* calcados del ejemplo `tmp/.../azure-pipelines.yml`
    (`Validate → BuildAndPush → Deploy → ValidateDeployment`), añadiendo `lint` como primer *stage*.
  - Nombres de *jobs* en inglés, en minúscula-con-guiones.

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

### Fase 11 — UI final (plugin de diseño)  🟡 APLICADA · pendiente validación visual
**Objetivo**: aplicar diseño visual definitivo sobre las plantillas funcionales existentes.

> **Hecho (2026-07-09):** rediseño aplicado con dirección **sobrio académico/profesional, tema claro**.
> - Sistema de diseño: paleta papel frío `#f6f7f9` + tinta pizarra `#17212b` + acento **teal `#1f6f78`**
>   (evita clichés cream/terracota/broadsheet); tipografía **IBM Plex** (Serif títulos · Sans cuerpo ·
>   Mono datos) vía Google Fonts; semánticos con contraste AA.
> - **Firma:** aparato de citas en el chat = cada fuente como referencia con **barra de fiabilidad**
>   (color por umbral 75/50) y `%`/página en mono. Materializa el *grounding by design*.
> - Reescritos: `app/static/styles.css` (completo), `base.html` (header + wordmark + skip-link + nav con
>   `aria-current` vía `request.url.path`), `login.html`, `admin.html`, `chat.html`, `chat_message.html`.
> - HTMX preservado (chat `hx-post`/`beforeend`, polling de admin). Templates/CSS montados como volumen
>   → basta refrescar el navegador, sin rebuild.
>
> **Pendiente:** validación visual del usuario (feedback de color/tipografía/densidad) + checklist de
> abajo. Tras confirmar, marcar ✅.

**Tareas**
- [x] Invocar `/frontend-design` con las plantillas actuales como base
- [x] Aplicar resultado a `base.html`, `login.html`, `admin.html`, `chat.html` (+ `chat_message.html`)
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

### Fase 12 — Documentación y validación final de rúbrica  🟡 APLICADA
**Objetivo**: documentación completa y verificación de los 6 criterios.

**Decisiones tomadas (2026-07-10):**
- **Makefile: descartado.** El objetivo del entregable es demostrar CI/CD; los comandos reales ya
  están documentados. `scripts/lint.ps1` y `doc/style-guide.md` también se descartan.
- **`[tool.ruff]` en pyproject: descartado.** Activar `E501`/`I`/`UP`/`B` obligaría a un refactor de
  alcance desconocido a cambio de cero puntos. Ruff sigue con defaults. Sí se crea `.editorconfig`.
- **Mejoras del docente**: se implementa el smoke test de la imagen antes de publicarla y se aligera
  el job `lint`. Se descartan, razonadas en `doc/verificacion.md`: Gunicorn (uvicorn ya es servidor
  de producción), `requirements-dev.txt` (rompería `docker-compose exec app pytest`) y OIDC +
  identidad administrada (no lo exige la rúbrica y arriesga un pipeline en verde).

**Tareas**
- [x] Quitar `novalidate` del `<form>` de `login.html` (los campos ya tenían `required`; era el
  `novalidate` lo que dejaba ver el JSON 422 de FastAPI al enviar vacío)
- [x] `.editorconfig`
- [x] `deploy.yml`: job `lint` instala solo ruff; smoke test de la imagen en `build-and-push`
- [x] `.dockerignore`: excluir `example/` y `.editorconfig`
- [x] `README.md` — aviso de proyecto académico, descripción, instalación rápida, enlace a la
  documentación, stack, criterios de valoración, licencia AGPL
- [x] `doc/index.md`, `doc/tecnica.md`, `doc/instalacion.md`, `doc/uso.md`, `doc/pipeline.md`,
  `doc/verificacion.md`
- [x] `doc/azure-setup.md` → `doc/azure.md`, con secciones nuevas de monitorización y limpieza de recursos
- [x] `entrega.md` — texto del correo de entrega
- [x] `doc/img/` con las 6 capturas
- [x] `git rm doc/azure-setup.md`
- [x] `doc/azure.md`: comandos de subida manual a ACR (`az acr login`/`docker tag`/`docker push`),
  que el enunciado enumera explícitamente
- [x] Nombrar las **pruebas de integración** en `pipeline.md` y `verificacion.md` (el enunciado las
  exige; existían pero no se llamaban así)
- [x] Checklist rúbrica (documentado en `doc/verificacion.md`, con evidencia gráfica):
  - [x] Criterio 1 — repo GitHub con estructura y `.env.example`
  - [x] Criterio 2 — `docker-compose up --build` funciona desde cero
  - [x] Criterio 3 — imagen visible en Azure Portal → ACR
  - [x] Criterio 4 — URL pública de Container Apps responde
  - [x] Criterio 5 — workflow de Actions con todos los jobs en verde
  - [x] Criterio 6 — `/health` con DB+Qdrant, `az containerapp logs show` muestra logs

**Cómo probar**
```powershell
# 1. Gate local antes de pushear
docker-compose run --rm --no-deps app ruff check .
docker-compose run --rm --no-deps app ruff format --check .
docker-compose exec app pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# 2. Login con campos vacíos → el navegador bloquea el envío, no aparece JSON

# 3. Simular descarga desde cero (otro directorio, sin .env)
docker-compose up --build
curl.exe -s "http://localhost:8000/health"

# 4. Push a main → observar el pipeline; el nuevo paso "Smoke test de la imagen" debe pasar
#    y capturar las 6 pantallas para doc/img/
```

---

### Fase 13 — Comprobación final de requisitos  🟡 EN CURSO
**Objetivo**: verificar contra `plan/entregable5.md` que no falta nada.

- [x] Releer `plan/entregable5.md` punto por punto
- [x] Confirmar que `doc/img/` tiene las 6 capturas con los nombres correctos
- [x] Confirmar que `.dockerignore` y todos los `.md` están actualizados
- [x] Revisar `entrega.md`
- [x] **Borrador del informe** en `informe.md` — 9 secciones, ~4 páginas maquetado, con marcadores
  `[FIGURA n]` para las 6 capturas y campos `⟨ ⟩` para URL, usuario y contraseña.
- [ ] **Maquetar el informe** y exportarlo a PDF/Word: Arial o Calibri 12, interlineado 1,5, insertar
  las figuras de `doc/img/`, rellenar los campos `⟨ ⟩` y borrar el bloque de instrucciones inicial.
  Es el artefacto que se califica.
- [ ] Rellenar los campos `⟨ ⟩` de `entrega.md` (URL, usuario, contraseña).

**Desviación consciente del enunciado:** las pautas proponen *Python (Flask)* o *Node.js (Express)*;
se usa **Python con FastAPI**. La rúbrica no menciona framework alguno. Razonado en
`doc/verificacion.md`.

---

## Ampliación futura — Modo quiz
Solo implementar tras completar Fase 12 y con nota 10/10 confirmada.
`GET /quiz` → Azure OpenAI genera 5 preguntas sobre el contenido activo → formulario HTMX → corrección inmediata en cliente. Sin persistencia en DB.
