# Verificación de la rúbrica

Este documento recorre los seis criterios de evaluación, señala dónde se cumple cada uno y qué
evidencia lo respalda. Después enumera lo que el proyecto aporta **por encima** de lo exigido, y
cierra con las decisiones que se han tomado conscientemente y no se han implementado.

---

## Cumplimiento de los criterios

### 1. Configuración y estructuración — 15 %

> *Correcta configuración del repositorio y estructura del código.*

- Repositorio en **GitHub**, con historial de *commits* por fases.
- Estructura modular: cada módulo de `app/` tiene una responsabilidad única (ver
  [tecnica.md](tecnica.md#componentes)). Tests separados en `tests/`, documentación en `doc/`,
  infraestructura en la raíz.
- **`.env.example`** con *placeholders* versionado en el repositorio; el `.env` real está en
  `.gitignore`. Ninguna credencial ha tocado nunca el historial de Git.
- `.dockerignore` para no filtrar secretos ni material innecesario a la imagen.
- `.editorconfig` con la convención de indentación del proyecto.

**Nota sobre el framework.** El enunciado propone *Python (Flask)* o *Node.js (Express)*. Se ha usado
**Python con FastAPI**, que cumple el espíritu del requisito —backend en Python— y aporta validación
de tipos, documentación OpenAPI automática y soporte nativo de tareas en segundo plano, necesario para
la ingesta de PDFs. La base de datos es **PostgreSQL**, una de las dos opciones admitidas.

### 2. Contenerización — 15 %

> *Creación adecuada del Dockerfile y docker-compose.yml.*

- **`Dockerfile`** multi-stage: un *stage* `builder` que instala las dependencias en un *virtualenv*
  aislado, y un *stage* `runtime` que copia solo ese *virtualenv* y el código. Corre como usuario
  **no-root** (`appuser`). Imagen final de **~380 MB**.
- **`docker-compose.yml`** con los tres servicios que pide el enunciado: `app`, `db`
  (PostgreSQL 16) y `qdrant`. Los dos servicios de datos tienen **healthcheck**, y `app` declara
  `depends_on: condition: service_healthy`, de modo que no arranca hasta que sus dependencias están
  listas. Volúmenes nombrados para persistir los datos entre reinicios.
- Variables de conexión inyectadas desde `.env` mediante `env_file`.

**Evidencia:** `docker-compose up --build` levanta los tres contenedores en estado *healthy* y
`GET /health` devuelve `{"status":"ok"}`. Instrucciones en [instalacion.md](instalacion.md).

### 3. Registro en Azure — 20 %

> *Uso correcto de ACR para almacenamiento de la imagen.*

- **Azure Container Registry** `acrentregable5` (SKU Basic), creado según el paso 2 de
  [azure.md](azure.md).
- El *job* `build-and-push` del pipeline hace `az acr login`, construye la imagen y la publica con
  **dos etiquetas**: el SHA del *commit* y `latest`. La etiqueta por SHA permite trazar exactamente
  qué código corre en producción y revertir a cualquier revisión anterior.
- El *push* está **condicionado a que la imagen supere un smoke test** (ver criterio 5).

**Evidencia:** [`img/03-build-and-push.png`](img/03-build-and-push.png).

### 4. Despliegue en Azure — 20 %

> *Configuración y ejecución en Container Apps o Container Instances.*

- **Azure Container Apps**: app `rag-chatbot` en el entorno `env-entregable5`, región
  `swedencentral`, con *ingress* externo sobre el puerto 8000.
- El *job* `deploy` actualiza la imagen con `az containerapp update --image ...:$SHA`, generando una
  revisión nueva sin interrumpir el servicio.
- Las **variables de entorno** se definen en el propio comando de despliegue. Los valores sensibles se
  inyectan antes como secretos de Container Apps (`az containerapp secret set`) y se referencian con
  `secretref:`, de forma que nunca aparecen en la imagen, el repositorio ni los logs del workflow.
- Base de datos accesible desde la aplicación: **Azure Database for PostgreSQL** (Flexible Server,
  Burstable B1ms), con TLS obligatorio y acceso permitido a los servicios de Azure.

**Evidencia:** [`img/04-deploy.png`](img/04-deploy.png) y la respuesta pública de `/health`.

### 5. Pipeline CI/CD — 20 %

> *Configuración del flujo de automatización con pruebas y despliegue continuo.*

Cinco *jobs* encadenados con `needs:`, disparados en cada `push` a `main`. Detalle completo en
[pipeline.md](pipeline.md).

| Stage | Función |
|---|---|
| `lint` | `ruff check` + `ruff format --check` |
| `test` | `pytest` con cobertura mínima del 80 % |
| `build-and-push` | construir → **probar la imagen** → publicar en ACR |
| `deploy` | inyectar secretos y actualizar Container Apps |
| `smoke-test` | validar que la aplicación desplegada responde |

El enunciado pide **pruebas unitarias y de integración**. Ambas están, en capas distintas:

- **Unitarias** (`test`): la lógica de `app/`, con SQLite en memoria y Qdrant y Azure OpenAI mockeados.
- **Integración** (`build-and-push`): la imagen Docker completa levantada contra un PostgreSQL 16 y un
  Qdrant reales, exigiendo que `/health` conecte con ambos.
- **Extremo a extremo** (`smoke-test`): la aplicación ya desplegada, consultada desde Internet contra
  sus bases de datos de producción.

**Evidencia:** [`img/00-deploy.png`](img/00-deploy.png) — ejecución completa en verde.

### 6. Monitoreo y validación — 10 %

> *Implementación de logs y pruebas de conexión.*

- **Endpoint `/health`** público, que reporta el estado de la aplicación y de **cada** dependencia por
  separado. Devuelve `"ok"` solo si PostgreSQL y Qdrant responden; `"degraded"` en caso contrario,
  indicando cuál falla. Nunca devuelve error, para no romper los sondeos.
- **Prueba de conexión automatizada, dos veces**: una sobre la imagen antes de publicarla y otra sobre
  el despliegue real. Ambas exigen `"status":"ok"`, es decir, conexión efectiva con la base de datos.
- **Logs** disponibles con `az containerapp logs show --name rag-chatbot --resource-group
  rg-entregable5 --follow`. Comandos de monitorización en la [sección 7 de azure.md](azure.md#7-monitorización).

**Evidencia:** [`img/05-smoke-test.png`](img/05-smoke-test.png).

---

## Evidencias del despliegue

| Captura | Qué demuestra |
|---|---|
| [`img/00-deploy.png`](img/00-deploy.png) | Pipeline completo en verde en GitHub Actions |
| [`img/01-lint.png`](img/01-lint.png) | Stage `lint` superado |
| [`img/02-test.png`](img/02-test.png) | Tests con cobertura ≥ 80 % |
| [`img/03-build-and-push.png`](img/03-build-and-push.png) | Imagen validada y publicada en ACR |
| [`img/04-deploy.png`](img/04-deploy.png) | Container App actualizada con la imagen del *commit* |
| [`img/05-smoke-test.png`](img/05-smoke-test.png) | `/health` responde `{"status":"ok"}` desde la URL pública |

---

## Por encima de la rúbrica

Nada de lo siguiente es exigido por los seis criterios. Se ha incluido porque mejora la calidad del
entregable.

**En el pipeline**

- **Stage `lint`** previo a los tests. La rúbrica pide pruebas; no pide análisis estático.
- **Puerta de cobertura del 80 %** (`--cov-fail-under=80`), que convierte la cobertura en un requisito
  y no en una métrica informativa.
- **Smoke test de la imagen antes de publicarla en ACR.** Los tests corren sobre el código fuente; la
  imagen se valida por separado, levantándola contra un PostgreSQL y un Qdrant efímeros y exigiendo
  que `/health` responda `"ok"`. Una imagen rota nunca llega al registro.
- **Smoke test del despliegue con reintentos**, exigiendo `"status":"ok"` y no un simple 200. El
  pipeline solo termina en verde si el servicio en producción alcanza sus dos bases de datos.
- **Etiquetado por SHA de commit** además de `latest`, para trazabilidad y *rollback*.

**En la seguridad**

- Credenciales gestionadas de extremo a extremo con **GitHub Secrets → Container Apps secrets →
  `secretref:`**. No hay valores sensibles en la imagen, el repositorio ni los logs.
- Contenedor ejecutado como **usuario no-root**.
- Contraseñas hasheadas con **bcrypt**; cookies de sesión **firmadas** (`itsdangerous`), HttpOnly y
  SameSite=lax.
- Validación de las subidas por extensión, cabecera mágica del fichero y tamaño máximo.

**En la aplicación**

- **RAG con *grounding by design***: prompt restrictivo, rechazo explícito cuando la información no
  está en los documentos, umbral de confianza y **citas obligatorias** con fichero, página y
  fiabilidad. Las respuestas son verificables contra la fuente.
- **Versionado de la base vectorial** con restauración a la versión anterior en un clic.
- **Endpoint `/health` granular**, que distingue el estado de cada dependencia.
- **Interfaz accesible** (WCAG AA): navegación completa por teclado, etiquetas asociadas, regiones
  `aria-live`, foco visible y contraste suficiente.
- **Imagen Docker multi-stage** de ~380 MB, sin cadena de compilación en el *runtime*.

**En el proyecto**

- Documentación completa en español, con guía de instalación, de uso, de despliegue y de limpieza de
  recursos.
- Licencia **AGPL-3.0**.

---

## Decisiones tomadas y no implementadas

Se recogen aquí las sugerencias de mejora recibidas en la corrección de un entregable anterior, junto
con la decisión adoptada para este. Las tres primeras se han implementado; las tres últimas se
descartan de forma razonada.

| Sugerencia | Decisión |
|---|---|
| Probar la imagen Docker antes de publicarla | **Implementada.** Es el paso *Smoke test de la imagen* del *job* `build-and-push`. |
| Validar el endpoint tras el despliegue | **Implementada.** El *job* `smoke-test` reintenta hasta 10 veces. |
| Incorporar un endpoint `/health` | **Implementada**, y ampliada: informa del estado de cada dependencia. |
| Aportar evidencias del despliegue | **Implementada.** Capturas de las cinco fases del pipeline, enlazadas arriba. |
| Utilizar un servidor de producción (Gunicorn) | **Descartada**, ver abajo. |
| Separar `requirements.txt` y `requirements-dev.txt` | **Descartada**, ver abajo. |
| Autenticación con OIDC e identidad administrada | **Descartada**, ver abajo. |

### Servidor de producción

La sugerencia original aplicaba a una aplicación **Flask** arrancada con su servidor de desarrollo, que
la propia documentación de Flask desaconseja explícitamente en producción.

Aquí no ocurre eso: la aplicación se sirve con **uvicorn**, que *es* un servidor ASGI apto para
producción. Añadir Gunicorn solo aportaría gestión multiproceso, y en Azure Container Apps la escala
horizontal se resuelve con **réplicas del contenedor**, no con *workers* dentro de él. Sumar una
dependencia para gestionar procesos que el orquestador ya gestiona no mejora nada.

### Separación de dependencias de ejecución y de testing

Sacar `pytest`, `pytest-cov` y `ruff` de la imagen ahorraría unos 40 MB. El coste es mayor que el
beneficio: todo el flujo de desarrollo del proyecto ejecuta las herramientas **dentro del
contenedor** (`docker-compose exec app pytest`, `docker-compose run --rm --no-deps app ruff check .`),
y esos comandos dejarían de funcionar. Hacerlo correctamente exigiría un *stage* `dev` en el
`Dockerfile` y que Compose construyera con `target: dev`.

Sí se ha aplicado la parte que afecta al CI, que es lo que aquí se evalúa: el *job* `lint` instala
**solo `ruff`** en vez de todo el `requirements.txt`, reduciendo su duración a unos segundos.

### OIDC e identidad administrada

Autenticar GitHub Actions contra Azure mediante **OIDC**, y dejar que Container Apps descargue la
imagen con una **identidad administrada** y el rol `AcrPull`, es la práctica correcta en un entorno
profesional: elimina los secretos de larga duración.

No se ha implementado por dos razones. La primera, que ninguno de los seis criterios de la rúbrica
exige un mecanismo de autenticación concreto; el criterio 3 pide «uso correcto de ACR» y el 5
«configuración del flujo de automatización», y ambos se cumplen. La segunda, que migrar a OIDC en la
fase final habría puesto en riesgo un pipeline verificado y en verde, a cambio de cero puntos.

El proyecto usa un **service principal** (`AZURE_CREDENTIALS`) y las credenciales de administrador del
ACR, que es el enfoque propuesto en la guía de la asignatura.

> **Sobre Azure for Students:** crear un service principal requiere permisos de creación de
> aplicaciones en Microsoft Entra ID, que algunas suscripciones educativas bloquean. Este proyecto se
> ha desplegado sobre una **suscripción de pago**, donde la operación está permitida, por lo que no ha
> sido necesario recurrir a la alternativa con credenciales de ACR y *bearer token* contra la API REST.

---

## Limitaciones conocidas

- Los **PDFs subidos se pierden al reiniciar** el contenedor en Azure, porque Container Apps no tiene
  sistema de ficheros persistente y no se ha montado un *Azure Files share*. Los vectores, que están en
  Qdrant Cloud, sí sobreviven. Aceptable para una demostración académica.
- **No hay OCR**: los PDFs escaneados como imagen no se pueden indexar.
- **Un único usuario**, sin registro ni gestión de roles.
- **Sin migraciones de esquema**: las tablas se crean con `create_all()` al arrancar.
