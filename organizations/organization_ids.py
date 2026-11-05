import uuid


def parse_organization_id(organization_reference: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(organization_reference))
    except ValueError:
        return None
