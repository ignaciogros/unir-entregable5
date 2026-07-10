# Instalación en local

## Requisitos

- **Docker** y **Docker Compose** (Docker Desktop en Windows/macOS).
- Un recurso de **Azure OpenAI** con dos *deployments*: uno de chat y uno de embeddings. Si aún no lo
  tienes, el paso 1 de [azure.md](azure.md) explica cómo crearlo.

No hace falta instalar Python: todo corre dentro de los contenedores.

---

## 1. Clonar el repositorio

```powershell
git clone https://github.com/ignaciogros/unir-entregable5.git
cd unir-entregable5
```

## 2. Crear el fichero `.env`

```powershell
copy .env.example .env
```

Edita `.env` y rellena los valores. El fichero está en `.gitignore`, nunca se sube al repositorio.

| Variable | Descripción | Valor en local |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | URL del recurso de Azure OpenAI | `https://tu-recurso.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Clave del recurso | *(tu clave)* |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Nombre del *deployment* de chat | `chat` |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Nombre del *deployment* de embeddings | `embedding` |
| `AZURE_OPENAI_API_VERSION` | Versión de la API | `2024-10-21` |
| `DATABASE_URL` | Cadena de conexión a PostgreSQL | `postgresql://raguser:ragpass@db:5432/ragdb` |
| `QDRANT_URL` | URL de Qdrant | `http://qdrant:6333` |
| `QDRANT_API_KEY` | Clave de Qdrant | *(vacío en local)* |
| `SECRET_KEY` | Firma de las cookies de sesión | cualquier cadena de ≥ 32 caracteres |
| `APP_USER` | Usuario del chatbot | `user1` |
| `APP_PASSWORD` | Contraseña del chatbot | `Pass134!` |

`DATABASE_URL` y `QDRANT_URL` apuntan a los nombres de servicio de Docker Compose (`db`, `qdrant`),
no a `localhost`. Déjalos como están.

## 3. Arrancar

```powershell
docker-compose up --build
```

Levanta tres contenedores: la aplicación (puerto 8000), PostgreSQL (5432) y Qdrant (6333). La
aplicación espera a que los otros dos estén *healthy* antes de arrancar, y al iniciarse crea las
tablas y siembra el usuario definido en `.env`.

## 4. Comprobar

```powershell
curl.exe -s "http://localhost:8000/health"
```

Respuesta esperada:

```json
{"status":"ok","postgres":"connected","qdrant":"connected","active_collection":null,"total_vectors":0}
```

Abre **http://localhost:8000** e inicia sesión con las credenciales de `APP_USER` y `APP_PASSWORD`.
A partir de aquí, sigue la [guía de uso](uso.md).

---

## Comandos útiles

```powershell
# Arrancar en segundo plano
docker-compose up --build -d

# Ver logs de la aplicación en tiempo real
docker-compose logs -f app

# Reiniciar solo la app, sin tocar la base de datos ni Qdrant
docker-compose up --build app

# Tests con cobertura (el mismo gate que el pipeline)
docker-compose exec app pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# Lint y formato (--no-deps evita esperar a los healthchecks)
docker-compose run --rm --no-deps app ruff check .
docker-compose run --rm --no-deps app ruff format --check .

# Autoarreglo
docker-compose run --rm --no-deps app ruff check . --fix
docker-compose run --rm --no-deps app ruff format .

# Parar y borrar volúmenes (se pierden los datos)
docker-compose down -v
```

---

## Problemas frecuentes

**La app no arranca y los logs muestran un error de conexión a PostgreSQL.**
Al iniciarse, la aplicación crea las tablas contra la base de datos; si no la alcanza, el proceso
termina. Comprueba que `DATABASE_URL` usa el host `db` y que el contenedor está *healthy* con
`docker ps`.

**`/health` responde `"status":"degraded"`.**
Uno de los dos servicios de datos no responde. El propio JSON indica cuál: mira los campos
`postgres` y `qdrant`.

**El chat responde siempre «No encuentro información sobre eso en los documentos disponibles».**
No hay colección activa todavía. Sube al menos un PDF y pulsa **Procesar** en el panel de
administración. Si ya lo hiciste, revisa que el PDF tenga texto seleccionable: los escaneados como
imagen no aportan contenido, porque no se aplica OCR.

**Error de autenticación contra Azure OpenAI.**
Revisa `AZURE_OPENAI_ENDPOINT` (debe acabar en `/`), la clave, y que los nombres de los
*deployments* de `.env` coincidan exactamente con los creados en Azure.
