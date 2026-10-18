import environ
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand

from security.superuser_bootstrap import ensure_superuser, rotate_superuser_password

env = environ.Env()


def read_required_variable(name):
    value = env.str(name, default="")
    if not value:
        raise ImproperlyConfigured(
            "ADMIN_EMAIL and ADMIN_PASSWORD must be set in the environment."
        )
    return value


class Command(BaseCommand):
    help = (
        "Creates the superuser in ADMIN_EMAIL with ADMIN_PASSWORD, for automated deployments. "
        "Use createsuperuser to create one interactively."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-password",
            action="store_true",
            help="Also set ADMIN_PASSWORD on the superuser if it already exists.",
        )

    def handle(self, *args, **options):
        email = read_required_variable("ADMIN_EMAIL")
        password = read_required_variable("ADMIN_PASSWORD")
        bootstrap = (
            rotate_superuser_password
            if options["update_password"]
            else ensure_superuser
        )
        outcome = bootstrap(email, password)
        self.stdout.write(self.style.SUCCESS(f'Superuser "{email}": {outcome}.'))
