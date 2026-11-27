"""Feed enquiry, signed inventory selections and reviewed stock corrections."""

import uuid
from datetime import datetime
from decimal import Decimal, localcontext
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from . import clock, services
from .context import scope
from .feed import FEED_TYPES, unit_for
from .models import Event, Inventory

COLUMNS = [
    ("name", "Product"), ("type", "Type"), ("units", "Units Remaining"),
    ("balance", "Remaining Stock"), ("size", "Quantity/Item"), ("price", "Price/Item"),
    ("cost", "Cost/Stock Unit"), ("feed_unit", "Feed Unit"), ("value", "Stock Value"),
    ("date", "Batch/Date"),
]


def table(request, items):
    mode = request.GET.get("select", "")
    if mode not in {"remove", "edit"}:
        mode = ""
    chosen = request.GET.getlist("chosen")
    if chosen:
        chosen = [str(i.pk) for i in selected_items(request.user, chosen, mode or "edit")]
    types = dict(FEED_TYPES)
    rows = []
    for item in items:
        rows.append(dict(
            item=item, identity=str(item.pk), name=item.name,
            type=types.get(item.feed_type, item.feed_type), units=item.packages_remaining,
            balance=item.balance, size=item.package_size, price=item.package_price,
            cost=item.cost_per_stock_unit, feed_unit=unit_for(item), value=item.remaining_value,
            date=item.date_value, batch=item.batch,
            selectable=mode != "remove" or not item.retired, checked=str(item.pk) in chosen,
        ))
    key = request.GET.get("sort", "name")
    if key not in dict(COLUMNS):
        key = "name"
    descending = request.GET.get("direction") == "desc"
    rows.sort(key=lambda row: int(row["identity"]))
    present = [r for r in rows if r[key] not in (None, "")]
    missing = [r for r in rows if r[key] in (None, "")]
    def value(row):
        v = row[key]
        if key == "date":
            return v, row["batch"].casefold()
        return v.casefold() if isinstance(v, str) else v
    present.sort(key=value, reverse=descending)
    if key == "date":
        missing.sort(key=lambda row: row["batch"].casefold(), reverse=descending)
    headings = []
    for column, label in COLUMNS:
        params = [
            ("select", mode), ("removed", request.GET.get("removed", "")),
            ("sort", column),
            ("direction", "asc" if column == key and descending else "desc" if column == key else "asc"),
            *[("chosen", identity) for identity in chosen],
        ]
        headings.append(dict(label=label, active=column == key,
            direction="descending" if descending else "ascending",
            arrow=(" ▼" if descending else " ▲") if column == key else "",
            url="?" + urlencode(params)))
    return dict(rows=present + missing, headings=headings, selection_mode=mode)


def selected_items(actor, ids, action):
    try:
        ids = [int(value) for value in ids]
    except (ValueError, TypeError, OverflowError):
        raise ValidationError("Select eligible feed products from Feed Inventory.")
    if not ids or len(ids) > 2000 or len(set(ids)) != len(ids) or any(i <= 0 for i in ids):
        raise ValidationError("Select one or more distinct feed products.")
    items = list(scope(Inventory, actor).filter(kind="feed", pk__in=ids).order_by("pk"))
    if len(items) != len(ids) or action == "remove" and any(i.retired for i in items):
        raise ValidationError("Selected feed is no longer eligible in this property. Select again.")
    return items


def selection(request, action, ids=None, token=None):
    salt = "feed-selection:" + str(request.user.pk)
    if ids is not None:
        items = selected_items(request.user, ids, action)
        state = dict(ids=[str(i.pk) for i in items], action=action, context=request.farm_context)
        return signing.dumps(state, salt=salt, compress=True), items
    state = signing.loads(token, salt=salt, max_age=3600)
    if state["context"] != request.farm_context or state["action"] != action:
        raise PermissionDenied("Property/PIC or inventory selection changed. Select again.")
    return token, selected_items(request.user, state["ids"], action)


class ProductEditForm(forms.Form):
    """Existing actual-balance, retirement and reason controls, grouped by product."""
    def __init__(self, items, action, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.items, self.action = items, action
        self.groups = []
        for item in items:
            prefix = str(item.pk) + "_"
            self.fields[prefix + "actual"] = forms.DecimalField(
                label="Actual remaining stock (" + item.base_unit + ")",
                max_digits=30, decimal_places=12, initial=item.balance,
                widget=forms.NumberInput(attrs={"step": "any"}))
            self.fields[prefix + "retired"] = forms.BooleanField(
                label="Retire product", required=False, initial=True if action == "remove" else item.retired)
            self.fields[prefix + "reason"] = forms.CharField(
                label="Reason", max_length=4000, widget=forms.Textarea(attrs={"rows": 2}))
            self.groups.append((item, [self[prefix + k] for k in ["actual", "retired", "reason"]]))

    def clean(self):
        d = super().clean()
        for item in self.items:
            prefix = str(item.pk) + "_"
            if self.action == "remove" and d.get(prefix + "actual") is not None:
                if d[prefix + "actual"] > item.balance:
                    self.add_error(prefix + "actual", "A removal cannot increase stock. Use Bulk Edit for a correction.")
        return d

    def payload(self):
        return services.clean(dict(
            action="selected_" + self.action,
            rows=[dict(item=str(i.pk), actual=self.cleaned_data[str(i.pk) + "_actual"],
                       retired=self.cleaned_data[str(i.pk) + "_retired"],
                       reason=self.cleaned_data[str(i.pk) + "_reason"],
                       before_balance=i.balance, before_retired=i.retired) for i in self.items],
        ))


def adjust_selected(actor, event, data):
    """Called inside execute's property lock; do not change receipt cost specifications."""
    action = data["action"].removeprefix("selected_")
    if action not in {"edit", "remove"}:
        raise ValidationError("Invalid feed adjustment.")
    rows = data.get("rows", [])
    items = selected_items(actor, [r["item"] for r in rows], action)
    by_id = {str(i.pk): i for i in items}
    saved, changes = [], []
    for row in rows:
        item = by_id[str(row["item"])]
        if not row.get("reason") or not isinstance(row.get("retired"), bool):
            raise ValidationError("Record a reason and retirement status for each product.")
        if Decimal(str(row["before_balance"])) != item.balance or row["before_retired"] != item.retired:
            raise ValidationError("Stock or retirement status changed. Preview again.")
        actual = services.number(row["actual"])
        if action == "remove" and actual > item.balance:
            raise ValidationError("A removal cannot increase stock.")
        saved.append(dict(item=item.pk, retired=item.retired, balance=str(item.balance)))
        changes.append(dict(product=item.name, unit=item.base_unit, before=item.balance,
                            after=actual, removed=item.balance-actual,
                            before_retired=item.retired, retired=row["retired"], reason=row["reason"]))
        if actual != item.balance:
            services.stocktake(actor, event, dict(item=item.pk, actual=actual, reason=row["reason"]))
        if row["retired"] != item.retired:
            services.retire(actor, event, dict(item=item.pk, retired=row["retired"]))
    event.before = {"feed_items": saved}
    return dict(count=len(items), items=[i.pk for i in items], changes=changes)


def usage(actor, item):
    # Shared stock enquiry; Event scope keeps feeding statistics on the active PIC.
    events = scope(Event, actor).filter(kind="feed", reversed_by__isnull=True)
    total, animals, missing_cohort, missing_quantity, latest = Decimal(0), set(), False, False, None
    for event in events.prefetch_related("stock_postings", "participants", "allocations"):
        postings = [p for p in event.stock_postings.all() if p.item_id == item.pk]
        if not postings and str(event.details.get("item", "")) != str(item.pk):
            continue
        ids = {p.animal_id for p in event.participants.all()}
        if not ids:
            ids = {a.animal_id for a in event.allocations.all() if a.category == "feed"}
        expected = event.details.get("count")
        try:
            complete = bool(ids) and (expected is None or len(ids) == int(expected))
        except (ValueError, TypeError):
            complete = False
        missing_cohort |= not complete
        animals.update(ids)
        if not postings:
            missing_quantity = True
        with localcontext() as ctx:
            ctx.prec = 60
            total -= sum((p.quantity for p in postings), Decimal(0))
        latest = max(latest if latest is not None else event.effective_at, event.effective_at)
    receipt = item.postings.filter(quantity__gt=0, event__kind="receipt",
                                  event__reversed_by__isnull=True).select_related("event").order_by(
                                      "event__effective_at", "event__effective_order").first()
    zone = ZoneInfo(actor.property.timezone)
    entry = datetime.fromtimestamp(receipt.event.effective_at, zone).date() if receipt else None
    local_today = datetime.fromtimestamp(clock.now(), zone).date()
    return dict(cattle=None if missing_cohort else len(animals),
                held_days=(local_today-entry).days if entry else None, entry=entry,
                total=None if missing_quantity else total, unit=item.base_unit, latest=latest)


def details_context(request, item):
    return dict(product=item, usage=usage(request.user, item), feed_unit=unit_for(item))


@login_required
def product_detail(request, pk):
    item = get_object_or_404(scope(Inventory, request.user), pk=pk, kind="feed")
    return edit_workflow(request, "edit", single=item)


@login_required
def manage(request, action):
    action = {"retire": "remove", "stocktake": "edit"}.get(action)
    if action is None:
        from django.http import Http404
        raise Http404
    return edit_workflow(request, action)


def edit_workflow(request, action, single=None):
    token = request.POST.get("selection_token") or request.GET.get("selection_token")
    title = "Remove Feed" if action == "remove" else "Edit Feed" if single else "Bulk Edit Feed"
    ctx = dict(title=title, action=action, operation="feed_adjust")
    if single:
        ctx.update(details_context(request, single))
    try:
        # Exact committed retries remain valid even when the save retired a selected product.
        if request.POST.get("confirmed_payload"):
            state = signing.loads(request.POST["confirmed_payload"], salt="feed-edit:" + str(request.user.pk), max_age=1800)
            if state["context"] != request.farm_context or state["action"] != action:
                raise PermissionDenied("Property/PIC or workflow changed. Preview again.")
            if single and state["ids"] != [str(single.pk)]:
                raise PermissionDenied("Product changed. Preview again.")
            try:
                services.execute(request.user, state["key"], "feed_adjust", state["data"], state["version"])
            except (ValidationError, IntegrityError) as exc:
                items = selected_items(request.user, state["ids"], action)
                token, items = selection(request, action, ids=state["ids"])
                entered = {str(row["item"]) + "_" + key: row[key]
                           for row in state["data"]["rows"] for key in ["actual", "retired", "reason"]}
                ctx.update(form=ProductEditForm(items, action, entered), selection_token=token,
                           error="; ".join(getattr(exc, "messages", [str(exc)])))
                return render(request, "herd/feed_edit.html", ctx)
            request.session["feed_confirmed"] = state["key"]
            messages.success(request, "Feed inventory updated.")
            return redirect("feed_product", pk=single.pk) if single else redirect("feed_inventory")
        if request.POST.get("task") == "select":
            token, items = selection(request, action, ids=request.POST.getlist("selected_ids"))
        elif single and not token:
            token, items = selection(request, action, ids=[single.pk])
        elif token:
            token, items = selection(request, action, token=token)
        else:
            return redirect("/inventory/feed/?select=" + action)
        if single and [str(i.pk) for i in items] != [str(single.pk)]:
            raise PermissionDenied("Select this product before editing it.")
    except (ValidationError, signing.BadSignature, KeyError, ValueError, TypeError) as exc:
        ctx.update(selection_error=True, error="; ".join(getattr(exc, "messages", ["Selection is invalid or expired. Select feed again."])))
        return render(request, "herd/feed_edit.html", ctx, status=400)
    form = ProductEditForm(items, action, request.POST if request.POST.get("task") == "preview" else None)
    ctx.update(form=form, selected_items=items, selection_token=token)
    try:
        if request.POST.get("task") == "preview" and form.is_valid():
            data = form.payload()
            reviewed = services.preview(request.user, "feed_adjust", data)
            state = dict(context=request.farm_context, action=action, ids=[str(i.pk) for i in items],
                         data=data, version=reviewed["version"], key=uuid.uuid4().hex)
            ctx.update(confirmation=signing.dumps(state, salt="feed-edit:" + str(request.user.pk), compress=True),
                       changes=reviewed["effects"]["changes"])
    except (ValidationError, IntegrityError, ValueError, KeyError) as exc:
        form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
    confirmed = request.session.pop("feed_confirmed", "")
    ctx["confirmed_submission"] = confirmed
    return render(request, "herd/feed_edit.html", ctx)
