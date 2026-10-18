from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission, OperationHolderMixin


class PublicRegistrationEnabled(BasePermission):
    message = _("Public registration is disabled.")

    def has_permission(self, request, view):
        return settings.ALLOW_PUBLIC_REGISTRATION


class ConfiguredPermission(OperationHolderMixin, BasePermission):
    """Base for permissions that take arguments in permission_classes.

    DRF calls each entry of permission_classes to build it, so an instance that returns
    itself when called can be declared as HasRole("billing") and combined with & | ~.
    """

    def __call__(self):
        return self

    # BasePermission allows every object, so ~HasRole(...) would deny every object.
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class HasPermission(ConfiguredPermission):
    def __init__(self, permission):
        if "." not in permission:
            raise ImproperlyConfigured(
                f"HasPermission({permission!r}) needs the form app_label.codename, "
                "for example 'security.view_auditlog'."
            )
        self.permission = permission

    def has_permission(self, request, view):
        return request.user.has_perm(self.permission)


class HasRole(ConfiguredPermission):
    def __init__(self, role):
        self.role = role

    def has_permission(self, request, view):
        user = request.user
        if user.is_active and user.is_superuser:
            return True
        return user.groups.filter(name=self.role).exists()
