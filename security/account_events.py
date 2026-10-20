from webhooks.events import emit_webhook_event

USER_REGISTERED = "user.registered"
USER_EMAIL_VERIFIED = "user.email_verified"


def emit_account_event(event, user):
    emit_webhook_event(event, {"user_id": str(user.pk), "email": user.email})
