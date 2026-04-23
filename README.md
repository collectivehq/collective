# Collective

Collective is a structured dialogue platform built with Django. It gives groups a shared space to open discussions, organise ideas hierarchically, react to posts, express opinions, and reach decisions.

## Stack

- Python 3.14
- Django 6
- PostgreSQL
- HTMX, Alpine.js, Tailwind CSS 4, DaisyUI 5
- TinyMCE, KaTeX, Prism.js, django-treebeard

## Features

- Public and invite-only spaces
- Role-based permissions for moderation, restructuring, and participant management
- Hierarchical discussions with drag-and-drop tree organisation
- Posts, reactions, and opinions within each discussion
- Email-based authentication with django-allauth
- Rich text editing with code and math support

## Local Development

### Prerequisites

- Python 3.14
- Node.js and npm
- PostgreSQL

### Environment

The project reads configuration from environment variables. These values are enough for local development:

```bash
export DJANGO_SETTINGS_MODULE=collective.settings.development
export POSTGRES_DB=collective
export POSTGRES_USER=collective
export POSTGRES_PASSWORD=collective
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
```

You can also place them in a `.env` file in the repository root.

### Install dependencies

```bash
python -m pip install -e .[dev]
npm install
```

### Run the app

Start the local infrastructure first.

For PostgreSQL, reuse the existing `collective-postgres` container if you already have one on the shared Docker network. Otherwise create it once:

```bash
docker network create collective 2>/dev/null || true
docker start collective-postgres || docker run -d \
	--name collective-postgres \
	--network collective \
	-e POSTGRES_DB=collective \
	-e POSTGRES_USER=collective \
	-e POSTGRES_PASSWORD=mysecretpassword \
	-v collective-postgres-data:/var/lib/postgresql/data \
	postgres:17
```

For Garage, build the local image once, then reuse the existing `collective-garage` container if it is already present. Otherwise create it and enable website access for the media bucket:

```bash
docker network create collective 2>/dev/null || true
docker build -t collective-garage-local ./_dev/docker/garage
docker start collective-garage || docker run -d \
	--name collective-garage \
	--network collective \
	-p 3900:3900 -p 3901:3901 -p 3902:3902 -p 3903:3903 \
	-e GARAGE_DEFAULT_ACCESS_KEY=GKcollectivegarage \
	-e GARAGE_DEFAULT_SECRET_KEY=collective-garage-secret-key \
	-e GARAGE_DEFAULT_BUCKET=collective-media \
	-v collective-garage-meta:/var/lib/garage/meta \
	-v collective-garage-data:/var/lib/garage/data \
	collective-garage-local /garage server --single-node --default-bucket
docker exec collective-garage /garage bucket website --allow collective-media
```

In one shell, build the CSS bundle in watch mode:

```bash
npm run dev
```

In another shell, apply migrations and start Django:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000.

The checked-in `.env` assumes the app is running from this dev container, which is already attached to the shared Docker network `collective`. That lets Django reach PostgreSQL at `collective-postgres` and Garage at `collective-garage` directly. If you run the app outside this dev container, replace those hosts with addresses reachable from your environment.
The checked-in `.env` only configures the Django app. The Garage bootstrap credentials belong to the Docker commands above, not to `.env`.

## Quality Checks

Run the project checks in this order:

```bash
python -m ruff format .
python -m ruff check --fix .
python -m mypy .
python manage.py check
python -m pytest --tb=short -q
```

If you rebuild `static/app.css`, run `python manage.py collectstatic --noinput` before relying on manifest-based static file checks.

## Docker

The repository includes a Dockerfile and entrypoint script for running the Django app in a container. The image expects PostgreSQL connection settings and serves the application with Gunicorn.

When running behind a TLS-terminating proxy or load balancer, production trusts `X-Forwarded-Proto` and `X-Forwarded-Host` by default so Django can detect the original HTTPS request correctly. Set `USE_X_FORWARDED_PROTO=false` or `USE_X_FORWARDED_HOST=false` if your deployment does not provide those headers safely.

### SMTP

Production uses Django's SMTP backend. Configure delivery with environment variables like these:

```bash
export EMAIL_HOST=smtp.example.com
export EMAIL_PORT=587
export EMAIL_HOST_USER=smtp-user
export EMAIL_HOST_PASSWORD=smtp-password
export EMAIL_USE_TLS=true
export DEFAULT_FROM_EMAIL="Collective <no-reply@example.com>"
```

Optional overrides:

- `EMAIL_USE_SSL` if your provider expects implicit TLS instead of STARTTLS
- `EMAIL_TIMEOUT` to change the SMTP socket timeout in seconds
- `SERVER_EMAIL` to override the sender used for server-generated error emails

### Object Storage Media

Image uploads can be stored in any S3-compatible object store, including Garage. Enable that backend with environment variables like these:

```bash
export USE_OBJECT_STORAGE=true
export OBJECT_STORAGE_ENDPOINT_URL=https://garage.example.com
export OBJECT_STORAGE_BUCKET_NAME=collective-media
export OBJECT_STORAGE_ACCESS_KEY_ID=garage-access-key
export OBJECT_STORAGE_SECRET_ACCESS_KEY=garage-secret-key
export OBJECT_STORAGE_REGION=garage
export OBJECT_STORAGE_ADDRESSING_STYLE=path
export MEDIA_STORAGE_PREFIX=media
```

Optional overrides:

- `MEDIA_CUSTOM_DOMAIN` if media should be served from a CDN or custom host
- `MEDIA_URL` if you want to override the generated object URL prefix
- `OBJECT_STORAGE_SIGNATURE_VERSION` if your S3-compatible provider requires a non-default signature

For local development, the repository includes `_dev/docker/garage/garage.toml` for a single-node Garage instance. The manual Docker commands above start PostgreSQL and Garage on the shared Docker network `collective`, create the `collective-media` bucket, enable website access for that bucket, and serve uploaded media from `http://collective-media.web.garage.localhost:3902/media/`.

## Project Layout

- `apps/spaces`: spaces, roles, invites, and participant management
- `apps/discussions`: discussion tree and discussion views
- `apps/posts`: posts and related actions
- `apps/opinions`: structured opinions on posts
- `apps/reactions`: reactions on posts
- `apps/subscriptions`: notifications and subscription flows
- `templates`: shared templates and allauth/user templates
- `assets/styles`: Tailwind source
- `static`: built frontend assets

## License

Released under the MIT License. See `LICENSE`.
