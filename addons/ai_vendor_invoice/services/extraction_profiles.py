# © 2024 Wukong Digital. License LGPL-3.
"""Code-managed extraction Profile registry for CC-16."""

from dataclasses import dataclass

from odoo.exceptions import ValidationError


def _normalize_supplier(value):
    return " ".join((value or "").strip().upper().split())


@dataclass(frozen=True)
class ExtractionProfile:
    key: str
    version: str
    extension_version: str
    extension: str
    supplier_names: frozenset = frozenset()


GENERIC_PROFILE = ExtractionProfile(
    key="generic",
    version="generic-v1",
    extension_version="generic-v1",
    extension="",
)

UPS_PROFILE = ExtractionProfile(
    key="ups_transport",
    version="ups-transport-v2",
    extension_version="ups-transport-extension-v2",
    extension=(
        "Preserve the explicit Returned Date as Returned Date. Do not infer "
        "Loading Date or Unloading Date when the document does not print that "
        "semantic. For every visible charge component, preserve Charge, "
        "Discount, and Net Charge as distinct facts when the selected output "
        "contract can represent them; do not silently replace the breakdown "
        "with only the net amount. In a UPS invoice, 'BTW' means value-added "
        "tax (VAT); preserve an explicitly printed percentage such as '21% "
        "BTW' as the VAT rate, not as a charge or a discount."
    ),
    supplier_names=frozenset({
        "UNITED PARCEL SERVICE NEDERLAND B.V.",
        "UNITED PARCEL SERVICE",
    }),
)

PROFILE_REGISTRY = {
    GENERIC_PROFILE.key: GENERIC_PROFILE,
    UPS_PROFILE.key: UPS_PROFILE,
}


def get_profile(profile_key):
    try:
        return PROFILE_REGISTRY[profile_key]
    except KeyError as error:
        raise ValidationError(
            "The requested extraction Profile is not registered."
        ) from error


def resolve_profile(task, provider_config=None):
    """Resolve only from trusted pre-extraction inputs.

    A supplier extracted by the current Attempt is intentionally never read
    here. A Statement supplier is trusted only before that Statement has a
    source ParseAttempt.
    """
    explicit_key = task.env.context.get("extraction_profile_key")
    if explicit_key:
        profile = get_profile(explicit_key)
    else:
        supplier_name = None
        statement = task.statement_id
        if statement and not statement.source_parse_attempt_id:
            supplier_name = statement.supplier_id.name if statement.supplier_id else None
        normalized_supplier = _normalize_supplier(supplier_name)
        profile = GENERIC_PROFILE
        for candidate in PROFILE_REGISTRY.values():
            if normalized_supplier in candidate.supplier_names:
                profile = candidate
                break
    return profile
