Pre-release. Optional multi-tenancy on top of v0.3.3: organizations with members and roles, email invitations, and the pieces to keep each organization's data apart in your own apps. It is off by default, so with the same `.env` the API answers as in v0.3.3.

[Español](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/docs/releases/RELEASE-v0.4.0.es.md)

### Upgrading

Run `python manage.py migrate`: there is a new `organizations` app with two migrations. There are no new dependencies. The new variables in `.env.example` can stay as they are while `TENANCY_ENABLED=False`.

### Added

- [Multi-tenancy](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.md#multi-tenancy), turned on with `TENANCY_ENABLED=True`. A user can belong to several organizations, with one role in each: `owner`, `admin` or `member`. Every organization keeps at least one owner.
- [Organizations and members API](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.md#organizations-and-members-api) under `/api/v1/organizations/`: list your organizations, create one, rename it, list its members, change their role, remove them or leave. Organizations are deleted only in the admin.
- [Invitations](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.md#invitations) by email. The link goes to `FRONTEND_INVITATION_URL`, which is required with the module on. The invited person accepts with their account or creates one from the link, also with the public registration closed. Tokens are stored as a hash, work once and expire after `TENANCY_INVITATION_TIMEOUT_HOURS`.
- [Models of an organization](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.md#models-of-an-organization) for your own apps: inherit `OrganizationScopedModel` and use `OrganizationScopedViewSet`, and each query only sees the rows of the organization in the URL. `IsOrganizationMember` and `HasOrganizationRole` protect any other view.
- [Webhook events](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/README.md#webhook-events) `organization.created`, `organization.member_added` and `organization.member_removed`.
- Admin pages for organizations, their members and the invitations, which can be revoked from the list.

### Changed

- A new rate limit, `THROTTLE_INVITATION_RATE` (`10/h`), for the public invitation routes.
- [DEPLOYMENT.md](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/DEPLOYMENT.md#2-variables) lists the multi-tenancy variables, and [CONTRIBUTING.md](https://github.com/VictorDiazJauregui/django-saas-base/blob/v0.4.0/CONTRIBUTING.md#tests) asks for an isolation test in every view that works on an organization's rows.

### Security

- An organization that doesn't exist and one the user isn't a member of get the same `404`, and so do the invitation tokens that don't exist, expired, were revoked or were used. The audit log redacts the invitation tokens.

### Requirements

Python 3.12 or later · Docker with Compose v2.

### License

MIT.
