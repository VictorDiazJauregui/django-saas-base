Pre-release. Arreglos y actualizaciones de dependencias sobre la v0.2.0. No cambia nada en la API, los comandos ni las variables, así que un proyecto construido sobre la v0.2.0 no tiene nada que actualizar.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.1/docs/releases/RELEASE-v0.2.1.md)

### Corregido

- La guía [Renombrar el proyecto](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.1/README.es.md#renombrar-el-proyecto) nombraba un `core/tests.py` que ya no existe y omitía la mayoría de las referencias a `core`. Ahora da un comando que las lista todas, sin `django.core`.
- Un test que hacía una request en español dejaba el español activo para los tests que corrían después. Con otro orden de tests, por ejemplo después de renombrar `core`, fallaba un test que esperaba un mensaje en inglés.
- Dependabot abría pull requests de paquetes transitivos que cambiaban solo los archivos de requirements, y la CI fallaba sin forma de arreglarlas. Ahora actualiza solo los paquetes declarados en `pyproject.toml` y agrupa las actualizaciones minor y patch en un pull request por semana.

### Cambiado

- `djangorestframework` 3.18.1 → 3.18.3, `ruff` 0.16.10 → 0.17.1 y `astral-sh/setup-uv` 10.2.0 → 10.3.0 en la CI.
- Las notas de la v0.1.0 ahora están en `docs/releases/`, en inglés y en español.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
