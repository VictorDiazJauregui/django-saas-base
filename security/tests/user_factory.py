from django.contrib.auth import get_user_model

DEFAULT_EMAIL = "jane.doe@example.com"
DEFAULT_PASSWORD = "Str0ng-Passphrase-42"


def build_registration_payload(**overrides):
    payload = {
        "email": DEFAULT_EMAIL,
        "password": DEFAULT_PASSWORD,
        "password2": DEFAULT_PASSWORD,
        "first_name": "Jane",
        "last_name": "Doe",
    }
    return {**payload, **overrides}


def create_user(email=DEFAULT_EMAIL, password=DEFAULT_PASSWORD):
    return get_user_model().objects.create_user(email=email, password=password)


def create_superuser(email="root@example.com", password=DEFAULT_PASSWORD):
    return get_user_model().objects.create_superuser(email=email, password=password)
