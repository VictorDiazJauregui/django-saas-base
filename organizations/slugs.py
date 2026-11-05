from itertools import count

from django.apps import apps
from django.utils.text import slugify

SLUG_MAX_LENGTH = 60
DEFAULT_SLUG = "organization"
# Room for "-" and a number, so a suffixed slug still fits the column.
BASE_MAX_LENGTH = SLUG_MAX_LENGTH - 8


def build_unique_slug(name):
    base = slugify(name)[:BASE_MAX_LENGTH].strip("-") or DEFAULT_SLUG
    taken = find_taken_slugs(base)
    if base not in taken:
        return base
    return next(f"{base}-{n}" for n in count(2) if f"{base}-{n}" not in taken)


def find_taken_slugs(base):
    organization_model = apps.get_model("organizations", "Organization")
    slugs = organization_model.objects.filter(slug__startswith=base)
    return set(slugs.values_list("slug", flat=True))
