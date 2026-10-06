Pre-release. La base ya está abierta a contribuciones: tiene guía de contribución, política de seguridad, plantillas de issues y de pull request, y CI en cada pull request. No cambió el código de la aplicación, la API ni los comandos, así que un proyecto construido sobre la v0.1.0 no tiene nada que actualizar.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.1.1/docs/releases/RELEASE-v0.1.1.md)

### Agregado

- `CONTRIBUTING.md` y `SECURITY.md`, en inglés y en español: entorno local, checks antes de un pull request, estilo de código, flujo de ramas, formato de commits y cómo reportar una vulnerabilidad en privado.
- Plantillas de issues para bugs y feature requests, y plantilla de pull request.
- CI en GitHub Actions en cada pull request y en cada push a `main` y `staging`: lockfile, archivos de requirements, `black`, migraciones pendientes y la suite de tests contra PostgreSQL 18.
- Un check que solo acepta pull requests hacia `main` desde `staging` o `hotfix/*`.

### Cambios

- El README ahora está en inglés, con la versión en español en `README.es.md`.
- `LEVANTAR-LOCAL.md` ahora es `LOCAL-SETUP.md`, en inglés, con `LOCAL-SETUP.es.md` al lado. Actualizá cualquier enlace al nombre anterior.

### Requisitos

Python 3.12 o superior · Docker con Compose v2.

### Licencia

MIT.
