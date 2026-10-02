# SaaS Base · Django + PostgreSQL

Base de backend lista para empezar un proyecto: Django y Django REST Framework corren en tu máquina, y PostgreSQL corre en Docker. Todo lo que identifica a un proyecto (nombres, credenciales y puertos) vive en un archivo `.env`, así que podés clonar la base tantas veces como quieras en la misma máquina sin que un proyecto pise a otro.

Funciona en **Linux**, **WSL** y **Windows** (PowerShell y cmd).

## Contenido

- [Qué incluye](#qué-incluye)
- [Requisitos](#requisitos)
- [Puesta en marcha](#puesta-en-marcha)
- [Guía por sistema](#guía-por-sistema)
- [Variables de entorno](#variables-de-entorno)
- [Varios proyectos en la misma máquina](#varios-proyectos-en-la-misma-máquina)
- [API](#api)
- [Dependencias](#dependencias)
- [Pruebas y formato](#pruebas-y-formato)
- [Solución de problemas](#solución-de-problemas)
- [Actualizar desde PostgreSQL 15](#actualizar-desde-postgresql-15)
- [Renombrar el proyecto](#renombrar-el-proyecto)
- [Internacionalización](#internacionalización)

---

## Qué incluye

- **Django 5.2 LTS** y **Django REST Framework**, con autenticación **JWT**.
- **PostgreSQL 18** en Docker Compose, configurado por variables.
- **Usuario personalizado** que inicia sesión con su email.
- **Auditoría:** cada petición que modifica datos queda registrada, con los datos sensibles censurados.
- **Panel de administración** con gestión de usuarios y consulta de la auditoría.
- **Internacionalización** preparada para inglés y español.
- **Pruebas automáticas** de la API, la auditoría y el panel.

---

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Python | 3.12 o superior (recomendada: 3.12) | Ejecutar Django |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Actual | Crear el entorno e instalar dependencias (recomendado). También podés usar `pip` |
| Docker con Compose v2 | Actual | Ejecutar PostgreSQL |
| Git | Actual | Clonar el repositorio |

Cómo instalar cada una según tu sistema: ver [Guía por sistema](#guía-por-sistema).

> Con `uv` no hace falta instalar Python a mano: si no encuentra la versión indicada en `.python-version`, la descarga solo.

---

## Puesta en marcha

Son seis pasos. Cuando un comando cambia según la terminal, se muestran las tres variantes.

### 1. Clonar

```bash
git clone <URL_DEL_REPOSITORIO> mi-proyecto
cd mi-proyecto
```

### 2. Crear tu archivo `.env`

El repositorio solo trae `.env.example`. Tu `.env` es una copia que no se versiona.

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

Abrí `.env` con tu editor y cambiá, como mínimo:

| Variable | Qué poner |
|---|---|
| `COMPOSE_PROJECT_NAME` | Un nombre único para este proyecto, en minúsculas (por ejemplo `tienda`) |
| `DB_CONTAINER_NAME` | Un nombre único para el contenedor (por ejemplo `tienda_db`) |
| `DB_NAME`, `DB_USER` | El nombre de la base y de su usuario |
| `DB_PASSWORD`, `ADMIN_PASSWORD` | Contraseñas propias |
| `SECRET_KEY` | Una clave generada (ver abajo) |
| `DB_PORT`, `APP_PORT` | Dejá `5432` y `8000`, salvo que ya estén en uso |

Para generar una clave o una contraseña segura, el mismo comando sirve en cualquier terminal:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> En Windows, si `python` no se reconoce, usá `py` en su lugar. Con `uv`, anteponé `uv run`.

> **Evitá `$` y `#` en los valores.** Docker Compose interpreta `$` como referencia a otra variable y un `#` precedido de un espacio como comentario, y recorta el valor; Django, en cambio, lo lee entero. Los dos terminan con valores distintos. El comando anterior solo produce caracteres seguros.

### 3. Levantar la base de datos

```bash
docker compose up -d --wait
```

`--wait` espera a que PostgreSQL esté listo para aceptar conexiones.

**Cómo llegan tus variables a Docker Compose.** Compose lee de forma automática el archivo `.env` que está junto a `docker-compose.yml` y reemplaza cada `${VARIABLE}` del archivo. No hay que exportar nada ni pasar opciones. Para ver exactamente qué entendió:

```bash
docker compose config
```

Si falta una variable, Compose se detiene y la nombra:

```text
required variable COMPOSE_PROJECT_NAME is missing a value: Set COMPOSE_PROJECT_NAME in the .env file
```

Si preferís que Compose use un archivo con otro nombre, indicalo en cada comando:

```bash
docker compose --env-file .env.otro up -d --wait
```

Tené en cuenta que **Django siempre lee `.env`**, así que ese archivo alternativo solo afecta a Compose.

Las variables que ya existan en tu terminal tienen prioridad sobre las del `.env`, tanto para Compose como para Django.

### 4. Crear el entorno de Python

Elegí **una** de las dos opciones.

#### Opción A · uv (recomendada)

Igual en todas las terminales, y no hay que activar nada:

```bash
uv sync
```

Crea la carpeta `.venv` e instala las versiones exactas que fija `uv.lock`. Para instalar solo lo necesario en producción: `uv sync --no-dev`.

A partir de acá, anteponé `uv run` a cada comando de Python.

#### Opción B · pip + venv

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

La línea `Set-ExecutionPolicy` es necesaria porque PowerShell, por omisión, no permite ejecutar scripts, y activar el entorno es ejecutar uno. Con `-Scope Process` el permiso vale solo para esa ventana.

**cmd**

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
```

Si tenés otra versión de Python (3.13, por ejemplo), cambiá `3.12` por la tuya. Para instalar solo lo necesario en producción, usá `requirements.txt`.

### 5. Preparar la base y arrancar

Con **uv**:

```bash
uv run python manage.py migrate
uv run python manage.py create_admin_auto
uv run python manage.py runserver
```

Con **pip + venv** (entorno activado):

```bash
python manage.py migrate
python manage.py create_admin_auto
python manage.py runserver
```

- `migrate` crea las tablas.
- `create_admin_auto` crea el superusuario con `ADMIN_EMAIL` y `ADMIN_PASSWORD`. Se puede ejecutar más de una vez sin duplicarlo.
- `runserver` usa el puerto de `APP_PORT`. Para un puerto puntual, escribilo: `runserver 9000`.

### 6. Comprobar

Con los valores por omisión:

- Panel de administración: <http://localhost:8000/admin/>
- API de autenticación: <http://localhost:8000/api/v1/auth/>

Para probar el inicio de sesión desde la terminal:

**bash / zsh**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "TU_CONTRASEÑA"}'
```

**PowerShell**

```powershell
$body = @{ email = "admin@example.com"; password = "TU_CONTRASEÑA" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login/ -ContentType "application/json" -Body $body
```

**cmd**

```bat
curl -X POST http://localhost:8000/api/v1/auth/login/ -H "Content-Type: application/json" -d "{\"email\": \"admin@example.com\", \"password\": \"TU_CONTRASEÑA\"}"
```

La respuesta trae dos tokens: `access` y `refresh`.

### Apagar

- El servidor: `Ctrl + C`.
- La base, **conservando los datos**: `docker compose down`
- La base, **borrando los datos**: `docker compose down -v`

---

## Guía por sistema

### Linux

1. **Docker Engine y Compose:** [instalación en Ubuntu](https://docs.docker.com/engine/install/ubuntu/) (la misma página enlaza a otras distribuciones) y los [pasos posteriores](https://docs.docker.com/engine/install/linux-postinstall/) para usar Docker sin `sudo`.
2. **uv:**

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Cerrá y volvé a abrir la terminal para que quede disponible.
3. Seguí la [Puesta en marcha](#puesta-en-marcha) con las variantes **bash / zsh**.

Si preferís administrar las versiones de Python por tu cuenta, [pyenv](https://github.com/pyenv/pyenv) reconoce el archivo `.python-version` del proyecto.

### WSL

WSL es Linux dentro de Windows: una vez instalado, todo se hace igual que en Linux.

1. **Instalar WSL** desde PowerShell como administrador y reiniciar ([guía oficial](https://learn.microsoft.com/es-es/windows/wsl/install)):

   ```powershell
   wsl --install
   ```

2. **Clonar dentro del sistema de archivos de Linux** (por ejemplo en `~/proyectos`), no en `/mnt/c/...`. Trabajar sobre el disco de Windows desde WSL es mucho más lento y mezcla los finales de línea. Más detalle en [Trabajar entre sistemas de archivos](https://learn.microsoft.com/es-es/windows/wsl/filesystems).
3. **Docker**, de una de dos formas:
   - **Docker Desktop** en Windows con la integración de WSL activada (*Settings → Resources → WSL integration*). Ver [Docker Desktop con WSL 2](https://docs.docker.com/desktop/features/wsl/).
   - **Docker Engine** instalado dentro de la distribución, como en Linux.

   Usá una sola: tener las dos a la vez genera conflictos.
4. Seguí la [Puesta en marcha](#puesta-en-marcha) con las variantes **bash / zsh**.

El servidor que levantes en WSL se abre desde el navegador de Windows en `http://localhost:8000`. Si no responde, revisá [Acceso a aplicaciones de red con WSL](https://learn.microsoft.com/es-es/windows/wsl/networking).

### Windows

1. **Git:** [descarga](https://git-scm.com/downloads/win), o `winget install --id Git.Git -e`.
2. **Docker Desktop:** [instalación](https://docs.docker.com/desktop/setup/install/windows-install/), o `winget install --id Docker.DockerDesktop -e`. Durante la instalación dejá marcada la opción de usar WSL 2.
3. **uv** (recomendado), desde PowerShell:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   o `winget install --id=astral-sh.uv -e`. Cerrá y volvé a abrir la terminal.
4. **Python**, solo si vas a usar `pip` en lugar de `uv`: [descarga](https://www.python.org/downloads/windows/), o `winget install --id Python.Python.3.12 -e`.

#### PowerShell

Seguí la [Puesta en marcha](#puesta-en-marcha) con las variantes **PowerShell**. Con `uv` no vas a necesitar cambiar la política de ejecución, porque `uv run` no activa ningún script.

#### cmd

Seguí la [Puesta en marcha](#puesta-en-marcha) con las variantes **cmd**. En cmd no existe la restricción de scripts de PowerShell.

#### Docker Desktop

- **Tiene que estar abierto** antes de ejecutar `docker compose`. Si no lo está, los comandos de Docker fallan al conectar.
- En la pestaña **Containers** vas a ver tu proyecto con el nombre que pusiste en `COMPOSE_PROJECT_NAME` y, adentro, el contenedor `DB_CONTAINER_NAME`. Desde ahí podés detenerlo, iniciarlo y ver sus registros.
- En **Volumes** aparece el volumen de datos, llamado `<COMPOSE_PROJECT_NAME>_postgres_data`.
- Si la aplicación no inicia o muestra errores de virtualización, ver [Solución de problemas](#solución-de-problemas).

Guías oficiales: [recorrido por Docker Desktop](https://docs.docker.com/desktop/use-desktop/) · [buenas prácticas con WSL 2](https://docs.docker.com/desktop/features/wsl/best-practices/) · [permisos necesarios en Windows](https://docs.docker.com/desktop/setup/install/windows-permission-requirements/).

---

## Variables de entorno

| Variable | La usa | Para qué | Valor de ejemplo |
|---|---|---|---|
| `ENVIRONMENT` | Django | Entorno. Con `prod`, se fuerza `DEBUG` a falso | `local` |
| `SECRET_KEY` | Django | Clave criptográfica del proyecto | *(generada)* |
| `DEBUG` | Django | Modo de depuración | `True` |
| `ALLOWED_HOSTS` | Django | Dominios permitidos, separados por coma | `'*'` |
| `APP_PORT` | Django | Puerto del servidor de desarrollo | `8000` |
| `COMPOSE_PROJECT_NAME` | Compose | Nombre del proyecto. De él salen el volumen y la red | `saas` |
| `DB_CONTAINER_NAME` | Compose | Nombre del contenedor de PostgreSQL | `saas_db` |
| `DB_NAME` | Ambos | Nombre de la base | `saas_db` |
| `DB_USER` | Ambos | Usuario de la base | `saas_user` |
| `DB_PASSWORD` | Ambos | Contraseña de la base | *(propia)* |
| `DB_HOST` | Django | Dónde está la base | `localhost` |
| `DB_PORT` | Ambos | Puerto de la base en tu máquina | `5432` |
| `ADMIN_EMAIL` | Django | Email del superusuario que crea `create_admin_auto` | `admin@example.com` |
| `ADMIN_PASSWORD` | Django | Contraseña de ese superusuario | *(propia)* |

Dos detalles que conviene saber:

- **PostgreSQL solo aplica `DB_NAME`, `DB_USER` y `DB_PASSWORD` la primera vez**, cuando crea el volumen. Si los cambiás después, la base ya existente no se entera: ver [Solución de problemas](#solución-de-problemas).
- **El puerto de la base se publica solo en `127.0.0.1`**: es accesible desde tu máquina, pero no desde otros equipos de la red.

---

## Varios proyectos en la misma máquina

Cada clon es un proyecto independiente mientras estos valores sean distintos en su `.env`:

| Variable | Proyecto A | Proyecto B |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `tienda` | `blog` |
| `DB_CONTAINER_NAME` | `tienda_db` | `blog_db` |
| `DB_PORT` | `5432` | `5433` |
| `APP_PORT` | `8000` | `8001` |

Con eso, cada uno tiene su contenedor, su volumen de datos, su red y sus puertos, y pueden estar levantados a la vez.

`DB_NAME` y `DB_USER` pueden repetirse, porque cada base vive en su propio contenedor; aun así, usar nombres distintos evita confusiones.

---

## API

| Método | Ruta | Qué hace | Cuerpo |
|---|---|---|---|
| `POST` | `/api/v1/auth/register/` | Registra un usuario | `email`, `password`, `password2`, `first_name`, `last_name` |
| `POST` | `/api/v1/auth/login/` | Devuelve los tokens `access` y `refresh` | `email`, `password` |
| `POST` | `/api/v1/auth/login/refresh/` | Devuelve un `access` nuevo | `refresh` |

Las rutas que agregues exigen autenticación por omisión: enviá el token en el encabezado `Authorization: Bearer <access>`.

El panel de administración está en `/admin/`.

---

## Dependencias

`pyproject.toml` es la única fuente. `uv.lock` fija la versión exacta de cada paquete para todos los sistemas, y los archivos `requirements` se generan a partir de él para quien use `pip`.

| Tarea | Comando |
|---|---|
| Agregar una dependencia | `uv add <paquete>` |
| Agregar una herramienta de desarrollo | `uv add --dev <paquete>` |
| Actualizar las versiones fijadas | `uv lock --upgrade` |
| Regenerar `requirements.txt` | `uv export --no-dev --no-hashes -o requirements.txt` |
| Regenerar `requirements-dev.txt` | `uv export --no-hashes -o requirements-dev.txt` |

**No edites los `requirements` a mano.** Después de cambiar una dependencia, regenerá los dos.

Más información: [dependencias en uv](https://docs.astral.sh/uv/concepts/projects/dependencies/) · [exportar el lock](https://docs.astral.sh/uv/concepts/projects/export/).

---

## Pruebas y formato

Las pruebas necesitan la base de datos levantada (paso 3).

| Tarea | Con uv | Con pip + venv |
|---|---|---|
| Ejecutar las pruebas | `uv run python manage.py test` | `python manage.py test` |
| Comprobar el formato | `uv run black --check .` | `black --check .` |
| Aplicar el formato | `uv run black .` | `black .` |

---

## Solución de problemas

### Variables y Compose

| Síntoma | Causa | Solución |
|---|---|---|
| `required variable ... is missing a value` | Falta el `.env` o le falta esa variable | Creá el `.env` (paso 2) o completá la variable |
| `Conflict. The container name "/..." is already in use` | Otro proyecto usa el mismo `DB_CONTAINER_NAME` | Cambialo en tu `.env` |
| `port is already allocated` o `ports are not available` | `DB_PORT` está ocupado | Cambiá `DB_PORT` en tu `.env` y volvé a levantar |
| `Error: That port is already in use.` al arrancar el servidor | `APP_PORT` está ocupado | Cambiá `APP_PORT` en tu `.env` |
| `password authentication failed for user` | Cambiaste las credenciales después de crear la base | PostgreSQL solo las aplica al crear el volumen. Volvé a los valores anteriores, o recreá la base con `docker compose down -v` (**borra los datos**) y `docker compose up -d --wait` |
| `Set the SECRET_KEY environment variable` | Django no encuentra el `.env` | Tiene que estar en la raíz del proyecto, junto a `manage.py` |
| Compose y Django no coinciden en un valor: la base se crea con otro nombre o la contraseña no sirve | El valor contiene `$`, o un `#` precedido de un espacio, y Compose lo recorta | Generá otro valor sin esos caracteres (paso 2) |

Referencias: [variables en Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) · [precedencia](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/) · [nombre del proyecto](https://docs.docker.com/compose/how-tos/project-name/).

### Docker Desktop en Windows

| Síntoma | Causa | Solución |
|---|---|---|
| `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine` | Docker Desktop no está abierto | Abrilo y esperá a que termine de iniciar |
| `Docker Desktop - Unexpected WSL error` o avisos de virtualización | La virtualización está desactivada o WSL no está al día | Activala en la BIOS/UEFI y ejecutá `wsl --update`. Ver [temas de solución de problemas](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/topics/) |
| `Docker Desktop - Access Denied` | Tu usuario no está en el grupo `docker-users` | Ver [permisos en Windows](https://docs.docker.com/desktop/setup/install/windows-permission-requirements/) |
| `docker` no se reconoce dentro de WSL | Falta activar la integración con tu distribución | *Settings → Resources → WSL integration*. Ver [Docker Desktop con WSL 2](https://docs.docker.com/desktop/features/wsl/) |
| El puerto figura libre pero Docker no puede publicarlo | Windows lo tiene en un rango reservado | Revisalo con `netsh interface ipv4 show excludedportrange protocol=tcp` y elegí otro `DB_PORT`. Ver [`netsh interface`](https://learn.microsoft.com/es-es/windows-server/administration/windows-commands/netsh-interface) |

Más ayuda: [solución de problemas de Docker Desktop](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/) · [preguntas frecuentes para Windows](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/windowsfaqs/) · [solución de problemas de WSL](https://learn.microsoft.com/es-es/windows/wsl/troubleshooting).

### Python en Windows

| Síntoma | Causa | Solución |
|---|---|---|
| `Activate.ps1 cannot be loaded because running scripts is disabled on this system` | Política de ejecución de PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` y volvé a activar; o usá `uv run`, que no activa nada. Ver [políticas de ejecución](https://learn.microsoft.com/es-es/powershell/module/microsoft.powershell.core/about/about_execution_policies) |
| `python` abre la tienda de Microsoft o no se reconoce | Python no está instalado o no está en el `PATH` | Usá `py`, o instalá Python. Ver [Python en Windows](https://docs.python.org/3/using/windows.html) |
| `uv` no se reconoce después de instalarlo | La terminal no recargó el `PATH` | Cerrá y volvé a abrir la terminal |
| Errores por rutas demasiado largas al instalar | Límite de 260 caracteres | Cloná en una ruta corta o habilitá las rutas largas. Ver [límite de longitud de rutas](https://learn.microsoft.com/es-es/windows/win32/fileio/maximum-file-path-limitation) |
| `makemessages` falla porque no encuentra `msguniq` | Falta `gettext` | Ver [gettext en Windows](https://docs.djangoproject.com/es/5.2/topics/i18n/translation/#gettext-on-windows) |

Más ayuda: [instalar Django en Windows](https://docs.djangoproject.com/es/5.2/howto/windows/) · [entornos virtuales](https://docs.python.org/3/library/venv.html) · [solución de problemas de uv](https://docs.astral.sh/uv/reference/troubleshooting/).

### Finales de línea

El archivo `.gitattributes` hace que Git guarde y entregue todos los archivos con finales de línea de Linux (LF), también en Windows. Si un editor los convierte a CRLF, Git los normaliza al confirmar los cambios. Más información en [configurar Git para los finales de línea](https://docs.github.com/es/get-started/git-basics/configuring-git-to-handle-line-endings).

---

## Actualizar desde PostgreSQL 15

Si ya usabas una versión anterior de esta base, tu volumen tiene datos de PostgreSQL 15. Una versión mayor nueva **no abre los datos de la anterior**, y además la versión 18 guarda los datos en otra ruta. El volumen viejo no se toca: sigue existiendo hasta que lo borres.

Para llevar tus datos, hacé una copia **antes** de actualizar. Estos comandos son iguales en cualquier terminal:

```bash
docker exec <contenedor_viejo> pg_dump --no-owner -U <usuario> -d <base> -f /tmp/respaldo.sql
docker cp <contenedor_viejo>:/tmp/respaldo.sql respaldo.sql
```

`--no-owner` permite restaurar aunque el usuario de la base nueva se llame distinto.

Después de actualizar y levantar la base nueva, y **antes de ejecutar `migrate`**:

```bash
docker cp respaldo.sql <contenedor_nuevo>:/tmp/respaldo.sql
docker exec <contenedor_nuevo> psql -U <usuario> -d <base> -f /tmp/respaldo.sql
```

Si no necesitás los datos anteriores, no hace falta hacer nada: la base nueva arranca vacía y `migrate` crea las tablas.

Referencia: [imagen oficial de PostgreSQL](https://hub.docker.com/_/postgres).

---

## Renombrar el proyecto

La carpeta `core` contiene la configuración. Podés dejarla con ese nombre; si querés cambiarlo (por ejemplo a `tienda`), **no uses buscar y reemplazar sobre todo el proyecto**: la palabra `core` también forma parte de `django.core`, y romperías esas importaciones.

Renombrá la carpeta y cambiá solo estas referencias:

| Archivo | Qué cambiar |
|---|---|
| `manage.py` | `"core.settings"` |
| `<carpeta>/asgi.py` | `"core.settings"` |
| `<carpeta>/wsgi.py` | `"core.settings"` |
| `<carpeta>/settings.py` | `ROOT_URLCONF`, `WSGI_APPLICATION` y la entrada `"core"` de `INSTALLED_APPS` |
| `<carpeta>/tests.py` | Las dos menciones a `"core"` |
| `pyproject.toml` | `name`, con el nombre de tu proyecto |

Comprobá el resultado con `python manage.py check` y `python manage.py test`.

---

## Internacionalización

El proyecto está preparado para inglés y español.

1. **Marcá los textos** con `gettext_lazy`:

   ```python
   from django.utils.translation import gettext_lazy as _

   class Product(models.Model):
       name = models.CharField(_("name"), max_length=100)
   ```

2. **Creá la carpeta de traducciones** la primera vez (`mkdir locale`) y **generá los archivos**:

   ```bash
   python manage.py makemessages -l es -l en
   ```

3. **Traducí** en `locale/es/LC_MESSAGES/django.po` y `locale/en/LC_MESSAGES/django.po`.
4. **Compilá:**

   ```bash
   python manage.py compilemessages --ignore ".venv*"
   ```

   Sin `--ignore`, Django recorre también el entorno virtual y vuelve a compilar los miles de catálogos de las librerías instaladas.

`makemessages` y `compilemessages` necesitan `gettext` instalado en el sistema. En Windows, ver [gettext en Windows](https://docs.djangoproject.com/es/5.2/topics/i18n/translation/#gettext-on-windows).
