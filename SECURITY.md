# Security policy

[English](SECURITY.md) · [Español](SECURITY.es.md)

## Supported versions

The project is in `0.x`. Only the latest release on `main` gets security fixes.

## Reporting a vulnerability

Do not open a public issue. Use **Report a vulnerability** in the
[Security tab](https://github.com/VictorDiazJauregui/django-saas-base/security/advisories/new) of
the repository, which opens a private report.

Include what is affected (endpoint, setting, command), how to reproduce it and the impact you see.
You will get an answer within 7 days. Once there is a fix, it ships in a release and the advisory is
published with credit to you, unless you prefer otherwise.

## Scope

In scope: the code in this repository and its defaults (settings, Docker Compose file, audit log
redaction, authentication endpoints).

Out of scope: vulnerabilities in Django, Django REST Framework or other dependencies (report them to
their projects), and problems caused by a project changing the defaults after cloning the base.
