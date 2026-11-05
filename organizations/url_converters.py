import uuid

ORGANIZATION_CONVERTER_NAME = "organization"


# Takes any path segment: a reference that is neither an id nor a slug must get the same
# organization_not_found as someone else's organization, not a different 404 from the router.
class OrganizationReferenceConverter:
    regex = "[^/]+"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: uuid.UUID | str) -> str:
        return str(value)
