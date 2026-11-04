"""Canonical text identifiers; legacy values are validated only when changed."""

import re

from django.core.exceptions import ValidationError

FORMATS = {
    "pic": (r"[0-9][A-Z]{4}[0-9]{3}", "PIC Number", "0XXXX000"),
    "nlis": (r"[0-9][A-Z]{4}[0-9]{3}[A-Z]{3}[0-9]{5}", "NLIS Visual ID", "0XXXX000XXX00000"),
    "rfid": (r"[0-9]{15}", "NLIS RFID", "15 ASCII digits"),
    "nvd": (r"[0-9]{8}", "NVD Number", "8 ASCII digits"),
}


def validate_identifier(kind, value):
    value = str(value or "").strip()
    if kind in {"nlis", "pic", "mother"}:
        value = value.upper()
    if kind == "mother":
        kind = "rfid" if re.fullmatch(r"[0-9]{15}", value) else "nlis"
    if kind not in FORMATS:
        raise ValidationError("Unsupported identifier type.")
    pattern, label, hint = FORMATS[kind]
    if not re.fullmatch(pattern, value):
        raise ValidationError(f"{label}: use {hint} in the required character order.")
    return value


def configure(field, kind):
    pattern, label, hint = FORMATS[kind]
    field.help_text = f"Format: {hint}. Leading zeros are preserved."
    field.widget.attrs.pop("maxlength", None)
    field.widget.attrs.update(pattern=r"\s*" + pattern + r"\s*", title=field.help_text)
    if kind in {"rfid", "nvd"}:
        field.widget.attrs["inputmode"] = "numeric"
    else:
        # HTML patterns must accept lowercase, just like authoritative validation.
        field.widget.attrs["pattern"] = r"\s*" + pattern.replace("[A-Z]", "[A-Za-z]") + r"\s*"
