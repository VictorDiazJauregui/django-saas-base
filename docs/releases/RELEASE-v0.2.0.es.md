Pre-release. La base ahora cubre todo el ciclo de vida de una cuenta en la API, se puede desplegar con su propia imagen de producción y endurece la configuración, la auditoría y el login. Varios cambios rompen la compatibilidad con la v0.1.x: leelos antes de actualizar.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.0/docs/releases/RELEASE-v0.2.0.md)

### Cambios que rompen compatibilidad

- El id del usuario ahora es un UUID aleatorio en vez de un entero, y el claim `user_id` del JWT es un string. Las migraciones iniciales se regeneraron, así que una base de la v0.1.x no migra: recreala con `docker compose down -v` y volvé a correr `migrate`.
- Los errores de validación pasaron de la raíz del body a `fields`. Todo error bajo `/api/` tiene ahora la forma `{"code", "detail", "fields"}`: leé `response.fields.email[0]` en vez de `response.email[0]`. Los errores de token ya no traen `messages`.
- El refresh token rota en cada uso y el anterior queda en la blacklist. El frontend tiene que guardar el `refresh` nuevo de cada response; reusar el viejo da `401`. Cambiar la contraseña también pone en la blacklist todos los refresh tokens de ese usuario.
- `POST /api/v1/auth/register/` siempre responde `201`, exista o no el email, y le manda un email al dueño de la cuenta existente. Un frontend que mostraba "ese email ya está registrado" con el `400` tiene que mostrar "revisá tu email".
- Las contraseñas pasan por una política configurable (largo, mayúscula, minúscula, dígito y símbolo). Contraseñas que antes pasaban ahora pueden dar `400`, y `create_admin_auto` rechaza un `ADMIN_PASSWORD` débil.
- `ENVIRONMENT` solo acepta `local`, `ci`, `staging` y `prod`. `staging` y `prod` exigen HTTPS y un `ALLOWED_HOSTS` explícito; con `ALLOWED_HOSTS='*'` ya no arranca.
- Las rutas de login, registro, contraseña y verificación de email tienen rate limit, y una cuenta queda bloqueada 15 minutos después de 5 logins fallidos desde la misma IP. Los dos casos responden `429` con `Retry-After`.
- Una ruta bajo `/api/` llamada sin la barra final responde `404` con el code `trailing_slash_required` en vez de un redirect `301`.

Para actualizar un proyecto construido sobre la v0.1.x: copiá las variables nuevas de `.env.example` a tu `.env`, recreá la base y adaptá el frontend a la forma de los errores, a la rotación del refresh y al `429`.

### Agregado

- `POST /api/v1/auth/logout/` y `GET`/`PATCH /api/v1/auth/me/`.
- `POST /api/v1/auth/password/change/`, reset de contraseña por email en dos pasos (`password/reset/` y `password/reset/confirm/`) y verificación de email opcional (`verify-email/` y `verify-email/resend/`, se activa con `REQUIRE_EMAIL_VERIFICATION`).
- Envío de emails configurado con `EMAIL_URL`, y `ALLOW_PUBLIC_REGISTRATION` para cerrar el registro público.
- Esquema OpenAPI 3 en `/api/schema/` y Swagger UI en `/api/docs/`: abiertos en `local` y `ci`, solo para staff en `staging` y `prod`.
- Roles declarados en `core/roles.py` y aplicados como grupos de Django con `sync_roles`, más las clases de permiso `HasPermission` y `HasRole`.
- `GET /api/v1/health/`, un `Dockerfile` de producción con gunicorn y whitenoise, y `DEPLOYMENT.md` en inglés y español.
- CORS para un frontend en otro dominio (`CORS_ALLOWED_ORIGINS`), y listados paginados por defecto (`API_PAGE_SIZE`, `API_MAX_PAGE_SIZE`).
- Logs en texto o JSON (`LOG_FORMAT`) con eventos de seguridad.
- Traducciones al español de los mensajes propios de la base, elegidas con `Accept-Language`.
- `purge_audit_logs` para borrar registros de auditoría viejos, y `create_admin_auto --update-password` para rotar la contraseña del admin en cada deploy.
- La auditoría guarda el status de la response, recorta los bodies grandes (`AUDIT_PAYLOAD_MAX_BYTES`) y registra los formularios sin leer los archivos subidos.
- `ruff` en la CI, reporte de cobertura, `pip-audit` sobre los requirements y configuración de Dependabot.

### Cambiado

- Los emails se guardan en minúsculas y son únicos sin distinguir mayúsculas. El login los acepta escritos de cualquier forma.
- El admin de auditoría es de solo lectura, y su listado ya no recorre toda la tabla en cada carga.
- La IP de la auditoría sale de `REMOTE_ADDR` y solo le cree a `X-Forwarded-For` hasta donde diga `TRUSTED_PROXY_COUNT`. Detrás de un proxy, poné la cantidad de proxies.
- Fuera de `DEBUG=True` la API responde solo JSON.
- Las conexiones a la base se reutilizan (`DB_CONN_MAX_AGE`) y PostgreSQL queda fijo en 18.6.
- La lista completa de variables nuevas está en `.env.example` y en la tabla [Variables de entorno](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.0/README.es.md#variables-de-entorno) del README.

### Seguridad

- Los system checks frenan un deploy que conserva los valores de ejemplo de `.env.example`, apaga HSTS o corre `staging`/`prod` sin HTTPS. La CI corre `check --deploy`.
- Las claves de credenciales como `api_key`, `otp` o `card_number` se censuran en la auditoría, y cada proyecto puede sumar las suyas con `AUDIT_EXTRA_SENSITIVE_KEYS`.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
