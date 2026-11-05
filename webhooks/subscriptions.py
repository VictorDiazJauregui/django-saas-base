from django.conf import settings
from django.utils.translation import gettext as _


class OrganizationEventNotAllowed(Exception):
    pass


# Account events concern the whole platform; an organization hears only what it owns.
def ensure_organization_events(events: list[str]) -> None:
    allowed = set(settings.WEBHOOK_ORGANIZATION_EVENTS)
    refused = [event for event in events if event not in allowed]
    if refused:
        raise OrganizationEventNotAllowed(
            _("An organization can't subscribe to: %(events)s.")
            % {"events": ", ".join(refused)}
        )
