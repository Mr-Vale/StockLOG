"""Canonical cattle input names, with read compatibility for earlier releases."""

from django.core.exceptions import ValidationError

ALIASES = {
    "estimated_weeks": "age_weeks",
    "vendor_name": "source_name",
    "vendor_address": "source_address",
}


def canonical(data, *, arrival=False):
    result = dict(data)
    aliases = dict(ALIASES)
    if arrival:
        aliases.update(effective_at="farm_entry_date", entry_date="farm_entry_date")
    for old, new in aliases.items():
        if old in result:
            value = result.pop(old)
            if new in result and result[new] != value:
                raise ValidationError(f"Conflicting values for {new} and {old}.")
            result[new] = value
    if arrival and "rows" in result:
        result["rows"] = [canonical(row, arrival=True) for row in result["rows"]]
    return result
