# Licencias y software de terceros

Este proyecto se distribuye bajo la **[GNU Affero General Public License v3.0](../LICENSE)**
(AGPL-3.0), Copyright © 2026 Ignacio Gros.

El software se apoya en librerías de terceros que conservan **su propia licencia** y a cuyos autores
se reconoce aquí la autoría, tal como exigen sus términos. Ninguna de ellas pasa a ser AGPL por
formar parte de esta obra.

---

## Compatibilidad con AGPL-3.0

Todas las dependencias son **permisivas** (MIT, BSD, Apache-2.0, 0BSD, OFL) o **LGPL-3.0**, y todas
son compatibles con la AGPL-3.0: sus términos permiten integrarlas en una obra con licencia
copyleft de la familia GPLv3. La compatibilidad es en un solo sentido —se puede combinar código MIT
o Apache-2.0 dentro de una obra AGPL, no al revés—, que es exactamente el sentido que necesita este
proyecto.

No hay ninguna dependencia con licencia GPLv2-only, que sí sería incompatible con las librerías
Apache-2.0 aquí utilizadas.

Un solo matiz merece mención explícita:

- **`psycopg2-binary`** es la única dependencia con licencia copyleft (**LGPL-3.0 con excepciones**).
  LGPL-3.0 y AGPL-3.0 pertenecen a la misma familia de licencias, por lo que la combinación es
  compatible sin condiciones adicionales. La LGPL exige además que quien reciba el programa pueda
  sustituir o reenlazar la librería: se cumple de forma natural, ya que el código se distribuye como
  fuente y la dependencia se resuelve con `pip` desde `requirements.txt`.
- Las librerías **Apache-2.0** exigen conservar los avisos de atribución al redistribuirlas. El
  repositorio distribuye únicamente código fuente propio, pero la imagen Docker sí las contiene
  (instaladas en `/opt/venv`); este documento sirve como aviso de atribución.

---

## Dependencias de Python

Declaradas en [`requirements.txt`](../requirements.txt).

| Paquete | Licencia | Titular del copyright |
|---|---|---|
| [fastapi](https://github.com/fastapi/fastapi) | MIT | Sebastián Ramírez |
| [uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | Encode OSS Ltd. |
| [jinja2](https://github.com/pallets/jinja) | BSD-3-Clause | Pallets |
| [itsdangerous](https://github.com/pallets/itsdangerous) | BSD-3-Clause | Pallets |
| [python-multipart](https://github.com/Kludex/python-multipart) | Apache-2.0 | Andrew Dunham |
| [sqlalchemy](https://github.com/sqlalchemy/sqlalchemy) | MIT | Michael Bayer y colaboradores |
| [psycopg2-binary](https://github.com/psycopg/psycopg2) | **LGPL-3.0 con excepciones** | Federico Di Gregorio, Daniele Varrazzo |
| [qdrant-client](https://github.com/qdrant/qdrant-client) | Apache-2.0 | Qdrant |
| [openai](https://github.com/openai/openai-python) | Apache-2.0 | OpenAI |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | Mathieu Fenniak y colaboradores |
| [bcrypt](https://github.com/pyca/bcrypt) | Apache-2.0 | The Python Cryptographic Authority |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD-3-Clause | Saurabh Kumar |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | Encode OSS Ltd. |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Holger Krekel y colaboradores |
| [pytest-cov](https://github.com/pytest-dev/pytest-cov) | MIT | Marc Schlaich, Ionel Cristian Mărieș |
| [ruff](https://github.com/astral-sh/ruff) | MIT | Astral Software Inc. |

Estas dependencias arrastran a su vez otras (`starlette`, `pydantic`, `anyio`, `h11`, `grpcio`,
`protobuf`, `certifi`…), todas con licencias permisivas —MIT, BSD, Apache-2.0 o MPL-2.0— igualmente
compatibles con la AGPL-3.0. El listado completo del entorno instalado puede obtenerse con:

```bash
pip install pip-licenses && pip-licenses --format=markdown
```

---

## Recursos de la interfaz

Se cargan desde una CDN en tiempo de ejecución; **no se redistribuyen** dentro de este repositorio ni
dentro de la imagen Docker.

| Recurso | Licencia | Titular del copyright |
|---|---|---|
| [htmx 1.9.12](https://github.com/bigskysoftware/htmx) | 0BSD | Big Sky Software |
| [IBM Plex](https://github.com/IBM/plex) (vía Google Fonts) | SIL Open Font License 1.1 | IBM Corp. |

---

## Imágenes base y servicios

Se ejecutan como **procesos separados** que se comunican por red. No se enlazan con el código de la
aplicación, por lo que constituyen mera agregación y no afectan a su licencia.

| Imagen | Licencia |
|---|---|
| [python:3.11-slim](https://hub.docker.com/_/python) | Python Software Foundation License + licencias de Debian |
| [postgres:16-alpine](https://hub.docker.com/_/postgres) | PostgreSQL License |
| [qdrant/qdrant](https://hub.docker.com/r/qdrant/qdrant) | Apache-2.0 |

Los servicios gestionados de Azure (Container Apps, Container Registry, Database for PostgreSQL,
Azure OpenAI) y Qdrant Cloud se consumen como servicio a través de sus APIs, bajo sus respectivos
términos de uso.
