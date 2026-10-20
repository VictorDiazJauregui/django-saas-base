# Despliegue

[English](DEPLOYMENT.md) · [Español](DEPLOYMENT.es.md)

Cómo correr la base en `staging` o `prod` con la imagen del `Dockerfile`: gunicorn sirve la app y whitenoise sirve los archivos estáticos del admin. Los settings que exige cada entorno están en [Producción](README.es.md#producción) del README.

Todos los comandos de esta guía son iguales en bash, zsh, PowerShell y cmd.

---

## 1. Construir la imagen

```bash
docker build -t myproject-api .
```

| Qué hace la imagen | Por qué |
|---|---|
| Instala las dependencias de `uv.lock`, sin el grupo de desarrollo | Las mismas versiones que en la CI |
| Corre `collectstatic` al construirse | El CSS y el JS del admin van dentro de la imagen, con hash y comprimidos |
| Corre con el usuario `app` (uid `10001`), con el código de solo lectura | Un proceso comprometido no puede modificar el código |
| Arranca `gunicorn core.wsgi:application` en el puerto `8000` | `runserver` es solo para desarrollo |
| Consulta `/api/v1/health/` cada 30 segundos (`HEALTHCHECK`) | Docker y Compose muestran el contenedor como `healthy` o `unhealthy` |
| No corre `migrate` al arrancar | Con varias réplicas, las migraciones competirían entre sí. Ver el paso 3 |

Ningún archivo `.env` entra en la imagen (`.dockerignore` los deja afuera): las variables las pone la plataforma cuando arranca el contenedor.

---

## 2. Variables

Pasale al contenedor las variables de `.env.example`, con estas ajustadas al entorno:

| Variable | Valor |
|---|---|
| `ENVIRONMENT` | `staging` o `prod` |
| `DEBUG` | `False` |
| `SECRET_KEY` | 50 caracteres aleatorios o más, nunca el valor de ejemplo |
| `ALLOWED_HOSTS` | El dominio de la API, como `api.example.com` |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Tu base de datos |
| `EMAIL_URL` | Un servidor SMTP: sin él, los emails de reset solo llegan al log |
| `FRONTEND_PASSWORD_RESET_URL` | La página del frontend con `{uid}` y `{token}` |
| `USE_X_FORWARDED_PROTO`, `TRUSTED_PROXY_COUNT` | `True` y `1` detrás de un proxy o load balancer que termina TLS |
| `LOG_FORMAT` | `json` si un colector de logs lee la salida. Ver [Logs](README.es.md#logs) |
| `WEB_CONCURRENCY` | Workers de gunicorn. Empezá con `2` por núcleo de CPU más `1` |

`docker run --env-file` no saca las comillas: en ese archivo escribí los valores sin comillas, también `FRONTEND_PASSWORD_RESET_URL`, aunque tenga `&` (las comillas de `.env.example` son para que la línea se pueda cargar en una shell).

Antes del primer despliegue, revisá los settings con tus variables de producción:

```bash
docker run --rm --env-file .env.prod myproject-api python manage.py check --deploy --fail-level WARNING
```

---

## 3. En cada despliegue

Corré estos tres comandos antes de que la versión nueva reciba tráfico, una sola vez, no en cada réplica:

```bash
docker run --rm --env-file .env.prod myproject-api python manage.py migrate
docker run --rm --env-file .env.prod myproject-api python manage.py sync_roles
docker run --rm --env-file .env.prod myproject-api python manage.py create_admin_auto --update-password
```

| Comando | Qué hace |
|---|---|
| `migrate` | Aplica las migraciones nuevas |
| `sync_roles` | Deja los grupos iguales a `core/roles.py`. Ver [Roles](README.es.md#roles) |
| `create_admin_auto --update-password` | Crea el superusuario de `ADMIN_EMAIL`, o le pone `ADMIN_PASSWORD`. Ver [El superusuario](README.es.md#el-superusuario) |

La mayoría de las plataformas tiene un lugar para esto: un release command (Heroku, Render, Railway), un `Job` de Kubernetes o un paso del pipeline.

---

## 4. Arrancar la app

```bash
docker run -d --env-file .env.prod -p 8000:8000 myproject-api
```

Poné adelante un proxy o un load balancer con TLS. Apuntá su chequeo de salud a `/api/v1/health/`: responde por HTTP incluso en `prod`, pero el header `Host` tiene que ser uno de `ALLOWED_HOSTS`. Ver [Health check](README.es.md#health-check).

Para probar la imagen en tu máquina, contra la base de Compose:

```bash
docker compose --profile app up -d --build
```

El servicio `app` lee el mismo `.env` (con `APP_ENV_FILE` usa otro archivo) y publica `APP_PORT`, el mismo puerto que `runserver`: corré uno o el otro.

### Worker de webhooks

Con `WEBHOOKS_ENABLED=True`, corré `deliver_webhooks` como un segundo proceso de la misma imagen, al lado de la app, con las mismas variables:

```bash
docker run -d --env-file .env.prod myproject-api python manage.py deliver_webhooks
```

Uno alcanza para la mayoría de los proyectos; sumá más si las entregas se acumulan. Si se corta en medio de un lote, esas entregas se vuelven a mandar cuando vence su reserva (el timeout por el tamaño del lote, unos minutos como mucho), así que los receptores tienen que ignorar un `Webhook-Id` que ya procesaron. Ver [Webhooks](README.es.md#webhooks).

---

## 5. Tareas programadas

Dos comandos limpian tablas que solo crecen. Corrélos una vez por día:

| Comando | Qué borra |
|---|---|
| `python manage.py purge_audit_logs --older-than 90 --no-input` | Los registros de auditoría de más de 90 días. Ver [Purga de registros viejos](README.es.md#purga-de-registros-viejos) |
| `python manage.py flushexpiredtokens` | Los refresh tokens ya vencidos, de las tablas de la blacklist |

Con cron, en un servidor con Docker:

```text
0 3 * * * docker run --rm --env-file /srv/myproject/.env.prod myproject-api python manage.py purge_audit_logs --older-than 90 --no-input
30 3 * * * docker run --rm --env-file /srv/myproject/.env.prod myproject-api python manage.py flushexpiredtokens
```

Con Kubernetes, un `CronJob` por comando:

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
