# RAG Chatbot

Chatbot que responde preguntas sobre tus propios documentos. Subes ficheros **PDF** desde un panel de
administración, la aplicación los indexa, y a partir de ese momento puedes conversar con ellos en
lenguaje natural.

Cada respuesta cita las fuentes en que se apoya —fichero, página y porcentaje de fiabilidad— y si la
información no está en los documentos, el asistente lo dice en lugar de inventarla.

> [!CAUTION]
> **Este proyecto es un trabajo académico con fines exclusivamente educativos.**
>
> Su único objetivo es demostrar la construcción de una aplicación contenerizada con un pipeline
> **CI/CD** completo y su despliegue automatizado en **Azure**, junto con un pipeline **RAG** sobre
> Azure OpenAI y una base de datos vectorial.
>
> **No se aconseja su uso en producción sin una revisión previa en profundidad**, en particular de la
> autenticación, la gestión de sesiones, la validación de las subidas de ficheros y la persistencia de
> los datos.

---

## Instalación rápida

Necesitas **Docker** y un recurso de **Azure OpenAI** con un *deployment* de chat y otro de
embeddings.

```powershell
git clone https://github.com/ignaciogros/unir-entregable5.git
cd unir-entregable5
copy .env.example .env
```

Edita `.env` con tus credenciales de Azure OpenAI y elige un usuario y una contraseña
(`APP_USER`, `APP_PASSWORD`). El resto de valores ya vienen configurados para el entorno local.

```powershell
docker-compose up --build
```

Abre **http://localhost:8000** e inicia sesión. La guía detallada, con la tabla completa de variables
de entorno y la resolución de problemas frecuentes, está en
**[doc/instalacion.md](doc/instalacion.md)**.

---

## 📚 Documentación técnica

> ### **[→ Ir a la documentación completa](doc/index.md)**
>
> Descripción de los componentes, guía de uso, explicación del pipeline CI/CD y **la guía completa de
> configuración de Azure** ([doc/azure.md](doc/azure.md)): creación del Container Registry, la
> Container App, la base de datos, los secrets de GitHub y la limpieza final de recursos.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.11 |
| Backend | FastAPI + uvicorn |
| Interfaz | Jinja2 + HTMX (sin framework de JavaScript) |
| Base de datos | PostgreSQL 16 · SQLAlchemy 2 |
| Base vectorial | Qdrant |
| Modelos de lenguaje | Azure OpenAI (chat + embeddings) |
| Procesado de PDF | pypdf |
| Seguridad | bcrypt · itsdangerous |
| Contenedores | Docker (multi-stage) · Docker Compose |
| CI/CD | GitHub Actions |
| Nube | Azure Container Registry · Azure Container Apps · Azure Database for PostgreSQL · Qdrant Cloud |
| Calidad | ruff · pytest · pytest-cov |

---

## Criterios de valoración

El proyecto cumple los **seis criterios de la rúbrica** del entregable, e incorpora una serie de
mejoras que van más allá de lo exigido: análisis estático en el pipeline, puerta de cobertura del
80 %, validación de la imagen Docker antes de publicarla en el registro, comprobación del despliegue
real contra sus bases de datos, gestión de credenciales sin secretos en el repositorio e interfaz
accesible.

> ### **[→ Verificación de la rúbrica](doc/verificacion.md)**
>
> Detalle de cómo se cubre cada criterio, evidencias del despliegue, y qué se aporta por encima de lo
> pedido.

---

## Licencia

Distribuido bajo la licencia **[GNU Affero General Public License v3.0](LICENSE)** (AGPL-3.0).

Esto implica, entre otras condiciones, que si modificas este software y lo ofreces como servicio a
través de una red, debes poner el código fuente de tu versión a disposición de sus usuarios.

Copyright © 2026 Ignacio Gros.
