Pre-release. API keys y webhooks de cada organización sobre la v0.4.0, el slug en las rutas de organizaciones y un chequeo que avisa de los modelos que no guardan su organización. Todo viene apagado, pero las tablas de webhooks se vuelven a crear: leé Cambios que rompen antes de migrar.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/docs/releases/RELEASE-v0.5.0.md)

### Cambios que rompen

- Los destinos y las entregas de [webhooks](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.es.md#webhooks) ahora tienen un UUID como `id`. La migración vuelve a crear las dos tablas, así que los destinos cargados en la v0.4.0 se borran, también con el multi-tenancy apagado. Anotalos antes de migrar y volvé a darlos de alta después; cada uno recibe un secreto nuevo.
- `Webhook-Id` y el `id` del cuerpo de cada envío son un UUID en texto en vez de un número. Los receptores que lo guardan o lo comparan como número tienen que cambiar.

### Cómo actualizar

Corré `python manage.py migrate`: hay dos migraciones en `organizations`, una en `security` y una en `webhooks`. No hay dependencias nuevas. La variable nueva de `.env.example` puede quedar como está.

### Agregado

- [Id o slug en la ruta](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.es.md#id-o-slug-en-la-ruta): todas las rutas bajo `/api/v1/organizations/<organization>/` aceptan el `id` o el `slug`. El `id` es el estable: cambiar el slug rompe los links guardados con el viejo.
- [API keys de organización](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.es.md#api-keys-de-organización) que pertenecen a la organización, no a una persona, y actúan con un rol (`admin` o `member`). Los admins las crean y las revocan en `/api-keys/` y en el admin. Necesitan `TENANCY_ENABLED` y `API_KEYS_ENABLED`.
- [Webhooks de la organización](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.es.md#webhooks-de-la-organización): admins y owners dan de alta sus destinos en `/webhooks/`, rotan el secreto y leen las entregas. Cada destino recibe solo los eventos de su organización, hasta `WEBHOOK_ORGANIZATION_ENDPOINT_LIMIT` destinos (`10`). Necesitan `TENANCY_ENABLED` y `WEBHOOKS_ENABLED`. Tus apps mandan un evento a una organización con `emit_webhook_event(..., organization=)`.

### Chequeo de aislamiento

- Con `TENANCY_ENABLED=True`, `check`, `runserver` y los tests avisan con `organizations.W001` de cada modelo sin una `ForeignKey` obligatoria a `Organization`, directa o a través de otro modelo: sus filas se podrían ver desde cualquier organización.
- Se resuelve heredando de `OrganizationScopedModel`, o de `GlobalModel` si todas las organizaciones comparten el modelo a propósito. El [README](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.es.md#chequeo-de-aislamiento) tiene los dos casos.
- Un proyecto que ya tenía modelos propios sin organización ve el aviso después de actualizar. No frena `runserver` ni `migrate`, pero `check --deploy --fail-level WARNING` falla.

### Cambiado

- Los slugs nuevos usan solo minúsculas, dígitos, `-` y `_`, y no pueden tener forma de UUID. Los existentes siguen funcionando.
- La auditoría guarda el `organization_id` y el prefijo de la clave en las acciones hechas con una clave de organización.
- Los tests corren con un hasher de contraseñas rápido (`TEST_RUNNER`). Un proyecto con su propio runner lo conserva pisando el setting.

### Corregido

- `compilemessages` fallaba con el catálogo en español porque dos textos en plural tenían dos formas en vez de tres.

### Seguridad

- Un evento de una organización nunca llega a los destinos de otra. Una clave de organización no puede gestionar organizaciones, miembros, claves ni webhooks (`403`), y el secreto de un webhook se muestra solo al crearlo o rotarlo.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
