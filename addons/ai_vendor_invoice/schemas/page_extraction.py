# © 2024 Wukong Digital. License LGPL-3.
"""Schema for the deliberately incomplete result of one page request."""

PAGE_EXTRACTION_RESULT_SCHEMA = {
    "type": "object",
    "required": ["page_number"],
    "additionalProperties": True,
    "properties": {
        "page_number": {"type": "integer", "minimum": 1},
        "header": {
            "type": "object",
            "additionalProperties": True,
        },
        "header_values": {"type": "object", "additionalProperties": True},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "is_multi_invoice": {"type": "boolean"},
    },
}
