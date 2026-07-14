# Documentación técnica — RAG Chatbot

Aplicación web que permite subir documentos PDF y hacer preguntas sobre su contenido en lenguaje
natural. Las respuestas se generan únicamente a partir de los documentos cargados, y cada una cita
las fuentes concretas (fichero, página y porcentaje de fiabilidad) en que se apoya.

El proyecto se despliega en **Azure Container Apps** mediante un pipeline **CI/CD en GitHub Actions**
que valida el código, prueba la imagen Docker, la publica en **Azure Container Registry** y actualiza
el servicio en producción, comprobando finalmente que responde.

> [!CAUTION]
> Proyecto **académico**, con fines exclusivamente educativos. No apto para producción sin una
> revisión de seguridad previa. Ver el aviso completo en el [README](../README.md).

---

## Contenido

| Documento | Qué encontrarás |
|---|---|
| [Descripción técnica](tecnica.md) | Componentes, flujo RAG, modelo de datos y por qué Qdrant es externo |
| [Instalación en local](instalacion.md) | Requisitos, variables de entorno y arranque con Docker Compose |
| [Configuración de Azure](azure.md) | Creación de la infraestructura, secrets de GitHub, monitorización y limpieza de recursos |
| [Guía de uso](uso.md) | Cómo iniciar sesión, subir PDFs, procesarlos y conversar con el chatbot |
| [Pipeline CI/CD](pipeline.md) | Explicación de cada stage, con capturas de una ejecución real |
| [Verificación de la rúbrica](verificacion.md) | Cumplimiento de los seis criterios y qué se aporta por encima de lo exigido |
| [Licencias y software de terceros](licencias.md) | Licencia del proyecto, dependencias utilizadas y reconocimiento de sus autores |

---

## Mapa rápido

```
Navegador
    │  HTTPS
    ▼
Azure Container Apps  ──────►  Azure Database for PostgreSQL
  (imagen desde ACR)              usuarios, configuración, metadatos de PDFs
    │
    ├──────►  Qdrant Cloud          vectores de los fragmentos de PDF
    │
    └──────►  Azure OpenAI          embeddings + generación de respuestas
```

El código fuente vive en GitHub. Cada `push` a `main` dispara el pipeline, que reconstruye la imagen,
la publica en ACR y la despliega en Container Apps. Los detalles están en
[pipeline.md](pipeline.md).
