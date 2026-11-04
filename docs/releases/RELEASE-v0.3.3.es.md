Pre-release. Actualización de mantenimiento sobre la v0.3.2. Solo cambian las herramientas de desarrollo y la CI: la API, los comandos, las variables y los requirements de producción siguen iguales, así que un proyecto construido sobre la v0.3.2 solo tiene que reinstalar las dependencias de desarrollo.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.3/docs/releases/RELEASE-v0.3.3.md)

### Cambiado

- `coverage` 7.16.2 → 7.17.0 y `ruff` 0.17.1 → 0.17.3, las dos herramientas de desarrollo. El código pasa `ruff` 0.17.3 sin cambios.
- `astral-sh/setup-uv` 10.3.1 → 10.3.3 en la CI. Ahora pide la lista de versiones de uv al mirror de Astral antes de probar con GitHub.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
