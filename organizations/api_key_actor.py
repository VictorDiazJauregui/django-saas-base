from django.contrib.auth.models import AnonymousUser

from .models import OrganizationApiKey


# Stands for the key, not for a person, and is never authenticated as one: every view that
# needs a person (IsAuthenticated) refuses it with 403, including the views of the project.
class OrganizationApiKeyActor(AnonymousUser):
    def __init__(self, organization_api_key: OrganizationApiKey) -> None:
        self.organization_api_key = organization_api_key

    def __str__(self) -> str:
        return str(self.organization_api_key)
