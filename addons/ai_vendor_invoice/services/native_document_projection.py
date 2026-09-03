# © 2024 Wukong Digital. License LGPL-3.
"""Projection of native document extraction into the existing flat contract."""

from decimal import Decimal, InvalidOperation
from datetime import datetime

from jsonschema import validate

from ..schemas.document_extraction import DOCUMENT_EXTRACTION_RESULT_SCHEMA


def normalize_amount(value):
    """Normalize common European and plain decimal representations."""
    if value is None:
        return None
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return format(Decimal(text), "f")
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid monetary value: %s" % value)


def normalize_date(value):
    if value is None:
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError("Invalid invoice date: %s" % value)


def _clues(line):
    clues = line.get("reconciliation_clues") or []
    if not isinstance(clues, list):
        raise ValueError("reconciliation_clues must be a list.")
    result = [{"label": str(item["label"]), "value": item["value"]} for item in clues]
    known_clue_keys = {
        "ref": "Ref",
        "reference": "Reference",
        "our_reference": "Our reference",
        "your_reference": "Your reference",
        "load_ref": "Load ref",
        "shipping_ref": "Shipping ref",
        "shipment_ref": "Shipment ref",
        "booking_ref": "Booking ref",
        "pickup_ref": "Pickup ref",
        "carrier_ref": "Carrier ref",
        "customer_ref": "Customer ref",
    }
    for key, label in known_clue_keys.items():
        if key in line and line[key] not in (None, ""):
            result.append({"label": label, "value": line[key]})
    return result


def _description(line, clues):
    labels = (
        ("Loading Date", "loading_date"),
        ("Unloading Date", "unloading_date"),
        ("Our Reference", "our_reference"),
        ("Your Reference", "your_reference"),
        ("Shipment Reference", "shipment_reference"),
        ("Load Reference", "load_ref"),
        ("Booking Reference", "booking_ref"),
        ("Loading Address", "loading_address"),
        ("Unloading Address", "unloading_address"),
        ("Cargo", "description"),
        ("Weight", "gross_weight"),
        ("Volume Weight", "volume_weight"),
        ("Volume", "volume"),
    )
    description = [
        "%s: %s" % (label, line[key])
        for label, key in labels
        if line.get(key) not in (None, "")
    ]
    known_values = {line.get(key) for _, key in labels}
    description.extend(
        "%s: %s" % (item["label"], item["value"])
        for item in clues
        if item["value"] not in known_values
    )
    return "\n".join(description) or None


def _charge_details(line):
    charges = line.get("charges") or {}
    if not isinstance(charges, dict):
        raise ValueError("charges must be an object.")
    return "\n".join(
        "%s: %s" % (label, value)
        for label, value in charges.items()
        if value not in (None, "")
    ) or None


def document_to_canonical(document):
    """Create one Canonical line for each document business line."""
    validate(document, DOCUMENT_EXTRACTION_RESULT_SCHEMA)
    invoice = document["invoice"]
    totals = invoice.get("totals") or {}
    issuer = invoice.get("issuer") or {}
    lines = []
    for source_line in invoice["lines"]:
        clues = _clues(source_line)
        lines.append({
            "description": {
                "value": _description(source_line, clues),
                "confidence": 0.0,
            },
            "amount": {
                "value": normalize_amount(source_line.get("amount")),
                "confidence": 0.0,
            },
            "tax_raw_text": {
                "value": source_line.get("tax_raw_text"),
                "confidence": 0.0,
            },
            "tax_rate": {
                "value": source_line.get("tax_rate"),
                "confidence": 0.0,
            },
            "tax_amount": {
                "value": normalize_amount(source_line.get("tax_amount")),
                "confidence": 0.0,
            },
            "reconciliation_clue": None,
            "charge_details": _charge_details(source_line),
            "reconciliation_clues": clues,
        })
    return {
        "header": {
            "invoice_number": {"value": invoice.get("invoice_number"), "confidence": 0.0},
            "invoice_date": {
                "value": normalize_date(invoice.get("invoice_date")),
                "confidence": 0.0,
            },
            "supplier_raw_text": {
                "value": (
                    invoice.get("supplier")
                    or invoice.get("supplier_name")
                    or issuer.get("name")
                ),
                "confidence": 0.0,
            },
            "currency_raw_text": {"value": invoice.get("currency"), "confidence": 0.0},
            "total_amount": {
                "value": normalize_amount(
                    invoice.get("grand_total")
                    or invoice.get("total_amount")
                    or totals.get("total_including_vat")
                ),
                "confidence": 0.0,
            },
            "total_tax": {
                "value": normalize_amount(
                    invoice.get("tax_total")
                    or invoice.get("total_tax")
                    or totals.get("vat_amount")
                ),
                "confidence": 0.0,
            },
            "subtotal": {
                "value": normalize_amount(
                    invoice.get("subtotal")
                    if invoice.get("subtotal") is not None
                    else Decimal(normalize_amount(
                        invoice.get("grand_total")
                        or invoice.get("total_amount")
                        or totals.get("total_including_vat")
                    ) or "0") - Decimal(normalize_amount(
                        invoice.get("tax_total")
                        or invoice.get("total_tax")
                        or totals.get("vat_amount")
                    ) or "0")
                ),
                "confidence": 0.0,
            },
        },
        "lines": lines,
        "is_multi_invoice": False,
    }
