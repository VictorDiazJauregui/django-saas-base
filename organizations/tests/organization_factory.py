from organizations.models import Membership, Organization
from organizations.organization_api_keys import issue_organization_api_key
from organizations.roles import OrganizationRole
from security.tests.user_factory import create_user


def create_organization(name="Acme", owner=None):
    organization = Organization.objects.create(name=name)
    if owner is not None:
        add_member(organization, owner, OrganizationRole.OWNER)
    return organization


def add_member(organization, user, role=OrganizationRole.MEMBER):
    return Membership.objects.create(organization=organization, user=user, role=role)


def create_member(organization, email, role=OrganizationRole.MEMBER):
    return add_member(organization, create_user(email=email), role)


def create_organization_api_key(organization, role=OrganizationRole.MEMBER, **details):
    details = {"name": "ERP", "role": role, **details}
    return issue_organization_api_key(organization, details)
