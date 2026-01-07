import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured


class Command(BaseCommand):
    """
    Custom management command to create a superuser automatically from environment variables.
    """

    help = "Creates a superuser automatically from ADMIN_EMAIL and ADMIN_PASSWORD environment variables."

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")

        if not email or not password:
            raise ImproperlyConfigured(
                "ADMIN_EMAIL and ADMIN_PASSWORD must be set in the environment."
            )

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.SUCCESS(f'Superuser "{email}" already exists.')
            )
        else:
            self.stdout.write(f'Creating superuser "{email}"...')
            User.objects.create_superuser(email=email, password=password)
            self.stdout.write(
                self.style.SUCCESS(f'Superuser "{email}" created successfully.')
            )
