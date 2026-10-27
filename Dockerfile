# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY shared/ /app/shared/
# These two values are public browser configuration, never backend secrets.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY
RUN test -n "$VITE_SUPABASE_URL" && test -n "$VITE_SUPABASE_PUBLISHABLE_KEY" \
    && npm run build

FROM python:3.12-slim-bookworm AS python-build
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY --from=python-build /app/backend/.venv /app/backend/.venv
COPY backend/app/ ./app/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini backend/start.py ./
COPY backend/tools/install_catalog.py ./tools/install_catalog.py
COPY shared/ /app/shared/
COPY assets/catalog/muselly-catalog.zip /app/assets/catalog/muselly-catalog.zip
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
RUN python tools/install_catalog.py \
    && useradd --create-home --uid 10001 muselly
USER muselly
EXPOSE 8080
CMD ["python", "/app/backend/start.py"]
