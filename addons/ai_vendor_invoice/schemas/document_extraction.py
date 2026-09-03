# © 2024 Wukong Digital. License LGPL-3.
"""Minimal document-level extraction contract for native document providers."""

from .reconciliation_clue import RECONCILIATION_CLUE_SCHEMA

DOCUMENT_EXTRACTION_RESULT_SCHEMA = {
    "type": "object",
    "required": ["document_type", "invoice"],
    "additionalProperties": True,
    "properties": {
        "document_type": {"type": ["string", "null"]},
        "invoice": {
            "type": "object",
            "required": ["lines"],
            "additionalProperties": True,
            "properties": {
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["description", "amount"],
                        "additionalProperties": True,
                        "properties": {
                            "description": {"type": ["string", "null"]},
                            "amount": {"type": ["string", "number", "null"]},
                            "reconciliation_clues": {
                                "type": "array",
                                "items": RECONCILIATION_CLUE_SCHEMA,
                            },
                            "charge_components": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["description", "amount"],
                                    "additionalProperties": True,
                                    "properties": {
                                        "description": {"type": ["string", "null"]},
                                        "amount": {"type": ["string", "number", "null"]},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}
