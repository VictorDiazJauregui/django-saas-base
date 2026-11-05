from itertools import count

from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .organization_ids import parse_organization_id

SLUG_MAX_LENGTH = 60
DEFAULT_SLUG = "organization"
# Room for "-" and a number, so a suffixed slug still fits the column.
BASE_MAX_LENGTH = SLUG_MAX_LENGTH - 8


def build_unique_slug(name: str) -> str:
    base = build_slug_base(name)
    taken = find_taken_slugs(base)
    if base not in taken:
        return base
    return next(f"{base}-{n}" for n in count(2) if f"{base}-{n}" not in taken)


def build_slug_base(name: str) -> str:
    base = slugify(name)[:BASE_MAX_LENGTH].strip("-")
    if not base or parse_organization_id(base) is not None:
        return DEFAULT_SLUG
    return base


def find_taken_slugs(base: str) -> set[str]:
    organization_model = apps.get_model("organizations", "Organization")
    slugs = organization_model.objects.filter(slug__startswith=base)
    return set(slugs.values_list("slug", flat=True))


# The URL takes an id or a slug: a slug shaped like a UUID would be read as an id.
def reject_uuid_shaped_slug(slug: str) -> None:
    if parse_organization_id(slug) is not None:
        raise ValidationError(
            _("A slug can't have the shape of an id."), code="uuid_shaped_slug"
        )


# Subdomains always arrive in lowercase: an uppercase slug could never be reached from one.
def reject_uppercase_slug(slug: str) -> None:
    if slug != slug.lower():
        raise ValidationError(
            _("A slug can only use lowercase letters."), code="uppercase_slug"
        )
