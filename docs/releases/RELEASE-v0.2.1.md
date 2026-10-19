Pre-release. Fixes and dependency updates on top of v0.2.0. Nothing changes in the API, the commands or the variables, so a project built on v0.2.0 has nothing to update.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.1/docs/releases/RELEASE-v0.2.1.es.md)

### Fixed

- The [Renaming the project](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.2.1/README.md#renaming-the-project) guide listed a `core/tests.py` that no longer exists and missed most references to `core`. It now gives a command that lists all of them, without `django.core`.
- A test request in Spanish left Spanish active for the tests that ran after it. With another test order, for example after renaming `core`, a test that expected an English message failed.
- Dependabot opened pull requests for transitive packages that changed only the requirements files, and the CI failed on them with no way to fix them. It now updates only the packages declared in `pyproject.toml`, and groups the minor and patch updates in one pull request a week.

### Changed

- `djangorestframework` 3.18.1 → 3.18.3, `ruff` 0.16.10 → 0.17.1 and `astral-sh/setup-uv` 10.2.0 → 10.3.0 in the CI.
- The release notes of v0.1.0 are now in `docs/releases/`, in English and Spanish.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
