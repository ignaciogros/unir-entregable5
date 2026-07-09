# syntax=docker/dockerfile:1

# --- Stage 1: builder — instala las dependencias en un venv aislado ---
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


# --- Stage 2: runtime — imagen final mínima, sin toolchain de build ---
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Usuario no-root
RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser

# Copiar el venv ya construido desde el builder
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app/ ./app/
COPY pyproject.toml .

# Directorio de subidas escribible por el usuario no-root
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
