"""Date-only cattle forms with signed, context-bound confirmation."""

import uuid

from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render

from . import services
from .cattle_services import (
    BULK_FIELDS,
    acquisition,
    calendar_date,
    current_visit,
    exit_timestamp,
    purchase_presence,
)
from .context import scope
from .entry import LABELS, EntryForm, today
from .forms import ActionForm
from .identifiers import configure, validate_identifier
from .models import Animal

EXIT_MODES = {"sale": "Sale", "transfer": "Transfer", "death": "Death"}
EDIT_ORDER = [
    "entry_date",
    "nlis",
    "rfid",
    "source_pic",
    "vendor_name",
    "vendor_address",
    "nvd",
    "breed",
    "sex",
    "mob",
    "purchase_cost",
    "estimated_weeks",
    "dob",
    "mother_nlis",
]
INSTRUCTIONS = "Review and update the animal’s details below. Enter the farm entry date without a time. Select an existing breed/description or type a new one. If the date of birth is unknown, enter the animal’s estimated age in weeks when it entered the farm. A recorded date of birth takes priority when calculating age. Some identification and source fields require an administrator to change. Confirm the details, then save."


def animal_choices(actor):
    return [
        (
            a.label,
            a.label
            + " — "
            + " / ".join(a.identifiers.filter(current=True).values_list("value", flat=True)),
        )
        for a in scope(Animal, actor).filter(status="active", purged=False).order_by("id")
    ]


def selection_field(actor):
    return forms.MultipleChoiceField(
        choices=animal_choices(actor),
        label="Animal Selection",
        required=False,
        widget=forms.SelectMultiple(attrs={"data-animal-selection": "", "size": 7}),
    )


class EditForm(EntryForm):
    def __init__(self, actor, operation, animal=None, data=None, **kwargs):
        super().__init__(actor, "purchase", data, **kwargs)
        self.operation, self.animal = operation, animal
        # Birth exposes DOB and mother controls; source fields remain editable here.
        source = ActionForm(actor, "register")
        self.fields.update({k: source.fields[k] for k in ["dob", "mother_nlis"]})
        self.fields["dob"] = forms.DateField(
            required=False,
            label=LABELS["dob"],
            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        )
        self.fields["entry_date"] = self.fields.pop("effective_at")
        self.fields["entry_date"].label = "Farm Entry Date"
        self.fields[
            "entry_date"
        ].help_text = "Property calendar date for the current on-farm period."
        self.fields["purchase_cost"].label = "Purchase Cost"
        self.fields["estimated_weeks"].label = "Estimated Age - weeks"
        self.fields["sex"].label = "SEX"
        self.fields["mother_nlis"].label = LABELS["mother_nlis"]
        self.fields[
            "mother_nlis"
        ].help_text = "NLIS Visual ID (0XXXX000XXX00000) or RFID (15 digits)."
        self.fields["mother_nlis"].widget.attrs["pattern"] = (
            r"\s*(?:[0-9][A-Za-z]{4}[0-9]{3}[A-Za-z]{3}[0-9]{5}|[0-9]{15})\s*"
        )
        self.fields = {k: self.fields[k] for k in EDIT_ORDER}
        self.fields["breed"].widget.attrs["list"] = "breed-options"
        for key in ["source_pic", "nvd"]:
            self.fields[key].required = False
        if animal:
            visit = current_visit(animal, actor)
            details = acquisition(animal, visit)
            tags = dict(animal.identifiers.filter(current=True).values_list("kind", "value"))
            self.initial.update(
                {
                    k: getattr(animal, k)
                    for k in ["breed", "sex", "estimated_weeks", "dob", "mother_nlis"]
                }
            )
            self.initial.update(
                {
                    k: details.get(k, "")
                    for k in ["source_pic", "vendor_name", "vendor_address", "nvd"]
                }
            )
            self.initial.update(tags)
            self.initial["entry_date"] = calendar_date(actor, visit.start)
            cost_visit = purchase_presence(animal, visit)
            self.initial["purchase_cost"] = (
                None
                if animal.allocations.filter(
                    presence=cost_visit, category="purchase", unknown=True, resolved_by__isnull=True
                ).exists()
                else -sum(
                    animal.allocations.filter(presence=cost_visit, category="purchase").values_list(
                        "amount", flat=True
                    )
                )
            )
            self.initial["mob"] = (
                animal.memberships.filter(end__isnull=True, superseded=False)
                .values_list("mob_id", flat=True)
                .first()
            )
            if not actor.administrator:
                for key in ["source_pic", "nvd"] + [k for k in ["nlis", "rfid"] if tags.get(k)]:
                    self.fields[key].disabled = True
        for key in ["nlis", "rfid", "source_pic", "nvd", "mother_nlis"]:
            if self.initial.get(key):
                try:
                    validate_identifier(
                        {"source_pic": "pic", "mother_nlis": "mother"}.get(key, key),
                        self.initial[key],
                    )
                except ValidationError:
                    self.fields[key].widget.attrs.pop("pattern", None)
        if operation == "bulk_edit":
            self.fields = {k: f for k, f in self.fields.items() if k in BULK_FIELDS}
            fields = {}
            fields["animals"] = selection_field(actor)
            for k, field in self.fields.items():
                fields["update_" + k] = forms.BooleanField(
                    required=False, label="Update " + field.label
                )
                field.required = False
                field.help_text += (
                    " Select Update to apply this value; an empty optional value clears it."
                )
                if data is not None and not data.get("update_" + k):
                    field.disabled = True
                fields[k] = field
            self.fields = fields

    def clean(self):
        d = forms.Form.clean(self)
        keys = [k for k in EDIT_ORDER if k in self.fields]
        if self.operation == "bulk_edit":
            keys = [k for k in keys if d.get("update_" + k)]
            if not keys:
                self.add_error(None, "Select at least one field to update.")
            if not d.get("animals"):
                self.add_error("animals", "Select at least one animal.")
        for key, kind in [
            ("nlis", "nlis"),
            ("rfid", "rfid"),
            ("source_pic", "pic"),
            ("nvd", "nvd"),
            ("mother_nlis", "mother"),
        ]:
            if (
                key in keys
                and d.get(key)
                and str(d[key]).strip().upper() != str(self.initial.get(key) or "").strip().upper()
            ):
                try:
                    d[key] = validate_identifier(kind, d[key])
                except ValidationError as exc:
                    self.add_error(key, exc)
        if "entry_date" in keys and not d.get("entry_date"):
            self.add_error("entry_date", "Farm Entry Date is required when updating it.")
        return {
            **{k: d.get(k) for k in keys},
            "update_fields": keys,
            **(
                {"animals": d.get("animals")}
                if self.operation == "bulk_edit"
                else {"animal": self.animal.label}
            ),
        }


class ExitForm(ActionForm):
    def __init__(self, actor, mode, data=None, **kwargs):
        super().__init__(actor, "sale", data, **kwargs)
        self.mode = mode
        self.fields["exit_date"] = forms.DateField(
            label="Farm Exit Date",
            initial=today(actor),
            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            help_text="Property calendar date. Backdating is allowed; future dates are not.",
        )
        self.fields["destination_address"] = forms.CharField(
            required=False, label="Destination Address"
        )
        self.fields["animals"] = selection_field(actor)
        self.fields["reason"] = forms.CharField(
            label="Reason", widget=forms.Textarea(attrs={"rows": 3})
        )
        for key, label in {
            "destination_pic": "Destination PIC",
            "destination_name": "Destination Name",
            "nvd": "NVD Number",
            "mob": "MOB Number",
            "price": "Sale Price",
            "price_mode": "Price Mode",
        }.items():
            self.fields[key].label = label
        self.fields["price_mode"].choices = [("per_head", "Per Head"), ("group", "Group Total")]
        self.fields["destination_pic"].required = True
        self.fields["nvd"].required = True
        configure(self.fields["destination_pic"], "pic")
        configure(self.fields["nvd"], "nvd")
        keys = [
            "exit_date",
            "destination_pic",
            "destination_name",
            "destination_address",
            "nvd",
            "mob",
            "animals",
        ]
        if mode == "sale":
            keys += ["price", "price_mode"]
            self.fields["price"].required = True
        if mode == "death":
            keys = ["exit_date", "animals", "reason"]
        self.fields = {k: self.fields[k] for k in keys}

    def clean(self):
        d = forms.Form.clean(self)
        if not d.get("mob") and not d.get("animals"):
            self.add_error("animals", "Choose animals or a whole mob.")
        for key, kind in [("destination_pic", "pic"), ("nvd", "nvd")]:
            if d.get(key):
                try:
                    d[key] = validate_identifier(kind, d[key])
                except ValidationError as exc:
                    self.add_error(key, exc)
        if d.get("exit_date"):
            try:
                d["effective_at"] = exit_timestamp(self.actor, d["exit_date"])
            except (ValidationError, ValueError) as exc:
                self.add_error("exit_date", exc)
        return d


def restriction_warnings(actor, data):
    animals = services.targets(actor, data, int(data["effective_at"]))
    warnings = []
    for a in animals:
        restriction = (
            a.restrictions.filter(
                event__reversed_by__isnull=True,
                superseded_by__isnull=True,
                starts_at__lte=data["effective_at"],
                ends_at__gt=data["effective_at"],
            )
            .order_by("-ends_at")
            .first()
        )
        if restriction:
            warnings.append(
                {
                    "animal": a.label,
                    "safe_date": calendar_date(actor, restriction.ends_at).isoformat(),
                }
            )
    return warnings


def workflow(request, operation, animal=None):
    actor = request.user
    is_exit = operation in EXIT_MODES
    if operation == "bulk_edit":
        services.administrator(actor)
    reference = (
        animal.label
        if animal
        else request.POST.get("animal_reference") or request.GET.get("animal")
    )
    if operation == "edit_animal" and animal is None:
        if not reference:
            return redirect("animals")
        try:
            animal = services.find_animal(actor, reference)
        except ValidationError:
            from django.http import Http404

            raise Http404("Animal is unavailable on this PIC.")
        if request.method == "GET":
            return redirect("animal", pk=animal.pk)
    initial = {}
    if is_exit:
        operation = request.POST.get("switch_mode") or request.POST.get("mode", operation)
        if operation not in EXIT_MODES:
            from django.http import Http404

            raise Http404("Choose Sale, Transfer or Death.")

    def make_form(data=None, initial=None):
        if is_exit:
            return ExitForm(actor, operation, data, initial=initial or {})
        return EditForm(actor, operation, animal, data, initial=initial or {})

    try:
        form = make_form(
            request.POST
            if request.method == "POST" and not request.POST.get("confirmed_payload")
            else None
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("animals")
    ctx = dict(
        form=form,
        operation=operation,
        title="Cattle Exit"
        if is_exit
        else "Bulk Edit"
        if operation == "bulk_edit"
        else "Edit Animal",
        modes=EXIT_MODES.items() if is_exit else [],
        animal_reference=reference or "",
        instructions=INSTRUCTIONS if animal else "",
        breeds=Animal.objects.filter(property=actor.property).exclude(breed="").values_list("breed", flat=True).distinct(),
        source=f"{actor.property.name} — PIC {actor.pic.number}",
    )
    salt = "cattle:" + str(actor.pk)
    try:
        if request.method == "POST" and request.POST.get("confirmed_payload"):
            state = signing.loads(request.POST["confirmed_payload"], salt=salt, max_age=1800)
            if state["context"] != request.farm_context or state["operation"] != operation:
                raise PermissionDenied("Property/PIC or operation changed. Refresh preview.")
            initial = state["data"]
            if animal and initial.get("animal") != animal.label:
                raise ValidationError("Animal changed. Refresh preview.")
            # The transaction version binds the exact selection and restrictions.
            if state.get("warnings") and not request.POST.get("accept_restriction"):
                raise ValidationError(
                    "Explicit acceptance of the displayed withholding warning is required."
                )
            result = services.execute(
                actor, state["key"], operation, state["data"], state["version"]
            )
            messages.success(request, f"Saved {result.get('count', 1)} animal(s).")
            if animal:
                return redirect("animal", pk=animal.pk)
            return redirect("animals")
        if request.method == "POST" and request.POST.get("task") == "preview" and form.is_valid():
            data = services.clean(form.cleaned_data)
            warnings = restriction_warnings(actor, data) if operation in {"sale", "death"} else []
            # Preview may simulate the existing explicit restriction acceptance; final confirmation
            # requires the user to actively accept the warnings shown, with the same version.
            if warnings:
                data["accept_restriction"] = True
            reviewed = services.preview(actor, operation, data)
            if is_exit:
                data["preview_animals"] = reviewed["effects"]["animals"]
            state = dict(
                context=request.farm_context,
                operation=operation,
                key=uuid.uuid4().hex,
                data=data,
                version=reviewed["version"],
                warnings=warnings,
            )
            ctx.update(
                confirmation=signing.dumps(state, salt=salt, compress=True),
                effects=reviewed["effects"],
                warnings=warnings,
                details=[
                    (
                        field.label,
                        (
                            ("Not supplied" if is_exit else "Clear / Unknown")
                            if data[k] in [None, ""]
                            else dict(field.choices).get(str(data[k]), data[k])
                            if isinstance(field, forms.ChoiceField)
                            else data[k]
                        ),
                    )
                    for k, field in form.fields.items()
                    if k in data and k != "animals"
                ],
            )
    except (ValidationError, signing.BadSignature, IntegrityError, ValueError, KeyError) as exc:
        ctx["error"] = "; ".join(getattr(exc, "messages", [str(exc)]))
        if initial:
            if operation == "bulk_edit":
                initial = {
                    **initial,
                    **{"update_" + k: True for k in initial.get("update_fields", [])},
                }
            ctx["form"] = make_form(data=initial)
    if animal:
        from .animal_details import summary

        ctx.update(summary(actor, animal))
        return render(request, "herd/animal.html", ctx)
    return render(request, "herd/cattle.html", ctx)
