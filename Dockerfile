# syntax=docker/dockerfile:1

# Builds the virtual environment and collects the static files.
FROM python:3.12.15-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Dependencies first: this layer is reused until pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY . .
# The settings refuse to load without these variables. The values only exist for this
# command: they don't end up in the image. ENVIRONMENT=prod writes the hashed files.
RUN ENVIRONMENT=prod \
    SECRET_KEY=build-only-not-a-secret-0123456789-abcdefghijklmnopqrstuvwxyz \
    ALLOWED_HOSTS=build.invalid \
    DB_NAME=build DB_USER=build DB_PASSWORD=build-only DB_HOST=build.invalid DB_PORT=5432 \
    FRONTEND_PASSWORD_RESET_URL="https://build.invalid/reset?uid={uid}&token={token}" \
    /app/.venv/bin/python manage.py collectstatic --noinput

FROM python:3.12.15-slim-bookworm AS runtime
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
# Owned by root and read-only for the app user: the process can't modify its own code.
COPY --from=build /app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "core.health_probe"]
# Migrations are not run here: with several replicas they would race each other. The app
# user has no home, where gunicorn would put its control socket, and nothing uses it.
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--no-control-socket"]
