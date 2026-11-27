"""Property-wide inventory pages and reviewed feed transactions."""

import uuid
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render

from . import clock, services
from .context import scope
from .models import Inventory, Mob

FEED_TYPES = [("hay", "Hay"), ("grain_mix", "Grain Mix"), ("pellet", "Pellet"), ("milk_powder", "Milk Powder")]
ITEM_UNITS = [(u, "ml" if u == "mL" else u) for u in ["kg", "g", "L", "mL"]]
FEED_UNITS = [("unit", "unit"), *ITEM_UNITS]
NO_FEED = "No feed available. Add feed to Feed Inventory before recording a feeding."
SOURCE_FIELDS = ["supplier_name", "origin_text", "batch", "declaration_reference", "date_kind", "date_value", "product_tested", "residue_test_details"]


def today(actor):
    return datetime.fromtimestamp(clock.now(), ZoneInfo(actor.property.timezone)).date()


def dated(actor, value, prepared=None, *, end=False):
    from .cattle_services import date_timestamp, exit_timestamp

    if end:
        return exit_timestamp(actor, value, prepared)
    at = date_timestamp(actor, value)
    if prepared is not None and int(prepared) != at:
        raise ValidationError("Date Stored changed. Preview again.")
    return at


def unit_for(item):
    return item.feed_unit or ("kg" if item.base_unit == "kg" else item.stock_unit)


def conversion(unit, base):
    factors = {
        ("kg", "kg"): Decimal(1), ("g", "kg"): Decimal(".001"),
        ("g", "g"): Decimal(1), ("kg", "g"): Decimal(1000),
        ("L", "mL"): Decimal(1000), ("mL", "mL"): Decimal(1),
        ("unit", "unit"): Decimal(1),
    }
    try:
        return factors[(unit, base)]
    except KeyError:
        raise ValidationError("Choose compatible units. Mass and volume cannot be converted.")


def compatible(item_unit, feed_unit):
    if feed_unit == "unit":
        return
    base = "kg" if item_unit in {"kg", "g"} else "mL"
    conversion(feed_unit, base)


def available(actor):
    return scope(Inventory, actor).filter(kind="feed", retired=False, balance__gt=0).order_by("name", "pk")


class FeedEntryForm(forms.Form):
    stored_date = forms.DateField(label="Date Stored", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    name = forms.CharField(label="Product Name", max_length=120)
    feed_type = forms.ChoiceField(label="Feed Type")
    packages = forms.DecimalField(label="Number of Units (No. Bales/Bags)", max_digits=30, decimal_places=12,
                                  widget=forms.NumberInput(attrs={"step": "any"}))
    package_size = forms.DecimalField(label="Quantity Per Unit (Bag or Bale Kg)", max_digits=30, decimal_places=12,
                                      widget=forms.NumberInput(attrs={"step": "any"}))
    stock_unit = forms.ChoiceField(label="Item Unit", choices=ITEM_UNITS)
    feed_unit = forms.ChoiceField(label="Feed Unit", choices=FEED_UNITS)
    package_price = forms.DecimalField(label="Cost per Item ($)", max_digits=12, decimal_places=2, min_value=0)
    home_grown = forms.BooleanField(label="Produced On Farm", required=False, initial=True)
    supplier_name = forms.CharField(label="Source Name", max_length=160, required=False)
    origin_text = forms.CharField(label="Source Address", max_length=4000, required=False)
    batch = forms.RegexField(label="Batch Number", regex=r"^[A-Za-z0-9]*$", max_length=80, required=False)
    declaration_reference = forms.RegexField(label="CVD or Equivalent Reference", regex=r"^[A-Za-z0-9]*$", max_length=80, required=False)
    date_kind = forms.ChoiceField(label="Date Type", choices=[("", "Not supplied"), ("expiry", "Expiry"), ("DOM", "Manufactured")], required=False)
    date_value = forms.DateField(label="Expiry/Manufacturing Date", required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    product_tested = forms.ChoiceField(label="Residue Tested", choices=[("no", "No"), ("yes", "Yes")], required=False)
    residue_test_details = forms.CharField(label="Residue Test Details", max_length=4000, required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, actor, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.actor = actor
        self.initial.setdefault("stored_date", today(actor))
        self.initial.setdefault("home_grown", True)
        self.initial.setdefault("product_tested", "no")
        self.initial.setdefault("date_kind", "expiry")
        self.initial.setdefault("stock_unit", "kg")
        self.initial.setdefault("feed_unit", "kg")
        types = dict(FEED_TYPES)
        for value in scope(Inventory, actor).filter(kind="feed").exclude(feed_type="").values_list("feed_type", flat=True).distinct():
            types.setdefault(value, value)
        self.fields["feed_type"].choices = list(types.items())
        for key in ["packages", "package_size"]:
            self.fields[key].help_text = "Rounded down to a whole number before preview and save."
        self.fields["package_price"].help_text = "$; at most 10 digits before the decimal and 2 decimal places."
        if data is not None and data.get("home_grown"):
            for key in SOURCE_FIELDS:
                self.fields[key].disabled = True

    def clean(self):
        d = super().clean()
        for key in ["packages", "package_size"]:
            if key in d:
                d[key] = d[key].to_integral_value(rounding=ROUND_FLOOR)
                if d[key] <= 0:
                    self.add_error(key, "The rounded whole number must be positive.")
        if d.get("stored_date"):
            try:
                d["effective_at"] = dated(self.actor, d["stored_date"], self.data.get("effective_at"))
            except (ValidationError, ValueError) as exc:
                self.add_error("stored_date", exc)
        if d.get("stock_unit") and d.get("feed_unit"):
            try:
                compatible(d["stock_unit"], d["feed_unit"])
            except ValidationError as exc:
                self.add_error("feed_unit", exc)
        if d.get("name") and scope(Inventory, self.actor).filter(kind="feed", retired=False, balance__gt=0, name__iexact=d["name"].strip()).exists():
            self.add_error("name", "An in-stock feed record already uses this product name.")
        if d.get("home_grown"):
            for key in SOURCE_FIELDS:
                d[key] = None if key == "date_value" else ""
        else:
            if d.get("date_value") and not d.get("date_kind"):
                self.add_error("date_kind", "Choose Expiry or Manufactured for this date.")
            if not d.get("date_value"):
                d["date_kind"] = ""
            d["product_tested"] = d.get("product_tested") or "no"
            if d["product_tested"] != "yes":
                d["residue_test_details"] = ""
        return d

    def payload(self):
        return services.clean({**self.cleaned_data, "kind": "feed", "feed_entry": True})


class FeedingForm(forms.Form):
    feed_date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    mob = forms.ChoiceField(label="Mob")
    feed_type = forms.ChoiceField(label="Feed Type")
    item = forms.ChoiceField(label="Feed")
    quantity = forms.DecimalField(label="Quantity", max_digits=30, decimal_places=12, widget=forms.NumberInput(attrs={"step": "any"}))
    mode = forms.ChoiceField(label="Mode")
    notes = forms.CharField(label="Note", required=False, max_length=4000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, actor, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.actor = actor
        self.products = list(available(actor))
        raw = data if data is not None else self.initial
        self.initial.setdefault("feed_date", today(actor))
        types = dict(FEED_TYPES)
        present = {i.feed_type or "__other__" for i in self.products}
        self.fields["feed_type"].choices = [(v, types.get(v, "Other / unclassified" if v == "__other__" else v)) for v in sorted(present)]
        chosen_type = raw.get("feed_type") or (self.fields["feed_type"].choices[0][0] if present else "")
        self.initial.setdefault("feed_type", chosen_type)
        eligible = [i for i in self.products if (i.feed_type or "__other__") == chosen_type]
        self.fields["item"].choices = [("", "Select feed")] + [(str(i.pk), i.name) for i in eligible]
        item = next((i for i in eligible if str(i.pk) == str(raw.get("item", ""))), None)
        self.fields["mode"].choices = [("unit", "Unit")]
        if item and unit_for(item) != "unit":
            self.fields["mode"].choices.append(("measure", "ml" if unit_for(item) == "mL" else unit_for(item)))
        self.initial.setdefault("mode", "unit")
        try:
            at = dated(actor, raw.get("feed_date") or today(actor), end=True)
        except (ValidationError, ValueError, TypeError):
            at = clock.now()
        mobs = []
        for mob in scope(Mob, actor).filter(retired=False).order_by("name"):
            try:
                services.members(actor, mob.pk, at)
                mobs.append((str(mob.pk), mob.name))
            except ValidationError:
                pass
        self.fields["mob"].choices = [("", "Select mob")] + mobs
        self.fields["quantity"].help_text = "Unit mode requires a whole number of items. Measurement mode permits fractions."

    def clean(self):
        d = super().clean()
        if d.get("feed_date"):
            try:
                d["effective_at"] = dated(self.actor, d["feed_date"], self.data.get("effective_at"), end=True)
            except (ValidationError, ValueError, TypeError) as exc:
                self.add_error("feed_date", exc)
        if "quantity" in d:
            if d["quantity"] <= 0:
                self.add_error("quantity", "Enter a positive quantity.")
            elif d.get("mode") == "unit" and d["quantity"] != d["quantity"].to_integral_value():
                self.add_error("quantity", "Unit mode requires a whole number of items.")
        return d

    def payload(self):
        item = next(i for i in self.products if str(i.pk) == str(self.cleaned_data["item"]))
        return services.clean({
            **self.cleaned_data, "feeding_form": True, "feed_unit": unit_for(item),
            "preview_balance": item.balance, "preview_unit_cost": item.unit_cost,
            "preview_base_per_package": item.base_per_package,
        })


def validate_receipt(actor, data):
    form = FeedEntryForm(actor, data)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    return form.payload()


def validate_feeding(actor, data):
    form = FeedingForm(actor, data)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    # Retain the reviewed snapshots for the transaction's comparison.
    return {**form.payload(), **{k: data[k] for k in [
        "preview_balance", "preview_unit_cost", "preview_base_per_package", "preview_animals", "feed_unit"
    ] if k in data}}


class FeedAdjustForm(forms.Form):
    items = forms.MultipleChoiceField(label="Feed records", widget=forms.CheckboxSelectMultiple)
    reason = forms.CharField(label="Reason", widget=forms.Textarea(attrs={"rows": 3}), max_length=4000)

    def __init__(self, actor, action, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.action = action
        self.items = list(scope(Inventory, actor).filter(kind="feed", retired=False).order_by("name"))
        self.fields["items"].choices = [(str(i.pk), i.name) for i in self.items]
        chosen = data.getlist("items") if hasattr(data, "getlist") else (data or {}).get("items", [])
        if action == "stocktake":
            for item in self.items:
                key = "balance_" + str(item.pk)
                self.fields[key] = forms.DecimalField(
                    label=item.name + " — actual remaining " + item.base_unit, required=False,
                    max_digits=30, decimal_places=12, initial=item.balance,
                    widget=forms.NumberInput(attrs={"step": "any"}),
                    disabled=data is not None and str(item.pk) not in chosen,
                )

    def clean(self):
        d = super().clean()
        if self.action == "stocktake":
            for value in d.get("items", []):
                key = "balance_" + value
                if d.get(key) is None:
                    self.add_error(key, "Enter the actual stock balance for this selected product.")
        return d

    def payload(self):
        d = self.cleaned_data
        return services.clean({
            "action": self.action, "reason": d["reason"],
            "rows": [{"item": value, **({"actual": d["balance_" + value]} if self.action == "stocktake" else {})} for value in d["items"]],
        })


def adjust_feed(actor, event, data):
    if data.get("action") in {"selected_edit", "selected_remove"}:
        from .feed_inventory import adjust_selected
        return adjust_selected(actor, event, data)
    if data.get("action") not in {"retire", "stocktake"} or not data.get("reason"):
        raise ValidationError("Choose a feed adjustment and record its reason.")
    rows = data.get("rows", [])
    if not rows or len(rows) > 2000 or len({str(r["item"]) for r in rows}) != len(rows):
        raise ValidationError("Select distinct feed records to adjust.")
    saved = []
    for row in rows:
        item = services.scoped(Inventory, actor, row["item"])
        if item.kind != "feed" or item.retired:
            raise ValidationError("Select current feed records in this property.")
        saved.append({"item": item.pk, "retired": item.retired, "balance": str(item.balance)})
        if data["action"] == "retire":
            services.retire(actor, event, {"item": item.pk, "retired": True})
        else:
            services.stocktake(actor, event, {**row, "reason": data["reason"]})
    event.before = {"feed_items": saved}
    return {"count": len(rows), "items": [r["item"] for r in saved]}


@login_required
def inventory_page(request, kind="feed"):
    from .feed_inventory import table
    items = list(scope(Inventory, request.user).filter(kind=kind).order_by("retired", "name"))
    if kind == "feed" and not request.GET.get("removed"):
        items = [item for item in items if not item.retired]
    for item in items:
        item.display_feed_unit = unit_for(item)
    confirmed = request.session.pop("feed_confirmed", "") if kind == "feed" else ""
    try:
        ctx = table(request, items) if kind == "feed" else {}
    except ValidationError as exc:
        return render(request, "herd/feed_edit.html", {"title": "Feed Inventory", "error": "; ".join(exc.messages)}, status=400)
    return render(request, "herd/inventory.html", {
        **ctx,
        "confirmed_submission": confirmed,
        "kind": kind, "items": items,
        "title": request.user.property.name + (" Feed Inventory" if kind == "feed" else " Chemical Inventory"),
    })


@login_required
def add_feed(request):
    return reviewed_workflow(request, "receipt", FeedEntryForm, "Add Feed")


@login_required
def feeding(request):
    return reviewed_workflow(request, "feed", FeedingForm, "Cattle Feeding")


@login_required
def manage_feed(request, action):
    from .feed_inventory import manage
    return manage(request, action)


def reviewed_workflow(request, operation, form_class, title):
    actor = request.user
    task = request.POST.get("task")
    form = form_class(actor, request.POST if request.method == "POST" and task == "preview" else None,
                      initial=request.POST.dict() if task == "refresh" else {})
    ctx = {"form": form, "title": title, "operation": operation}
    salt = "feed-workflow:" + str(actor.pk)
    state = None
    try:
        if request.method == "POST" and request.POST.get("confirmed_payload"):
            state = signing.loads(request.POST["confirmed_payload"], salt=salt, max_age=1800)
            if state["context"] != request.farm_context or state["operation"] != operation or state["title"] != title:
                raise PermissionDenied("Property/PIC or workflow changed. Preview again.")
            # execute checks the exact digest for retries, then version and validation under its lock.
            services.execute(actor, state["key"], operation, state["data"], state["version"])
            request.session["feed_confirmed"] = state["key"]
            messages.success(request, "Feed record saved." if operation == "receipt" else "Feeding saved." if operation == "feed" else "Feed inventory updated.")
            return redirect("feed_inventory")
        if task == "preview" and form.is_valid():
            data = form.payload()
            reviewed = services.preview(actor, operation, data)
            if operation == "feed":
                data["preview_animals"] = sorted(str(row["animal_id"]) for row in reviewed["effects"]["allocations"])
            state = {
                "operation": operation, "title": title, "context": request.farm_context,
                "key": uuid.uuid4().hex, "data": data, "version": reviewed["version"],
            }
            details = []
            for key, field in form.fields.items():
                value = form.cleaned_data.get(key)
                if operation == "receipt" and key in SOURCE_FIELDS and form.cleaned_data.get("home_grown"):
                    continue
                if key == "residue_test_details" and form.cleaned_data.get("product_tested") != "yes":
                    continue
                if isinstance(field, forms.ChoiceField):
                    value = dict(field.choices).get(str(value), value)
                if isinstance(value, bool):
                    value = "Yes" if value else "No"
                details.append((field.label, value if value not in (None, "") else "Not recorded"))
            ctx.update(
                confirmation=signing.dumps(state, salt=salt, compress=True),
                details=details, preview_rows=preview_rows(form, details), effects=reviewed["effects"],
                negative_balance=operation == "feed" and Decimal(str(reviewed["effects"]["balance"])) < 0,
            )
    except (ValidationError, signing.BadSignature, IntegrityError, ValueError, KeyError) as exc:
        ctx["error"] = "; ".join(getattr(exc, "messages", [str(exc)]))
        if state:
            initial = state["data"]
            if operation == "feed_adjust":
                initial = {"items": [str(r["item"]) for r in initial["rows"]], "reason": initial["reason"],
                           **{"balance_" + str(r["item"]): r.get("actual") for r in initial["rows"]}}
            form = form_class(actor, initial)
            ctx["form"] = form
    ctx["no_feed"] = operation == "feed" and not available(actor).exists()
    if isinstance(ctx["form"], FeedingForm):
        ctx["products"] = [{"id": str(i.pk), "name": i.name, "type": i.feed_type or "__other__", "unit": unit_for(i)} for i in ctx["form"].products]
    return render(request, "herd/feed_workflow.html", ctx)


def preview_rows(form, details):
    """Keep signed payloads exact; format a separate representation for review."""
    from .templatetags.display import compact, money
    rows = []
    labels = {field.label: key for key, field in form.fields.items()}
    data = form.cleaned_data
    for label, value in details:
        key = labels[label]
        if key in {"package_price"}:
            value = money(value)
        elif key in {"packages", "package_size", "quantity"}:
            value = compact(value)
            if key == "packages":
                value += " units"
            elif key == "package_size":
                value += " " + data["stock_unit"]
            elif key == "quantity":
                item = next(i for i in form.products if str(i.pk) == str(data["item"]))
                value += " " + ("units" if data["mode"] == "unit" else unit_for(item))
        rows.append((label, value))
    return rows
