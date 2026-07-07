# ── Etapa 1: compilar el frontend ───────────────────────────────────────────
FROM node:24-slim AS frontend
WORKDIR /app/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY frontend/ ./
RUN pnpm build

# ── Etapa 2: backend + estáticos ────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código: dominio, backend y datos
COPY src/ ./src/
COPY backend/ ./backend/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY locales/ ./locales/

# Frontend compilado desde la etapa 1
COPY --from=frontend /app/frontend/dist ./frontend/dist

EXPOSE 8001
HEALTHCHECK CMD curl --fail http://localhost:8001/api/health || exit 1

# El backend sirve la API y el SPA (frontend/dist) en el mismo proceso.
ENTRYPOINT ["uvicorn", "server:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8001"]
