# Deployment

[English](DEPLOYMENT.md) · [Español](DEPLOYMENT.es.md)

How to run the base in `staging` or `prod` with the image of the `Dockerfile`: gunicorn serves the app and whitenoise serves the admin's static files. The settings each environment requires are in [Production](README.md#production) of the README.

Every command here is the same in bash, zsh, PowerShell and cmd.

---

## 1. Build the image

```bash
docker build -t myproject-api .
```

| What the image does | Why |
|---|---|
| Installs the dependencies of `uv.lock`, without the development group | The same versions as in the CI |
| Runs `collectstatic` while building | The admin's CSS and JS ship inside the image, hashed and compressed |
| Runs as the `app` user (uid `10001`), with the code read-only | A compromised process can't modify the code |
| Starts `gunicorn core.wsgi:application` on port `8000` | `runserver` is for development only |
| Checks `/api/v1/health/` every 30 seconds (`HEALTHCHECK`) | Docker and Compose report the container as `healthy` or `unhealthy` |
| Doesn't run `migrate` on start | With several replicas, the migrations would race each other. See step 3 |

No `.env` file gets into the image (`.dockerignore` keeps them out): the variables come from the platform when the container starts.

---

## 2. Variables

Give the container the variables of `.env.example`, with these ones set for the environment:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `staging` or `prod` |
| `DEBUG` | `False` |
| `SECRET_KEY` | 50 random characters or more, never the example value |
| `ALLOWED_HOSTS` | The API domain, such as `api.example.com` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Your database |
| `EMAIL_URL` | An SMTP server: without it the reset emails only reach the log |
| `FRONTEND_PASSWORD_RESET_URL` | The frontend page with `{uid}` and `{token}` |
| `USE_X_FORWARDED_PROTO`, `TRUSTED_PROXY_COUNT` | `True` and `1` behind a proxy or load balancer that terminates TLS |
| `LOG_FORMAT` | `json` if a log collector reads the output. See [Logging](README.md#logging) |
| `WEB_CONCURRENCY` | gunicorn workers. Start with `2` per CPU core plus `1` |

`docker run --env-file` keeps quotes as part of the value: write the values without them in that file, `FRONTEND_PASSWORD_RESET_URL` included, even with its `&` (the quotes in `.env.example` are there so the line can be loaded in a shell).

Before the first deploy, check the settings with your production variables loaded:

```bash
docker run --rm --env-file .env.prod myproject-api python manage.py check --deploy --fail-level WARNING
```

---

## 3. Every deploy

Run these three commands before the new version takes traffic, once, not on every replica:

```bash
docker run --rm --env-file .env.prod myproject-api python manage.py migrate
docker run --rm --env-file .env.prod myproject-api python manage.py sync_roles
docker run --rm --env-file .env.prod myproject-api python manage.py create_admin_auto --update-password
```

| Command | What it does |
|---|---|
| `migrate` | Applies the new migrations |
| `sync_roles` | Makes the groups match `core/roles.py`. See [Roles](README.md#roles) |
| `create_admin_auto --update-password` | Creates the superuser of `ADMIN_EMAIL`, or sets `ADMIN_PASSWORD` on it. See [The superuser](README.md#the-superuser) |

Most platforms have a place for this: a release command (Heroku, Render, Railway), a Kubernetes `Job`, or a step of the pipeline.

---

## 4. Start the app

```bash
docker run -d --env-file .env.prod -p 8000:8000 myproject-api
```

Put a proxy or a load balancer with TLS in front. Point its health check at `/api/v1/health/`: it answers over plain HTTP even in `prod`, but the `Host` header has to be one of `ALLOWED_HOSTS`. See [Health check](README.md#health-check).

To try the image on your machine, against the database of Compose:

```bash
docker compose --profile app up -d --build
```

The `app` service reads the same `.env` (set `APP_ENV_FILE` to use another file) and publishes `APP_PORT`, the same port as `runserver`: run one or the other.

### Webhook worker

With `WEBHOOKS_ENABLED=True`, run `deliver_webhooks` as a second process of the same image, next to the app, with the same variables:

```bash
docker run -d --env-file .env.prod myproject-api python manage.py deliver_webhooks
```

One is enough for most projects; add more if the deliveries pile up. If it stops in the middle of a batch, those deliveries are sent again once their lease ends (the timeout times the batch size, a few minutes at most), so receivers should ignore a `Webhook-Id` they already processed. See [Webhooks](README.md#webhooks).

---

## 5. Scheduled tasks

Two commands clean tables that only grow. Run them once a day:

| Command | What it deletes |
|---|---|
| `python manage.py purge_audit_logs --older-than 90 --no-input` | Audit log records older than 90 days. See [Purging old records](README.md#purging-old-records) |
| `python manage.py flushexpiredtokens` | Refresh tokens already expired, from the blacklist tables |

With cron on a server that has Docker:

```text
0 3 * * * docker run --rm --env-file /srv/myproject/.env.prod myproject-api python manage.py purge_audit_logs --older-than 90 --no-input
30 3 * * * docker run --rm --env-file /srv/myproject/.env.prod myproject-api python manage.py flushexpiredtokens
```

With Kubernetes, a `CronJob` per command:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: purge-audit-logs
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: purge-audit-logs
              image: myproject-api
              command: ["python", "manage.py", "purge_audit_logs", "--older-than", "90", "--no-input"]
              envFrom:
                - secretRef:
                    name: myproject-env
```
