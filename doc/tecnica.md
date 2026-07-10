# Descripción técnica

## Visión general

La aplicación es un **RAG** (*Retrieval-Augmented Generation*): en lugar de responder con el
conocimiento interno del modelo de lenguaje, recupera fragmentos relevantes de los PDFs cargados y
obliga al modelo a redactar la respuesta usando solo esos fragmentos.

Un único proceso FastAPI sirve tanto la interfaz web (plantillas Jinja2 + HTMX) como la API. No hay
framework de JavaScript ni proceso de build de frontend.

---

## Componentes

### Aplicación (`app/`)

| Módulo | Responsabilidad |
|---|---|
| `main.py` | Instancia FastAPI, `lifespan`, rutas raíz, `/login`, `/logout` y `/health` |
| `auth.py` | Hash bcrypt, cookie de sesión firmada y `AuthMiddleware` que protege todas las rutas |
| `admin.py` | Subir, listar y borrar PDFs; lanzar el procesado; restaurar la versión anterior |
| `chat.py` | Página de chat e endpoint `POST /chat/ask` que devuelve HTML parcial para HTMX |
| `rag.py` | Pipeline de respuesta: *embed* → *retrieve* → *generate*, con citas y umbral de confianza |
| `ingest.py` | Parseo de PDFs, troceado, generación de embeddings e inserción en Qdrant |
| `vector_store.py` | Operaciones sobre Qdrant: colecciones, búsqueda, borrado por fuente y versionado |
| `database.py` | Motor SQLAlchemy y sesión de base de datos |
| `models.py` | Modelos `User`, `Config` y `UploadedFile` |
| `init_db.py` | Crea las tablas al arrancar y siembra el usuario inicial si no existe |

### Servicios de infraestructura

| Servicio | En local | En producción |
|---|---|---|
| Base de datos relacional | Contenedor `postgres:16-alpine` | Azure Database for PostgreSQL (Flexible Server, B1ms) |
| Base de datos vectorial | Contenedor `qdrant/qdrant` | Qdrant Cloud (free tier, 1 GB) |
| Modelos de lenguaje | Azure OpenAI | Azure OpenAI |

---

## Por qué Qdrant es externo en producción

En local, Qdrant corre como un contenedor más de `docker-compose.yml` y guarda sus vectores en un
volumen. En Azure **no** se despliega como contenedor, y la razón es concreta:

Qdrant es un servicio **con estado**: necesita un disco que sobreviva a los reinicios. Azure Container
Apps está pensado para cargas sin estado; su sistema de ficheros es efímero y se pierde en cada
revisión nueva o reinicio de réplica. Persistirlo exigiría montar un *Azure Files share*, lo que
implica una cuenta de almacenamiento, un `storage mount` en el entorno de Container Apps, y asumir
que Qdrant sobre un sistema de ficheros de red (SMB) tiene un rendimiento notablemente peor que sobre
disco local.

La alternativa —**Qdrant Cloud**, capa gratuita de 1 GB— elimina todo eso: sin volúmenes, sin coste
adicional, con backups gestionados, y la aplicación solo cambia dos variables de entorno
(`QDRANT_URL` y `QDRANT_API_KEY`). Para el volumen de datos de este proyecto, 1 GB es holgado.

**PostgreSQL sí se queda dentro de Azure**, porque Azure ofrece Postgres gestionado de primera clase
(Flexible Server) y mantener la base relacional en la nube del entregable da coherencia a la
arquitectura. La rúbrica no exige que la base de datos esté en Azure, pero se elige así.

---

## Flujo RAG

Cada pregunta del usuario recorre estos pasos (`app/rag.py:51`):

1. **Embed.** La pregunta se convierte en un vector de 1536 dimensiones con el *deployment* de
   embeddings de Azure OpenAI (`text-embedding-3-small`).
2. **Retrieve.** Se buscan los 5 fragmentos más próximos por similitud coseno en la colección Qdrant
   activa. Si no hay colección o no hay resultados, se devuelve directamente el mensaje de rechazo.
3. **Prompt.** Se construye la conversación: *system prompt* restrictivo, los últimos 6 intercambios
   del historial, y un mensaje de usuario que incrusta los fragmentos recuperados como `CONTEXTO`.
4. **Generate.** Azure OpenAI redacta la respuesta con `temperature=0.2`.
5. **Citar.** Se devuelven las fuentes de los fragmentos usados y se marca `low_confidence` si el
   mejor *score* no alcanza 0,75.

### Grounding by design

Cuatro mecanismos garantizan que la respuesta esté anclada en los documentos y no en el conocimiento
paramétrico del modelo:

1. **System prompt restrictivo.** Obliga a responder en español y exclusivamente con el `CONTEXTO`,
   prohibiendo el conocimiento externo.
2. **Rechazo explícito.** Si la información no está, la respuesta es literalmente
   «No encuentro información sobre eso en los documentos disponibles.»
3. **Umbral de confianza.** Si ningún fragmento supera un *score* de 0,75, la interfaz muestra el
   aviso «⚠️ Baja confianza».
4. **Citas obligatorias.** Cada respuesta lista fichero, página y fiabilidad (*score* coseno × 100),
   con enlace al PDF original.

---

## Ingesta y troceado

Al pulsar **Procesar** en el panel de administración (`app/ingest.py:71`):

1. Se crea una colección nueva llamada `knowledge_{timestamp}`.
2. Cada PDF se parsea con `pypdf`, página a página, descartando las que no tienen texto.
3. El texto de cada página se trocea en fragmentos de 2000 caracteres con 200 de solapamiento.
4. Cada fragmento se convierte en vector y se inserta en Qdrant con el *payload*
   `{source, page, chunk_idx, content}`.
5. Se marcan los ficheros como procesados y se rota la colección activa.

El proceso corre como *background task* de FastAPI; la interfaz consulta `GET /admin/status` cada
pocos segundos para mostrar el progreso.

> **Limitación conocida:** solo se extrae texto. Los PDFs escaneados como imagen, sin capa de texto,
> no aportan contenido. No hay OCR.

---

## Versionado de la base vectorial

La tabla `config` guarda dos claves: `active_collection` y `previous_collection`. Se mantienen como
mucho **dos** colecciones a la vez.

- **Procesar** crea una colección nueva, la marca como activa, mueve la anterior a
  `previous_collection` y **elimina** la que ocupaba ese puesto.
- **Restaurar versión anterior** intercambia ambas claves, sin borrar nada. El botón solo aparece si
  existe `previous_collection`.

La colección a consultar se lee de `config` en cada petición de chat, nunca se cachea en memoria. Eso
hace que un cambio de versión tenga efecto inmediato, incluso con varias réplicas del contenedor.

---

## Modelo de datos

```sql
users(id SERIAL PK, username TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL)
config(key TEXT PK, value TEXT NOT NULL)
uploaded_files(id SERIAL PK, filename TEXT UNIQUE NOT NULL, size_bytes INT,
               uploaded_at TIMESTAMP DEFAULT now(), processed BOOL DEFAULT false)
```

Las tablas se crean solas al arrancar (`init_db.init()`), y el usuario inicial se siembra desde las
variables `APP_USER` y `APP_PASSWORD` si la tabla `users` está vacía. No hay sistema de migraciones:
para un proyecto de este alcance, `create_all()` es suficiente.

---

## Autenticación y sesiones

Un único usuario, con la contraseña hasheada con **bcrypt**. La sesión se guarda en una cookie
`session` firmada con `itsdangerous` (HttpOnly, SameSite=lax, 8 horas de validez). El historial de
conversación viaja en una segunda cookie firmada, `chat_history`, limitada a los 6 últimos
intercambios para no superar los 4 KB.

No hace falta Redis ni almacenar sesiones en base de datos, y el contenedor sigue siendo sin estado.

`AuthMiddleware` protege todas las rutas salvo `/login`, `/health` y los ficheros estáticos.

---

## Seguridad

- Las credenciales **nunca** están en el repositorio. `.env.example` contiene solo *placeholders*;
  el `.env` real está en `.gitignore`.
- En producción, los valores sensibles viajan desde GitHub Secrets a los secretos de Container Apps
  (`az containerapp secret set`) y se referencian como `secretref:` en las variables de entorno. En
  ningún momento quedan escritos en la imagen ni en el workflow.
- La subida de ficheros valida extensión, cabecera mágica `%PDF` y tamaño máximo de 20 MB.
- El contenedor corre como usuario **no-root** (`appuser`).

> Los PDFs subidos se guardan en el sistema de ficheros del contenedor. En Azure Container Apps eso
> significa que **se pierden al reiniciar**, ya que no hay volumen persistente. Es una limitación
> asumida para una demostración académica.

---

## Endpoint de salud

`GET /health` es público y no falla nunca: siempre devuelve 200, degradando el estado si algún
servicio no responde.

```json
{
  "status": "ok",
  "postgres": "connected",
  "qdrant": "connected",
  "active_collection": "knowledge_1234567890",
  "total_vectors": 142
}
```

`status` vale `"ok"` solo si Postgres **y** Qdrant responden; en caso contrario, `"degraded"`. El
pipeline lo usa dos veces: para validar la imagen antes de publicarla y para validar el despliegue
después de actualizarlo.
