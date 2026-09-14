# © 2024 Wukong Digital. License LGPL-3.
"""Numeric parsing helpers for provider and business-document values."""

from odoo import _
from odoo.exceptions import ValidationError


def parse_localized_float(value):
    """Parse standard and European decimal representations into a float."""
    if value in (False, None, ""):
        return 0.0
    if isinstance(value, str):
        text = value.strip().replace(" ", "")
        comma = text.rfind(",")
        dot = text.rfind(".")
        if comma >= 0 and dot >= 0:
            decimal_separator = "," if comma > dot else "."
            thousands_separator = "." if decimal_separator == "," else ","
            text = text.replace(thousands_separator, "")
            text = text.replace(decimal_separator, ".")
        elif comma >= 0:
            fractional_digits = len(text) - comma - 1
            if fractional_digits == 3 and len(text[:comma]) <= 3:
                text = text.replace(",", "")
            else:
                text = text.replace(",", ".")
        value = text
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(_("Invalid monetary value: %s") % value) from error
