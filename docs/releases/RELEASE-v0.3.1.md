Pre-release. Security update on top of v0.3.0. Nothing changes in the API, the commands or the variables, so a project built on v0.3.0 only has to reinstall the development dependencies.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.3.1/docs/releases/RELEASE-v0.3.1.es.md)

### Security

- `black` 25.12.0 → 26.10.1, a development tool. 25.12.0 could write its cache file outside the cache folder if someone controlled `--python-cell-magics` ([CVE-2026-32274](https://github.com/advisories/GHSA-3936-cmfr-pm3m)). The production requirements and the Docker image don't include `black`.
- The CI now runs `pip-audit` on `requirements-dev.txt` as well as `requirements.txt`, so a vulnerable development tool fails the build too.

### Changed

- `manage.py` follows the black 26 style: a blank line after the module docstring.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
