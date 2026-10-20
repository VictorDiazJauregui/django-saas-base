Pre-release. Optional modules on top of v0.2.1: API keys, two-factor authentication, login with Google, outgoing webhooks, email through a provider's API, and base models for your own apps. All of them are off by default, so with the same `.env` the API answers as in v0.2.1.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/docs/releases/RELEASE-v0.3.0.es.md)

### Upgrading

Install the new dependencies (`uv sync`, or `python -m pip install -r requirements.txt`) and run `python manage.py migrate`: there are three new migrations in `security` and a new `webhooks` app. The new variables in `.env.example` can stay empty.

### Added

- [API keys](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.md#api-keys) for server-to-server calls, sent as `Authorization: Api-Key <key>`. They are created and revoked in the admin, shown once, stored as a hash, and act as the user they belong to. Turn them on with `API_KEYS_ENABLED`.
- [Two-factor authentication](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.md#two-factor-authentication) with an authenticator app and recovery codes, in the API and the admin login. With `TOTP_ENABLED=True`, `login/` answers `mfa_required` and an `mfa_token` for a user who turned it on, and the login finishes in `login/2fa/`. It needs `TOTP_ENCRYPTION_KEY`.
- [Login with Google](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.md#login-with-google): `POST /api/v1/auth/google/` takes the `id_token` from Google Identity Services and answers like the email login. Set `GOOGLE_CLIENT_IDS` to turn it on.
- [Webhooks](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.md#webhooks): a signed `POST` to each endpoint registered in the admin, with retries and a delivery log. The base emits `user.registered` and `user.email_verified`, and your apps can emit their own with `emit_webhook_event()`. The `deliver_webhooks` worker sends them and [`purge_webhook_deliveries`](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.md#purging-old-deliveries) deletes old ones. Turn them on with `WEBHOOKS_ENABLED`.
- [Email through a provider's API](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.md#sending-through-a-providers-api) with anymail, as an alternative to SMTP: set `EMAIL_PROVIDER` and the `ANYMAIL_*` variables of your provider. A missing API key stops the server at startup.
- [Base models](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/README.md#base-models) `TimestampedModel` and `SoftDeleteModel`, to inherit in your own apps.

### Changed

- New dependencies: `django-anymail`, `pyotp` and `cryptography`.
- [DEPLOYMENT.md](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.0/DEPLOYMENT.md#webhook-worker) adds the webhook worker, and the purge of old deliveries to the scheduled tasks.

### Security

- The audit log also redacts `recovery_code`. Two-factor secrets are encrypted with their own key, and webhook receivers on private addresses are refused in `staging` and `prod`.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
