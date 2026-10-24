Pre-release. Security update on top of v0.3.1. Nothing changes in the API, the commands or the variables, so a project built on v0.3.1 only has to reinstall the dependencies.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.2/docs/releases/RELEASE-v0.3.2.es.md)

### Security

- `django` 5.2.17 → 5.2.18 ([release notes](https://docs.djangoproject.com/en/5.2/releases/5.2.18/)). Two of its fixes reach this base: a denial of service when parsing headers such as `Accept` or `Content-Type` (CVE-2026-84429) and another with very long language codes (CVE-2026-77050). The header fix relies on Python's email parser, so it needs a recent Python patch release: 3.12.15, the one in the Docker image, has it, and 3.12.3 does not.
- `pyproject.toml` now requires `django>=5.2.18`, so a fresh lock can't go back to a vulnerable version.

### Changed

- Dependabot skips Django 6.0 and 6.1, which are not LTS releases, and keeps proposing the 5.2 patches. Django 6.2 LTS is still proposed when it comes out.
- `astral-sh/setup-uv` 10.3.0 → 10.3.1 in the CI.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
