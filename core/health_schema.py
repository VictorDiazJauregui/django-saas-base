from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers

from .health import HEALTHY, UNHEALTHY

HEALTH = inline_serializer(
    "Health",
    {"status": serializers.CharField(), "database": serializers.CharField()},
)


def health_response(description, state):
    value = {"status": state, "database": state}
    example = OpenApiExample(state, value=value, response_only=True)
    return OpenApiResponse(HEALTH, description=description, examples=[example])


health_schema = extend_schema(
    tags=["ops"],
    summary=_("Check that the API and its database answer"),
    description=_(
        "Public and never rate limited, for load balancers and orchestrators. In staging "
        "and prod it also answers over plain HTTP, but the Host header must still be one "
        "of ALLOWED_HOSTS."
    ),
    responses={
        200: health_response(_("The API and the database answer."), HEALTHY),
        503: health_response(_("The database does not answer."), UNHEALTHY),
    },
)
