# Running the project locally

[English](LOCAL-SETUP.md) · [Español](LOCAL-SETUP.es.md)

Runbook: what runs, on which port, with which commands, and how to check it is up. Commands are in **bash / zsh**; the PowerShell and cmd variants, and how to install the tools on each system, are in the [README](README.md).

---

## 1. Stack

| Piece | Technology | Where it runs |
|---|---|---|
| Application | Django 5.2 LTS + Django REST Framework + JWT, on Python 3.12 or later | On the machine, inside `.venv` |
| Database | PostgreSQL 18 | In Docker, service `db` in `docker-compose.yml` |
| Dependencies | `uv` (`pyproject.toml` + `uv.lock`) | — |

There is no frontend: the only web interface is the Django admin panel.

---

## 2. Ports

| Service | Variable | Default | Used by |
|---|---|---|---|
| PostgreSQL | `DB_PORT` | `5432` | Django |
| Django | `APP_PORT` | `8000` | The browser and API clients |

Both ports are set **once**, in `.env`. Compose uses `DB_PORT` to publish the database and Django uses the same value to connect, so changing it needs nothing else.

---

## 3. Environment file

| File | Versioned? | Template | Read by |
|---|---|---|---|
| `.env` | No | `.env.example` | Docker Compose, automatically, and Django, from `core/settings.py` |

There is no need to load `.env` into the terminal: neither Compose nor Django needs it.

Create it:

```bash
cp .env.example .env
```

Then edit at least `COMPOSE_PROJECT_NAME`, `DB_CONTAINER_NAME`, `SECRET_KEY`, `DB_PASSWORD` and `ADMIN_PASSWORD`. Each variable is described in the [README](README.md#environment-variables).

To read one value **without printing the whole file** (it holds passwords):

```bash
grep '^APP_PORT=' .env | cut -d= -f2-
```

---

## 4. Start

Always from the project root, in this order:

```bash
docker compose up -d --wait
uv sync
uv run python manage.py migrate
uv run python manage.py create_admin_auto
uv run python manage.py runserver
```

| Command | What it does |
|---|---|
| `docker compose up -d --wait` | Starts PostgreSQL and waits until it accepts connections |
| `uv sync` | Creates `.venv` and installs the exact versions in `uv.lock` |
| `migrate` | Creates or updates the tables |
| `create_admin_auto` | Creates the test superuser; if it already exists, it does not duplicate it |
| `runserver` | Starts the server on the `APP_PORT` port |

`runserver` holds the terminal. To stop it: `Ctrl + C`.

---

## 5. Test user

| Field | Value |
|---|---|
| Email | `ADMIN_EMAIL` in `.env` |
| Password | `ADMIN_PASSWORD` in `.env` |
| Role | Superuser |

**The password is never written in any document.** To read it:

```bash
grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-
```

If the user does not exist, create it with `uv run python manage.py create_admin_auto`.

---

## 6. Check that everything is up

With the server running, in another terminal:

```bash
docker compose ps
uv run python manage.py migrate --check
APP_PORT=$(grep '^APP_PORT=' .env | cut -d= -f2-)
curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:${APP_PORT}/admin/login/"
```

| Check | Expected result |
|---|---|
| `docker compose ps` | The `db` service shows as `healthy` |
| `manage.py migrate --check` | Ends with no output: Django reaches the database and no migrations are pending |
| `curl` to the admin | `200` |

> To know whether Django reaches the database, use `migrate --check`. `manage.py check` opens no connection: it passes even with the database down or a wrong password.

---

## 7. If a port is taken

1. Find out what is using it:

   ```bash
   ss -ltnp | grep ':5432'
   ```

2. Decide between stopping that process or changing the project's port.
3. To change it, edit `DB_PORT` or `APP_PORT` in `.env`. There is no other file to touch.
4. If you changed `DB_PORT`, recreate the container so it publishes the new port:

   ```bash
   docker compose up -d --wait
   ```

No data is lost: it lives in the volume, not in the container.

---

## 8. Shut down

| Goal | Command |
|---|---|
| Stop the database **keeping the data** | `docker compose down` |
| Stop the database **and delete the data** | `docker compose down -v` |

---

## 9. Tests

They need the database running: Django creates and drops a temporary database to run them.

```bash
uv run python manage.py test
uv run black --check .
```

---

## 10. Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `required variable ... is missing a value` | `.env` or one of its variables is missing | Create `.env` or fill in the variable |
| `Conflict. The container name ... is already in use` | Another project uses the same `DB_CONTAINER_NAME` | Change it in `.env` |
| `port is already allocated` | `DB_PORT` is taken | Section 7 |
| `Error: That port is already in use.` | `APP_PORT` is taken | Section 7 |
| `password authentication failed for user` | The credentials changed after the database was created | PostgreSQL only applies them when it creates the volume: go back to the previous ones or recreate with `docker compose down -v` |
| `Conflict. The container name ... is already in use` after changing `COMPOSE_PROJECT_NAME` | With another project name, Compose tries to create a new container with the same name. The data volume would change too | Go back to the previous name. The conflict is what stops you from starting on an empty volume |

The full list, including the Windows and Docker Desktop cases, is in the [README](README.md#troubleshooting).
