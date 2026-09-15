# © 2024 Wukong Digital. License LGPL-3.
from types import SimpleNamespace
from unittest import TestCase

from odoo.exceptions import ValidationError

from ..adapters.prompts import prompt_for_mode
from ..services.extraction_profiles import resolve_profile


def _task(supplier_name=None, source_attempt=None, context=None):
    supplier = SimpleNamespace(name=supplier_name) if supplier_name else None
    statement = SimpleNamespace(
        supplier_id=supplier,
        source_parse_attempt_id=source_attempt,
    )
    return SimpleNamespace(
        env=SimpleNamespace(context=context or {}),
        statement_id=statement,
    )


def _provider(mode="native_pdf"):
    return SimpleNamespace(document_input_mode=mode)


class TestExtractionProfiles(TestCase):
    def test_unknown_supplier_uses_generic(self):
        profile = resolve_profile(_task("Unknown Carrier"), _provider())
        self.assertEqual(profile.key, "generic")

    def test_trusted_supplier_mapping_selects_ups(self):
        profile = resolve_profile(
            _task("United Parcel Service Nederland B.V."),
            _provider(),
        )
        self.assertEqual(profile.key, "ups_transport")

    def test_current_attempt_supplier_cannot_select_profile(self):
        profile = resolve_profile(
            _task("United Parcel Service Nederland B.V.", source_attempt=42),
            _provider(),
        )
        self.assertEqual(profile.key, "generic")

    def test_invalid_explicit_profile_is_rejected(self):
        with self.assertRaises(ValidationError):
            resolve_profile(
                _task(context={"extraction_profile_key": "missing"}),
                _provider(),
            )

    def test_mapped_profile_is_independent_of_input_mode(self):
        profile = resolve_profile(
            _task("United Parcel Service Nederland B.V."),
            _provider("markdown"),
        )
        self.assertEqual(profile.key, "ups_transport")

    def test_generic_prompt_is_unchanged_without_extension(self):
        base = prompt_for_mode("native_pdf")
        generic = prompt_for_mode("native_pdf", "", "generic-v1")
        self.assertEqual(base, generic)

    def test_profile_extension_is_composed_on_input_mode_prompt(self):
        prompt = prompt_for_mode("native_pdf", "UPS rule", "ups-v1")
        self.assertIn("UPS rule", prompt.instructions)
        self.assertTrue(prompt.version.endswith("+ups-v1"))

    def test_ups_profile_interprets_btw_as_vat_rate(self):
        profile = resolve_profile(
            _task("United Parcel Service Nederland B.V."),
            _provider(),
        )
        self.assertIn(
            "'BTW' means Dutch value-added tax "
            "(Belasting over de toegevoegde waarde, VAT)",
            profile.extension,
        )
        self.assertIn("'21% BTW' as the VAT rate", profile.extension)
