from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from security.role_sync import (
    RoleDefinitionError,
    apply_role_sync_plan,
    build_role_sync_plan,
    load_declared_roles,
    permission_name,
)


def describe_change(change):
    parts = ["create"] if change.group is None else []
    if change.to_add:
        parts.append("add " + ", ".join(map(permission_name, change.to_add)))
    if change.to_remove:
        parts.append("remove " + ", ".join(map(permission_name, change.to_remove)))
    return f'Role "{change.name}": {", ".join(parts)}'


def describe_totals(plan):
    return (
        f"Roles synced: {plan.created_count} created, "
        f"{plan.added_count} permissions added, {plan.removed_count} removed."
    )


class Command(BaseCommand):
    help = (
        "Create or update the Django groups of the roles declared in ROLE_DEFINITIONS."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change and change nothing.",
        )

    def handle(self, *args, **options):
        roles = self.load_roles()
        if not roles:
            self.stdout.write(f"No roles declared in {settings.ROLE_DEFINITIONS}.")
            return
        plan = build_role_sync_plan(roles)
        self.report(plan)
        if not plan.pending:
            self.stdout.write("Roles already in sync.")
            return
        if options["dry_run"]:
            self.stdout.write("Dry run: nothing was changed.")
            return
        apply_role_sync_plan(plan)
        self.stdout.write(self.style.SUCCESS(describe_totals(plan)))

    def load_roles(self):
        try:
            return load_declared_roles()
        except RoleDefinitionError as error:
            raise CommandError(str(error)) from error

    def report(self, plan):
        for change in plan.pending:
            self.stdout.write(describe_change(change))
        for change in plan.changes:
            for permission in change.missing:
                self.stderr.write(
                    self.style.WARNING(
                        f'Warning: role "{change.name}" declares {permission}, '
                        "which does not exist. Run migrate first?"
                    )
                )
        for name in plan.undeclared_groups:
            self.stdout.write(
                f'Group "{name}" exists in the database but is not declared; left as is.'
            )
