Pre-release. Actualización de seguridad y mantenimiento sobre la v0.5.0. No cambia nada en la API, los comandos ni las variables, y no hay migraciones nuevas, así que un proyecto construido sobre la v0.5.0 solo tiene que reinstalar las dependencias.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.1/docs/releases/RELEASE-v0.5.1.md)

### Seguridad

- `django` 5.2.18 → 5.2.19 ([notas de la versión](https://docs.djangoproject.com/en/5.2/releases/5.2.19/)). Uno de sus cinco arreglos alcanza a esta base: una parte `multipart/form-data` enviada con `Content-Transfer-Encoding: base64` se cargaba entera en memoria, sin respetar `FILE_UPLOAD_MAX_MEMORY_SIZE` (CVE-2026-108147). Todos los endpoints de la API aceptan cuerpos multipart, porque la base deja los parsers por defecto de DRF. Los otros cuatro arreglos son de `django.contrib.gis` y del middleware de cache, que la base no usa.
- `pyproject.toml` ahora exige `django>=5.2.19`, así que un lock nuevo no puede volver a una versión vulnerable.

### Cambiado

- `django-axes` 8.3.1 → 9.0.0. Trunca los usernames más largos que su campo (255 caracteres) antes de contar los intentos; los emails tienen como mucho 254, así que el bloqueo funciona igual que antes. Sus migraciones no cambian.
- `psycopg[binary]` 3.3.6 → 3.3.9, con arreglos de bugs del driver. `pyproject.toml` ahora exige `psycopg[binary]>=3.3.9`.
- `coverage` 7.17.0 → 7.17.2, `ipython` 9.17.1 → 9.18.1 y `ruff` 0.17.3 → 0.17.4, todas herramientas de desarrollo. El código pasa `ruff` 0.17.4 sin cambios.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
