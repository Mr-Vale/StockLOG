"""Dedicated plain-language workflow forms. Domain services revalidate every input."""

from django import forms

from .clock import local_timestamp
from .models import Account, Inventory, Mob, ReportTemplate

LABELS = {
    "nlis": "NLIS visual ID (16 characters)",
    "rfid": "RFID (15 digits)",
    "effective_at": "Event date and time",
    "time_offset": "UTC offset for repeated daylight-saving time (optional, e.g. +10:00)",
    "package_size": "Quantity per container / kg per bale",
    "package_price": "AUD per container or package",
    "packages": "Number of packages / containers",
    "purchase_cost": "Purchase price AUD (leave empty if unknown)",
    "mother_nlis": "Mother's NLIS visual ID",
    "dose": "Actual dose per animal",
    "fee": "Procedure / vet fee AUD",
    "actual": "Actual remaining stock in base units",
    "administration": "Historical administration: I have reviewed consequential changes",
}
COMMON = ["effective_at", "time_offset", "reason"]
FIELDS = {
    "identifier_review": [
        "animal",
        "identifier_kind",
        "identifier_value",
        "resolution",
    ],
    "register": [
        "entry_source",
        "nlis",
        "rfid",
        "source_pic",
        "nvd",
        "nlis_upload_reference",
        "vendor_name",
        "vendor_address",
        "destination_paddock_text",
        "purchase_cost",
        "breed",
        "sex",
        "estimated_weeks",
        "dob",
        "mother_nlis",
        "mob",
        "notes",
    ],
    "mob": ["name"],
    "move": ["animal", "mob", "destination", "administration"],
    "replace_tag": ["animal", "nlis", "rfid"],
    "edit_animal": [
        "animal",
        "breed",
        "sex",
        "estimated_weeks",
        "dob",
        "purchase_cost",
    ],
    "sale": [
        "animals",
        "mob",
        "destination_pic",
        "destination_name",
        "nvd",
        "nlis_upload_reference",
        "origin_paddock_text",
        "price",
        "price_mode",
        "accept_restriction",
    ],
    "death": ["animals", "mob"],
    "receipt": [
        "kind",
        "name",
        "feed_type",
        "category",
        "packages",
        "package_size",
        "stock_unit",
        "package_price",
        "dose_unit",
        "batch",
        "date_kind",
        "date_value",
        "restriction_days",
        "storage",
        "supplier_name",
        "origin_text",
        "home_grown",
        "declaration_type",
        "declaration_reference",
        "declaration_details",
        "residue_certificate_available",
        "product_tested",
        "residue_test_reference",
        "residue_test_details",
        "signed_by_name",
    ],
    "feed": ["mob", "item", "quantity", "mode", "storage", "responsible_name"],
    "treat": [
        "animal",
        "mob",
        "item",
        "dose",
        "dose_unit",
        "administered_by",
        "administered_by_contact",
        "livestock_description",
        "location_text",
        "administration_method",
        "rate_description",
        "expired_override",
        "override_reason",
        "adverse_reactions",
        "broken_needle_status",
        "broken_needle_details",
        "equipment_cleaned_calibrated",
        "equipment_description",
        "equipment_checked_on",
        "equipment_checked_by_name",
        "equipment_checked_by_contact",
        "notes",
    ],
    "procedure": [
        "animal",
        "mob",
        "procedure",
        "fee",
        "fee_mode",
        "administered_by",
        "administered_by_contact",
        "notes",
    ],
    "vet": [
        "animal",
        "mob",
        "fee",
        "fee_mode",
        "administered_by",
        "administered_by_contact",
        "notes",
    ],
    "stocktake": ["item", "actual"],
    "retire": ["item", "retired"],
    "observation": ["animal", "mob", "notes"],
    "reverse": ["original"],
    "purge": ["animal", "confirm"],
    "template": ["template", "name", "definition", "delete"],
    "account": ["account", "username", "role", "active", "password"],
}
CHOICES = {
    "identifier_kind": [("rfid", "RFID"), ("nlis", "NLIS visual")],
    "resolution": [
        (
            "reject_conflicting_link",
            "Reject incorrect link and preserve both identities",
        ),
        (
            "retire_incorrect_current",
            "Retire this animal’s incorrect current tag without releasing its reservation",
        ),
    ],
    "entry_source": [
        ("purchase", "Purchase"),
        ("birth", "Farm-born"),
        ("repurchase", "Repurchase"),
    ],
    "kind": [("feed", "Feed"), ("chemical", "Chemical")],
    "stock_unit": [(u, u) for u in ["kg", "g", "L", "mL", "unit"]],
    "dose_unit": [(u, u) for u in ["mL", "L", "g", "kg", "unit"]],
    "mode": [
        ("total_kg", "Total kg"),
        ("bales", "Fractional bales"),
        ("kg_per_head", "kg per animal"),
        ("stock_units", "Total stock units"),
    ],
    "price_mode": [("per_head", "Per head"), ("group", "Group total")],
    "fee_mode": [("per_head", "Per head"), ("group", "Group total")],
    "date_kind": [
        ("", "Not supplied"),
        ("expiry", "Expiry"),
        ("DOM", "Manufacture date"),
    ],
    "category": [("veterinary", "Veterinary"), ("agricultural", "Agricultural")],
    "role": [("standard", "Standard user"), ("admin", "Administrator")],
    "sex": [("", "Unknown"), ("M", "Male"), ("F", "Female"), ("STEER", "Steer")],
    "broken_needle_status": [("", "Unknown"), ("no", "No"), ("yes", "Yes")],
    "equipment_cleaned_calibrated": [("", "Unknown"), ("no", "No"), ("yes", "Yes")],
    "residue_certificate_available": [("", "Unknown"), ("no", "No"), ("yes", "Yes")],
    "product_tested": [("", "Unknown"), ("no", "No"), ("yes", "Yes")],
}
BOOL = {
    "administration",
    "accept_restriction",
    "expired_override",
    "retired",
    "confirm",
    "delete",
    "active",
    "home_grown",
}
DECIMAL = {
    "packages",
    "package_size",
    "package_price",
    "purchase_cost",
    "price",
    "quantity",
    "dose",
    "fee",
    "actual",
}
TEXT = {
    "notes",
    "reason",
    "adverse_reactions",
    "broken_needle_details",
    "declaration_details",
    "residue_test_details",
}


class ActionForm(forms.Form):
    def __init__(self, actor, operation, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor, self.operation = actor, operation
        for key in COMMON + FIELDS[operation]:
            label = LABELS.get(key, key.replace("_", " ").capitalize())
            if key == "effective_at":
                f = forms.CharField(
                    required=False,
                    label=label,
                    help_text="Local time in your property timezone; use ISO time with an explicit UTC offset during a repeated daylight-saving hour.",
                    widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
                )
            elif key in BOOL:
                f = forms.BooleanField(
                    required=False, label=label, initial=key in ["active", "retired"]
                )
            elif key in DECIMAL:
                f = forms.DecimalField(
                    required=False,
                    max_digits=30,
                    decimal_places=12,
                    label=label,
                    widget=forms.NumberInput(attrs={"step": "any"}),
                )
            elif key in CHOICES:
                f = forms.ChoiceField(required=False, choices=CHOICES[key], label=label)
            elif key in ["mob", "destination", "item", "template", "account"]:
                model = {
                    "mob": Mob,
                    "destination": Mob,
                    "item": Inventory,
                    "template": ReportTemplate,
                    "account": Account,
                }[key]
                qs = model.objects.filter(property=actor.property)
                if key == "item" and operation in ["feed", "treat"]:
                    qs = qs.filter(
                        retired=False,
                        kind="feed" if operation == "feed" else "chemical",
                    )
                    if operation == "feed":
                        qs = qs.exclude(balance=0)
                f = forms.ChoiceField(
                    required=False,
                    label=label,
                    choices=[("", "Select if applicable")]
                    + [
                        (
                            str(r.pk),
                            getattr(r, "name", getattr(r, "username", str(r.pk)))
                            + (f" — {r.balance} {r.base_unit}" if isinstance(r, Inventory) else ""),
                        )
                        for r in qs
                    ],
                )
            elif key == "definition":
                f = forms.JSONField(
                    required=False,
                    label="Report settings",
                    help_text="Use the report builder to obtain validated report settings.",
                    initial={},
                )
            else:
                f = forms.CharField(
                    required=False,
                    max_length=4000,
                    label=label,
                    widget=forms.PasswordInput(render_value=False)
                    if key == "password"
                    else forms.Textarea(attrs={"rows": 3})
                    if key in TEXT or key == "animals"
                    else forms.TextInput(),
                )
            self.fields[key] = f

    def clean(self):
        d = super().clean()
        if d.get("effective_at"):
            try:
                d["effective_at"] = local_timestamp(
                    d["effective_at"] + str(d.get("time_offset") or ""),
                    self.actor.property.timezone,
                )
            except (ValueError, TypeError) as e:
                self.add_error("effective_at", str(e))
        else:
            d.pop("effective_at", None)
        if d.get("animals"):
            d["animals"] = [
                x.strip() for x in d["animals"].replace(",", "\n").splitlines() if x.strip()
            ]
        for key in ["estimated_weeks", "restriction_days"]:
            if d.get(key) not in [None, ""]:
                try:
                    d[key] = int(d[key])
                except ValueError:
                    self.add_error(key, "Enter whole nonnegative weeks/days.")
        return {k: v for k, v in d.items() if v not in [None, ""]}
