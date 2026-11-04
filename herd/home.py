"""Property administration, selection and aggregate homepage data."""

import calendar
import time
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import clock, services
from .context import properties_for, scope
from .identifiers import configure
from .models import PIC, Account, Animal, Audit, Mob, Property


def pic_number(value):
    return services.validate_identifier("pic", value)


class PropertyForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure(self.fields["number"], "pic")

    name = forms.CharField(max_length=160, label="Property name")
    address = forms.CharField(widget=forms.Textarea, label="Property address")
    owner = forms.CharField(max_length=160)
    manager = forms.CharField(
        max_length=160, required=False, help_text="Leave empty if managed by the owner."
    )
    number = forms.CharField(max_length=8, label="Initial PIC")

    def clean_number(self):
        return pic_number(self.cleaned_data["number"])


class PICForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure(self.fields["number"], "pic")

    property = forms.ModelChoiceField(queryset=Property.objects.all())
    number = forms.CharField(max_length=8, label="PIC number")

    def clean_number(self):
        return pic_number(self.cleaned_data["number"])


@login_required
def add_property(request):
    services.administrator(request.user)
    form = PropertyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                d = dict(form.cleaned_data)
                number = d.pop("number")
                prop = Property.objects.create(**d)
                PIC.objects.create(property=prop, number=number)
                Audit.objects.create(
                    property=prop,
                    actor=request.user,
                    action="property_create",
                    details={**d, "pic": number},
                )
            messages.success(
                request,
                "Property and initial PIC created. Select them on the homepage.",
            )
            return redirect("dashboard")
        except IntegrityError:
            form.add_error("number", "That PIC is already registered.")
    return render(
        request, "herd/simple_form.html", {"form": form, "title": "Add property"}
    )


@login_required
def add_pic(request):
    services.administrator(request.user)
    form = PICForm(
        request.POST or None, initial={"property": request.GET.get("property")}
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                prop = Property.objects.select_for_update().get(
                    pk=form.cleaned_data["property"].pk
                )
                pic = PIC.objects.create(
                    property=prop, number=form.cleaned_data["number"]
                )
                Audit.objects.create(
                    property=prop,
                    actor=request.user,
                    action="pic_create",
                    details={"pic": pic.number},
                )
            return redirect("dashboard")
        except IntegrityError:
            form.add_error("number", "That PIC is already registered.")
    return render(request, "herd/simple_form.html", {"form": form, "title": "Add PIC"})


@login_required
@require_POST
def select_context(request):
    try:
        property_id, pic_id = int(request.POST.get("property", "")), int(
            request.POST.get("pic", "")
        )
    except ValueError:
        return JsonResponse({"error": "Select both a property and PIC."}, status=400)
    prop = properties_for(request.user).filter(pk=property_id).first()
    pic = PIC.objects.filter(property=prop, pk=pic_id).first() if prop else None
    if not pic:
        return JsonResponse(
            {"error": "Select an authorised property and a PIC belonging to it."},
            status=400,
        )
    pair = [prop.pk, pic.pk]
    changed = pair != request.session.get("farm_selection")
    request.session["farm_selection"] = pair
    if changed:
        request.session["farm_generation"] = uuid.uuid4().hex
        request.session["farm_ready_at"] = time.time() + 5
    # Persist only an explicit Save; changing selection remains session-local.
    if request.POST.get("save") == "1":
        Account.objects.filter(pk=request.user.pk).update(property=prop, pic=pic)
        request.session["selection_compact"] = True
    return JsonResponse(
        {
            "wait_ms": max(
                0, int((request.session.get("farm_ready_at", 0) - time.time()) * 1000)
            ),
            "property": prop.name,
            "pic": pic.number,
        }
    )


@login_required
def context_ready(request):
    return JsonResponse({"ready": request.context_ready and bool(request.user.pic_id)})


@login_required
def access(request):
    services.administrator(request.user)

    class AccessForm(forms.Form):
        account = forms.ModelChoiceField(queryset=Account.objects.all())
        properties = forms.ModelMultipleChoiceField(
            queryset=Property.objects.all(), required=False
        )

    form = AccessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = Account.objects.select_for_update().get(
                pk=form.cleaned_data["account"].pk
            )
            before = list(user.properties.values_list("pk", flat=True))
            user.properties.set(form.cleaned_data["properties"])
            after = list(user.properties.values_list("pk", flat=True))
            for prop in Property.objects.filter(pk__in=set(before + after)):
                Audit.objects.create(
                    property=prop,
                    actor=request.user,
                    action="property_access",
                    details={"account": user.pk, "before": before, "after": after},
                )
        messages.success(
            request,
            "Property access updated. Administrators can access all properties.",
        )
        return redirect("access")
    return render(
        request,
        "herd/access.html",
        {"form": form, "accounts": Account.objects.prefetch_related("properties")},
    )


def months_after(d, months):
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def summary(user):
    cattle = Animal.objects.filter(
        property=user.property, status="active", purged=False
    )
    pics = [
        {
            "number": p.number,
            "cattle": cattle.filter(pic=p).count(),
            "mobs": Mob.objects.filter(pic=p, retired=False).count(),
        }
        for p in user.property.pics.all()
    ]
    sex, breeds, ages = Counter(), Counter(), Counter()
    today = datetime.fromtimestamp(clock.now(), ZoneInfo(user.property.timezone)).date()
    for a in cattle:
        sex[{"M": "Male", "STEER": "Male", "F": "Female"}.get(a.sex, "Unknown")] += 1
        breeds[a.breed or "Unknown"] += 1
        born = a.dob
        if not born and a.estimated_weeks is not None and a.age_reference is not None:
            born = datetime.fromtimestamp(
                a.age_reference, ZoneInfo(user.property.timezone)
            ).date() - timedelta(weeks=a.estimated_weeks)
        group = (
            "Unknown age"
            if not born
            else (
                "Under 3 months"
                if today < months_after(born, 3)
                else (
                    "3–12 months"
                    if today < months_after(born, 12)
                    else (
                        "12–24 months"
                        if today < months_after(born, 24)
                        else "24 months and over"
                    )
                )
            )
        )
        ages[group] += 1
    return pics, [
        {
            "key": key,
            "title": title,
            "rows": [{"label": k, "count": v} for k, v in values.items()],
            "display": user.chart_preferences.get(key, "pie"),
        }
        for key, title, values in [
            ("sex", "Sex", sex),
            ("breed", "Breed", breeds),
            ("age", "Age groups", ages),
        ]
    ]


@login_required
@require_POST
def charts(request):
    prefs = dict(request.user.chart_preferences)
    for key in ("sex", "breed", "age"):
        value = request.POST.get(key)
        if value not in ("pie", "bar"):
            return JsonResponse({"error": "Choose pie or bar."}, status=400)
        prefs[key] = value
    Account.objects.filter(pk=request.user.pk).update(chart_preferences=prefs)
    return redirect("dashboard")


@login_required
def mobs(request):
    return render(
        request,
        "herd/mobs.html",
        {
            "mobs": scope(Mob, request.user),
            "cattle": scope(Animal, request.user).filter(status="active", purged=False),
        },
    )


@login_required
def workflow(request, group):
    groups = {
        "entry": ("Cattle Entry", [("register", "Purchase, birth or repurchase")]),
        "exit": ("Cattle Exit", [("sale", "Sale"), ("death", "Death")]),
        "treatment": (
            "Cattle Treatment",
            [
                ("treat", "Chemical treatment"),
                ("procedure", "Procedure / castration"),
                ("vet", "Vet fees"),
            ],
        ),
        "feeding": ("Cattle Feeding", [("feed", "Record feeding")]),
    }
    if group not in groups:
        from django.http import Http404

        raise Http404
    if group == "exit":
        from .cattle import workflow
        return workflow(request, "sale")
    if group == "entry":
        from .entry import entry
        return entry(request)
    title, actions = groups[group]
    return render(request, "herd/workflow.html", {"title": title, "actions": actions})


@login_required
def retire_mob(request, pk):
    mob = get_object_or_404(scope(Mob, request.user), pk=pk)
    error = ""
    if request.method == "POST":
        try:
            services.execute(
                request.user,
                request.POST.get("submission_key"),
                "mob",
                {"retire_mob": mob.pk},
            )
            return redirect("mobs")
        except ValidationError as exc:
            error = "; ".join(exc.messages)
    return render(
        request,
        "herd/retire_mob.html",
        {"mob": mob, "error": error, "submission_key": uuid.uuid4().hex},
    )
