Pre-release. The base is now open to contributions: it has a contributing guide, a security policy, issue and pull request templates, and CI on every pull request. The application code, the API and the commands did not change, so a project built on v0.1.0 has nothing to update.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.1.1/docs/releases/RELEASE-v0.1.1.es.md)

### Added

- `CONTRIBUTING.md` and `SECURITY.md`, in English and Spanish: local setup, checks before a pull request, code style, branch flow, commit format and how to report a vulnerability privately.
- Issue templates for bugs and feature requests, and a pull request template.
- CI on GitHub Actions for every pull request and every push to `main` and `staging`: lockfile, requirements files, `black`, missing migrations and the test suite against PostgreSQL 18.
- A check that only accepts pull requests into `main` from `staging` or `hotfix/*`.

### Changed

- The README is now in English, with the Spanish version in `README.es.md`.
- `LEVANTAR-LOCAL.md` is now `LOCAL-SETUP.md`, in English, with `LOCAL-SETUP.es.md` next to it. Update any link to the old name.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
