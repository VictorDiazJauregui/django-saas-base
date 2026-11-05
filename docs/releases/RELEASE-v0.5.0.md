Pre-release. Organization API keys and webhooks on top of v0.4.0, the slug in the organization routes, and a check that warns about models that don't store their organization. All of it is off by default, but the webhook tables are recreated: read Breaking changes before you migrate.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/docs/releases/RELEASE-v0.5.0.es.md)

### Breaking changes

- [Webhook](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.md#webhooks) endpoints and deliveries now have a UUID as `id`. The migration recreates both tables, so the endpoints registered in v0.4.0 are deleted, even with multi-tenancy off. Write them down before migrating and add them again afterwards; each one gets a new secret.
- `Webhook-Id` and the `id` in the body of every delivery are a UUID string instead of a number. Receivers that store or compare it as a number have to change.

### Upgrading

Run `python manage.py migrate`: there are two migrations in `organizations`, one in `security` and one in `webhooks`. There are no new dependencies. The new variable in `.env.example` can stay as it is.

### Added

- [Id or slug in the route](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.md#id-or-slug-in-the-route): every route under `/api/v1/organizations/<organization>/` takes the `id` or the `slug`. The `id` is the stable one: changing the slug breaks the links saved with the old one.
- [Organization API keys](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.md#organization-api-keys) that belong to the organization, not to a person, and act with a role (`admin` or `member`). Admins create and revoke them in `/api-keys/` and in the admin. They need `TENANCY_ENABLED` and `API_KEYS_ENABLED`.
- [Organization webhooks](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.md#organization-webhooks): admins and owners add their own endpoints in `/webhooks/`, rotate the secret and read the deliveries. Each one receives only the events of its organization, up to `WEBHOOK_ORGANIZATION_ENDPOINT_LIMIT` endpoints (`10`). They need `TENANCY_ENABLED` and `WEBHOOKS_ENABLED`. Your apps send an event to one organization with `emit_webhook_event(..., organization=)`.

### Isolation check

- With `TENANCY_ENABLED=True`, `check`, `runserver` and the tests warn with `organizations.W001` about every model without a required `ForeignKey` to `Organization`, directly or through another model: its rows could be seen from any organization.
- Fix it by inheriting from `OrganizationScopedModel`, or from `GlobalModel` if every organization shares the model on purpose. The [README](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.0/README.md#isolation-check) has both cases.
- A project that already had its own models without an organization sees the warning after upgrading. It doesn't stop `runserver` or `migrate`, but `check --deploy --fail-level WARNING` fails.

### Changed

- New slugs use only lowercase letters, digits, `-` and `_`, and can't have the shape of a UUID. Existing slugs keep working.
- The audit log stores the `organization_id` and the key prefix of the actions made with an organization key.
- The tests run with a fast password hasher (`TEST_RUNNER`). A project with its own runner keeps it by overriding the setting.

### Fixed

- `compilemessages` failed on the Spanish catalog because two plural entries had two forms instead of three.

### Security

- An event of one organization never reaches the endpoints of another. An organization key can't manage organizations, members, keys or webhooks (`403`), and the webhook secret is shown only when it is created or rotated.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
