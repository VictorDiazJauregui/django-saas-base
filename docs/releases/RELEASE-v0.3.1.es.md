Pre-release. Actualización de seguridad sobre la v0.3.0. No cambia nada en la API, los comandos ni las variables, así que un proyecto construido sobre la v0.3.0 solo tiene que reinstalar las dependencias de desarrollo.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.1/docs/releases/RELEASE-v0.3.1.md)

### Seguridad

- `black` 25.12.0 → 26.10.1, una herramienta de desarrollo. La 25.12.0 podía escribir su archivo de caché fuera de la carpeta de caché si alguien controlaba `--python-cell-magics` ([CVE-2026-32274](https://github.com/advisories/GHSA-3936-cmfr-pm3m)). Los requirements de producción y la imagen de Docker no incluyen `black`.
- La CI ahora corre `pip-audit` sobre `requirements-dev.txt` además de `requirements.txt`, así que una herramienta de desarrollo vulnerable también hace fallar el build.

### Cambiado

- `manage.py` sigue el estilo de black 26: una línea en blanco después del docstring del módulo.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
