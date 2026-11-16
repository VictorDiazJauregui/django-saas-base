Pre-release. Security and maintenance update on top of v0.5.0. Nothing changes in the API, the commands or the variables, and there are no new migrations, so a project built on v0.5.0 only has to reinstall the dependencies.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.5.1/docs/releases/RELEASE-v0.5.1.es.md)

### Security

- `django` 5.2.18 → 5.2.19 ([release notes](https://docs.djangoproject.com/en/5.2/releases/5.2.19/)). One of its five fixes reaches this base: a `multipart/form-data` part sent with `Content-Transfer-Encoding: base64` was buffered whole in memory, ignoring `FILE_UPLOAD_MAX_MEMORY_SIZE` (CVE-2026-108147). Every API endpoint accepts multipart bodies, because the base keeps the default DRF parsers. The other four fixes are in `django.contrib.gis` and in the cache middleware, which the base doesn't use.
- `pyproject.toml` now requires `django>=5.2.19`, so a fresh lock can't go back to a vulnerable version.

### Changed

- `django-axes` 8.3.1 → 9.0.0. It truncates usernames longer than its field (255 characters) before counting attempts; emails are at most 254, so the lockout works as before. Its migrations don't change.
- `psycopg[binary]` 3.3.6 → 3.3.9, with bug fixes in the driver. `pyproject.toml` now requires `psycopg[binary]>=3.3.9`.
- `coverage` 7.17.0 → 7.17.2, `ipython` 9.17.1 → 9.18.1 and `ruff` 0.17.3 → 0.17.4, all development tools. The code passes `ruff` 0.17.4 without changes.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
