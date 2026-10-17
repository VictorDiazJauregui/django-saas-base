NO_ROLES = {}

TWO_ROLES = {
    "auditors": ["security.view_auditlog"],
    "support": ["security.view_user", "security.change_user"],
}

SUPPORT_WITHOUT_CHANGE = {
    "auditors": ["security.view_auditlog"],
    "support": ["security.view_user"],
}

WITH_MISSING_PERMISSION = {
    "reports": ["security.view_auditlog", "billing.export_invoice"],
}

WITHOUT_APP_LABEL = {
    "auditors": ["security.view_auditlog"],
    "broken": ["view_auditlog"],
}

PERMISSIONS_NOT_IN_A_LIST = {"auditors": "security.view_auditlog"}

ROLE_WITHOUT_PERMISSIONS = {"guests": []}

ONE_PERMISSION = {"staff": ["security.view_user"]}

FIVE_PERMISSIONS = {
    "staff": [
        "security.view_user",
        "security.add_user",
        "security.change_user",
        "security.delete_user",
        "security.view_auditlog",
    ]
}
