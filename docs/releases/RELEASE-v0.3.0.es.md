Pre-release. Módulos opcionales sobre la v0.2.1: API keys, autenticación en dos pasos, login con Google, webhooks salientes, envío de emails por la API del proveedor y modelos base para tus propias apps. Todos vienen apagados, así que con el mismo `.env` la API responde igual que en la v0.2.1.

[English](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/docs/releases/RELEASE-v0.3.0.md)

### Cómo actualizar

Instalá las dependencias nuevas (`uv sync`, o `python -m pip install -r requirements.txt`) y corré `python manage.py migrate`: hay tres migraciones nuevas en `security` y una app nueva, `webhooks`. Las variables nuevas de `.env.example` pueden quedar vacías.

### Agregado

- [API keys](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.es.md#api-keys) para llamadas entre servidores, con `Authorization: Api-Key <key>`. Se crean y se revocan en el admin, se muestran una sola vez, se guardan como hash y actúan como el usuario al que pertenecen. Se encienden con `API_KEYS_ENABLED`.
- [Autenticación en dos pasos](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.es.md#autenticación-en-dos-pasos) con una app de autenticación y códigos de recuperación, en la API y en el login del admin. Con `TOTP_ENABLED=True`, `login/` responde `mfa_required` y un `mfa_token` a los usuarios que la activaron, y el login termina en `login/2fa/`. Necesita `TOTP_ENCRYPTION_KEY`.
- [Login con Google](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.es.md#login-con-google): `POST /api/v1/auth/google/` recibe el `id_token` de Google Identity Services y responde como el login por email. Se enciende con `GOOGLE_CLIENT_IDS`.
- [Webhooks](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.es.md#webhooks): un `POST` firmado a cada endpoint registrado en el admin, con reintentos y un registro de entregas. La base emite `user.registered` y `user.email_verified`, y tus apps pueden emitir sus propios eventos con `emit_webhook_event()`. El worker `deliver_webhooks` los manda y [`purge_webhook_deliveries`](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.es.md#purga-de-entregas-viejas) borra los viejos. Se encienden con `WEBHOOKS_ENABLED`.
- [Envío de emails por la API del proveedor](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.es.md#envío-por-la-api-del-proveedor) con anymail, como alternativa a SMTP: configurá `EMAIL_PROVIDER` y las variables `ANYMAIL_*` de tu proveedor. Si falta la API key, el servidor no arranca.
- [Modelos base](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.es.md#modelos-base) `TimestampedModel` y `SoftDeleteModel`, para heredar en tus propias apps.

### Cambiado

- Dependencias nuevas: `django-anymail`, `pyotp` y `cryptography`.
- [DEPLOYMENT.es.md](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/DEPLOYMENT.es.md#worker-de-webhooks) suma el worker de webhooks, y la purga de entregas viejas a las tareas programadas.

### Seguridad

- La auditoría también censura `recovery_code`. Los secretos del segundo factor se cifran con su propia clave, y en `staging` y `prod` se rechazan los receptores de webhooks con direcciones privadas.

### Requisitos

Python 3.12 o posterior · Docker con Compose v2.

### Licencia

MIT.
