# © 2024 Wukong Digital. License LGPL-3.
import copy
import re

from jsonschema import ValidationError, validate

from .base import AIProviderPermanentError, BaseAIProviderAdapter
from ..schemas.canonical import CANONICAL_INVOICE_RESULT_SCHEMA
from ..schemas.page_extraction import PAGE_EXTRACTION_RESULT_SCHEMA


class DocumentNormalizationError(AIProviderPermanentError):
    """Page results cannot be converted into one canonical invoice."""

    def __init__(self, message, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic or {}


_HEADER_ALIASES = {
    "invoice_number": {"invoice_number", "invoice_no", "invoicenumber", "factuurnummer"},
    "invoice_date": {"invoice_date", "invoicedate", "factuurdatum"},
    "supplier_raw_text": {"supplier", "supplier_name", "supplier_raw_text", "leverancier"},
    "currency_raw_text": {"currency", "currency_raw_text", "valuta"},
    "total_amount": {"total", "total_amount", "totalamount", "totaal", "totaalbedrag"},
    "total_tax": {"tax", "total_tax", "totaltax", "btw", "btwbedrag"},
}


def _key(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _semantic_values(values):
    result = {}
    for field, value in values.items():
        normalized = _key(field)
        for canonical, aliases in _HEADER_ALIASES.items():
            if normalized in {_key(alias) for alias in aliases}:
                result[canonical] = value
                break
    return result


def _header_candidates(page_result):
    candidates = []
    containers = (
        ("header", page_result.get("header", {}), 3),
        ("header_values", page_result.get("header_values", {}), 2),
    )
    for source_label, values, source_weight in containers:
        for field, value in _semantic_values(values).items():
            candidates.append((field, value, source_weight, source_label))
    for field, value in _semantic_values({
        field: value for field, value in page_result.items()
        if field not in {"page_number", "header", "header_values",
                         "lines", "is_multi_invoice"}
    }).items():
        candidates.append((field, value, 1, "page_top_level"))
    return candidates


def _select_header_values(ordered):
    candidates_by_field = {}
    for page_result in ordered:
        candidates = _header_candidates(page_result)
        for field, value, source_weight, source_label in candidates:
            if value in (None, ""):
                continue
            candidates_by_field.setdefault(field, []).append({
                "page": page_result["page_number"],
                "value": value,
                "source_label": source_label,
                "score": source_weight * 1000 + len(candidates),
            })

    selected = {}
    for field, candidates in candidates_by_field.items():
        unique_values = {}
        for candidate in candidates:
            unique_values.setdefault(str(candidate["value"]), []).append(candidate)
        if len(unique_values) == 1:
            selected[field] = candidates[0]["value"]
            continue
        for value_candidates in unique_values.values():
            frequency = len(value_candidates)
            for candidate in value_candidates:
                candidate["score"] += frequency * 10
        best_score = max(candidate["score"] for candidate in candidates)
        best = [candidate for candidate in candidates
                if candidate["score"] == best_score]
        best_values = {str(candidate["value"]) for candidate in best}
        if len(best_values) != 1:
            raise DocumentNormalizationError(
                "Document normalization produced an invalid canonical result.",
                {
                    "code": "HEADER_CONFLICT",
                    "field": field,
                    "candidate_count": len(unique_values),
                    "pages": sorted({candidate["page"] for candidate in best}),
                },
            )
        selected[field] = best[0]["value"]
    return selected


def normalize_page_results(page_results):
    try:
        for page_result in page_results:
            validate(page_result, PAGE_EXTRACTION_RESULT_SCHEMA)
        if not page_results:
            raise ValueError("No page extraction results were returned.")

        ordered = sorted(page_results, key=lambda result: result["page_number"])
        lines = []
        multi_invoice = set()
        for page_result in ordered:
            multi_invoice.add(page_result.get("is_multi_invoice", False))
            lines.extend(page_result.get("lines", []))
        if len(multi_invoice) > 1:
            raise ValueError("Conflicting document multi-invoice flags.")
        header_values = _select_header_values(ordered)

        fields = (
            "invoice_number", "invoice_date", "supplier_raw_text",
            "currency_raw_text", "total_amount", "total_tax",
        )
        header = {
            field: {"value": header_values.get(field), "confidence": 0.0}
            for field in fields
        }
        canonical_lines = []
        for line in lines:
            normalized = {_key(field): value for field, value in line.items()}
            canonical_lines.append({
                "description": {
                    "value": next(
                        (normalized[key] for key in ("description", "omschrijving",
                                                     "aantalunitomschrijving")
                         if key in normalized), None
                    ),
                    "confidence": 0.0,
                },
                "amount": {
                    "value": next(
                        (normalized[key] for key in ("amount", "bedrag", "kosten",
                                                     "subtotal", "totaal")
                         if key in normalized), None
                    ),
                    "confidence": 0.0,
                },
                "tax_raw_text": {
                    "value": next(
                        (normalized[key] for key in ("tax", "taxrawtext", "btw")
                         if key in normalized), None
                    ),
                    "confidence": 0.0,
                },
            })
        result = {
            "header": header,
            "lines": canonical_lines,
            "is_multi_invoice": next(iter(multi_invoice)),
        }
        result = BaseAIProviderAdapter._canonical(result)
        validate(result, CANONICAL_INVOICE_RESULT_SCHEMA)
        return result
    except (ValidationError, TypeError, ValueError, AIProviderPermanentError) as error:
        if isinstance(error, DocumentNormalizationError):
            raise
        raise DocumentNormalizationError(
            "Document normalization produced an invalid canonical result."
        ) from error
