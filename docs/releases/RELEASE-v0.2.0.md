Pre-release. The base now covers the full account lifecycle in the API, can be deployed with its own production image, and hardens settings, auditing and login. Several changes break compatibility with v0.1.x: read them before you update.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.0/docs/releases/RELEASE-v0.2.0.es.md)

### Breaking changes

- The user id is now a random UUID instead of an integer, and the `user_id` claim of the JWT is a string. The initial migrations were regenerated, so a v0.1.x database does not migrate: recreate it with `docker compose down -v` and run `migrate` again.
- Validation errors moved from the root of the body to `fields`. Every error under `/api/` now has the shape `{"code", "detail", "fields"}`: read `response.fields.email[0]` instead of `response.email[0]`. Token errors no longer include `messages`.
- The refresh token rotates on every use and the old one is blacklisted. The frontend has to store the new `refresh` from each response; reusing the old one returns `401`. Changing a password also blacklists every refresh token of that user.
- `POST /api/v1/auth/register/` always returns `201`, whether the email exists or not, and emails the owner of an existing account. A frontend that showed "email already registered" from the `400` has to show "check your email" instead.
- Passwords go through a configurable policy (length, uppercase, lowercase, digit and symbol). Passwords that passed before can now return `400`, and `create_admin_auto` rejects a weak `ADMIN_PASSWORD`.
- `ENVIRONMENT` only accepts `local`, `ci`, `staging` and `prod`. `staging` and `prod` require HTTPS and an explicit `ALLOWED_HOSTS`; `ALLOWED_HOSTS='*'` no longer starts.
- Login, registration, password and email verification routes are rate limited, and an account is locked for 15 minutes after 5 failed logins from the same IP. Both answer `429` with `Retry-After`.
- A route under `/api/` called without its trailing slash returns `404` with code `trailing_slash_required` instead of a `301` redirect.

To update a project built on v0.1.x: copy the new variables from `.env.example` into your `.env`, recreate the database, and adapt the frontend to the error shape, the refresh rotation and `429`.

### Added

- `POST /api/v1/auth/logout/` and `GET`/`PATCH /api/v1/auth/me/`.
- `POST /api/v1/auth/password/change/`, password reset by email in two steps (`password/reset/` and `password/reset/confirm/`) and optional email verification (`verify-email/` and `verify-email/resend/`, enabled with `REQUIRE_EMAIL_VERIFICATION`).
- Email sending configured with `EMAIL_URL`, and `ALLOW_PUBLIC_REGISTRATION` to close the public registration.
- OpenAPI 3 schema at `/api/schema/` and Swagger UI at `/api/docs/`: open in `local` and `ci`, staff only in `staging` and `prod`.
- Roles declared in `core/roles.py` and applied as Django groups with `sync_roles`, plus the `HasPermission` and `HasRole` permission classes.
- `GET /api/v1/health/`, a production `Dockerfile` with gunicorn and whitenoise, and `DEPLOYMENT.md` in English and Spanish.
- CORS for a frontend on another domain (`CORS_ALLOWED_ORIGINS`), and paginated lists by default (`API_PAGE_SIZE`, `API_MAX_PAGE_SIZE`).
- Logs as text or JSON (`LOG_FORMAT`) with security events.
- Spanish translations for the base's own messages, selected with `Accept-Language`.
- `purge_audit_logs` to delete old audit records, and `create_admin_auto --update-password` to rotate the admin password on each deploy.
- The audit log stores the response status, caps large bodies (`AUDIT_PAYLOAD_MAX_BYTES`) and records form submissions without reading uploaded files.
- `ruff` in the CI, coverage report, `pip-audit` on the requirements and Dependabot configuration.

### Changed

- Emails are stored in lowercase and are unique regardless of case. Login accepts them in any case.
- The audit admin is read-only, and its list no longer scans the whole table on each load.
- The audit IP comes from `REMOTE_ADDR` and trusts `X-Forwarded-For` only as far as `TRUSTED_PROXY_COUNT` says. Behind a proxy, set it to the number of proxies.
- Outside `DEBUG=True` the API answers JSON only.
- Database connections are reused (`DB_CONN_MAX_AGE`) and PostgreSQL is pinned to 18.6.
- The full list of new variables is in `.env.example` and in the [Environment variables](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.0/README.md#environment-variables) table of the README.

### Security

- System checks stop a deploy that keeps the example values of `.env.example`, disables HSTS or runs `staging`/`prod` without HTTPS. The CI runs `check --deploy`.
- Credential keys such as `api_key`, `otp` or `card_number` are redacted in the audit log, and each project can add its own with `AUDIT_EXTRA_SENSITIVE_KEYS`.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
