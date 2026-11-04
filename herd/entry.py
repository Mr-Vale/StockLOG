"""Signed, temporary browser-carried input. No animal or draft is persisted before Save."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import render

from . import clock, services
from .forms import ActionForm
from .models import Submission

MODES = {"purchase": "Purchase", "birth": "Birth", "repurchase": "Re-Purchase"}
ORDER = {
    "purchase": [
        "farm_entry_date",
        "nlis",
        "rfid",
        "source_pic",
        "source_name",
        "source_address",
        "nvd",
        "breed",
        "sex",
        "mob",
        "purchase_cost",
        "age_weeks",
    ],
    "repurchase": [
        "farm_entry_date",
        "nlis",
        "rfid",
        "source_pic",
        "source_name",
        "source_address",
        "nvd",
    ],
    "birth": [
        "farm_entry_date",
        "nlis",
        "rfid",
        "source_pic",
        "source_name",
        "source_address",
        "breed",
        "sex",
        "mob",
        "purchase_cost",
        "dob",
        "mother_nlis",
    ],
}
LABELS = {
    "farm_entry_date": "Event Date",
    "nlis": "NLIS Visual ID — 16 characters",
    "rfid": "NLIS RFID — 15 digits",
    "source_pic": "Source PIC",
    "source_name": "Source Name",
    "source_address": "Source Address",
    "nvd": "NVD Number",
    "breed": "Breed/Description",
    "sex": "Sex",
    "mob": "MOB Number",
    "purchase_cost": "Cost (AUD)",
    "age_weeks": "Estimated Age — weeks",
    "dob": "Date of Birth",
    "mother_nlis": "Mother’s NLIS ID or RFID",
}


def today(actor):
    return datetime.fromtimestamp(clock.now(), ZoneInfo(actor.property.timezone)).date()


class EntryForm(ActionForm):
    def __init__(self, actor, mode, data=None, **kwargs):
        super().__init__(actor, "register", data, **kwargs)
        self.mode = mode
        self.fields = {k: self.fields[k] for k in ORDER[mode]}
        self.fields["farm_entry_date"] = forms.DateField(
            label="Event Date",
            initial=today(actor),
            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        )
        self.fields["farm_entry_date"].help_text = (
            "Property calendar date. Historical dates require an administrator."
        )
        for k, field in self.fields.items():
            field.label = LABELS[k]
        for k in ["nlis", "rfid"]:
            self.fields[k].max_length = 16 if k == "nlis" else 15
            self.fields[k].widget.attrs.update(maxlength=self.fields[k].max_length)
        if "dob" in self.fields:
            self.fields["dob"] = forms.DateField(
                required=False,
                label="Date of Birth",
                widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            )
        if "age_weeks" in self.fields:
            self.fields["age_weeks"] = forms.IntegerField(
                required=False, min_value=0, label=LABELS["age_weeks"]
            )
        if mode != "birth":
            for k in ["source_pic", "nvd"]:
                self.fields[k].required = True
        else:
            for k, v in dict(
                source_pic=actor.pic.number,
                source_name=actor.property.name,
                source_address=actor.property.address,
                purchase_cost="0.00",
            ).items():
                self.fields[k].disabled = True
                self.fields[k].initial = v

    def clean(self):
        d = forms.Form.clean(self)
        if not d.get("nlis") and not d.get("rfid"):
            self.add_error("nlis", "Supply at least one of NLIS Visual ID or NLIS RFID.")
        for k in ["nlis", "rfid"]:
            if d.get(k):
                try:
                    d[k] = services.validate_identifier(k, d[k])
                except ValidationError as e:
                    self.add_error(k, e)
        day = d.get("farm_entry_date")
        if day:
            if day > today(self.actor):
                self.add_error("farm_entry_date", "Future event dates are not accepted.")
            if day < today(self.actor) and not self.actor.administrator:
                self.add_error(
                    "farm_entry_date",
                    "Administrator access is required for historical entry dates.",
                )
            if d.get("dob") and d["dob"] > day:
                self.add_error("dob", "Birth date cannot be later than arrival.")
        return d

    def payload(self):
        d = services.clean(self.cleaned_data)
        d["entry_source"] = self.mode

        return d


def entry(request):
    actor = request.user
    salt = "entry-list-v2:" + str(actor.pk)

    def empty_state():
        return dict(
            rows=[],
            context=request.farm_context,
            key=uuid.uuid4().hex,
            destination=f"{actor.property.name} — PIC {actor.pic.number}",
        )

    state = empty_state()
    error = ""
    if request.POST.get("review_state"):
        try:
            state = signing.loads(request.POST["review_state"], salt=salt, max_age=86400)
        except signing.BadSignature:
            raise PermissionDenied("Review list expired or invalid. Restart Cattle Entry.")
    bound = state["context"] == request.farm_context
    mode = request.POST.get("mode", "purchase")
    if mode not in MODES:
        mode = "purchase"
    task = request.POST.get("task", "")
    editing = request.POST.get("editing", "")
    form = EntryForm(actor, mode, request.POST if task == "add" else None)
    try:
        if task == "restart":
            state = empty_state()
            bound = True
        if not bound:
            raise ValidationError(
                "Property/PIC changed. This list cannot be redirected. Review the rows shown here and explicitly restart the list before preparing entries for this selection."
            )
        if task.startswith("remove:"):
            state["rows"].pop(int(task.split(":")[1]))
        elif task.startswith("edit:"):
            editing = int(task.split(":")[1])
            row = state["rows"][editing]
            mode = row["entry_source"]
            form = EntryForm(actor, mode, initial=row)
        elif task == "add" and form.is_valid():
            row = form.payload()
            if row.get("mob"):
                row["mob_display"] = dict(form.fields["mob"].choices)[row["mob"]]
            candidate = list(state["rows"])
            if editing != "":
                candidate[int(editing)] = row
            else:
                candidate.append(row)
            services.preview(actor, "register", {"rows": candidate})
            state["rows"] = candidate
            editing = ""
            retained = {
                k: v
                for k, v in form.cleaned_data.items()
                if k
                in [
                    "farm_entry_date",
                    "source_pic",
                    "source_name",
                    "source_address",
                    "nvd",
                    "mob",
                ]
            }
            form = EntryForm(actor, mode, initial=retained)
        elif task == "save":
            if not state["rows"]:
                raise ValidationError("Add at least one animal to the review list.")
            # Revalidate editable field sets as well as all authoritative domain checks.
            # A confirmed retry may arrive on a later calendar day. The domain
            # service rechecks access and the exact digest before returning it.
            if not Submission.objects.filter(
                property=actor.property, actor=actor, key=state["key"]
            ).exists():
                for i, row in enumerate(state["rows"], 1):
                    check = EntryForm(actor, row["entry_source"], row)
                    if not check.is_valid():
                        raise ValidationError(f"Row {i}: {check.errors.as_text()}")
            result = services.execute(actor, state["key"], "register", {"rows": state["rows"]})
            messages.success(
                request,
                f"Saved {result['count']} animals to {actor.property.name} — PIC {actor.pic.number}.",
            )
            return render(
                request,
                "herd/saved.html",
                {"result": result, "submission_key": state["key"]},
            )
    except (ValidationError, ValueError, IndexError, KeyError, IntegrityError) as exc:
        error = (
            "; ".join(getattr(exc, "messages", [str(exc)]))
            if not isinstance(exc, IntegrityError)
            else "Identifier conflict: no animals were saved. Review all rows and retry."
        )
    reviews = []
    for original in state["rows"]:
        row = dict(original)
        if row.get("purchase_cost") in [None, ""]:
            row["purchase_cost"] = "Unknown — total will be incomplete"
        reviews.append(
            dict(
                mode=MODES[row["entry_source"]],
                fields=[
                    (
                        LABELS.get(
                            "mob" if k == "mob_display" else k,
                            k,
                        ),
                        (
                            datetime.fromisoformat(v).strftime(actor.date_format.split(" ")[0])
                            if k in ["farm_entry_date", "dob"] and v
                            else v
                        ),
                    )
                    for k, v in row.items()
                    if k not in ["entry_source", "mob"] and v not in ["", None]
                ],
            )
        )
    return render(
        request,
        "herd/entry.html",
        dict(
            form=form,
            mode=mode,
            modes=MODES.items(),
            reviews=reviews,
            review_state=signing.dumps(state, salt=salt, compress=True),
            editing=editing,
            error=error,
            context_matches=bound,
            destination=state["destination"],
        ),
    )
