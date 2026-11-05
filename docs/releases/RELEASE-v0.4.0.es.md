Pre-release. Multi-tenancy opcional sobre la v0.3.3: organizaciones con miembros y roles, invitaciones por email, y las piezas para mantener separados los datos de cada organización en tus propias apps. Viene apagado, así que con el mismo `.env` la API responde igual que en la v0.3.3.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/docs/releases/RELEASE-v0.4.0.md)

### Cómo actualizar

Corré `python manage.py migrate`: hay una app nueva, `organizations`, con dos migraciones. No hay dependencias nuevas. Las variables nuevas de `.env.example` pueden quedar como están mientras `TENANCY_ENABLED=False`.

### Agregado

- [Multi-tenancy](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.es.md#multi-tenancy), que se enciende con `TENANCY_ENABLED=True`. Un usuario puede pertenecer a varias organizaciones, con un rol en cada una: `owner`, `admin` o `member`. Toda organización conserva al menos un owner.
- [API de organizaciones y miembros](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.es.md#api-de-organizaciones-y-miembros) bajo `/api/v1/organizations/`: listar las tuyas, crear una, renombrarla, listar sus miembros, cambiarles el rol, sacarlos o salir. Las organizaciones se borran solo desde el admin.
- [Invitaciones](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.es.md#invitaciones) por email. El link apunta a `FRONTEND_INVITATION_URL`, obligatoria con el módulo encendido. La persona invitada acepta con su cuenta o la crea desde el link, también con el registro público cerrado. Los tokens se guardan como hash, funcionan una vez y vencen a las `TENANCY_INVITATION_TIMEOUT_HOURS`.
- [Modelos de una organización](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.es.md#modelos-de-una-organización) para tus apps: heredá `OrganizationScopedModel` y usá `OrganizationScopedViewSet`, y cada consulta solo ve las filas de la organización de la URL. `IsOrganizationMember` y `HasOrganizationRole` protegen cualquier otra vista.
- [Eventos de webhooks](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.es.md#eventos-de-webhooks) `organization.created`, `organization.member_added` y `organization.member_removed`.
- Pantallas del admin para las organizaciones, sus miembros y las invitaciones, que se revocan desde el listado.

### Cambiado

- Un límite nuevo, `THROTTLE_INVITATION_RATE` (`10/h`), para las rutas públicas de invitaciones.
- [DEPLOYMENT.es.md](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/DEPLOYMENT.es.md#2-variables) lista las variables de multi-tenancy, y [CONTRIBUTING.es.md](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/CONTRIBUTING.es.md#tests) pide un test de aislamiento en cada vista que trabaja sobre las filas de una organización.

### Seguridad

- Una organización que no existe y una de la que el usuario no es miembro reciben el mismo `404`, y lo mismo pasa con los tokens de invitación inexistentes, vencidos, revocados o usados. La auditoría oculta los tokens de invitación.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
