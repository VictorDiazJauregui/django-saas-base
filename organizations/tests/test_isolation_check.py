# ruff: noqa: DJ008 - these models only exist for the check to inspect; nothing prints them.
import sysconfig
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.checks import run_checks
from django.db import models
from django.test import SimpleTestCase, override_settings
from django.test.utils import isolate_apps
from django.utils import translation

from organizations.checks import (
    check_models_store_their_organization,
    is_installed_package,
)
from organizations.models import GlobalModel, Organization, OrganizationScopedModel

ISOLATION_WARNING_ID = "organizations.W001"


# The models of each test live in a registry of their own: no table and no migration. The
# check reviews the base apps too, so a new model of organizations stands for any app.
@override_settings(TENANCY_ENABLED=True)
@isolate_apps("organizations", attr_name="registry")
class ModelIsolationCheckTests(SimpleTestCase):
    def warned_models(self):
        app_configs = self.registry.get_app_configs()
        return [
            warning.obj
            for warning in check_models_store_their_organization(app_configs)
        ]

    def test_model_without_organization_is_warned(self):
        class Invoice(models.Model):
            number = models.CharField(max_length=20)

        self.assertEqual(self.warned_models(), [Invoice])

    def test_warning_names_the_model_and_the_ways_out(self):
        class Invoice(models.Model):
            number = models.CharField(max_length=20)

        app_configs = self.registry.get_app_configs()
        [warning] = check_models_store_their_organization(app_configs)
        self.assertEqual(warning.id, ISOLATION_WARNING_ID)
        self.assertTrue(
            str(warning).startswith("organizations.Invoice: (organizations.W001)")
        )
        for way_out in ("OrganizationScopedModel", "ForeignKey", "GlobalModel"):
            self.assertIn(way_out, str(warning.hint))

    def test_required_foreign_key_to_organization_passes(self):
        class Invoice(models.Model):
            organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

        self.assertEqual(self.warned_models(), [])

    def test_organization_scoped_model_passes(self):
        class Invoice(OrganizationScopedModel):
            number = models.CharField(max_length=20)

        self.assertEqual(self.warned_models(), [])

    def test_required_foreign_key_to_a_scoped_model_passes(self):
        class Invoice(OrganizationScopedModel):
            number = models.CharField(max_length=20)

        class InvoiceLine(models.Model):
            invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)

        self.assertEqual(self.warned_models(), [])

    def test_organization_two_foreign_keys_away_passes(self):
        class Invoice(OrganizationScopedModel):
            number = models.CharField(max_length=20)

        class InvoiceLine(models.Model):
            invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)

        class LineNote(models.Model):
            line = models.ForeignKey(InvoiceLine, on_delete=models.CASCADE)

        self.assertEqual(self.warned_models(), [])

    def test_optional_foreign_key_to_organization_is_warned(self):
        class Invoice(models.Model):
            organization = models.ForeignKey(
                Organization, on_delete=models.CASCADE, null=True
            )

        self.assertEqual(self.warned_models(), [Invoice])

    def test_optional_foreign_key_to_a_scoped_model_is_warned(self):
        class Invoice(OrganizationScopedModel):
            number = models.CharField(max_length=20)

        class InvoiceLine(models.Model):
            invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True)

        self.assertEqual(self.warned_models(), [InvoiceLine])

    def test_foreign_key_to_a_global_model_is_warned(self):
        class Country(GlobalModel):
            code = models.CharField(max_length=2)

        class Address(models.Model):
            country = models.ForeignKey(Country, on_delete=models.CASCADE)

        self.assertEqual(self.warned_models(), [Address])

    def test_cycle_without_organization_warns_both_models(self):
        class Team(models.Model):
            lead = models.ForeignKey("Person", on_delete=models.CASCADE)

        class Person(models.Model):
            team = models.ForeignKey(Team, on_delete=models.CASCADE)

        self.assertEqual(self.warned_models(), [Team, Person])

    def test_global_model_passes(self):
        class Country(GlobalModel):
            code = models.CharField(max_length=2)

        self.assertEqual(self.warned_models(), [])

    def test_proxy_model_is_ignored(self):
        class Invoice(models.Model):
            number = models.CharField(max_length=20)

        class PaidInvoice(Invoice):
            class Meta:
                proxy = True

        self.assertEqual(self.warned_models(), [Invoice])

    def test_unmanaged_model_is_ignored(self):
        class LegacyInvoice(models.Model):
            number = models.CharField(max_length=20)

            class Meta:
                managed = False

        self.assertEqual(self.warned_models(), [])

    def test_automatic_many_to_many_table_is_ignored(self):
        class Tag(GlobalModel):
            name = models.CharField(max_length=20)

        class Invoice(OrganizationScopedModel):
            tags = models.ManyToManyField(Tag)

        self.assertEqual(self.warned_models(), [])

    def test_child_of_a_scoped_model_passes(self):
        class Invoice(OrganizationScopedModel):
            number = models.CharField(max_length=20)

        class CreditNote(Invoice):
            reason = models.CharField(max_length=100)

        self.assertEqual(self.warned_models(), [])

    @override_settings(TENANCY_ENABLED=False)
    def test_nothing_is_warned_with_multi_tenancy_off(self):
        class Invoice(models.Model):
            number = models.CharField(max_length=20)

        self.assertEqual(self.warned_models(), [])

    def test_check_is_registered(self):
        class Invoice(models.Model):
            number = models.CharField(max_length=20)

        messages = run_checks(app_configs=self.registry.get_app_configs())
        self.assertIn(ISOLATION_WARNING_ID, [message.id for message in messages])

    def test_warning_is_translated(self):
        class Invoice(models.Model):
            number = models.CharField(max_length=20)

        app_configs = self.registry.get_app_configs()
        [warning] = check_models_store_their_organization(app_configs)
        with translation.override("es"):
            self.assertIn("organización", str(warning.msg))
            self.assertIn("GlobalModel", str(warning.hint))


@override_settings(TENANCY_ENABLED=True)
class InstalledModelTests(SimpleTestCase):
    def test_base_models_pass(self):
        self.assertEqual(check_models_store_their_organization(None), [])

    def test_django_and_third_party_models_are_ignored(self):
        app_configs = [apps.get_app_config(label) for label in ("auth", "axes")]
        self.assertEqual(check_models_store_their_organization(app_configs), [])


class InstalledPackageTests(SimpleTestCase):
    def test_path_inside_site_packages_is_an_installed_package(self):
        site_packages = Path(sysconfig.get_paths()["purelib"])
        self.assertTrue(is_installed_package(site_packages / "axes"))

    def test_project_path_is_not_an_installed_package(self):
        self.assertFalse(is_installed_package(settings.BASE_DIR / "organizations"))
