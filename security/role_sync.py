from dataclasses import dataclass
from functools import reduce
from operator import or_

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Q
from django.utils.module_loading import import_string


class RoleDefinitionError(Exception):
    pass


@dataclass(frozen=True)
class RoleChange:
    name: str
    group: Group | None
    to_add: tuple[Permission, ...]
    to_remove: tuple[Permission, ...]
    missing: tuple[str, ...]

    @property
    def is_pending(self):
        return self.group is None or bool(self.to_add or self.to_remove)


@dataclass(frozen=True)
class RoleSyncPlan:
    changes: tuple[RoleChange, ...]
    undeclared_groups: tuple[str, ...]

    @property
    def pending(self):
        return tuple(change for change in self.changes if change.is_pending)

    @property
    def created_count(self):
        return sum(change.group is None for change in self.pending)

    @property
    def added_count(self):
        return sum(len(change.to_add) for change in self.pending)

    @property
    def removed_count(self):
        return sum(len(change.to_remove) for change in self.pending)


@dataclass(frozen=True)
class PlanningContext:
    groups: dict[str, Group]
    permissions: dict[str, Permission]


def load_declared_roles():
    path = settings.ROLE_DEFINITIONS
    try:
        roles = import_string(path)
    except ImportError as error:
        raise RoleDefinitionError(
            f"Cannot load the roles of ROLE_DEFINITIONS={path!r}: {error}"
        ) from error
    validate_roles(roles)
    return roles


def validate_roles(roles):
    if not isinstance(roles, dict):
        raise RoleDefinitionError(
            f"{settings.ROLE_DEFINITIONS} must be a dict of role name to permission list."
        )
    for name, permissions in roles.items():
        validate_role(name, permissions)


def validate_role(name, permissions):
    if not isinstance(permissions, list | tuple):
        raise RoleDefinitionError(
            f'Role "{name}": the permissions must be a list of "app_label.codename".'
        )
    for permission in permissions:
        if not isinstance(permission, str) or "." not in permission:
            raise RoleDefinitionError(
                f'Role "{name}": "{permission}" needs the form app_label.codename, '
                'for example "security.view_auditlog".'
            )


def permission_name(permission):
    return f"{permission.content_type.app_label}.{permission.codename}"


# One query for every declared permission, however many roles declare them.
def find_permissions(names):
    if not names:
        return {}
    pairs = (name.split(".", 1) for name in names)
    query = reduce(
        or_, (Q(content_type__app_label=app, codename=code) for app, code in pairs)
    )
    found = Permission.objects.filter(query).select_related("content_type")
    return {permission_name(permission): permission for permission in found}


def plan_role(name, declared, context):
    group, known = context.groups.get(name), context.permissions
    wanted = {
        permission: known[permission] for permission in declared if permission in known
    }
    current = {permission_name(p): p for p in group.permissions.all()} if group else {}
    return RoleChange(
        name=name,
        group=group,
        to_add=tuple(wanted[key] for key in sorted(wanted.keys() - current.keys())),
        to_remove=tuple(current[key] for key in sorted(current.keys() - wanted.keys())),
        missing=tuple(permission for permission in declared if permission not in known),
    )


def build_role_sync_plan(roles):
    declared = {
        permission for permissions in roles.values() for permission in permissions
    }
    groups = Group.objects.prefetch_related("permissions__content_type")
    context = PlanningContext(
        groups={group.name: group for group in groups},
        permissions=find_permissions(declared),
    )
    return RoleSyncPlan(
        changes=tuple(plan_role(name, perms, context) for name, perms in roles.items()),
        undeclared_groups=tuple(sorted(context.groups.keys() - roles.keys())),
    )


@transaction.atomic
def apply_role_sync_plan(plan):
    for change in plan.pending:
        group = change.group or Group.objects.create(name=change.name)
        if change.to_add:
            group.permissions.add(*change.to_add)
        if change.to_remove:
            group.permissions.remove(*change.to_remove)
