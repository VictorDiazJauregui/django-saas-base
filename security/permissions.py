from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission


class PublicRegistrationEnabled(BasePermission):
    message = _("Public registration is disabled.")

    def has_permission(self, request, view):
        return settings.ALLOW_PUBLIC_REGISTRATION
