# SaaS Base · Django + PostgreSQL

[English](README.md) · [Español](README.es.md)

Base de backend lista para empezar un proyecto: Django y Django REST Framework corren en tu máquina, y PostgreSQL corre en Docker. Todo lo que identifica a un proyecto (nombres, credenciales y puertos) vive en un archivo `.env`, así que podés clonar la base tantas veces como quieras en la misma máquina sin que un proyecto pise a otro.

Funciona en **Linux**, **WSL** y **Windows** (PowerShell y cmd).

## Contenido

- [Qué incluye](#qué-incluye)
- [Requisitos](#requisitos)
- [Puesta en marcha](#puesta-en-marcha)
- [Guía por sistema](#guía-por-sistema)
- [Variables de entorno](#variables-de-entorno)
- [Producción](#producción)
- [Varios proyectos en la misma máquina](#varios-proyectos-en-la-misma-máquina)
- [API](#api)
- [Email](#email)
- [Auditoría](#auditoría)
- [Dependencias](#dependencias)
- [Tests y formato](#tests-y-formato)
- [Solución de problemas](#solución-de-problemas)
- [Actualizar desde PostgreSQL 15](#actualizar-desde-postgresql-15)
- [Renombrar el proyecto](#renombrar-el-proyecto)
- [Internacionalización](#internacionalización)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

---

## Qué incluye

- **Django 5.2 LTS** y **Django REST Framework**, con autenticación **JWT** y refresh tokens que rotan en cada uso.
- **Protección del login:** límites de requests por IP y bloqueo de cuenta tras varios logins fallidos, en la API y en el admin.
- **PostgreSQL 18** en Docker Compose, configurado por variables.
- **Usuario personalizado** que inicia sesión con su email y tiene un UUID aleatorio como clave primaria.
- **Endpoints de cuenta:** logout, el perfil propio en `/me/`, cambio y recuperación de contraseña por email, verificación de email opcional y cierre de todas las sesiones al cambiar la contraseña. El registro y la recuperación no revelan qué emails tienen cuenta.
- **Email** por cualquier proveedor SMTP, configurado con una URL; en desarrollo se imprime en la consola.
- **Auditoría:** cada request que modifica datos queda registrada, con los datos sensibles censurados.
- **Esquema OpenAPI y Swagger UI** para el frontend, abiertos en desarrollo y solo para staff en producción.
- **Roles** declarados en el código y aplicados como grupos de Django con `sync_roles`.
- **Panel de administración** con gestión de usuarios y consulta de la auditoría.
- **Internacionalización** preparada para inglés y español.
- **Tests automáticos** de la API, la auditoría y el panel.

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

Son seis pasos. Cuando un comando cambia según la terminal, se muestran las tres variantes. Para una guía corta con los puertos, las comprobaciones y los errores frecuentes, ver [LOCAL-SETUP.es.md](LOCAL-SETUP.es.md).

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
| `DB_PASSWORD`, `ADMIN_PASSWORD` | Contraseñas propias. `ADMIN_PASSWORD` tiene que cumplir la [política de contraseñas](#api) |
| `SECRET_KEY` | Una clave generada (ver abajo) |
| `DB_PORT`, `APP_PORT` | Dejá `5432` y `8000`, salvo que ya estén en uso |

Para generar una clave o una contraseña segura, el mismo comando sirve en cualquier terminal:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> En Windows, si `python` no se reconoce, usá `py` en su lugar. Con `uv`, anteponé `uv run`.

> El valor generado no siempre trae un símbolo, y la política de contraseñas lo pide. Si `create_admin_auto` rechaza `ADMIN_PASSWORD`, dice qué regla no cumple: agregale un `-` o un `_` y volvé a correrlo.

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
- `create_admin_auto` crea el superusuario con `ADMIN_EMAIL` y `ADMIN_PASSWORD`. Se puede ejecutar más de una vez sin duplicarlo. Ver [El superusuario](#el-superusuario).
- `runserver` usa el puerto de `APP_PORT`. Para un puerto puntual, escribilo: `runserver 9000`.

### 6. Comprobar

Con los valores por omisión:

- Panel de administración: <http://localhost:8000/admin/>
- API de autenticación: <http://localhost:8000/api/v1/auth/>
- Documentación de la API: <http://localhost:8000/api/docs/>

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
| `ENVIRONMENT` | Django | `local`, `ci`, `staging` o `prod`. Con otro valor, Django no arranca. Ver [Producción](#producción) | `local` |
| `SECRET_KEY` | Django | Clave criptográfica del proyecto | *(generada)* |
| `DEBUG` | Django | Modo de depuración. Solo se permite en `local` y `ci` | `True` |
| `ALLOWED_HOSTS` | Django | Dominios que sirven el proyecto, separados por coma, sin esquema ni puerto. Obligatoria en `staging` y `prod`, donde `*` se rechaza | `localhost,127.0.0.1` |
| `APP_PORT` | Django | Puerto del servidor de desarrollo | `8000` |
| `SECURE_HSTS_SECONDS` | Django | Cuánto tiempo recuerda el navegador que solo debe usar HTTPS (`staging` y `prod`) | `3600` |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Django | Extiende HSTS a todos los subdominios | `False` |
| `SECURE_HSTS_PRELOAD` | Django | Permite anotar el dominio en la lista de precarga HSTS de los navegadores | `False` |
| `USE_X_FORWARDED_PROTO` | Django | Confía en el header `X-Forwarded-Proto` del proxy que termina TLS | `False` |
| `CSRF_TRUSTED_ORIGINS` | Django | Orígenes extra que pueden enviar formularios, separados por coma, con esquema | *(vacía)* |
| `THROTTLE_ANON_RATE` | Django | Límite para requests anónimas a cualquier endpoint. Vacía: sin límite | *(vacía)* |
| `THROTTLE_USER_RATE` | Django | Límite para requests autenticadas a cualquier endpoint. Vacía: sin límite | *(vacía)* |
| `THROTTLE_LOGIN_RATE` | Django | Límite de `POST /api/v1/auth/login/` | `10/10m` |
| `THROTTLE_REGISTER_RATE` | Django | Límite de `POST /api/v1/auth/register/` | `5/h` |
| `THROTTLE_VERIFY_EMAIL_RATE` | Django | Límite de `verify-email/` y `verify-email/resend/` | `5/h` |
| `THROTTLE_PASSWORD_RATE` | Django | Límite del cambio y de la recuperación de contraseña, y de los endpoints que agregues con `throttle_scope = "password"` | `5/h` |
| `TRUSTED_PROXY_COUNT` | Django | Proxies delante de Django que agregan su entrada a `X-Forwarded-For`. Con `0` se ignora el header. La usan los límites de requests y la auditoría. Un número negativo no deja arrancar Django | `0` |
| `CACHE_URL` | Django | Cache donde se cuentan los límites | `locmemcache://` |
| `AUDIT_EXTRA_SENSITIVE_KEYS` | Django | Claves extra que la auditoría censura, separadas por coma. Ver [Auditoría](#auditoría) | *(vacía)* |
| `AUDIT_PAYLOAD_MAX_BYTES` | Django | Body más grande que guarda la auditoría, en bytes. Uno más grande se guarda como una marca con su tamaño. `0` es sin límite. Un número negativo o un texto no deja arrancar Django | `65536` |
| `JWT_ACCESS_MINUTES` | Django | Duración del token `access`, en minutos. Ver [Tokens](#tokens) | `5` |
| `JWT_REFRESH_DAYS` | Django | Duración del token `refresh`, en días | `1` |
| `JWT_SIGNING_KEY` | Django | Clave con la que se firman los tokens. Vacía: `SECRET_KEY` | *(vacía)* |
| `AXES_FAILURE_LIMIT` | Django | Logins fallidos que bloquean una cuenta. Ver [Bloqueo de cuenta](#bloqueo-de-cuenta) | `5` |
| `AXES_COOLOFF_MINUTES` | Django | Minutos que dura el bloqueo | `15` |
| `AXES_LOCKOUT_PARAMETERS` | Django | Qué se bloquea: `username`, `ip_address`, `user_agent`, unidos con `+` | `username+ip_address` |
| `EMAIL_URL` | Django | A dónde van los emails, como URL. Vacía: se imprimen en la consola. Ver [Email](#email) | *(vacía)* |
| `DEFAULT_FROM_EMAIL` | Django | Remitente de los emails que manda el proyecto | `webmaster@localhost` |
| `ALLOW_PUBLIC_REGISTRATION` | Django | `False` cierra `POST /api/v1/auth/register/` con `403`. Ver [Registro público](#registro-público) | `True` |
| `FRONTEND_PASSWORD_RESET_URL` | Django | Página del frontend a la que apunta el email de recuperación, con `{uid}` y `{token}`. Obligatoria: sin ella, o sin uno de los marcadores, Django no arranca. Ver [Recuperación de contraseña](#recuperación-de-contraseña) | `'http://localhost:3000/reset-password?uid={uid}&token={token}'` |
| `PASSWORD_RESET_TIMEOUT_MINUTES` | Django | Minutos que dura un link de recuperación | `60` |
| `REQUIRE_EMAIL_VERIFICATION` | Django | `True`: un registro público entra recién después de seguir el link de su email. Ver [Verificación de email](#verificación-de-email) | `False` |
| `FRONTEND_EMAIL_VERIFICATION_URL` | Django | Página del frontend a la que apunta el email de verificación, con `{uid}` y `{token}`. Obligatoria solo con `REQUIRE_EMAIL_VERIFICATION=True` | `'http://localhost:3000/verify-email?uid={uid}&token={token}'` |
| `EMAIL_VERIFICATION_TIMEOUT_HOURS` | Django | Horas que dura un link de verificación | `24` |
| `API_PAGE_SIZE` | Django | Elementos por página de un listado. Ver [Paginación](#paginación) | `20` |
| `API_MAX_PAGE_SIZE` | Django | El `?page_size=` más grande que puede pedir un cliente. `API_PAGE_SIZE` no puede superarlo | `100` |
| `API_DOCS_ENABLED` | Django | Quién ve `/api/schema/` y `/api/docs/`. Vacía: cualquiera en `local` y `ci`, solo staff en `staging` y `prod`. Ver [Documentación de la API](#documentación-de-la-api) | *(vacío)* |
| `CORS_ALLOWED_ORIGINS` | Django | Orígenes que pueden llamar a `/api/` desde un navegador, separados por coma, con esquema y puerto. Vacía: ninguno. Ver [CORS](#cors) | *(vacía)* |
| `COMPOSE_PROJECT_NAME` | Compose | Nombre del proyecto. De él salen el volumen y la red | `saas` |
| `DB_CONTAINER_NAME` | Compose | Nombre del contenedor de PostgreSQL | `saas_db` |
| `DB_NAME` | Ambos | Nombre de la base | `saas_db` |
| `DB_USER` | Ambos | Usuario de la base | `saas_user` |
| `DB_PASSWORD` | Ambos | Contraseña de la base | *(propia)* |
| `DB_HOST` | Django | Dónde está la base | `localhost` |
| `DB_PORT` | Ambos | Puerto de la base en tu máquina | `5432` |
| `ADMIN_EMAIL` | Django | Email del superusuario que crea `create_admin_auto` | `admin@example.com` |
| `ADMIN_PASSWORD` | Django | Contraseña de ese superusuario. Tiene que cumplir la política de contraseñas | *(propia)* |
| `PASSWORD_MIN_LENGTH` | Django | Largo mínimo de la contraseña | `8` |
| `PASSWORD_REQUIRE_UPPERCASE` | Django | La contraseña necesita una mayúscula (`A-Z`) | `True` |
| `PASSWORD_REQUIRE_LOWERCASE` | Django | La contraseña necesita una minúscula (`a-z`) | `True` |
| `PASSWORD_REQUIRE_DIGIT` | Django | La contraseña necesita un dígito (`0-9`) | `True` |
| `PASSWORD_REQUIRE_SYMBOL` | Django | La contraseña necesita un símbolo (puntuación ASCII, como `!`, `#`, `-`, `_`) | `True` |

Dos detalles que conviene saber:

- **PostgreSQL solo aplica `DB_NAME`, `DB_USER` y `DB_PASSWORD` la primera vez**, cuando crea el volumen. Si los cambiás después, la base ya existente no se entera: ver [Solución de problemas](#solución-de-problemas).
- **El puerto de la base se publica solo en `127.0.0.1`**: es accesible desde tu máquina, pero no desde otros equipos de la red.

---

## Producción

`ENVIRONMENT` define qué tan estricta es la configuración. Django no arranca si un valor no corresponde al entorno, así el error aparece en el deploy y no con tráfico real.

| | `local`, `ci` | `staging`, `prod` |
|---|---|---|
| `DEBUG=True` | Permitido | Django no arranca |
| `ALLOWED_HOSTS` | Opcional; por defecto `*` con `DEBUG` y `localhost` sin él | Obligatoria, sin `*` |
| Requests por HTTP | Se atienden | Se redirigen a HTTPS |
| Cookies de sesión y CSRF | Viajan por HTTP | `Secure`: solo HTTPS |
| HSTS | Apagado | `SECURE_HSTS_SECONDS`, `3600` por defecto |

Django también revisa los valores copiados de `.env.example`. Si `SECRET_KEY`, `DB_PASSWORD` o `ADMIN_PASSWORD` siguen con el valor del ejemplo, `runserver`, `migrate` y `check` lo informan: como aviso en `local` y `ci` (`core.W001` a `core.W003`) y como error que frena el comando en `staging` y `prod` (`core.E001` a `core.E003`). Una `SECRET_KEY` corta la informa Django mismo (`security.W009`). En `staging` y `prod`, un `EMAIL_URL` que no entrega emails (vacío, consola, archivo o memoria) recibe el aviso `core.W004`: la recuperación de contraseña imprimiría sus links en el log y no le llegarían a nadie.

Antes de desplegar, corré el mismo chequeo que la CI, con el `.env` de producción cargado:

```bash
python manage.py check --deploy --fail-level WARNING
```

Termina con `System check identified no issues (2 silenced)`. Los dos avisos silenciados son los de HSTS que se explican abajo.

Lo que conviene saber antes de salir a producción:

- **Detrás de un proxy o load balancer que termina TLS**, poné `USE_X_FORWARDED_PROTO=True` y asegurate de que el proxy pise `X-Forwarded-Proto`. Sin eso, Django ve HTTP y redirige en loop.
- **Subí `SECURE_HSTS_SECONDS` a `31536000`** (un año) cuando todas las páginas funcionen por HTTPS. El navegador guarda el valor: bajarlo después solo afecta a visitantes nuevos.
- **`SECURE_HSTS_PRELOAD=True` es casi irreversible.** La lista de precarga viene dentro de los navegadores y salir de ella tarda meses. Por eso está apagado y su aviso de `check --deploy` queda silenciado mientras siga así; lo mismo vale para `SECURE_HSTS_INCLUDE_SUBDOMAINS`.
- **`CSRF_TRUSTED_ORIGINS`** solo hace falta si el admin u otro formulario se envía desde un origen distinto del que lo sirve. Un origen comodín total como `https://*` se rechaza en `staging` y `prod`.
- **En cada despliegue, corré `migrate` y después `sync_roles`**, así los grupos coinciden con `core/roles.py`. Ver [Roles](#roles).
- **La documentación de la API es solo para staff** en `staging` y `prod`. Ver [Documentación de la API](#documentación-de-la-api).

### El superusuario

`create_admin_auto` está pensado para despliegues automáticos: lee `ADMIN_EMAIL` y `ADMIN_PASSWORD` y no pregunta nada. Para crear un superusuario a mano, usá el comando de Django, que también pide el email:

```bash
python manage.py createsuperuser
```

Lo que hace `create_admin_auto` depende del email:

| `ADMIN_EMAIL` | Resultado | Exit code |
|---|---|---|
| No existe | Crea el superusuario, si `ADMIN_PASSWORD` cumple la política de contraseñas | `0`, o `1` con las reglas que no cumple |
| Es de un superusuario | Nada: no revisa ni cambia la contraseña | `0` |
| Es de un usuario común | Nada: no promueve usuarios. Promovelo desde el admin o usá otro email | `1` |

El email se compara sin distinguir mayúsculas. Con `--update-password`, un superusuario que ya existe también recibe `ADMIN_PASSWORD`, y si no existe se crea, así que un despliegue puede correr siempre:

```bash
python manage.py create_admin_auto --update-password
```

La contraseña nunca aparece en la salida, tampoco cuando se rechaza.

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

| Método | Ruta | Qué hace | Body |
|---|---|---|---|
| `POST` | `/api/v1/auth/register/` | Registra un usuario | `email`, `password`, `password2`, `first_name`, `last_name` |
| `POST` | `/api/v1/auth/login/` | Devuelve los tokens `access` y `refresh` | `email`, `password` |
| `POST` | `/api/v1/auth/login/refresh/` | Devuelve un `access` y un `refresh` nuevos; el `refresh` enviado deja de servir. Ver [Tokens](#tokens) | `refresh` |
| `POST` | `/api/v1/auth/logout/` | Pone en la blacklist el `refresh` enviado. Ver [Logout](#logout) | `refresh` |
| `GET` | `/api/v1/auth/me/` | Devuelve el perfil del usuario autenticado. Ver [Perfil](#perfil) | — |
| `PATCH` | `/api/v1/auth/me/` | Actualiza `first_name` y `last_name` | `first_name`, `last_name` (los dos opcionales) |
| `POST` | `/api/v1/auth/password/change/` | Cambia la contraseña del usuario autenticado. Ver [Cambio de contraseña](#cambio-de-contraseña) | `current_password`, `new_password`, `new_password2` |
| `POST` | `/api/v1/auth/password/reset/` | Manda por email un link para elegir una contraseña nueva. Ver [Recuperación de contraseña](#recuperación-de-contraseña) | `email` |
| `POST` | `/api/v1/auth/password/reset/confirm/` | Guarda la contraseña nueva con el `uid` y el `token` del link | `uid`, `token`, `new_password`, `new_password2` |
| `POST` | `/api/v1/auth/verify-email/` | Verifica el email de una cuenta con el `uid` y el `token` del link. Ver [Verificación de email](#verificación-de-email) | `uid`, `token` |
| `POST` | `/api/v1/auth/verify-email/resend/` | Manda por email un link de verificación nuevo | `email` |

Las rutas que agregues exigen autenticación por omisión: enviá el token en el header `Authorization: Bearer <access>`.

### Documentación de la API

| Ruta | Qué sirve |
|---|---|
| `GET /api/schema/` | Esquema OpenAPI 3 de la API, en YAML. `?format=json` lo devuelve en JSON |
| `GET /api/docs/` | Swagger UI: cada endpoint con su body, sus respuestas y ejemplos, y un botón **Authorize** para probarlos con un token |

Quién las ve depende de `API_DOCS_ENABLED`:

| `API_DOCS_ENABLED` | Quién ve las docs |
|---|---|
| Vacía (por defecto) | Cualquiera en `local` y `ci`; solo staff en `staging` y `prod` |
| `True` | Cualquiera, en todos los entornos |
| `False` | Solo usuarios staff activos |

- Un staff entra con la sesión del admin (inicia sesión en `/admin/` y abre `/api/docs/` en el mismo navegador) o con un token.
- El resto recibe el mismo `404` que una ruta que no existe.
- `True` en `staging` o `prod` publica la documentación de tu API. Es una decisión para APIs públicas, no un default.
- Swagger UI lo sirve el propio backend (`drf-spectacular-sidecar`), sin CDN. En `staging` y `prod` necesita los archivos estáticos servidos, igual que el admin.

Un frontend puede generar sus tipos y su cliente a partir del esquema, por ejemplo con [openapi-typescript](https://openapi-ts.dev/):

```bash
npx openapi-typescript http://localhost:8000/api/schema/ -o src/api/schema.d.ts
```

El esquema lo arma [drf-spectacular](https://drf-spectacular.readthedocs.io/). Una vista con `serializer_class` se documenta sola; lo que el código no dice (un `204` sin body, los errores) va en `extend_schema`. Los errores tienen la forma de [Errores](#errores) y se documentan con `core.api_schema.error_responses`, que recibe los códigos de error que la vista puede responder:

```python
from drf_spectacular.utils import extend_schema

from core.api_schema import RETRY_AFTER_HEADER, error_responses


@extend_schema(
    parameters=[RETRY_AFTER_HEADER],  # solo si la vista tiene límite de requests
    responses={204: None, **error_responses("invalid", "not_authenticated", "throttled")},
)
class ArchiveInvoiceView(GenericAPIView):
    ...
```

La CI corre `python manage.py spectacular --validate --fail-on-warn` y falla si el esquema tiene algún aviso, por ejemplo una vista que drf-spectacular no sabe describir.

La API responde JSON. Solo con `DEBUG=True` una ruta abierta en el navegador muestra el Browsable API de DRF; en `staging` y `prod` el navegador también recibe JSON.

El claim `user_id` de los dos tokens es el UUID del usuario como string, por ejemplo
`"user_id": "8f419aff-49ec-4f42-b9b6-0d8faa76199c"`.

Los emails se guardan en minúsculas y sin espacios alrededor, y son únicos sin distinguir mayúsculas: registrar `Jane@Example.com` cuando existe `jane@example.com` no crea nada (ver [Verificación de email](#verificación-de-email)). El login acepta el email con cualquier combinación de mayúsculas.

La política de contraseñas rige en la API y en el admin. Por defecto una contraseña necesita 8 caracteres, una mayúscula, una minúscula, un dígito y un símbolo, y no puede parecerse demasiado al email ni al nombre. Solo cuenta ASCII: `ñ` o `€` se aceptan pero no cumplen ninguna regla. Cada regla se cambia con las variables `PASSWORD_*`. Un registro que incumple varias reglas recibe todos los mensajes en `fields.password`:

```json
{"code": "invalid", "detail": "Invalid input.", "fields": {"password": ["This password is too short. It must contain at least 8 characters.", "This password must contain at least one symbol, such as ! ? # - _."]}}
```

### Errores

Todo error bajo `/api/` tiene la misma forma, sea cual sea el status:

```json
{"code": "invalid", "detail": "Invalid input.", "fields": {"email": ["Enter a valid email address."], "password": ["This password is too common."]}}
```

| Clave | Contenido |
|---|---|
| `code` | Identificador fijo, en inglés, para que el frontend decida qué hacer. No cambia con el idioma |
| `detail` | Mensaje para una persona, en el idioma del request (`Accept-Language`) |
| `fields` | Mensajes por campo, solo en los errores de validación (`400` con `code` `invalid`). Los que no son de un campo van en `non_field_errors`. Siempre está: `{}` cuando no hay |

| Status | `code` |
|---|---|
| `400` | `invalid` (con `fields`), `parse_error` (el body no es JSON válido) |
| `401` | `not_authenticated` (sin token), `token_not_valid` (token vencido, malformado o en la blacklist), `no_active_account` (email o contraseña incorrectos), `authentication_failed` |
| `403` | `permission_denied` |
| `404` | `not_found`, también para una ruta que no existe |
| `405` | `method_not_allowed` |
| `406` | `not_acceptable` (el cliente solo acepta un formato que no es JSON) |
| `429` | `throttled` (límite de requests), `account_locked_out` (bloqueo). La espera en segundos está en el header `Retry-After` |
| `500` | `server_error` |

Con `DEBUG=True`, una ruta que no existe y un error no manejado siguen mostrando la página de debug de Django, con la lista de rutas y el traceback. Fuera de `/api/`, el admin mantiene sus páginas HTML.

El formato sale de `core.exceptions.api_exception_handler`. Para usar uno propio, apuntá `EXCEPTION_HANDLER` a tu función en `REST_FRAMEWORK` (`core/settings.py`):

```python
REST_FRAMEWORK = {
    # ...
    "EXCEPTION_HANDLER": "myproject.errors.my_exception_handler",
}
```

Las rutas que no existen y las respuestas `500` salen de `handler404` y `handler500` en `core/urls.py`.

### Tokens

El token `access` dura 5 minutos y el `refresh` 1 día (`JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`). Cada llamada a `login/refresh/` devuelve los dos tokens y pone en la blacklist el `refresh` que recibió:

```json
{"access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..."}
```

**El frontend tiene que guardar el `refresh` nuevo después de cada refresh.** Volver a mandar el viejo responde `401`:

```json
{"code": "token_not_valid", "detail": "Token is blacklisted", "fields": {}}
```

- Dos pestañas que refrescan a la vez con el mismo token: la segunda recibe `401`. Compartí el token guardado entre pestañas, o mandá al usuario al login ante ese `401`.
- El token `access` no se revoca: sirve hasta que vence. Mantené corto `JWT_ACCESS_MINUTES`.
- Cambiar la contraseña de un usuario pone en la blacklist todos sus `refresh`, lo que cierra todas sus sesiones: el próximo refresh de cada una recibe `401` y el frontend lo manda al login. Vale para cualquier forma de cambiarla (el admin, `changepassword`, `create_admin_auto --update-password` o `set_password()` seguido de `save()` en tu código), pero no para `User.objects.filter(...).update(password=...)`, que no pasa por `save()`.
- El refresh de un usuario borrado o inactivo recibe `401` con `"No active account found for the given token."`.
- Los tokens se firman con `JWT_SIGNING_KEY`, o con `SECRET_KEY` si está vacía. Cambiar la clave invalida todos los tokens emitidos.

Cada token emitido y cada token en la blacklist es una fila en la base, visible en el admin en "Token Blacklist". Borrá los vencidos una vez por día:

```bash
python manage.py flushexpiredtokens
```

En Linux y WSL, con cron (`crontab -e`), ajustando las rutas:

```text
0 3 * * * cd /ruta/al/proyecto && .venv/bin/python manage.py flushexpiredtokens
```

En Windows, con el Programador de tareas, desde PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\ruta\al\proyecto\.venv\Scripts\python.exe" -Argument "manage.py flushexpiredtokens" -WorkingDirectory "C:\ruta\al\proyecto"
Register-ScheduledTask -TaskName "flushexpiredtokens" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 3am)
```

### Logout

`POST /api/v1/auth/logout/` pone en la blacklist el `refresh` del body. No lleva header `Authorization`: quien tiene el refresh ya puede usarlo, así que también puede revocarlo, y el logout sigue funcionando aunque el access haya vencido.

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh>"}'
```

| Status | Body | Cuándo |
|---|---|---|
| `200` | `{}` | El `refresh` quedó en la blacklist. Usarlo en `login/refresh/` responde `401` |
| `400` | `{"code": "invalid", "detail": "Invalid input.", "fields": {"refresh": ["This field is required."]}}` | Falta `refresh` en el body |
| `401` | `{"code": "token_not_valid", "detail": "Token is blacklisted", "fields": {}}` | El `refresh` ya se usó o ya se cerró. Otros mensajes para un token vencido, malformado o un `access`, siempre con `"code": "token_not_valid"` |

**El token `access` no se revoca**: sirve hasta que vence (`JWT_ACCESS_MINUTES`, 5 minutos por defecto). El frontend tiene que borrar los dos tokens al hacer logout. Un `401` del logout significa que la sesión ya estaba cerrada: el frontend lo puede tratar como un logout.

### Registro público

El registro está abierto por defecto. Con `ALLOW_PUBLIC_REGISTRATION=False`, `POST /api/v1/auth/register/` responde `403` y no crea nada:

```json
{"code": "permission_denied", "detail": "Public registration is disabled.", "fields": {}}
```

Se pueden seguir agregando usuarios desde el admin o con `create_admin_auto`, y los usuarios existentes entran como siempre. Los rechazos no cuentan para `THROTTLE_REGISTER_RATE`. Solo `true`, `yes`, `y`, `on`, `ok` o `1` (sin importar mayúsculas) lo dejan abierto: cualquier otro valor, un error de tipeo incluido, lo cierra.

### Perfil

`/api/v1/auth/me/` es el perfil de quien manda el token (`Authorization: Bearer <access>`). Sin un token válido responde `401`.

```bash
curl http://localhost:8000/api/v1/auth/me/ -H "Authorization: Bearer <access>"
```

```json
{"id": "8f419aff-49ec-4f42-b9b6-0d8faa76199c", "email": "jane@example.com", "first_name": "Jane", "last_name": "Doe", "date_joined": "2026-10-16T13:20:05.123456Z"}
```

`PATCH` cambia `first_name` y `last_name` (hasta 150 caracteres cada uno, vacío permitido) y devuelve el perfil completo. `id`, `email` y `date_joined` son de solo lectura: si llegan en el body se ignoran sin error, igual que cualquier otro campo. Un nombre demasiado largo responde `400` con `{"code": "invalid", "detail": "Invalid input.", "fields": {"first_name": ["Ensure this field has no more than 150 characters."]}}`. `PUT`, `POST` y `DELETE` responden `405`.

El email no se cambia acá: hace falta verificar la casilla nueva primero.

### Cambio de contraseña

`POST /api/v1/auth/password/change/` cambia la contraseña de quien manda el token. Pide la contraseña actual, y la nueva pasa por la misma política que el registro.

```bash
curl -X POST http://localhost:8000/api/v1/auth/password/change/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"current_password": "<actual>", "new_password": "<nueva>", "new_password2": "<nueva>"}'
```

| Status | Body | Cuándo |
|---|---|---|
| `204` | — | La contraseña cambió |
| `400` | `{"code": "invalid", "detail": "Invalid input.", "fields": {"current_password": ["Your current password is incorrect."]}}` | Contraseña actual incorrecta. Una nueva débil llena `fields.new_password`, una confirmación que no coincide llena `fields.new_password2`, y un campo faltante recibe `"This field is required."` |
| `401` | `{"code": "not_authenticated", ...}` | Sin token. Uno inválido o vencido recibe `"code": "token_not_valid"` |
| `429` | `{"code": "throttled", ...}` | Más intentos que `THROTTLE_PASSWORD_RATE` (5 por hora por defecto, por usuario) |

**Se cierran todas las sesiones del usuario, incluida la que hizo el cambio**: todos sus refresh tokens van a la blacklist, como en cualquier cambio de contraseña (ver [Tokens](#tokens)). El frontend ya tiene la contraseña nueva: después del `204` vuelve a hacer login para obtener un par nuevo. El `access` actual sigue sirviendo hasta que vence.

### Recuperación de contraseña

La API no tiene páginas propias, así que la recuperación son dos llamadas y una página de tu frontend:

1. `POST /api/v1/auth/password/reset/` con `{"email": "..."}`. Responde siempre `200` con el mismo body, tenga cuenta el email o no, así nadie puede usarlo para averiguar quién está registrado:

   ```json
   {"detail": "If the email belongs to an account, a reset link is on its way."}
   ```

   Si la cuenta existe, está activa y tiene contraseña, recibe un email con un link armado desde `FRONTEND_PASSWORD_RESET_URL`, con `{uid}` y `{token}` reemplazados.
2. El link abre la página de tu frontend, que pide la contraseña nueva y la manda con los dos valores:

   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/password/reset/confirm/ \
     -H "Content-Type: application/json" \
     -d '{"uid": "<uid>", "token": "<token>", "new_password": "<nueva>", "new_password2": "<nueva>"}'
   ```

| Status | Body | Cuándo |
|---|---|---|
| `204` | — | La contraseña cambió |
| `400` | `{"code": "invalid", "detail": "Invalid input.", "fields": {"token": ["Invalid or expired link."]}}` | El link ya se usó, venció (`PASSWORD_RESET_TIMEOUT_MINUTES`, 60 por defecto) o fue alterado. Un `uid` incorrecto recibe la misma respuesta. Una contraseña débil llena `fields.new_password`, y una confirmación que no coincide llena `fields.new_password2` |
| `429` | `{"code": "throttled", ...}` | Más requests que `THROTTLE_PASSWORD_RATE` desde la misma IP (5 por hora por defecto, compartido por las dos rutas) |

Un link sirve una sola vez: guardar la contraseña cambia aquello con lo que se firmó el token, y hacer login después de pedirlo también. Un reset confirmado cierra todas las sesiones del usuario, como cualquier cambio de contraseña, y borra los logins fallidos que habían bloqueado la cuenta (ver [Bloqueo de cuenta](#bloqueo-de-cuenta)). El email sale en segundo plano, así que pedir un reset tarda lo mismo exista la cuenta o no.

`FRONTEND_PASSWORD_RESET_URL` es obligatoria en todos los entornos. Dejala entre comillas en el `.env`: el `&` de la query string rompe la línea cuando un shell hace `source .env`.

### Verificación de email

`POST /api/v1/auth/register/` responde `201` con el `email`, el `first_name` y el `last_name` enviados, tenga cuenta el email o no. Con un email existente no se crea ni se cambia nada, y al dueño le llega un email avisando que alguien intentó registrarse con él. El duplicado tarda en responder lo mismo que una cuenta nueva, así que el tiempo tampoco lo delata. Un body que no pasa la validación (contraseñas que no coinciden, una contraseña débil) sigue recibiendo `400`.

Con `REQUIRE_EMAIL_VERIFICATION=True`, la cuenta nueva además recibe un email con un link armado desde `FRONTEND_EMAIL_VERIFICATION_URL`, y no puede entrar hasta seguirlo:

1. Mientras tanto, el login responde `401` con el mismo body que una contraseña incorrecta. Una respuesta distinta le diría a quien registró un email si ese email ya tenía cuenta. Después de registrarse, el frontend puede mostrar "revisá tu email, o pedí otro link".
2. La página del frontend manda los dos valores del link:

   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/verify-email/ \
     -H "Content-Type: application/json" -d '{"uid": "<uid>", "token": "<token>"}'
   ```

   Responde `204`, y desde ese momento el login funciona. Un link usado, vencido (`EMAIL_VERIFICATION_TIMEOUT_HOURS`, 24 por defecto) o alterado recibe `400` con `{"code": "invalid", "detail": "Invalid input.", "fields": {"token": ["Invalid or expired link."]}}`.
3. `POST /api/v1/auth/verify-email/resend/` con `{"email": "..."}` manda un link nuevo. Responde siempre `200` con el mismo body, y solo manda el email si la cuenta existe, está activa y sigue pendiente.

Las dos rutas comparten `THROTTLE_VERIFY_EMAIL_RATE` (5 por hora por defecto, por IP). Los usuarios creados en el admin o con `create_admin_auto`, y los que ya existían, cuentan como verificados. El admin muestra la columna y el filtro "Email verified", y el campo se puede marcar a mano. Un usuario desactivado sigue desactivado: verificar nunca toca `is_active`. Apagar el flag deja entrar a las cuentas pendientes.

Con `REQUIRE_EMAIL_VERIFICATION=False` (el default), la cuenta nueva entra enseguida. El `201` esconde el duplicado, pero probar el login con la contraseña recién usada igual muestra si la cuenta era nueva: para cerrar eso hace falta la verificación activa.

### Límites de requests

El login admite 10 requests cada 10 minutos; el registro, el cambio y la recuperación de contraseña y la verificación de email, 5 por hora cada uno. Se cuentan por IP del cliente, salvo el cambio de contraseña, que se cuenta por usuario. La request siguiente recibe `429` hasta que el período libera un lugar, con la espera en segundos en el header `Retry-After` y en `detail`:

```json
{"code": "throttled", "detail": "Request was throttled. Expected available in 542 seconds.", "fields": {}}
```

Cuenta cada request, sin importar el resultado: una contraseña correcta después de 10 intentos fallidos también recibe `429`. Cada límite es una variable `THROTTLE_*_RATE` con el formato `<requests>/<período>`, donde el período es `s`, `m`, `h` o `d` con un múltiplo opcional (`10/m`, `10/10m`, `100/6h`). Un valor vacío apaga el límite y uno inválido no deja arrancar a Django. Para limitar una vista que agregues, poné `throttle_scope` con uno de los scopes, o sumá el tuyo a `THROTTLE_RATE_DEFAULTS` en `core/settings.py`.

Dos cosas para configurar antes de producción:

- **Detrás de un proxy**, poné en `TRUSTED_PROXY_COUNT` la cantidad de proxies que agregan su entrada a `X-Forwarded-For`. Con `0`, todas las requests parecen venir del proxy y todos los clientes comparten un mismo límite. Un número mayor al real deja que el cliente elija su propia IP.
- **Con varios procesos** (workers de gunicorn, más de un servidor), la cache por defecto es por proceso y cada uno cuenta por su lado: 4 workers admiten 40 logins cada 10 minutos. Apuntá `CACHE_URL` a Redis (`redis://host:6379/0`) y sumá el paquete `redis` al proyecto.

### Bloqueo de cuenta

Tras 5 logins fallidos de la misma cuenta desde la misma IP, ese par queda bloqueado 15 minutos, en la API y en el admin. El quinto fallo ya recibe el bloqueo, y también la contraseña correcta mientras dura. La API responde `429` con la misma forma que los límites de requests:

```json
{"code": "account_locked_out", "detail": "Too many failed login attempts. Expected available in 900 seconds.", "fields": {}}
```

El admin muestra una página con los minutos que faltan, también con `429`.

- La cuenta es el email en minúsculas: cambiar mayúsculas no empieza una cuenta nueva.
- La misma cuenta desde otra IP sigue pudiendo entrar, así un atacante no puede dejar a un usuario afuera de su propia red.
- Un login correcto reinicia la cuenta de fallos. También actualiza `last_login`, en la API incluida.
- Cada intento fallido durante el bloqueo vuelve a empezar los 15 minutos para esa cuenta e IP.
- La IP es la misma que usan los límites de requests y la auditoría (`TRUSTED_PROXY_COUNT`).

Para desbloquear antes de tiempo, borrá el intento en el admin, en "Axes" → "Access attempts", o corré uno de estos:

```bash
python manage.py axes_reset_username user@example.com
python manage.py axes_reset
```

Los intentos nunca guardan la contraseña. Los logins correctos quedan en "Access logs"; `python manage.py axes_reset_logs 30` borra los de más de 30 días.

`AXES_FAILURE_LIMIT` y `AXES_COOLOFF_MINUTES` cambian los números. `AXES_LOCKOUT_PARAMETERS` decide qué se bloquea: los campos unidos con `+` bloquean su combinación, y las comas separan reglas independientes. Los campos son `username`, `ip_address` y `user_agent`; cualquier otro valor no deja arrancar a Django.

| Valor | Bloquea |
|---|---|
| `username+ip_address` (default) | La cuenta desde esa IP |
| `username` | La cuenta desde cualquier IP. Cualquiera puede bloquear a cualquier usuario |
| `ip_address` | Todas las cuentas desde esa IP |

Los límites de requests y el bloqueo se complementan: los primeros cuentan requests por IP y frenan a una IP que prueba muchas cuentas; el segundo cuenta fallos por cuenta y frena los intentos lentos contra una sola.

El panel de administración está en `/admin/`.

### Paginación

Los listados se paginan por número de página. Una vista de listado (`ListAPIView`, o un `ViewSet` con `list`) devuelve:

```json
{"count": 134, "next": "http://localhost:8000/api/v1/items/?page=2", "previous": null, "results": [{"id": 1}, {"id": 2}]}
```

- `?page=` elige la página, desde `1`. Una página que no existe responde `404` con `code` `not_found`.
- `?page_size=` cambia el tamaño hasta `API_MAX_PAGE_SIZE`. Un número mayor recibe el máximo, no un error; `0`, un número negativo o texto reciben el valor por defecto.
- `API_PAGE_SIZE` (por defecto `20`) y `API_MAX_PAGE_SIZE` (por defecto `100`) se leen del `.env`. Cero, un número negativo, texto o un tamaño de página mayor que el máximo impiden que Django arranque.

Una vista puede cambiar su paginación con `pagination_class`, o apagarla con `None`:

```python
from rest_framework.pagination import LimitOffsetPagination


class ItemListView(ListAPIView):
    pagination_class = LimitOffsetPagination


class CountryListView(ListAPIView):
    pagination_class = None
```

### Permisos

`security.permissions` trae dos clases para proteger una vista en una línea, sobre los permisos y los grupos de Django:

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

- `HasPermission("app_label.codename")` deja pasar si el usuario tiene ese permiso, directo o por uno de sus grupos (`user.has_perm`). Un nombre sin la app impide que Django arranque cuando se importa la vista.
- `HasRole("nombre")` deja pasar si el usuario pertenece al `Group` de Django con ese nombre. Los grupos se crean en el admin, en "Authentication and Authorization" → "Groups", o desde el código con [Roles](#roles).
- Un superusuario activo pasa las dos, así que `~HasRole(...)` deja afuera a los superusuarios.
- Sin token responden `401`; con token y sin el permiso o el rol, `403` con `code` `permission_denied`.
- Se combinan con `&`, `|` y `~`, entre sí y con las clases de DRF.
- Un permiso o un rol que no existe nunca se cumple, salvo para un superusuario. Django crea cuatro permisos por modelo, con la forma `<app_label>.<add|change|delete|view>_<modelo>` (`security.view_auditlog`).

#### Roles

Los roles viven en el código, así todos los entornos tienen los mismos grupos. Se declaran en `core/roles.py`, cada uno con su lista de permisos:

```python
ROLES = {
    "auditors": ["security.view_auditlog"],
    "support": ["security.view_user", "security.change_user"],
}
```

Después se crean o actualizan sus grupos:

```bash
python manage.py sync_roles --dry-run   # muestra qué cambiaría
python manage.py sync_roles
```

- Cada rol queda como un `Group` de Django con ese nombre, el mismo que revisa `HasRole("auditors")`.
- Agrega los permisos que le faltan a un grupo y quita los que ya no están declarados. Correrlo otra vez no cambia nada.
- Un permiso que no existe se informa como aviso y el resto se aplica. Los permisos los crea `migrate`, así que `sync_roles` va después.
- Un permiso sin la app (`view_auditlog`) frena el comando antes de cambiar nada.
- Los grupos de la base que no están declarados se listan y se dejan como están.
- Lo que se cambie en el admin sobre un rol declarado se pierde en la siguiente corrida: hay que editar `core/roles.py`.
- La base no declara ningún rol. Para tenerlos en otro lado, apuntá `ROLE_DEFINITIONS` de `core/settings.py` a tu propio dict.

### CORS

Un navegador solo deja que un frontend en otro dominio o puerto llame a la API si la API permite ese origen. Los orígenes van en `CORS_ALLOWED_ORIGINS`, cada uno con su esquema y su puerto y sin `/` final:

```dotenv
CORS_ALLOWED_ORIGINS=https://app.example.com,http://localhost:5173
```

- Vacía (el valor por defecto) no permite ningún origen: la API sigue funcionando igual para servidores, `curl` y páginas del mismo origen.
- `*`, o un dominio sin esquema, impide que Django arranque. No existe la opción de permitir todos los orígenes.
- Solo aplica a `/api/`. El admin nunca se expone a otros orígenes.
- Las cookies no viajan entre orígenes: el frontend manda el token en `Authorization`, que está permitido.
- El frontend puede leer el header `Retry-After` de un `429` (ver [Límites de requests](#límites-de-requests)).

---

## Email

El proyecto manda emails por cualquier proveedor SMTP, configurado con una sola variable. Con `EMAIL_URL` vacía, cada email se imprime en la consola de `runserver`, que alcanza para desarrollar.

| Proveedor | `EMAIL_URL` |
|---|---|
| SendGrid | `smtp+tls://apikey:<api-key>@smtp.sendgrid.net:587` |
| Mailgun | `smtp+tls://postmaster%40mg.example.com:<smtp-password>@smtp.mailgun.org:587` |
| Amazon SES | `smtp+tls://<smtp-username>:<smtp-password>@email-smtp.us-east-1.amazonaws.com:587` |

- `smtp+tls://` usa STARTTLS, en general en el puerto `587`. Para TLS desde el primer byte (puerto `465`) usá `smtp+ssl://`. `smtp://` manda sin cifrar. Ojo: acá `smtps://` significa STARTTLS, no el puerto 465.
- El usuario y la contraseña van dentro de la URL, así que estos caracteres se codifican: `@` como `%40`, `:` como `%3A`, `/` como `%2F`, `#` como `%23`, `?` como `%3F` y `%` como `%25`. Las contraseñas de Amazon SES suelen tener `/`. Para codificar una: `python -c "import urllib.parse; print(urllib.parse.quote(input(), safe=''))"`.
- `DEFAULT_FROM_EMAIL` tiene que ser una dirección desde la que el proveedor te deje enviar (un dominio o remitente verificado).
- Un esquema desconocido (`foo://`) no deja arrancar a Django.

Para mandar un email desde tu código, escribí tres plantillas en una carpeta de tu app, `templates/<prefijo>/subject.txt`, `body.txt` y `body.html`, y llamá:

```python
from core.emails import send_templated_email

send_templated_email("emails/welcome", user.email, {"name": user.first_name})
```

Las plantillas se renderizan en el idioma activo, así que `{% translate %}` y `{% blocktranslate %}` funcionan como en cualquier plantilla. También escapan HTML como cualquier plantilla: envolvé `subject.txt` y `body.txt` en `{% autoescape off %}`, o un link con `&` llega como `&amp;` en la versión de texto plano. El email sale en un hilo aparte cuando la transacción de la base hace commit: el request no espera al servidor SMTP, y si la transacción se revierte no se manda nada. Un error de envío queda en el log `core.emails` con el nombre de la plantilla, sin el destinatario. Cada envío espera hasta 10 segundos al servidor. Si el proceso se corta justo en ese momento, ese email se pierde.

## Auditoría

`security.middleware.AuditMiddleware` guarda cada `POST`, `PUT`, `PATCH` y `DELETE` en `AuditLog`: usuario, IP, user agent, método, path, el status de la respuesta y el body. Se consulta en el admin, en **Security › Audit Logs**.

En el admin la auditoría es de solo lectura: nadie, ni siquiera un superusuario, puede agregar, editar o borrar registros. Los registros viejos se borran con [`purge_audit_logs`](#purga-de-registros-viejos). Un usuario staff necesita el permiso `security.view_auditlog` para verla.

### Bodies que se guardan

| `Content-Type` | Qué se guarda |
|---|---|
| `application/json` | El JSON parseado |
| `application/x-www-form-urlencoded` | Los campos del formulario, en cualquier método. Es el que usan los formularios del admin |
| `multipart/form-data` | Los campos del formulario de un `POST`. Los archivos subidos nunca se leen ni se guardan. Un `PUT` o un `PATCH` guarda `{}` |
| Cualquier otro | `{}` |

Los campos con un solo valor se guardan como texto, y los repetidos como lista. El token CSRF (`csrfmiddlewaretoken`) se descarta. Todo body pasa por la censura de abajo, así que las contraseñas del login del admin y de los formularios de usuario (`password`, `password1`, `password2`) se guardan como `[REDACTED]`. El email del login del admin se guarda en claro en `username`, igual que el login de la API guarda `email`.

Los campos de un formulario pueden tener datos personales. Las claves de tus formularios que no se deben guardar van en `AUDIT_EXTRA_SENSITIVE_KEYS`.

### IP del cliente

La IP sale de `core.client_ip.get_client_ip`, la misma función que usan los límites de requests, así que los dos ven el mismo cliente.

| `TRUSTED_PROXY_COUNT` | IP guardada | Cuándo |
|---|---|---|
| `0` (default) | La dirección de la conexión. `X-Forwarded-For` se ignora | Django recibe las requests directo |
| `1` | La última entrada de `X-Forwarded-For` | Un proxy o load balancer adelante |
| `N` | La N-ésima entrada desde la derecha | N proxies, cada uno agrega su entrada |

Cada proxy agrega a la derecha del header la dirección que vio, y lo que queda más a la izquierda lo puede escribir el cliente. Si la entrada elegida no es una IP válida, o no hay header, se guarda la dirección de la conexión.

### Valores censurados

Los valores cuya clave parece una credencial se guardan como `[REDACTED]`, a cualquier profundidad del body. Las claves se comparan en minúsculas y sin `-` ni `_`, así que `api_key`, `apiKey` y `API-Key` son la misma clave.

| Regla | Claves |
|---|---|
| Contiene | `password`, `passwd`, `token`, `secret`, `apikey`, `authorization`, `credential`, `privatekey` |
| Es exactamente | `otp`, `pin`, `cvv`, `cvc`, `cardnumber`, `ssn`, `access`, `refresh` |

Las palabras cortas solo coinciden con la clave entera: como fragmento, `pin` también ocultaría `shipping`. Para claves propias del proyecto, listalas en `AUDIT_EXTRA_SENSITIVE_KEYS`. Coinciden con la clave entera después de la misma normalización: `AUDIT_EXTRA_SENSITIVE_KEYS=tax-id,iban` censura `tax_id`, `taxId` e `IBAN`, pero no `tax_id_type`.

Los registros guardados antes de sumar una clave conservan su valor.

### Tamaño del payload

Los bodies de más de `AUDIT_PAYLOAD_MAX_BYTES` (64 KB por defecto) no se guardan. En su lugar, el registro guarda una marca con el tamaño:

```json
{"_omitted": "payload_too_large", "size_bytes": 2097152}
```

El tamaño se mide antes de parsear el body, así que un body demasiado grande nunca se parsea. En `multipart/form-data` se mide lo que ocupan los campos guardados, sin los archivos. Nunca se corta un body a la mitad: un JSON truncado sería inválido y podría terminar antes de que se censure una clave sensible. Con `0` se guardan todos.

Django rechaza con `400` los bodies de más de `DATA_UPLOAD_MAX_MEMORY_SIZE` (2,5 MB por defecto) antes de que el request llegue a la vista, y esos requests no dejan registro de auditoría.

### Purga de registros viejos

La auditoría crece con cada request y desde el admin no se pueden borrar registros. `purge_audit_logs` borra los que tienen más de una cantidad de días:

```bash
python manage.py purge_audit_logs --older-than 90
```

```text
About to delete 1520 audit log records, from 2026-01-03 to 2026-07-17 inclusive.
Continue? [y/N]
```

| Opción | Efecto |
|---|---|
| `--older-than DAYS` | Obligatoria, 1 o más. Cuenta días completos en `TIME_ZONE`: corrida el 2026-10-16, `--older-than 30` borra hasta el 2026-09-15 inclusive y conserva todo desde el 2026-09-16 |
| `--dry-run` | Muestra la cantidad y el rango, y no borra nada |
| `--no-input` | Borra sin preguntar. Sin esta opción y sin terminal, el comando termina con un error |

Si no hay nada para borrar, lo dice y no pregunta. Los registros se borran en lotes de 5000, cada uno en su propia transacción, así que la tabla nunca queda bloqueada durante toda la purga.

En Linux y WSL, con cron (`crontab -e`), ajustando las rutas y el período:

```text
30 3 * * * cd /path/to/project && .venv/bin/python manage.py purge_audit_logs --older-than 90 --no-input
```

En Windows, con el Programador de tareas, desde PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\path\to\project\.venv\Scripts\python.exe" -Argument "manage.py purge_audit_logs --older-than 90 --no-input" -WorkingDirectory "C:\path\to\project"
Register-ScheduledTask -TaskName "purge_audit_logs" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 3:30am)
```

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

## Tests y formato

Los tests necesitan la base de datos levantada (paso 3).

| Tarea | Con uv | Con pip + venv |
|---|---|---|
| Correr los tests | `uv run python manage.py test` | `python manage.py test` |
| Comprobar el formato | `uv run black --check .` | `black --check .` |
| Aplicar el formato | `uv run black .` | `black .` |
| Correr el linter | `uv run ruff check .` | `ruff check .` |

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

---

## Contribuir

Los bugs, las ideas y los pull requests son bienvenidos. Antes de abrir uno, leé la [guía de contribución](CONTRIBUTING.es.md) ([English](CONTRIBUTING.md)): explica el flujo de ramas (`staging` para el trabajo diario, `main` para las releases), el formato de los commits y los checks que corre la CI. Las vulnerabilidades se reportan en privado, como indica [SECURITY.es.md](SECURITY.es.md).

---

## Licencia

Distribuido bajo la licencia MIT. El texto completo está en [LICENSE](LICENSE).
