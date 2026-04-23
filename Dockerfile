FROM node:22-bookworm-slim AS assets

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY assets/ assets/
RUN npm run build


FROM python:3.14-slim

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=collective.settings.production \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY manage.py ./
COPY collective/ collective/
COPY apps/ apps/
COPY templates/ templates/
COPY static/ static/
COPY --from=assets /app/static/app.css /app/static/app.css
COPY entrypoint.sh ./

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x entrypoint.sh \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
