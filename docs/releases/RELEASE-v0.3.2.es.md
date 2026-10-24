Pre-release. Actualización de seguridad sobre la v0.3.1. No cambia nada en la API, los comandos ni las variables, así que un proyecto construido sobre la v0.3.1 solo tiene que reinstalar las dependencias.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.2/docs/releases/RELEASE-v0.3.2.md)

### Seguridad

- `django` 5.2.17 → 5.2.18 ([notas de la versión](https://docs.djangoproject.com/en/5.2/releases/5.2.18/)). Dos de sus arreglos alcanzan a esta base: un denial of service al parsear headers como `Accept` o `Content-Type` (CVE-2026-84429) y otro con códigos de idioma muy largos (CVE-2026-77050). El arreglo de los headers usa el parser de email de Python, así que necesita un patch reciente de Python: la 3.12.15, la de la imagen de Docker, lo tiene, y la 3.12.3 no.
- `pyproject.toml` ahora exige `django>=5.2.18`, así que un lock nuevo no puede volver a una versión vulnerable.

### Cambiado

- Dependabot salta Django 6.0 y 6.1, que no son LTS, y sigue proponiendo los parches de la 5.2. Django 6.2 LTS se va a proponer cuando salga.
- `astral-sh/setup-uv` 10.3.0 → 10.3.1 en la CI.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
