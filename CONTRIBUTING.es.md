# Cómo contribuir a django-saas-base

[English](CONTRIBUTING.md) · [Español](CONTRIBUTING.es.md)

Los reportes de bugs, las ideas y los pull requests son bienvenidos. Podés escribir los issues y los
pull requests en español o en inglés.

Este proyecto es una base que otros clonan para construir encima. Todo lo que se agrega acá termina
en cada proyecto que nace de ella, así que una dependencia, una app o un setting nuevo tiene que
servirle a la mayoría de los proyectos, no a uno solo.

## Issues

Antes de abrir uno, buscá entre los issues abiertos por si alguien ya reportó lo mismo.

- **Bug.** Usá la plantilla de bug. Incluí el commit o la versión, tu sistema operativo, cómo
  ejecutás Python (`uv` o `pip`), qué esperabas y qué pasó.
- **Feature o cambio.** Usá la plantilla de feature request y describí el problema antes que la
  solución. Para algo más grande que un fix chico, abrí el issue antes de escribir código así
  acordamos el enfoque.
- **Pregunta.** Abrí un issue común.

Los problemas de seguridad no se reportan en un issue público. Ver [SECURITY.es.md](SECURITY.es.md).

## Entorno local

Necesitás Python 3.12 o superior, [uv](https://docs.astral.sh/uv/) y Docker con Compose v2. El
[README](README.es.md) explica Linux, WSL y Windows en detalle.

```bash
git clone https://github.com/VictorDiazJauregui/django-saas-base.git
cd django-saas-base
cp .env.example .env            # después completá las contraseñas y SECRET_KEY
docker compose up -d --wait
uv sync
uv run python manage.py migrate
uv run python manage.py create_admin_auto
uv run python manage.py runserver
```

El admin queda en `http://localhost:8000/admin/` y la API bajo `http://localhost:8000/api/v1/`.

## Antes de abrir un pull request

Corré los mismos checks que la CI, con la base levantada:

```bash
uv run black --check .
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test
```

Si cambiaste una dependencia, regenerá los dos archivos de requirements y commitealos junto con
`pyproject.toml` y `uv.lock`:

```bash
uv export --no-dev --no-hashes -o requirements.txt
uv export --no-hashes -o requirements-dev.txt
```

## Estilo de código

`black` formatea el código. El resto se revisa en el review:

- Cada función hace una sola cosa, tiene como máximo 20 líneas y 3 parámetros (sin contar `self` ni
  `cls`). Si hacen falta más, se agrupan en un objeto.
- Early returns en vez de `if`/`else` anidados. Como máximo dos niveles de anidación.
- Nombres en inglés que digan qué es o qué hace cada cosa. Nada de `utils`, `helpers`, `manager` o
  `data` como cajón de sastre.
- Las views orquestan. Las reglas de negocio van en funciones o services que se puedan testear sin
  HTTP; los serializers validan y dan forma a los datos.
- Se capturan excepciones específicas. Nunca un `except` desnudo ni uno que se trague el error.
- Los comentarios explican el porqué, no el qué. Nada de código comentado, imports sin usar ni
  `print`.
- Nada de secretos, credenciales ni valores de un proyecto concreto en el código. Un setting nuevo
  sale del entorno: se agrega a `.env.example` y a la tabla de variables del README.
- Todo texto visible para el usuario pasa por `gettext_lazy`.

## Tests

Los tests viven en `<app>/tests/` y usan el test runner de Django (`django.test.TestCase` y el
`APITestCase` de DRF). Necesitan PostgreSQL levantado, porque Django crea y borra una base de test.

- Un fix viene con un test que falla sin el fix.
- Una feature nueva viene con tests del camino principal, de los errores de validación y de los
  permisos (usuario anónimo, usuario sin permiso, usuario con permiso).
- Un cambio de modelo viene con su migración. `makemigrations --check` no tiene que detectar nada.
- Un campo sensible nuevo (password, token, key) tiene que quedar cubierto por
  `security/redaction.py`, con su test, para que nunca llegue en claro al audit log.

## Cambios en la API

Las rutas bajo `/api/v1/`, los campos de request y response, los status codes y los permisos son un
contrato con cada proyecto construido sobre esta base. Si tu cambio altera alguno, decilo en el pull
request y explicá qué tiene que cambiar un cliente. Los breaking changes salen en una versión minor
mientras el proyecto esté en `0.x`.

## Documentación

La documentación pasa a tener el inglés como idioma principal, con una copia en español (`*.es.md`)
al lado de cada archivo. En la copia en español los términos técnicos quedan en inglés (endpoint,
payload, token, merge). Si cambiás un comportamiento, actualizá las dos; si solo escribís una,
decilo en el pull request.

Corto y concreto. Cada comando de la documentación tiene que funcionar tal cual está escrito.

## Ramas, commits y pull requests

- Creá la rama desde `staging` y abrí el pull request contra `staging`. `main` solo recibe releases.
- Nombre de rama: `<tipo>/<descripcion-corta>`, por ejemplo `fix/audit-log-read-only`. Tipos:
  `feat`, `fix`, `refac`, `docs`, `test`, `chore`.
- Mensajes de commit en inglés, una oración corta que empieza con un prefijo en mayúsculas: `FEAT`,
  `FIX`, `REFAC`, `DOC`, `TEST`, `CHORE`, `CI`, `SEC` o `DEL`. Por ejemplo
  `FIX: keep audit log read only in admin`. El asunto, en menos de 50 caracteres.
- Un commit por cambio lógico. Una migración va en el mismo commit que el cambio de modelo.
- Títulos de pull request con la forma `TIPO(ámbito): Descripción`, por ejemplo
  `FIX(admin): Make the audit log read only`.
- Cada pull request trata una sola cosa y completa la plantilla.

## Releases

Las versiones siguen [Semantic Versioning](https://semver.org/lang/es/). Una release es un pull
request de `staging` a `main` que sube `version` en `pyproject.toml`, seguido de un tag `vX.Y.Z`
sobre `main` y una GitHub release con las notas.

## Licencia

El proyecto se distribuye bajo la [licencia MIT](LICENSE). Al enviar una contribución aceptás que se
publique bajo la misma licencia.
