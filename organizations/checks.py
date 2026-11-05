import sysconfig
from collections.abc import Iterable
from pathlib import Path

from django.apps import AppConfig, apps
from django.conf import settings
from django.core.checks import Tags, Warning, register
from django.db.models import ForeignKey, Model
from django.utils.translation import gettext_lazy as _

from .models import GlobalModel, Organization

INSTALLED_PACKAGE_DIRECTORIES = frozenset(
    Path(sysconfig.get_paths()[scheme_key]).resolve()
    for scheme_key in ("purelib", "platlib")
)


# All organizations share the tables: a model that forgets its organization shows its rows
# to every one of them, and nothing else catches it before a customer does.
@register(Tags.models)
def check_models_store_their_organization(
    app_configs: Iterable[AppConfig] | None, **kwargs
) -> list[Warning]:
    if not settings.TENANCY_ENABLED:
        return []
    return [
        build_missing_organization_warning(model)
        for model in list_project_models(app_configs)
        if needs_organization(model) and not stores_its_organization(model)
    ]


def list_project_models(app_configs: Iterable[AppConfig] | None) -> list[type[Model]]:
    configs = apps.get_app_configs() if app_configs is None else app_configs
    return [
        model
        for config in configs
        if is_project_app(config)
        for model in config.get_models()
    ]


def is_project_app(app_config: AppConfig) -> bool:
    app_path = Path(app_config.path).resolve()
    return app_path.is_relative_to(settings.BASE_DIR) and not is_installed_package(
        app_path
    )


# uv keeps the virtual environment inside the project, so being under BASE_DIR isn't enough.
def is_installed_package(path: Path) -> bool:
    resolved_path = path.resolve()
    return any(
        resolved_path.is_relative_to(directory)
        for directory in INSTALLED_PACKAGE_DIRECTORIES
    )


def needs_organization(model: type[Model]) -> bool:
    if model._meta.proxy or not model._meta.managed:
        return False
    return not issubclass(model, GlobalModel)


def stores_its_organization(
    model: type[Model], visited: frozenset[type[Model]] = frozenset()
) -> bool:
    if model is Organization:
        return True
    if model in visited or issubclass(model, GlobalModel):
        return False
    return any(
        stores_its_organization(field.related_model, visited | {model})
        for field in list_required_foreign_keys(model)
    )


def list_required_foreign_keys(model: type[Model]) -> list[ForeignKey]:
    return [
        field
        for field in model._meta.concrete_fields
        if isinstance(field, ForeignKey) and not field.null
    ]


def build_missing_organization_warning(model: type[Model]) -> Warning:
    return Warning(
        _("This model doesn't store which organization each row belongs to."),
        hint=_(
            "Inherit from OrganizationScopedModel, add a required ForeignKey to a model "
            "that has one, or inherit from GlobalModel if every organization shares it "
            "on purpose."
        ),
        obj=model,
        id="organizations.W001",
    )
