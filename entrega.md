# Entrega — Entregable 5

Buenos días:

Adjunto el Entregable 5. Se trata de un **chatbot RAG**: permite subir documentos PDF, los indexa en
una base de datos vectorial y responde preguntas sobre ellos citando fichero, página y fiabilidad de
cada fuente.

| | |
|---|---|
| **Repositorio** | https://github.com/ignaciogros/unir-entregable5 |
| **Aplicación desplegada** | ⟨URL_PÚBLICA⟩ |
| **Usuario** | ⟨USUARIO⟩ |
| **Contraseña** | ⟨CONTRASEÑA⟩ |

El endpoint de salud, accesible sin autenticación, es `⟨URL_PÚBLICA⟩/health`.

## Criterios de la rúbrica

Se cumplen los seis:

| Criterio | Cómo se cumple |
|---|---|
| Configuración y estructuración | Repositorio en GitHub, estructura modular, `.env.example` versionado y `.env` fuera del repositorio |
| Contenerización | `Dockerfile` multi-stage con usuario no-root y `docker-compose.yml` con tres servicios (app, PostgreSQL, Qdrant) y healthchecks |
| Registro en Azure | Azure Container Registry, con push automático de la imagen etiquetada por SHA de commit y `latest` |
| Despliegue en Azure | Azure Container Apps, actualizado por el pipeline con `az containerapp update` |
| Pipeline CI/CD | GitHub Actions: `lint` → `test` → `build-and-push` → `deploy` → `smoke-test`, encadenados |
| Monitoreo y validación | Endpoint `/health` con estado de cada dependencia, logs vía `az containerapp logs show` y prueba de conexión automatizada en el pipeline |

Las **evidencias del despliegue** (capturas del pipeline completo en verde, de la publicación en ACR y
de la respuesta pública de `/health`) están en `doc/verificacion.md`.

## Por encima de la rúbrica

- **Stage de análisis estático** (`ruff`) previo a los tests.
- **Puerta de cobertura del 80 %**: si baja, el pipeline no despliega.
- **La imagen Docker se prueba antes de publicarse en ACR**: se levanta contra un PostgreSQL y un
  Qdrant efímeros y debe responder `/health` con `"status":"ok"`. Una imagen rota nunca llega al
  registro.
- **El smoke test final exige conexión real con las bases de datos**, no un simple HTTP 200.
- **Credenciales sin secretos en el repositorio**: GitHub Secrets → secretos de Container Apps →
  referencias `secretref:` en las variables de entorno.
- **Trazabilidad y rollback**: cada imagen se etiqueta con el SHA del commit.
- **Aplicación con *grounding by design***: el asistente responde solo con el contenido de los PDFs,
  cita sus fuentes, avisa cuando la confianza es baja y rechaza explícitamente lo que no está en los
  documentos.
- **Versionado del índice vectorial** con restauración a la versión anterior.
- **Interfaz accesible** (WCAG AA, navegable solo con teclado).
- Documentación completa en español, incluida la guía de limpieza de recursos de Azure.

En `doc/verificacion.md` se detallan también las sugerencias de mejora recibidas en el entregable
anterior: cuáles se han incorporado y cuáles se han descartado de forma razonada.

Un saludo,
Ignacio Gros
