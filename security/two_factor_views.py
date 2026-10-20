from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .security_events import log_two_factor_changed
from .token_pair import issue_token_pair
from .two_factor import (
    TotpNotEnabled,
    confirm_totp_setup,
    count_unused_recovery_codes,
    disable_totp,
    find_confirmed_device,
    replace_recovery_codes,
    start_totp_setup,
)
from .two_factor_api_docs import (
    login_two_factor_schema,
    recovery_codes_schema,
    totp_confirm_schema,
    totp_disable_schema,
    totp_setup_schema,
    totp_status_schema,
)
from .two_factor_serializers import (
    MfaLoginSerializer,
    SecondFactorSerializer,
    TotpConfirmSerializer,
    TotpDisableSerializer,
    TotpSetupSerializer,
    TotpStatusSerializer,
)
from .views import PublicAccountView


# With the module off the routes don't exist, as before it was added.
class TwoFactorModuleMixin:
    def initial(self, request, *args, **kwargs):
        if not settings.TOTP_ENABLED:
            raise NotFound
        super().initial(request, *args, **kwargs)

    def validated_data(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class AccountTwoFactorView(TwoFactorModuleMixin, generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = "mfa"

    def require_enabled(self, user):
        if find_confirmed_device(user) is None:
            raise TotpNotEnabled


@totp_status_schema
class TotpStatusView(AccountTwoFactorView):
    serializer_class = TotpStatusSerializer
    throttle_scope = None

    def get(self, request):
        answer = {
            "enabled": find_confirmed_device(request.user) is not None,
            "recovery_codes_left": count_unused_recovery_codes(request.user),
        }
        return Response(answer)


@totp_setup_schema
class TotpSetupView(AccountTwoFactorView):
    serializer_class = TotpSetupSerializer
    throttle_scope = None

    def post(self, request):
        return Response(start_totp_setup(request.user))


@totp_confirm_schema
class TotpConfirmView(AccountTwoFactorView):
    serializer_class = TotpConfirmSerializer

    def post(self, request):
        recovery_codes = confirm_totp_setup(self.validated_data(request)["device"])
        log_two_factor_changed(request.user, enabled=True)
        return Response({"recovery_codes": recovery_codes})


@totp_disable_schema
class TotpDisableView(AccountTwoFactorView):
    serializer_class = TotpDisableSerializer

    def post(self, request):
        self.require_enabled(request.user)
        self.validated_data(request)
        disable_totp(request.user)
        log_two_factor_changed(request.user, enabled=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


@recovery_codes_schema
class RecoveryCodesView(AccountTwoFactorView):
    serializer_class = SecondFactorSerializer

    def post(self, request):
        self.require_enabled(request.user)
        self.validated_data(request)
        return Response({"recovery_codes": replace_recovery_codes(request.user)})


@login_two_factor_schema
class LoginTwoFactorView(TwoFactorModuleMixin, PublicAccountView):
    serializer_class = MfaLoginSerializer
    throttle_scope = "mfa"

    def post(self, request):
        user = self.validated_data(request)["user"]
        request._request.user_for_audit = user
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        return Response(issue_token_pair(user))
