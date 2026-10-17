# SaaS Base · Django + PostgreSQL

[English](README.md) · [Español](README.es.md)

Backend base to start a project from: Django and Django REST Framework run on your machine, and PostgreSQL runs in Docker. Everything that identifies a project (names, credentials and ports) lives in a `.env` file, so you can clone the base as many times as you want on the same machine without one project stepping on another.

It works on **Linux**, **WSL** and **Windows** (PowerShell and cmd).

## Contents

- [What it includes](#what-it-includes)
- [Requirements](#requirements)
- [Getting started](#getting-started)
- [Setup by operating system](#setup-by-operating-system)
- [Environment variables](#environment-variables)
- [Production](#production)
- [Several projects on the same machine](#several-projects-on-the-same-machine)
- [API](#api)
- [Email](#email)
- [Audit log](#audit-log)
- [Dependencies](#dependencies)
- [Tests and formatting](#tests-and-formatting)
- [Troubleshooting](#troubleshooting)
- [Upgrading from PostgreSQL 15](#upgrading-from-postgresql-15)
- [Renaming the project](#renaming-the-project)
- [Internationalization](#internationalization)
- [Contributing](#contributing)
- [License](#license)

---

## What it includes

- **Django 5.2 LTS** and **Django REST Framework**, with **JWT** authentication and refresh tokens that rotate on every use.
- **Login protection:** request limits per IP and an account lockout after repeated failed logins, in the API and the admin.
- **PostgreSQL 18** in Docker Compose, configured through variables.
- **Custom user** that logs in with an email and has a random UUID as primary key.
- **Account endpoints:** logout, the user's own profile in `/me/`, password change and reset by email, optional email verification, and every session closed when the password changes. Registration and reset don't reveal which emails have an account.
- **Email** through any SMTP provider, configured with one URL; printed to the console while developing.
- **Audit log:** every request that changes data is recorded, with sensitive values redacted.
- **OpenAPI schema and Swagger UI** for the frontend, open while developing and staff only in production.
- **Roles** declared in code and applied as Django groups with `sync_roles`.
- **Admin panel** to manage users and browse the audit log.
- **Internationalization** ready for English and Spanish.
- **Automated tests** for the API, the audit log and the admin.

---

## Requirements

| Tool | Version | Used for |
|---|---|---|
| Python | 3.12 or later (recommended: 3.12) | Running Django |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Current | Creating the environment and installing dependencies (recommended). `pip` works too |
| Docker with Compose v2 | Current | Running PostgreSQL |
| Git | Current | Cloning the repository |

How to install each one on your system: see [Setup by operating system](#setup-by-operating-system).

> With `uv` you don't need to install Python yourself: if it can't find the version set in `.python-version`, it downloads it.

---

## Getting started

Six steps. When a command differs between terminals, all three variants are shown. For a short runbook with the ports, the health checks and the common errors, see [LOCAL-SETUP.md](LOCAL-SETUP.md).

### 1. Clone

```bash
git clone <REPOSITORY_URL> my-project
cd my-project
```

### 2. Create your `.env` file

The repository only ships `.env.example`. Your `.env` is a copy that is not versioned.

**bash / zsh (Linux, WSL)**

```bash
cp .env.example .env
```

**PowerShell**

```powershell
Copy-Item .env.example .env
```

**cmd**

```bat
copy .env.example .env
```

Open `.env` in your editor and change at least:

| Variable | What to set |
|---|---|
| `COMPOSE_PROJECT_NAME` | A unique, lowercase name for this project (for example `shop`) |
| `DB_CONTAINER_NAME` | A unique name for the container (for example `shop_db`) |
| `DB_NAME`, `DB_USER` | The database name and its user |
| `DB_PASSWORD`, `ADMIN_PASSWORD` | Your own passwords. `ADMIN_PASSWORD` has to pass the [password policy](#api) |
| `SECRET_KEY` | A generated key (see below) |
| `DB_PORT`, `APP_PORT` | Keep `5432` and `8000` unless they are already taken |

To generate a key or a strong password, the same command works in any terminal:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> On Windows, if `python` is not recognized, use `py` instead. With `uv`, prefix it with `uv run`.

> The generated value doesn't always include a symbol, which the password policy asks for. If `create_admin_auto` rejects `ADMIN_PASSWORD`, it says which rule failed: add a `-` or a `_` and run it again.

> **Avoid `$` and `#` in the values.** Docker Compose reads `$` as a reference to another variable and a `#` after a space as a comment, and cuts the value there; Django reads the whole value. The two end up with different values. The command above only produces safe characters.

### 3. Start the database

```bash
docker compose up -d --wait
```

`--wait` waits until PostgreSQL accepts connections.

**How your variables reach Docker Compose.** Compose automatically reads the `.env` file next to `docker-compose.yml` and replaces every `${VARIABLE}` in the file. There is nothing to export and no option to pass. To see exactly what it understood:

```bash
docker compose config
```

If a variable is missing, Compose stops and names it:

```text
required variable COMPOSE_PROJECT_NAME is missing a value: Set COMPOSE_PROJECT_NAME in the .env file
```

If you want Compose to use a file with another name, pass it on every command:

```bash
docker compose --env-file .env.other up -d --wait
```

Keep in mind that **Django always reads `.env`**, so that alternative file only affects Compose.

Variables already set in your terminal take precedence over the ones in `.env`, for both Compose and Django.

### 4. Create the Python environment

Pick **one** of the two options.

#### Option A · uv (recommended)

Same command in every terminal, and nothing to activate:

```bash
uv sync
```

It creates the `.venv` folder and installs the exact versions pinned in `uv.lock`. To install only what production needs: `uv sync --no-dev`.

From here on, prefix every Python command with `uv run`.

#### Option B · pip + venv

**bash / zsh (Linux, WSL)**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

**PowerShell**

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

The `Set-ExecutionPolicy` line is needed because PowerShell does not allow running scripts by default, and activating the environment runs one. With `-Scope Process` the permission only applies to that window.

**cmd**

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
```

If you have another Python version (3.13, for example), replace `3.12` with yours. To install only what production needs, use `requirements.txt`.

### 5. Prepare the database and start

With **uv**:

```bash
uv run python manage.py migrate
uv run python manage.py create_admin_auto
uv run python manage.py runserver
```

With **pip + venv** (environment activated):

```bash
python manage.py migrate
python manage.py create_admin_auto
python manage.py runserver
```

- `migrate` creates the tables.
- `create_admin_auto` creates the superuser from `ADMIN_EMAIL` and `ADMIN_PASSWORD`. Running it again does not duplicate it. See [The superuser](#the-superuser).
- `runserver` uses the port in `APP_PORT`. For a one-off port, pass it: `runserver 9000`.

### 6. Check it works

With the default values:

- Admin panel: <http://localhost:8000/admin/>
- Authentication API: <http://localhost:8000/api/v1/auth/>
- API documentation: <http://localhost:8000/api/docs/>

To try the login from the terminal:

**bash / zsh**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "YOUR_PASSWORD"}'
```

**PowerShell**

```powershell
$body = @{ email = "admin@example.com"; password = "YOUR_PASSWORD" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login/ -ContentType "application/json" -Body $body
```

**cmd**

```bat
curl -X POST http://localhost:8000/api/v1/auth/login/ -H "Content-Type: application/json" -d "{\"email\": \"admin@example.com\", \"password\": \"YOUR_PASSWORD\"}"
```

The response has two tokens: `access` and `refresh`.

### Shutting down

- The server: `Ctrl + C`.
- The database, **keeping the data**: `docker compose down`
- The database, **deleting the data**: `docker compose down -v`

---

## Setup by operating system

### Linux

1. **Docker Engine and Compose:** [install on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) (the same page links to other distributions) and the [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) to use Docker without `sudo`.
2. **uv:**

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Close and reopen the terminal so it is on the `PATH`.
3. Follow [Getting started](#getting-started) with the **bash / zsh** variants.

If you prefer to manage Python versions yourself, [pyenv](https://github.com/pyenv/pyenv) picks up the project's `.python-version` file.

### WSL

WSL is Linux inside Windows: once installed, everything works as on Linux.

1. **Install WSL** from PowerShell as administrator and restart ([official guide](https://learn.microsoft.com/en-us/windows/wsl/install)):

   ```powershell
   wsl --install
   ```

2. **Clone inside the Linux file system** (for example in `~/projects`), not under `/mnt/c/...`. Working on the Windows disk from WSL is much slower and mixes line endings. More in [Working across file systems](https://learn.microsoft.com/en-us/windows/wsl/filesystems).
3. **Docker**, in one of two ways:
   - **Docker Desktop** on Windows with the WSL integration turned on (*Settings → Resources → WSL integration*). See [Docker Desktop WSL 2 backend](https://docs.docker.com/desktop/features/wsl/).
   - **Docker Engine** installed inside the distribution, as on Linux.

   Use only one: having both at once causes conflicts.
4. Follow [Getting started](#getting-started) with the **bash / zsh** variants.

A server started in WSL opens from the Windows browser at `http://localhost:8000`. If it does not respond, check [Accessing network applications with WSL](https://learn.microsoft.com/en-us/windows/wsl/networking).

### Windows

1. **Git:** [download](https://git-scm.com/downloads/win), or `winget install --id Git.Git -e`.
2. **Docker Desktop:** [install](https://docs.docker.com/desktop/setup/install/windows-install/), or `winget install --id Docker.DockerDesktop -e`. Keep the WSL 2 option checked during the installation.
3. **uv** (recommended), from PowerShell:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   or `winget install --id=astral-sh.uv -e`. Close and reopen the terminal.
4. **Python**, only if you will use `pip` instead of `uv`: [download](https://www.python.org/downloads/windows/), or `winget install --id Python.Python.3.12 -e`.

#### PowerShell

Follow [Getting started](#getting-started) with the **PowerShell** variants. With `uv` you won't need to change the execution policy, because `uv run` does not activate any script.

#### cmd

Follow [Getting started](#getting-started) with the **cmd** variants. cmd does not have PowerShell's script restriction.

#### Docker Desktop

- **It has to be running** before you run `docker compose`. If it is not, Docker commands fail to connect.
- The **Containers** tab shows your project under the name you set in `COMPOSE_PROJECT_NAME` and, inside it, the `DB_CONTAINER_NAME` container. From there you can stop it, start it and read its logs.
- **Volumes** shows the data volume, named `<COMPOSE_PROJECT_NAME>_postgres_data`.
- If the app does not start or shows virtualization errors, see [Troubleshooting](#troubleshooting).

Official guides: [Docker Desktop tour](https://docs.docker.com/desktop/use-desktop/) · [WSL 2 best practices](https://docs.docker.com/desktop/features/wsl/best-practices/) · [permission requirements on Windows](https://docs.docker.com/desktop/setup/install/windows-permission-requirements/).

---

## Environment variables

| Variable | Read by | Used for | Example value |
|---|---|---|---|
| `ENVIRONMENT` | Django | `local`, `ci`, `staging` or `prod`. Any other value stops Django from starting. See [Production](#production) | `local` |
| `SECRET_KEY` | Django | The project's cryptographic key | *(generated)* |
| `DEBUG` | Django | Debug mode. Only allowed in `local` and `ci` | `True` |
| `ALLOWED_HOSTS` | Django | Domains that serve the project, comma separated, without scheme or port. Required in `staging` and `prod`, where `*` is rejected | `localhost,127.0.0.1` |
| `APP_PORT` | Django | Development server port | `8000` |
| `SECURE_HSTS_SECONDS` | Django | How long browsers remember to use HTTPS only (`staging` and `prod`) | `3600` |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Django | Extends HSTS to every subdomain | `False` |
| `SECURE_HSTS_PRELOAD` | Django | Allows submitting the domain to the browsers' HSTS preload list | `False` |
| `USE_X_FORWARDED_PROTO` | Django | Trusts the `X-Forwarded-Proto` header of the proxy that terminates TLS | `False` |
| `CSRF_TRUSTED_ORIGINS` | Django | Extra origins allowed to send forms, comma separated, with scheme | *(empty)* |
| `THROTTLE_ANON_RATE` | Django | Limit for anonymous requests to any endpoint. Empty: no limit | *(empty)* |
| `THROTTLE_USER_RATE` | Django | Limit for authenticated requests to any endpoint. Empty: no limit | *(empty)* |
| `THROTTLE_LOGIN_RATE` | Django | Limit for `POST /api/v1/auth/login/` | `10/10m` |
| `THROTTLE_REGISTER_RATE` | Django | Limit for `POST /api/v1/auth/register/` | `5/h` |
| `THROTTLE_VERIFY_EMAIL_RATE` | Django | Limit for `verify-email/` and `verify-email/resend/` | `5/h` |
| `THROTTLE_PASSWORD_RATE` | Django | Limit for the password change and the password reset, and for the endpoints you add with `throttle_scope = "password"` | `5/h` |
| `TRUSTED_PROXY_COUNT` | Django | Proxies in front of Django that append to `X-Forwarded-For`. `0` ignores the header. Used by the rate limits and the audit log. A negative number stops Django from starting | `0` |
| `CACHE_URL` | Django | Cache where the limits are counted | `locmemcache://` |
| `AUDIT_EXTRA_SENSITIVE_KEYS` | Django | Extra keys the audit log redacts, comma separated. See [Audit log](#audit-log) | *(empty)* |
| `AUDIT_PAYLOAD_MAX_BYTES` | Django | Largest body the audit log stores, in bytes. A larger one is stored as a marker with its size. `0` means no limit. A negative number or text stops Django from starting | `65536` |
| `JWT_ACCESS_MINUTES` | Django | Lifetime of the `access` token, in minutes. See [Tokens](#tokens) | `5` |
| `JWT_REFRESH_DAYS` | Django | Lifetime of the `refresh` token, in days | `1` |
| `JWT_SIGNING_KEY` | Django | Key that signs the tokens. Empty: `SECRET_KEY` | *(empty)* |
| `AXES_FAILURE_LIMIT` | Django | Failed logins that lock an account. See [Account lockout](#account-lockout) | `5` |
| `AXES_COOLOFF_MINUTES` | Django | Minutes the lockout lasts | `15` |
| `AXES_LOCKOUT_PARAMETERS` | Django | What is locked: `username`, `ip_address`, `user_agent`, joined with `+` | `username+ip_address` |
| `EMAIL_URL` | Django | Where emails go, as a URL. Empty: printed to the console. See [Email](#email) | *(empty)* |
| `DEFAULT_FROM_EMAIL` | Django | Sender of the emails the project sends | `webmaster@localhost` |
| `ALLOW_PUBLIC_REGISTRATION` | Django | `False` closes `POST /api/v1/auth/register/` with `403`. See [Public registration](#public-registration) | `True` |
| `FRONTEND_PASSWORD_RESET_URL` | Django | Frontend page the reset email links to, with `{uid}` and `{token}`. Required: without it, or without a marker, Django doesn't start. See [Password reset](#password-reset) | `'http://localhost:3000/reset-password?uid={uid}&token={token}'` |
| `PASSWORD_RESET_TIMEOUT_MINUTES` | Django | Minutes a reset link works | `60` |
| `REQUIRE_EMAIL_VERIFICATION` | Django | `True`: a public registration logs in only after following the link of its email. See [Email verification](#email-verification) | `False` |
| `FRONTEND_EMAIL_VERIFICATION_URL` | Django | Frontend page the verification email links to, with `{uid}` and `{token}`. Required only with `REQUIRE_EMAIL_VERIFICATION=True` | `'http://localhost:3000/verify-email?uid={uid}&token={token}'` |
| `EMAIL_VERIFICATION_TIMEOUT_HOURS` | Django | Hours a verification link works | `24` |
| `API_PAGE_SIZE` | Django | Items per page of a list. See [Pagination](#pagination) | `20` |
| `API_MAX_PAGE_SIZE` | Django | Largest `?page_size=` a client can ask for. `API_PAGE_SIZE` can't be larger | `100` |
| `API_DOCS_ENABLED` | Django | Who sees `/api/schema/` and `/api/docs/`. Empty: anyone in `local` and `ci`, only staff in `staging` and `prod`. See [API documentation](#api-documentation) | *(empty)* |
| `CORS_ALLOWED_ORIGINS` | Django | Origins allowed to call `/api/` from a browser, comma separated, with scheme and port. Empty: none. See [CORS](#cors) | *(empty)* |
| `COMPOSE_PROJECT_NAME` | Compose | Project name. The volume and the network are named after it | `saas` |
| `DB_CONTAINER_NAME` | Compose | PostgreSQL container name | `saas_db` |
| `DB_NAME` | Both | Database name | `saas_db` |
| `DB_USER` | Both | Database user | `saas_user` |
| `DB_PASSWORD` | Both | Database password | *(your own)* |
| `DB_HOST` | Django | Where the database is | `localhost` |
| `DB_PORT` | Both | Database port on your machine | `5432` |
| `ADMIN_EMAIL` | Django | Email of the superuser created by `create_admin_auto` | `admin@example.com` |
| `ADMIN_PASSWORD` | Django | That superuser's password. It has to pass the password policy | *(your own)* |
| `PASSWORD_MIN_LENGTH` | Django | Minimum password length | `8` |
| `PASSWORD_REQUIRE_UPPERCASE` | Django | Passwords need an uppercase letter (`A-Z`) | `True` |
| `PASSWORD_REQUIRE_LOWERCASE` | Django | Passwords need a lowercase letter (`a-z`) | `True` |
| `PASSWORD_REQUIRE_DIGIT` | Django | Passwords need a digit (`0-9`) | `True` |
| `PASSWORD_REQUIRE_SYMBOL` | Django | Passwords need a symbol (ASCII punctuation, such as `!`, `#`, `-`, `_`) | `True` |

Two details worth knowing:

- **PostgreSQL only applies `DB_NAME`, `DB_USER` and `DB_PASSWORD` the first time**, when it creates the volume. If you change them later, the existing database does not pick them up: see [Troubleshooting](#troubleshooting).
- **The database port is published on `127.0.0.1` only**: reachable from your machine, not from other machines on the network.

---

## Production

`ENVIRONMENT` decides how strict the settings are. Django refuses to start when a value doesn't fit the environment, so a mistake shows up at deploy time and not in production traffic.

| | `local`, `ci` | `staging`, `prod` |
|---|---|---|
| `DEBUG=True` | Allowed | Django doesn't start |
| `ALLOWED_HOSTS` | Optional; defaults to `*` with `DEBUG` and `localhost` without it | Required, without `*` |
| HTTP requests | Served | Redirected to HTTPS |
| Session and CSRF cookies | Sent over HTTP | `Secure`: HTTPS only |
| HSTS | Off | `SECURE_HSTS_SECONDS`, `3600` by default |

Django also checks the values copied from `.env.example`. If `SECRET_KEY`, `DB_PASSWORD` or `ADMIN_PASSWORD` still have the example value, `runserver`, `migrate` and `check` report it: a warning in `local` and `ci` (`core.W001` to `core.W003`) and an error that stops the command in `staging` and `prod` (`core.E001` to `core.E003`). A short `SECRET_KEY` is reported by Django itself (`security.W009`). In `staging` and `prod`, an `EMAIL_URL` that doesn't deliver emails (empty, console, file or memory) gets the warning `core.W004`: the password reset would print its links to the log and nobody would get them.

Before deploying, run the same check the CI runs, with your production `.env` loaded:

```bash
python manage.py check --deploy --fail-level WARNING
```

It ends with `System check identified no issues (2 silenced)`. The two silenced warnings are the HSTS ones explained below.

Things to know before going live:

- **Behind a proxy or load balancer that terminates TLS**, set `USE_X_FORWARDED_PROTO=True` and make sure the proxy overwrites `X-Forwarded-Proto`. Without it Django sees plain HTTP and redirects forever.
- **Raise `SECURE_HSTS_SECONDS` to `31536000`** (one year) once every page works over HTTPS. Browsers keep the value: lowering it later only helps new visitors.
- **`SECURE_HSTS_PRELOAD=True` is close to irreversible.** Browsers ship the preload list, and leaving it takes months. That's why it's off and its `check --deploy` warning is silenced while it stays off; the same applies to `SECURE_HSTS_INCLUDE_SUBDOMAINS`.
- **`CSRF_TRUSTED_ORIGINS`** is only needed when the admin or another form is posted from a different origin than the one serving it. A match-all origin such as `https://*` is rejected in `staging` and `prod`.
- **On every deploy, run `migrate` and then `sync_roles`**, so the groups match `core/roles.py`. See [Roles](#roles).
- **The API docs are staff only** in `staging` and `prod`. See [API documentation](#api-documentation).

### The superuser

`create_admin_auto` is meant for automated deployments: it reads `ADMIN_EMAIL` and `ADMIN_PASSWORD` and never asks anything. To create a superuser by hand, use Django's own command, which also asks for the email:

```bash
python manage.py createsuperuser
```

What `create_admin_auto` does depends on the email:

| `ADMIN_EMAIL` | Result | Exit code |
|---|---|---|
| Doesn't exist | Creates the superuser, if `ADMIN_PASSWORD` passes the password policy | `0`, or `1` with the rules it breaks |
| Belongs to a superuser | Nothing: the password is not checked or changed | `0` |
| Belongs to a regular user | Nothing: it doesn't promote users. Promote it from the admin or use another email | `1` |

The email is matched in any case. With `--update-password`, an existing superuser also gets `ADMIN_PASSWORD`, and a missing one is created, so a deployment can always run:

```bash
python manage.py create_admin_auto --update-password
```

The password never appears in the output, not even when it's rejected.

---

## Several projects on the same machine

Each clone is an independent project as long as these values differ in its `.env`:

| Variable | Project A | Project B |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `shop` | `blog` |
| `DB_CONTAINER_NAME` | `shop_db` | `blog_db` |
| `DB_PORT` | `5432` | `5433` |
| `APP_PORT` | `8000` | `8001` |

With that, each one has its own container, data volume, network and ports, and they can run at the same time.

`DB_NAME` and `DB_USER` can repeat, because each database lives in its own container; different names still avoid confusion.

---

## API

| Method | Path | What it does | Body |
|---|---|---|---|
| `POST` | `/api/v1/auth/register/` | Registers a user | `email`, `password`, `password2`, `first_name`, `last_name` |
| `POST` | `/api/v1/auth/login/` | Returns the `access` and `refresh` tokens | `email`, `password` |
| `POST` | `/api/v1/auth/login/refresh/` | Returns a new `access` and a new `refresh`; the `refresh` sent stops working. See [Tokens](#tokens) | `refresh` |
| `POST` | `/api/v1/auth/logout/` | Blacklists the `refresh` sent. See [Logout](#logout) | `refresh` |
| `GET` | `/api/v1/auth/me/` | Returns the profile of the authenticated user. See [Profile](#profile) | — |
| `PATCH` | `/api/v1/auth/me/` | Updates `first_name` and `last_name` | `first_name`, `last_name` (both optional) |
| `POST` | `/api/v1/auth/password/change/` | Changes the password of the authenticated user. See [Change password](#change-password) | `current_password`, `new_password`, `new_password2` |
| `POST` | `/api/v1/auth/password/reset/` | Emails a link to choose a new password. See [Password reset](#password-reset) | `email` |
| `POST` | `/api/v1/auth/password/reset/confirm/` | Sets the new password with the `uid` and `token` of the link | `uid`, `token`, `new_password`, `new_password2` |
| `POST` | `/api/v1/auth/verify-email/` | Verifies the email of an account with the `uid` and `token` of the link. See [Email verification](#email-verification) | `uid`, `token` |
| `POST` | `/api/v1/auth/verify-email/resend/` | Emails a new verification link | `email` |

Routes you add require authentication by default: send the token in the `Authorization: Bearer <access>` header.

### API documentation

| Route | What it serves |
|---|---|
| `GET /api/schema/` | OpenAPI 3 schema of the API, in YAML. `?format=json` returns JSON |
| `GET /api/docs/` | Swagger UI: every endpoint with its body, its answers and examples, and an **Authorize** button to try them with a token |

Who sees them depends on `API_DOCS_ENABLED`:

| `API_DOCS_ENABLED` | Who sees the docs |
|---|---|
| Empty (default) | Anyone in `local` and `ci`; only staff in `staging` and `prod` |
| `True` | Anyone, in every environment |
| `False` | Only active staff users |

- Staff users get in with the admin session (log in at `/admin/` and open `/api/docs/` in the same browser) or with a token.
- Anyone else gets the same `404` as a route that doesn't exist.
- `True` in `staging` or `prod` publishes the docs of your API. That's a choice for public APIs, not a default.
- Swagger UI is served by the backend itself (`drf-spectacular-sidecar`), with no CDN. In `staging` and `prod` it needs the static files served, like the admin.

A frontend can generate its types and its client from the schema, for example with [openapi-typescript](https://openapi-ts.dev/):

```bash
npx openapi-typescript http://localhost:8000/api/schema/ -o src/api/schema.d.ts
```

The schema comes from [drf-spectacular](https://drf-spectacular.readthedocs.io/). A view with a `serializer_class` gets documented on its own; what the code can't tell (a `204` without body, the errors) goes in `extend_schema`. Errors use the shape of [Errors](#errors), documented with `core.api_schema.error_responses`, which takes the error codes the view can answer:

```python
from drf_spectacular.utils import extend_schema

from core.api_schema import RETRY_AFTER_HEADER, error_responses


@extend_schema(
    parameters=[RETRY_AFTER_HEADER],  # only if the view has a rate limit
    responses={204: None, **error_responses("invalid", "not_authenticated", "throttled")},
)
class ArchiveInvoiceView(GenericAPIView):
    ...
```

The CI runs `python manage.py spectacular --validate --fail-on-warn` and fails if the schema has a warning, for example a view that drf-spectacular can't describe.

The API answers JSON. Only with `DEBUG=True` does a route opened in the browser show DRF's browsable API; in `staging` and `prod` the browser gets JSON too.

The `user_id` claim of both tokens is the user's UUID as a string, for example
`"user_id": "8f419aff-49ec-4f42-b9b6-0d8faa76199c"`.

Emails are stored in lowercase and without surrounding spaces, and they are unique regardless of case: registering `Jane@Example.com` when `jane@example.com` exists creates nothing (see [Email verification](#email-verification)). Login accepts the email in any case.

The password policy applies to the API and the admin. By default a password needs 8 characters, an uppercase letter, a lowercase letter, a digit and a symbol, and it can't be too similar to the email or the name. Only ASCII counts: `ñ` or `€` are allowed but don't meet any rule. Each rule can be changed with the `PASSWORD_*` variables. A registration that breaks several rules gets every message in `fields.password`:

```json
{"code": "invalid", "detail": "Invalid input.", "fields": {"password": ["This password is too short. It must contain at least 8 characters.", "This password must contain at least one symbol, such as ! ? # - _."]}}
```

### Errors

Every error under `/api/` has the same shape, whatever its status:

```json
{"code": "invalid", "detail": "Invalid input.", "fields": {"email": ["Enter a valid email address."], "password": ["This password is too common."]}}
```

| Key | Content |
|---|---|
| `code` | Fixed identifier, in English, for the frontend to branch on. It doesn't change with the language |
| `detail` | Message for a person, in the request's language (`Accept-Language`) |
| `fields` | Messages per field, only for validation errors (`400` with `code` `invalid`). Errors that aren't tied to a field go in `non_field_errors`. Always present: `{}` when there are none |

| Status | `code` |
|---|---|
| `400` | `invalid` (with `fields`), `parse_error` (the body isn't valid JSON) |
| `401` | `not_authenticated` (no token), `token_not_valid` (expired, malformed or blacklisted token), `no_active_account` (wrong email or password), `authentication_failed` |
| `403` | `permission_denied` |
| `404` | `not_found`, also for a route that doesn't exist |
| `405` | `method_not_allowed` |
| `406` | `not_acceptable` (the client only accepts a format other than JSON) |
| `429` | `throttled` (rate limit), `account_locked_out` (lockout). The wait in seconds is in the `Retry-After` header |
| `500` | `server_error` |

With `DEBUG=True` a route that doesn't exist and an unhandled error still show Django's debug page, which lists the routes and the traceback. Outside `/api/`, the admin keeps its HTML pages.

The format comes from `core.exceptions.api_exception_handler`. To use your own, point `EXCEPTION_HANDLER` at it in `REST_FRAMEWORK` (`core/settings.py`):

```python
REST_FRAMEWORK = {
    # ...
    "EXCEPTION_HANDLER": "myproject.errors.my_exception_handler",
}
```

The routes that don't exist and the `500` responses come from `handler404` and `handler500` in `core/urls.py`.

### Tokens

The `access` token lasts 5 minutes and the `refresh` token 1 day (`JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`). Every call to `login/refresh/` returns both tokens and blacklists the `refresh` it received:

```json
{"access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..."}
```

**A frontend has to store the new `refresh` after each refresh.** Sending the old one again gets `401`:

```json
{"code": "token_not_valid", "detail": "Token is blacklisted", "fields": {}}
```

- Two tabs that refresh at the same time with the same token: the second one gets `401`. Share the stored token between tabs, or send the user back to login on that `401`.
- An `access` token is not revoked: it works until it expires. Keep `JWT_ACCESS_MINUTES` short.
- Changing a user's password blacklists every `refresh` token that user has, which closes all their sessions: the next refresh of each one gets `401` and the frontend sends the user back to login. It applies to every way of changing it (the admin, `changepassword`, `create_admin_auto --update-password` or `set_password()` followed by `save()` in your code), but not to `User.objects.filter(...).update(password=...)`, which skips `save()`.
- A refresh token of a deleted or inactive user gets `401` with `"No active account found for the given token."`.
- Tokens are signed with `JWT_SIGNING_KEY`, or with `SECRET_KEY` when it's empty. Changing the key invalidates every token already issued.

Each issued and each blacklisted token is a row in the database, visible in the admin under "Token Blacklist". Delete the expired ones once a day:

```bash
python manage.py flushexpiredtokens
```

On Linux and WSL, with cron (`crontab -e`), adjusting the paths:

```text
0 3 * * * cd /path/to/project && .venv/bin/python manage.py flushexpiredtokens
```

On Windows, with the Task Scheduler, from PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\path\to\project\.venv\Scripts\python.exe" -Argument "manage.py flushexpiredtokens" -WorkingDirectory "C:\path\to\project"
Register-ScheduledTask -TaskName "flushexpiredtokens" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 3am)
```

### Logout

`POST /api/v1/auth/logout/` blacklists the `refresh` token in the body. It needs no `Authorization` header: whoever holds the refresh token can already use it, so it can also revoke it, and logout keeps working after the access token expired.

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh>"}'
```

| Status | Body | When |
|---|---|---|
| `200` | `{}` | The `refresh` is now blacklisted. Using it in `login/refresh/` gets `401` |
| `400` | `{"code": "invalid", "detail": "Invalid input.", "fields": {"refresh": ["This field is required."]}}` | No `refresh` in the body |
| `401` | `{"code": "token_not_valid", "detail": "Token is blacklisted", "fields": {}}` | The `refresh` was already used or logged out. Other messages for an expired, malformed or `access` token, always with `"code": "token_not_valid"` |

**The `access` token is not revoked**: it keeps working until it expires (`JWT_ACCESS_MINUTES`, 5 minutes by default). The frontend has to delete both tokens on logout. A `401` from logout means the session was already closed, so the frontend can treat it as a logout.

### Public registration

Registration is open by default. With `ALLOW_PUBLIC_REGISTRATION=False`, `POST /api/v1/auth/register/` answers `403` and creates nothing:

```json
{"code": "permission_denied", "detail": "Public registration is disabled.", "fields": {}}
```

Users can still be added from the admin or with `create_admin_auto`, and existing users log in as before. The rejections don't count against `THROTTLE_REGISTER_RATE`. Only `true`, `yes`, `y`, `on`, `ok` or `1` (any case) keep it open: any other value, a typo included, closes it.

### Profile

`/api/v1/auth/me/` is the profile of whoever sends the token (`Authorization: Bearer <access>`). Without a valid token it answers `401`.

```bash
curl http://localhost:8000/api/v1/auth/me/ -H "Authorization: Bearer <access>"
```

```json
{"id": "8f419aff-49ec-4f42-b9b6-0d8faa76199c", "email": "jane@example.com", "first_name": "Jane", "last_name": "Doe", "date_joined": "2026-10-16T13:20:05.123456Z"}
```

`PATCH` changes `first_name` and `last_name` (up to 150 characters each, empty allowed) and returns the whole profile. `id`, `email` and `date_joined` are read-only: if they come in the body they are ignored without an error, and any other field too. A name that is too long gets `400` with `{"code": "invalid", "detail": "Invalid input.", "fields": {"first_name": ["Ensure this field has no more than 150 characters."]}}`. `PUT`, `POST` and `DELETE` get `405`.

Changing the email is not available here: it needs the new address verified first.

### Change password

`POST /api/v1/auth/password/change/` changes the password of whoever sends the token. It asks for the current password, and the new one goes through the same policy as the registration.

```bash
curl -X POST http://localhost:8000/api/v1/auth/password/change/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"current_password": "<current>", "new_password": "<new>", "new_password2": "<new>"}'
```

| Status | Body | When |
|---|---|---|
| `204` | — | The password changed |
| `400` | `{"code": "invalid", "detail": "Invalid input.", "fields": {"current_password": ["Your current password is incorrect."]}}` | Wrong current password. A weak new password fills `fields.new_password`, a confirmation that doesn't match fills `fields.new_password2`, and a missing field gets `"This field is required."` |
| `401` | `{"code": "not_authenticated", ...}` | No token. An invalid or expired one gets `"code": "token_not_valid"` |
| `429` | `{"code": "throttled", ...}` | More than `THROTTLE_PASSWORD_RATE` attempts (5 per hour by default, per user) |

**Every session of the user is closed, the one that made the change included**: all its refresh tokens go to the blacklist, as with any password change (see [Tokens](#tokens)). The frontend already has the new password, so after the `204` it logs in again to get a new pair. The current `access` token keeps working until it expires.

### Password reset

The API has no pages of its own, so the reset takes two calls and a page in your frontend:

1. `POST /api/v1/auth/password/reset/` with `{"email": "..."}`. It always answers `200` with the same body, whether the email has an account or not, so nobody can use it to find out who is registered:

   ```json
   {"detail": "If the email belongs to an account, a reset link is on its way."}
   ```

   If the account exists, is active and has a password, it gets an email with a link built from `FRONTEND_PASSWORD_RESET_URL`, where `{uid}` and `{token}` are replaced.
2. The link opens your frontend page, which asks for the new password and sends it with the two values:

   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/password/reset/confirm/ \
     -H "Content-Type: application/json" \
     -d '{"uid": "<uid>", "token": "<token>", "new_password": "<new>", "new_password2": "<new>"}'
   ```

| Status | Body | When |
|---|---|---|
| `204` | — | The password changed |
| `400` | `{"code": "invalid", "detail": "Invalid input.", "fields": {"token": ["Invalid or expired link."]}}` | The link was already used, expired (`PASSWORD_RESET_TIMEOUT_MINUTES`, 60 by default) or was altered. A wrong `uid` gets the same answer. A weak password fills `fields.new_password`, and a confirmation that doesn't match fills `fields.new_password2` |
| `429` | `{"code": "throttled", ...}` | More than `THROTTLE_PASSWORD_RATE` requests from the same IP (5 per hour by default, shared by both routes) |

A link works once: setting the password changes what the token was signed with, and so does logging in after asking for it. A confirmed reset closes every session of the user, like any password change, and clears the failed logins that had locked the account (see [Account lockout](#account-lockout)). The email goes out in the background, so asking for a reset takes the same time whether the account exists or not.

`FRONTEND_PASSWORD_RESET_URL` is required in every environment. Keep it in quotes in `.env`: the `&` of a query string breaks the line when a shell runs `source .env`.

### Email verification

`POST /api/v1/auth/register/` answers `201` with the submitted `email`, `first_name` and `last_name` whether the email already had an account or not. With an existing email nothing is created or changed, and the owner gets an email saying someone tried to register with it. The duplicate takes as long to answer as a new account, so the timing doesn't give it away either. A body that fails validation (passwords that don't match, a weak password) still gets `400`.

With `REQUIRE_EMAIL_VERIFICATION=True`, a new account also gets an email with a link built from `FRONTEND_EMAIL_VERIFICATION_URL`, and it can't log in until it follows it:

1. Until then, login answers `401` with the same body as a wrong password. A different answer would tell whoever registered an email whether it already had an account. After a registration, the frontend can show "check your email, or ask for a new link".
2. The frontend page sends the two values of the link:

   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/verify-email/ \
     -H "Content-Type: application/json" -d '{"uid": "<uid>", "token": "<token>"}'
   ```

   It answers `204`, and from then on login works. A used, expired (`EMAIL_VERIFICATION_TIMEOUT_HOURS`, 24 by default) or altered link gets `400` with `{"code": "invalid", "detail": "Invalid input.", "fields": {"token": ["Invalid or expired link."]}}`.
3. `POST /api/v1/auth/verify-email/resend/` with `{"email": "..."}` sends a new link. It always answers `200` with the same body, and only sends when the account exists, is active and is still pending.

Both routes share `THROTTLE_VERIFY_EMAIL_RATE` (5 per hour by default, per IP). Users created in the admin or with `create_admin_auto`, and the ones that existed before, are verified. The admin shows the "Email verified" column and filter, and the field can be ticked by hand. A deactivated user stays deactivated: verifying never touches `is_active`. Turning the flag off lets pending accounts log in.

With `REQUIRE_EMAIL_VERIFICATION=False` (the default), a new account logs in right away. The `201` hides the duplicate, but trying to log in with the password just used still shows whether the account was new: closing that needs the verification on.

### Rate limits

Login allows 10 requests every 10 minutes; registration, the password change and reset, and the email verification 5 per hour each. They are counted by client IP, except the password change, which is counted per user. The next request gets `429` until the period frees a slot, with the wait in seconds in the `Retry-After` header and in `detail`:

```json
{"code": "throttled", "detail": "Request was throttled. Expected available in 542 seconds.", "fields": {}}
```

Every request counts, whatever its result: a correct password after 10 failed attempts also gets `429`. Each limit is a `THROTTLE_*_RATE` variable written as `<requests>/<period>`, where the period is `s`, `m`, `h` or `d` with an optional multiple (`10/m`, `10/10m`, `100/6h`). An empty value turns the limit off, and an invalid one stops Django from starting. To limit a view you add, set `throttle_scope` to one of the scopes, or add yours to `THROTTLE_RATE_DEFAULTS` in `core/settings.py`.

Two things to set before production:

- **Behind a proxy**, set `TRUSTED_PROXY_COUNT` to the number of proxies that append to `X-Forwarded-For`. With `0`, every request seems to come from the proxy and all clients share one limit. A higher number than the real one lets clients pick their own IP.
- **With several processes** (gunicorn workers, more than one server), the default cache is per process and each one counts on its own: 4 workers allow 40 logins every 10 minutes. Point `CACHE_URL` at Redis (`redis://host:6379/0`) and add the `redis` package to the project.

### Account lockout

After 5 failed logins for the same account from the same IP, that pair is locked for 15 minutes, in the API and in the admin. The fifth failure already gets the lockout, and so does the right password while it lasts. The API answers `429` with the same shape as the rate limits:

```json
{"code": "account_locked_out", "detail": "Too many failed login attempts. Expected available in 900 seconds.", "fields": {}}
```

The admin shows a page with the minutes left, also with `429`.

- The account is the email in lowercase: changing its case doesn't start a new count.
- The same account from another IP can still log in, so an attacker can't lock a user out of their own network.
- A successful login resets the count. It also updates `last_login`, in the API too.
- Each failed attempt during the lockout restarts the 15 minutes for that account and IP.
- The IP is the same one the rate limits and the audit log use (`TRUSTED_PROXY_COUNT`).

To unlock before the time is up, delete the attempt in the admin, under "Axes" → "Access attempts", or run one of these:

```bash
python manage.py axes_reset_username user@example.com
python manage.py axes_reset
```

The attempts never store the password. Successful logins are kept in "Access logs"; `python manage.py axes_reset_logs 30` deletes the ones older than 30 days.

`AXES_FAILURE_LIMIT` and `AXES_COOLOFF_MINUTES` change the numbers. `AXES_LOCKOUT_PARAMETERS` decides what is locked: fields joined with `+` lock their combination, and commas separate independent rules. The fields are `username`, `ip_address` and `user_agent`; any other value stops Django from starting.

| Value | Locks |
|---|---|
| `username+ip_address` (default) | The account from that IP |
| `username` | The account from every IP. Anyone can lock out any user |
| `ip_address` | Every account from that IP |

The rate limits and the lockout complement each other: the first counts requests per IP and stops one IP trying many accounts; the second counts failures per account and stops slow attempts against one account.

The admin panel is at `/admin/`.

### Pagination

Lists are paginated by page number. A list view (`ListAPIView`, or a `ViewSet` with `list`) returns:

```json
{"count": 134, "next": "http://localhost:8000/api/v1/items/?page=2", "previous": null, "results": [{"id": 1}, {"id": 2}]}
```

- `?page=` picks the page, from `1`. A page that doesn't exist gets `404` with `code` `not_found`.
- `?page_size=` changes the size up to `API_MAX_PAGE_SIZE`. A larger number gets the maximum, not an error; `0`, a negative number or text gets the default.
- `API_PAGE_SIZE` (default `20`) and `API_MAX_PAGE_SIZE` (default `100`) are read from `.env`. Zero, a negative number, text, or a page size larger than the maximum stop Django from starting.

A view can change its own pagination with `pagination_class`, or turn it off with `None`:

```python
from rest_framework.pagination import LimitOffsetPagination


class ItemListView(ListAPIView):
    pagination_class = LimitOffsetPagination


class CountryListView(ListAPIView):
    pagination_class = None
```

### Permissions

`security.permissions` has two classes to protect a view in one line, on top of Django's permissions and groups:

```python
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from security.permissions import HasPermission, HasRole


class AuditLogListView(ListAPIView):
    permission_classes = (HasPermission("security.view_auditlog"),)


class InvoiceListView(ListAPIView):
    permission_classes = (HasRole("billing") | HasPermission("billing.view_invoice"),)


class ReportView(ListAPIView):
    permission_classes = (IsAuthenticated & ~HasRole("guest"),)
```

- `HasPermission("app_label.codename")` passes if the user has that permission, directly or through one of their groups (`user.has_perm`). A name without the app label stops Django when the view is imported.
- `HasRole("name")` passes if the user belongs to the Django `Group` with that name. Groups are created in the admin, under "Authentication and Authorization" → "Groups", or from the code with [Roles](#roles).
- An active superuser passes both, so `~HasRole(...)` leaves superusers out.
- Without a token they answer `401`; with a token and without the permission or role, `403` with `code` `permission_denied`.
- They combine with `&`, `|` and `~`, between themselves and with DRF's classes.
- A permission or role that doesn't exist is never met, except by a superuser. Django creates four permissions per model, named `<app_label>.<add|change|delete|view>_<model>` (`security.view_auditlog`).

#### Roles

Roles live in the code, so every environment gets the same groups. Declare them in `core/roles.py`, each with its list of permissions:

```python
ROLES = {
    "auditors": ["security.view_auditlog"],
    "support": ["security.view_user", "security.change_user"],
}
```

Then create or update their groups:

```bash
python manage.py sync_roles --dry-run   # shows what would change
python manage.py sync_roles
```

- Each role becomes a Django `Group` with that name, the one `HasRole("auditors")` checks.
- It adds the permissions a group lacks and removes the ones no longer declared. Running it again changes nothing.
- A permission that doesn't exist is reported as a warning and the rest is applied. Permissions are created by `migrate`, so run `sync_roles` after it.
- A permission without the app label (`view_auditlog`) stops the command before it changes anything.
- Groups in the database that aren't declared are listed and left as they are.
- Changes made in the admin to a declared role are undone by the next run: edit `core/roles.py` instead.
- The base declares no roles. To keep them elsewhere, point `ROLE_DEFINITIONS` in `core/settings.py` at your own dict.

### CORS

A browser only lets a frontend on another domain or port call the API if the API allows that origin. List the origins in `CORS_ALLOWED_ORIGINS`, each with its scheme and port and without a trailing slash:

```dotenv
CORS_ALLOWED_ORIGINS=https://app.example.com,http://localhost:5173
```

- Empty (the default) allows no origin: the API works as before for servers, `curl` and same-origin pages.
- `*`, or a domain without scheme, stops Django from starting. There is no "allow every origin" setting.
- It only applies to `/api/`. The admin is never exposed to other origins.
- Cookies are not sent across origins: the frontend sends the token in `Authorization`, which is allowed.
- The frontend can read the `Retry-After` header of a `429` (see [Rate limits](#rate-limits)).

---

## Email

The project sends email through any SMTP provider, configured with one variable. With `EMAIL_URL` empty, each email is printed in the `runserver` console, which is enough to develop.

| Provider | `EMAIL_URL` |
|---|---|
| SendGrid | `smtp+tls://apikey:<api-key>@smtp.sendgrid.net:587` |
| Mailgun | `smtp+tls://postmaster%40mg.example.com:<smtp-password>@smtp.mailgun.org:587` |
| Amazon SES | `smtp+tls://<smtp-username>:<smtp-password>@email-smtp.us-east-1.amazonaws.com:587` |

- `smtp+tls://` uses STARTTLS, usually on port `587`. For TLS from the first byte (port `465`) use `smtp+ssl://`. `smtp://` sends without encryption. Watch out: `smtps://` means STARTTLS here, not port 465.
- The user and the password go inside the URL, so these characters have to be percent-encoded: `@` as `%40`, `:` as `%3A`, `/` as `%2F`, `#` as `%23`, `?` as `%3F` and `%` as `%25`. Amazon SES passwords often have `/`. To encode one: `python -c "import urllib.parse; print(urllib.parse.quote(input(), safe=''))"`.
- `DEFAULT_FROM_EMAIL` has to be an address the provider lets you send from (a verified domain or sender).
- An unknown scheme (`foo://`) stops Django from starting.

To send an email from your code, write three templates in a folder of your app, `templates/<prefix>/subject.txt`, `body.txt` and `body.html`, and call:

```python
from core.emails import send_templated_email

send_templated_email("emails/welcome", user.email, {"name": user.first_name})
```

The templates render in the active language, so `{% translate %}` and `{% blocktranslate %}` work as in any other template. They also escape HTML like any template: wrap `subject.txt` and `body.txt` in `{% autoescape off %}`, or a link with `&` arrives as `&amp;` in the plain text version. The email goes out in a separate thread once the database transaction commits: the request does not wait for the SMTP server, and nothing is sent if the transaction rolls back. A delivery error is logged under the `core.emails` logger with the template name, not the recipient. Each send waits up to 10 seconds for the server. If the process stops in that instant, that email is lost.

## Audit log

`security.middleware.AuditMiddleware` stores every `POST`, `PUT`, `PATCH` and `DELETE` in `AuditLog`: user, IP, user agent, method, path, the response status and the body. You can browse it in the admin under **Security › Audit Logs**.

The admin shows the audit log read-only: nobody, superusers included, can add, edit or delete records there. Old records are deleted with [`purge_audit_logs`](#purging-old-records). Staff users need the `security.view_auditlog` permission to see it.

### Stored bodies

| `Content-Type` | What is stored |
|---|---|
| `application/json` | The parsed JSON |
| `application/x-www-form-urlencoded` | The form fields, in any method. Admin forms use this one |
| `multipart/form-data` | The form fields of a `POST`. Uploaded files are never read or stored. A `PUT` or `PATCH` stores `{}` |
| Anything else | `{}` |

Form fields with one value are stored as a string, and repeated fields as a list. The CSRF token (`csrfmiddlewaretoken`) is dropped. Every body goes through the redaction below, so the passwords of the admin login and of the user forms (`password`, `password1`, `password2`) are stored as `[REDACTED]`. The email of the admin login is stored in clear under `username`, the same way the API login stores `email`.

Form fields can hold personal data. Add the keys of your own forms that must not be stored to `AUDIT_EXTRA_SENSITIVE_KEYS`.

### Client IP

The IP comes from `core.client_ip.get_client_ip`, the same function the rate limits use, so both see the same client.

| `TRUSTED_PROXY_COUNT` | IP stored | When |
|---|---|---|
| `0` (default) | The connection address. `X-Forwarded-For` is ignored | Django receives the requests directly |
| `1` | The last entry of `X-Forwarded-For` | One proxy or load balancer in front |
| `N` | The Nth entry from the right | N proxies, each appending its own entry |

Each proxy appends the address it saw to the right of the header, and anything further left can be written by the client. If the chosen entry isn't a valid IP, or the header is missing, the connection address is stored.

### Redacted values

Values whose key looks like a credential are stored as `[REDACTED]`, at any depth of the body. Keys are compared in lowercase and without `-` or `_`, so `api_key`, `apiKey` and `API-Key` are the same key.

| Rule | Keys |
|---|---|
| Contains | `password`, `passwd`, `token`, `secret`, `apikey`, `authorization`, `credential`, `privatekey` |
| Is exactly | `otp`, `pin`, `cvv`, `cvc`, `cardnumber`, `ssn`, `access`, `refresh` |

Short words only match whole keys: as a fragment, `pin` would also hide `shipping`. For keys of your own project, list them in `AUDIT_EXTRA_SENSITIVE_KEYS`. They match whole keys after the same normalization: `AUDIT_EXTRA_SENSITIVE_KEYS=tax-id,iban` redacts `tax_id`, `taxId` and `IBAN`, but not `tax_id_type`.

Records stored before a key was added keep their value.

### Payload size

Bodies larger than `AUDIT_PAYLOAD_MAX_BYTES` (64 KB by default) are not stored. The record keeps a marker with the size instead:

```json
{"_omitted": "payload_too_large", "size_bytes": 2097152}
```

The size is measured before parsing the body, so an oversized body is never parsed. For `multipart/form-data` the size is that of the stored fields, without the files. A body is never cut in half: a truncated JSON would be invalid and could end before a sensitive key gets redacted. Set `0` to store every body.

Django rejects bodies over `DATA_UPLOAD_MAX_MEMORY_SIZE` (2.5 MB by default) with a `400` before the request reaches the view, and those requests leave no audit record.

### Purging old records

The audit log grows with every request, and the admin can't delete records. `purge_audit_logs` deletes the ones older than a number of days:

```bash
python manage.py purge_audit_logs --older-than 90
```

```text
About to delete 1520 audit log records, from 2026-01-03 to 2026-07-17 inclusive.
Continue? [y/N]
```

| Option | Effect |
|---|---|
| `--older-than DAYS` | Required, 1 or more. Counts whole days in `TIME_ZONE`: run on 2026-10-16, `--older-than 30` deletes up to 2026-09-15 inclusive and keeps everything from 2026-09-16 |
| `--dry-run` | Shows the count and the range, and deletes nothing |
| `--no-input` | Deletes without asking. Without it and without a terminal, the command stops with an error |

With nothing to delete it says so and doesn't ask. Records are deleted in batches of 5000, each in its own transaction, so the table is never locked for the whole purge.

On Linux and WSL, with cron (`crontab -e`), adjusting the paths and the period:

```text
30 3 * * * cd /path/to/project && .venv/bin/python manage.py purge_audit_logs --older-than 90 --no-input
```

On Windows, with the Task Scheduler, from PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\path\to\project\.venv\Scripts\python.exe" -Argument "manage.py purge_audit_logs --older-than 90 --no-input" -WorkingDirectory "C:\path\to\project"
Register-ScheduledTask -TaskName "purge_audit_logs" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 3:30am)
```

---

## Dependencies

`pyproject.toml` is the single source. `uv.lock` pins the exact version of every package for all platforms, and the `requirements` files are generated from it for `pip` users.

| Task | Command |
|---|---|
| Add a dependency | `uv add <package>` |
| Add a development tool | `uv add --dev <package>` |
| Upgrade the pinned versions | `uv lock --upgrade` |
| Regenerate `requirements.txt` | `uv export --no-dev --no-hashes -o requirements.txt` |
| Regenerate `requirements-dev.txt` | `uv export --no-hashes -o requirements-dev.txt` |

**Do not edit the `requirements` files by hand.** After changing a dependency, regenerate both.

More: [managing dependencies in uv](https://docs.astral.sh/uv/concepts/projects/dependencies/) · [exporting the lockfile](https://docs.astral.sh/uv/concepts/projects/export/).

---

## Tests and formatting

The tests need the database running (step 3).

| Task | With uv | With pip + venv |
|---|---|---|
| Run the tests | `uv run python manage.py test` | `python manage.py test` |
| Check formatting | `uv run black --check .` | `black --check .` |
| Apply formatting | `uv run black .` | `black .` |
| Lint | `uv run ruff check .` | `ruff check .` |

---

## Troubleshooting

### Variables and Compose

| Symptom | Cause | Fix |
|---|---|---|
| `required variable ... is missing a value` | The `.env` file is missing, or it lacks that variable | Create `.env` (step 2) or fill in the variable |
| `Conflict. The container name "/..." is already in use` | Another project uses the same `DB_CONTAINER_NAME` | Change it in your `.env` |
| `port is already allocated` or `ports are not available` | `DB_PORT` is taken | Change `DB_PORT` in your `.env` and start again |
| `Error: That port is already in use.` when starting the server | `APP_PORT` is taken | Change `APP_PORT` in your `.env` |
| `password authentication failed for user` | You changed the credentials after the database was created | PostgreSQL only applies them when it creates the volume. Go back to the previous values, or recreate the database with `docker compose down -v` (**deletes the data**) and `docker compose up -d --wait` |
| `Set the SECRET_KEY environment variable` | Django can't find `.env` | It has to be at the project root, next to `manage.py` |
| Compose and Django disagree on a value: the database gets another name or the password is rejected | The value contains `$`, or a `#` after a space, and Compose cuts it | Generate another value without those characters (step 2) |

References: [variables in Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) · [precedence](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/) · [project name](https://docs.docker.com/compose/how-tos/project-name/).

### Docker Desktop on Windows

| Symptom | Cause | Fix |
|---|---|---|
| `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine` | Docker Desktop is not running | Open it and wait until it finishes starting |
| `Docker Desktop - Unexpected WSL error` or virtualization warnings | Virtualization is off or WSL is out of date | Turn it on in the BIOS/UEFI and run `wsl --update`. See [troubleshooting topics](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/topics/) |
| `Docker Desktop - Access Denied` | Your user is not in the `docker-users` group | See [permission requirements on Windows](https://docs.docker.com/desktop/setup/install/windows-permission-requirements/) |
| `docker` is not recognized inside WSL | The integration with your distribution is off | *Settings → Resources → WSL integration*. See [Docker Desktop WSL 2 backend](https://docs.docker.com/desktop/features/wsl/) |
| The port looks free but Docker can't publish it | Windows holds it in a reserved range | Check with `netsh interface ipv4 show excludedportrange protocol=tcp` and pick another `DB_PORT`. See [`netsh interface`](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-interface) |

More help: [Docker Desktop troubleshooting](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/) · [Windows FAQs](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/windowsfaqs/) · [WSL troubleshooting](https://learn.microsoft.com/en-us/windows/wsl/troubleshooting).

### Python on Windows

| Symptom | Cause | Fix |
|---|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled on this system` | PowerShell execution policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` and activate again; or use `uv run`, which activates nothing. See [execution policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies) |
| `python` opens the Microsoft Store or is not recognized | Python is not installed or not on the `PATH` | Use `py`, or install Python. See [Python on Windows](https://docs.python.org/3/using/windows.html) |
| `uv` is not recognized after installing it | The terminal did not reload the `PATH` | Close and reopen the terminal |
| Errors about paths that are too long during installation | 260-character limit | Clone into a short path or enable long paths. See [maximum path length limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) |
| `makemessages` fails because it can't find `msguniq` | `gettext` is missing | See [gettext on Windows](https://docs.djangoproject.com/en/5.2/topics/i18n/translation/#gettext-on-windows) |

More help: [how to install Django on Windows](https://docs.djangoproject.com/en/5.2/howto/windows/) · [virtual environments](https://docs.python.org/3/library/venv.html) · [uv troubleshooting](https://docs.astral.sh/uv/reference/troubleshooting/).

### Line endings

`.gitattributes` makes Git store and check out every file with Linux line endings (LF), on Windows too. If an editor converts them to CRLF, Git normalizes them on commit. More in [configuring Git to handle line endings](https://docs.github.com/en/get-started/git-basics/configuring-git-to-handle-line-endings).

---

## Upgrading from PostgreSQL 15

If you used an earlier version of this base, your volume holds PostgreSQL 15 data. A new major version **does not open the previous version's data**, and version 18 also stores the data in another path. The old volume is left untouched: it stays until you delete it.

To keep your data, take a dump **before** upgrading. These commands are the same in every terminal:

```bash
docker exec <old_container> pg_dump --no-owner -U <user> -d <database> -f /tmp/backup.sql
docker cp <old_container>:/tmp/backup.sql backup.sql
```

`--no-owner` lets you restore even if the user of the new database has a different name.

After upgrading and starting the new database, and **before running `migrate`**:

```bash
docker cp backup.sql <new_container>:/tmp/backup.sql
docker exec <new_container> psql -U <user> -d <database> -f /tmp/backup.sql
```

If you don't need the old data, there is nothing to do: the new database starts empty and `migrate` creates the tables.

Reference: [official PostgreSQL image](https://hub.docker.com/_/postgres).

---

## Renaming the project

The `core` folder holds the configuration. You can keep that name; if you want to change it (for example to `shop`), **don't search and replace across the whole project**: the word `core` is also part of `django.core`, and you would break those imports.

Rename the folder and change only these references:

| File | What to change |
|---|---|
| `manage.py` | `"core.settings"` |
| `<folder>/asgi.py` | `"core.settings"` |
| `<folder>/wsgi.py` | `"core.settings"` |
| `<folder>/settings.py` | `ROOT_URLCONF`, `WSGI_APPLICATION` and the `"core"` entry in `INSTALLED_APPS` |
| `<folder>/tests.py` | The two mentions of `"core"` |
| `pyproject.toml` | `name`, with your project's name |

Check the result with `python manage.py check` and `python manage.py test`.

---

## Internationalization

The project is ready for English and Spanish.

1. **Mark the strings** with `gettext_lazy`:

   ```python
   from django.utils.translation import gettext_lazy as _

   class Product(models.Model):
       name = models.CharField(_("name"), max_length=100)
   ```

2. **Create the translations folder** the first time (`mkdir locale`) and **generate the files**:

   ```bash
   python manage.py makemessages -l es -l en
   ```

3. **Translate** in `locale/es/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`.
4. **Compile:**

   ```bash
   python manage.py compilemessages --ignore ".venv*"
   ```

   Without `--ignore`, Django also walks the virtual environment and recompiles the thousands of catalogs of the installed libraries.

`makemessages` and `compilemessages` need `gettext` installed on the system. On Windows, see [gettext on Windows](https://docs.djangoproject.com/en/5.2/topics/i18n/translation/#gettext-on-windows).

---

## Contributing

Bug reports, ideas and pull requests are welcome. Before opening one, read the [contributing guide](CONTRIBUTING.md) ([Español](CONTRIBUTING.es.md)): it covers the branch flow (`staging` for day-to-day work, `main` for releases), the commit format and the checks CI runs. Report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md).

---

## License

Released under the MIT license. The full text is in [LICENSE](LICENSE).
