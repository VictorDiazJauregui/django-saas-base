# Política de seguridad

[English](SECURITY.md) · [Español](SECURITY.es.md)

## Versiones con soporte

El proyecto está en `0.x`. Solo la última release en `main` recibe fixes de seguridad.

## Reportar una vulnerabilidad

No abras un issue público. Usá **Report a vulnerability** en la
[pestaña Security](https://github.com/VictorDiazJauregui/django-saas-base/security/advisories/new)
del repositorio, que abre un reporte privado.

Incluí qué está afectado (endpoint, setting, comando), cómo reproducirlo y qué impacto ves. La
respuesta llega en 7 días como máximo. Cuando haya un fix, sale en una release y el advisory se
publica con tu crédito, salvo que prefieras lo contrario.

## Alcance

Dentro del alcance: el código de este repositorio y sus valores por defecto (settings, archivo de
Docker Compose, censura del audit log, endpoints de autenticación).

Fuera del alcance: vulnerabilidades de Django, Django REST Framework u otras dependencias
(reportalas en sus proyectos) y problemas causados por un proyecto que cambió los valores por
defecto después de clonar la base.
