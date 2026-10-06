# Levantar el proyecto en local

[English](LOCAL-SETUP.md) · [Español](LOCAL-SETUP.es.md)

Guía operativa: qué corre, en qué puerto, con qué comandos y cómo comprobar que quedó arriba. Los comandos están en **bash / zsh**; las variantes para PowerShell y cmd, y la instalación de las herramientas en cada sistema, están en el [README](README.es.md).

---

## 1. Tecnologías

| Pieza | Tecnología | Dónde corre |
|---|---|---|
| Aplicación | Django 5.2 LTS + Django REST Framework + JWT, sobre Python 3.12 o superior | En la máquina, dentro de `.venv` |
| Base de datos | PostgreSQL 18 | En Docker, servicio `db` de `docker-compose.yml` |
| Dependencias | `uv` (`pyproject.toml` + `uv.lock`) | — |

No hay frontend: la interfaz web disponible es el panel de administración de Django.

---

## 2. Puertos

| Servicio | Variable | Valor por omisión | Quién lo consume |
|---|---|---|---|
| PostgreSQL | `DB_PORT` | `5432` | Django |
| Django | `APP_PORT` | `8000` | El navegador y los clientes de la API |

Los dos puertos se definen **una sola vez**, en `.env`. Compose usa `DB_PORT` para publicar la base y Django usa el mismo valor para conectarse, así que al cambiarlo no hay nada más que alinear.

---

## 3. Archivo de entorno

| Archivo | ¿Versionado? | Plantilla | Quién lo lee |
|---|---|---|---|
| `.env` | No | `.env.example` | Docker Compose, de forma automática, y Django, desde `core/settings.py` |

No hace falta cargar el `.env` en la terminal: ni Compose ni Django lo necesitan.

Crearlo:

```bash
cp .env.example .env
```

Después hay que editar, como mínimo, `COMPOSE_PROJECT_NAME`, `DB_CONTAINER_NAME`, `SECRET_KEY`, `DB_PASSWORD` y `ADMIN_PASSWORD`. El detalle de cada variable está en el [README](README.es.md#variables-de-entorno).

Para consultar un valor **sin mostrar el archivo entero** (contiene contraseñas):

```bash
grep '^APP_PORT=' .env | cut -d= -f2-
```

---

## 4. Levantar

Siempre desde la raíz del proyecto, en este orden:

```bash
docker compose up -d --wait
uv sync
uv run python manage.py migrate
uv run python manage.py create_admin_auto
uv run python manage.py runserver
```

| Comando | Qué hace |
|---|---|
| `docker compose up -d --wait` | Levanta PostgreSQL y espera a que acepte conexiones |
| `uv sync` | Crea `.venv` e instala las versiones exactas de `uv.lock` |
| `migrate` | Crea o actualiza las tablas |
| `create_admin_auto` | Crea el superusuario de prueba; si ya existe, no lo duplica |
| `runserver` | Inicia el servidor en el puerto de `APP_PORT` |

`runserver` ocupa la terminal. Para detenerlo: `Ctrl + C`.

---

## 5. Usuario de prueba

| Dato | Valor |
|---|---|
| Email | El de `ADMIN_EMAIL` en `.env` |
| Contraseña | La de `ADMIN_PASSWORD` en `.env` |
| Rol | Superusuario |

**La contraseña no se escribe en ningún documento.** Para leerla:

```bash
grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-
```

Si el usuario no existe, se crea con `uv run python manage.py create_admin_auto`.

---

## 6. Comprobar que todo levantó

Con el servidor iniciado, en otra terminal:

```bash
docker compose ps
uv run python manage.py migrate --check
APP_PORT=$(grep '^APP_PORT=' .env | cut -d= -f2-)
curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:${APP_PORT}/admin/login/"
```

| Comprobación | Resultado correcto |
|---|---|
| `docker compose ps` | El servicio `db` figura como `healthy` |
| `manage.py migrate --check` | Termina sin mensajes: Django se conecta a la base y no quedan migraciones pendientes |
| `curl` al panel | `200` |

> Para saber si Django llega a la base hay que usar `migrate --check`. `manage.py check` no abre ninguna conexión: termina bien aunque la base esté apagada o la contraseña sea incorrecta.

---

## 7. Si un puerto está ocupado

1. Identificar quién lo usa:

   ```bash
   ss -ltnp | grep ':5432'
   ```

2. Decidir entre detener ese proceso o cambiar el puerto del proyecto.
3. Para cambiarlo, editar `DB_PORT` o `APP_PORT` en `.env`. No hay otro archivo que tocar.
4. Si se cambió `DB_PORT`, recrear el contenedor para que publique el puerto nuevo:

   ```bash
   docker compose up -d --wait
   ```

Los datos no se pierden: viven en el volumen, no en el contenedor.

---

## 8. Apagar

| Objetivo | Comando |
|---|---|
| Detener la base **conservando los datos** | `docker compose down` |
| Detener la base **y borrar los datos** | `docker compose down -v` |

---

## 9. Tests

Necesitan la base levantada: Django crea y elimina una base temporal para correrlos.

```bash
uv run python manage.py test
uv run black --check .
```

---

## 10. Errores frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `required variable ... is missing a value` | Falta el `.env` o una de sus variables | Crear el `.env` o completar la variable |
| `Conflict. The container name ... is already in use` | Otro proyecto usa el mismo `DB_CONTAINER_NAME` | Cambiarlo en `.env` |
| `port is already allocated` | `DB_PORT` ocupado | Sección 7 |
| `Error: That port is already in use.` | `APP_PORT` ocupado | Sección 7 |
| `password authentication failed for user` | Se cambiaron las credenciales después de crear la base | PostgreSQL solo las aplica al crear el volumen: volver a las anteriores o recrear con `docker compose down -v` |
| `Conflict. The container name ... is already in use` después de cambiar `COMPOSE_PROJECT_NAME` | Con otro nombre de proyecto, Compose intenta crear un contenedor nuevo con el mismo nombre. El volumen de datos también cambiaría | Volver al nombre anterior. El conflicto es lo que evita levantar sobre un volumen vacío |

La lista completa, incluidos los casos propios de Windows y Docker Desktop, está en el [README](README.es.md#solución-de-problemas).
