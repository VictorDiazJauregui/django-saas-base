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
- [Several projects on the same machine](#several-projects-on-the-same-machine)
- [API](#api)
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

- **Django 5.2 LTS** and **Django REST Framework**, with **JWT** authentication.
- **PostgreSQL 18** in Docker Compose, configured through variables.
- **Custom user** that logs in with an email.
- **Audit log:** every request that changes data is recorded, with sensitive values redacted.
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
| `DB_PASSWORD`, `ADMIN_PASSWORD` | Your own passwords |
| `SECRET_KEY` | A generated key (see below) |
| `DB_PORT`, `APP_PORT` | Keep `5432` and `8000` unless they are already taken |

To generate a key or a strong password, the same command works in any terminal:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> On Windows, if `python` is not recognized, use `py` instead. With `uv`, prefix it with `uv run`.

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
- `create_admin_auto` creates the superuser from `ADMIN_EMAIL` and `ADMIN_PASSWORD`. Running it again does not duplicate it.
- `runserver` uses the port in `APP_PORT`. For a one-off port, pass it: `runserver 9000`.

### 6. Check it works

With the default values:

- Admin panel: <http://localhost:8000/admin/>
- Authentication API: <http://localhost:8000/api/v1/auth/>

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
| `ENVIRONMENT` | Django | Environment name. `prod` forces `DEBUG` off | `local` |
| `SECRET_KEY` | Django | The project's cryptographic key | *(generated)* |
| `DEBUG` | Django | Debug mode | `True` |
| `ALLOWED_HOSTS` | Django | Allowed domains, comma separated | `'*'` |
| `APP_PORT` | Django | Development server port | `8000` |
| `COMPOSE_PROJECT_NAME` | Compose | Project name. The volume and the network are named after it | `saas` |
| `DB_CONTAINER_NAME` | Compose | PostgreSQL container name | `saas_db` |
| `DB_NAME` | Both | Database name | `saas_db` |
| `DB_USER` | Both | Database user | `saas_user` |
| `DB_PASSWORD` | Both | Database password | *(your own)* |
| `DB_HOST` | Django | Where the database is | `localhost` |
| `DB_PORT` | Both | Database port on your machine | `5432` |
| `ADMIN_EMAIL` | Django | Email of the superuser created by `create_admin_auto` | `admin@example.com` |
| `ADMIN_PASSWORD` | Django | That superuser's password | *(your own)* |

Two details worth knowing:

- **PostgreSQL only applies `DB_NAME`, `DB_USER` and `DB_PASSWORD` the first time**, when it creates the volume. If you change them later, the existing database does not pick them up: see [Troubleshooting](#troubleshooting).
- **The database port is published on `127.0.0.1` only**: reachable from your machine, not from other machines on the network.

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
| `POST` | `/api/v1/auth/login/refresh/` | Returns a new `access` token | `refresh` |

Routes you add require authentication by default: send the token in the `Authorization: Bearer <access>` header.

The admin panel is at `/admin/`.

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
