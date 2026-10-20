# Contributing to django-saas-base

[English](CONTRIBUTING.md) · [Español](CONTRIBUTING.es.md)

Bug reports, ideas and pull requests are welcome. Issues and pull requests can be written in
English or Spanish.

This project is a base that other projects clone and build on. Anything added here ends up in every
project created from it, so the bar for new dependencies, apps and settings is high: each one has to
be useful to most projects, not just one.

## Issues

Search the open issues first, in case someone already reported the same thing.

- **Bug.** Use the bug report template. Include the commit or version, your operating system, how
  you run Python (`uv` or `pip`), what you expected and what happened.
- **Feature or change.** Use the feature request template and describe the problem before the
  solution. For anything bigger than a small fix, open the issue before writing code so we can agree
  on the approach.
- **Question.** Open a regular issue.

Do not report security problems in a public issue. See [SECURITY.md](SECURITY.md).

## Local setup

You need Python 3.12 or later, [uv](https://docs.astral.sh/uv/) and Docker with Compose v2. The
[README](README.md) covers Linux, WSL and Windows in detail.

```bash
git clone https://github.com/VictorDiazJauregui/django-saas-base.git
cd django-saas-base
cp .env.example .env            # then set the passwords and SECRET_KEY
docker compose up -d --wait
uv sync
uv run python manage.py migrate
uv run python manage.py create_admin_auto
uv run python manage.py runserver
```

The admin runs at `http://localhost:8000/admin/` and the API under `http://localhost:8000/api/v1/`.

## Before opening a pull request

Run the same checks as CI, with the database up:

```bash
uv run black --check .
uv run ruff check .
uv run python manage.py makemigrations --check --dry-run
uv run coverage run manage.py test
uv run coverage report
uvx pip-audit==2.10.1 -r requirements.txt -r requirements-dev.txt --no-deps --disable-pip --strict
```

The commands are the same in bash, zsh, PowerShell and cmd. With pip and a virtual environment,
drop `uv run`. `coverage report` prints the lines the tests don't run and fails if the total
drops below `fail_under` in `pyproject.toml`. Raise that value when the coverage goes up; never
lower it to make the CI pass. `LOG_LEVEL=ERROR` in your `.env` keeps the test output short.

If you changed a dependency, regenerate both requirements files and commit them together with
`pyproject.toml` and `uv.lock`:

```bash
uv export --no-dev --no-hashes -o requirements.txt
uv export --no-hashes -o requirements-dev.txt
```

### Dependabot pull requests

Every week Dependabot opens one pull request that groups the minor and patch updates of the
packages declared in `pyproject.toml`, and a separate one for each major update. It changes
`pyproject.toml` and `uv.lock` but not the requirements files, so the CI fails on its pull requests.
Before merging one, check out its branch, run the two `uv export` commands above, commit both files
and push: the CI runs again. Transitive packages are updated with the direct ones that need them.

## Code style

`black` formats the code and `ruff` lints it (rules in `pyproject.toml`). If a rule does not fit,
turn it off in `pyproject.toml` with the reason, not with a loose `noqa`. The rest is checked in
review:

- Functions do one thing, have at most 20 lines and 3 parameters (not counting `self` or `cls`).
  Group more parameters in an object.
- Early returns instead of nested `if`/`else`. At most two levels of nesting.
- Names in English that say what the thing is or does. No `utils`, `helpers`, `manager` or `data`
  catch-alls.
- Views orchestrate. Business rules go in plain functions or services that can be tested without
  HTTP; serializers validate and shape data.
- Catch specific exceptions. Never a bare `except` or one that swallows the error.
- Comments explain why, not what. No commented-out code, unused imports or `print` calls.
- No secrets, credentials or project-specific values in the code. New settings come from the
  environment: add them to `.env.example` and to the variables table in the README.
- Every user-facing string goes through `gettext_lazy`.

## Tests

Tests live in `<app>/tests/` and use Django's test runner (`django.test.TestCase` and DRF's
`APITestCase`). They need PostgreSQL running, because Django creates and drops a test database.

- A fix comes with a test that fails without it.
- A new feature comes with tests for the main path, the validation errors and the permissions
  (anonymous user, user without permission, user with permission).
- A model change comes with its migration. `makemigrations --check` must report no changes.
- A new sensitive field (password, token, key) must be covered by `security/redaction.py`, with a
  test, so it never reaches the audit log in plain text.

## API changes

The routes under `/api/v1/`, their request and response fields, status codes and permissions are a
contract with every project built on this base. If your change alters any of them, say so in the
pull request and describe what a client has to change. Breaking changes go in a minor release while
the project is in `0.x`.

## Documentation

The docs are moving to English as the main language with a Spanish copy (`*.es.md`) next to each
file. In the Spanish copy, technical terms stay in English (endpoint, payload, token, merge). Update
both when you change behaviour; if you only write one of them, say so in the pull request.

Keep it short and concrete. Every command in the docs should work exactly as written.

## Branches, commits and pull requests

- Branch from `staging` and open the pull request against `staging`. `main` only receives releases.
- Branch names: `<type>/<short-description>`, for example `fix/audit-log-read-only`. Types: `feat`,
  `fix`, `refac`, `docs`, `test`, `chore`.
- Commit messages in English, one short sentence starting with an uppercase prefix: `FEAT`, `FIX`,
  `REFAC`, `DOC`, `TEST`, `CHORE`, `CI`, `SEC` or `DEL`. For example
  `FIX: keep audit log read only in admin`. Keep the subject under 50 characters.
- One commit per logical change. A migration goes in the same commit as the model change.
- Pull request titles follow `TYPE(scope): Description`, for example
  `FIX(admin): Make the audit log read only`.
- Keep each pull request about one thing and fill in the template.

## Releases

Versions follow [Semantic Versioning](https://semver.org/). A release is a pull request from
`staging` to `main` that bumps `version` in `pyproject.toml`, followed by a `vX.Y.Z` tag on `main`
and a GitHub release with the notes.

## License

The project is released under the [MIT license](LICENSE). By sending a contribution you agree that
it is released under the same license.
