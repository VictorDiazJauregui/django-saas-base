Pre-release. Maintenance update on top of v0.3.2. Only the development tools and the CI change: the API, the commands, the variables and the production requirements stay the same, so a project built on v0.3.2 only has to reinstall the development dependencies.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.3/docs/releases/RELEASE-v0.3.3.es.md)

### Changed

- `coverage` 7.16.2 → 7.17.0 and `ruff` 0.17.1 → 0.17.3, both development tools. The code passes `ruff` 0.17.3 without changes.
- `astral-sh/setup-uv` 10.3.1 → 10.3.3 in the CI. It now gets the list of uv versions from Astral's mirror before trying GitHub.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
