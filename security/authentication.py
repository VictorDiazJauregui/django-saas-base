from django.conf import settings
from django.contrib.auth.backends import ModelBackend


# Refusing here, like an inactive account, makes an unverified login look exactly like a wrong
# password: a different answer would tell whoever registered an email whether it already
# had an account.
class VerifiedEmailModelBackend(ModelBackend):
    def user_can_authenticate(self, user):
        if not super().user_can_authenticate(user):
            return False
        return user.is_email_verified or not settings.REQUIRE_EMAIL_VERIFICATION
