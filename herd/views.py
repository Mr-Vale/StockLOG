import hashlib
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import clock, home, reports, services
from .context import properties_for, scope
from .forms import FIELDS, ActionForm
from .models import (
    Account,
    Animal,
    Event,
    ImportPreview,
    Inventory,
    LoginAttempt,
    Mob,
    ReportTemplate,
)


def error_text(error):
    return "; ".join(getattr(error, "messages", [str(error)]))


def login_view(request):
    error = ""
    if request.method == "POST":
        name = request.POST.get("username", "")
        identity = hashlib.sha256(
            (name.casefold() + "|" + request.META.get("REMOTE_ADDR", "")).encode()
        ).hexdigest()
        with transaction.atomic():
            attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(
                identity_hash=identity
            )
            if attempt.blocked_until > clock.now():
                error = "Too many attempts. Try again after 15 minutes."
            else:
                user = authenticate(
                    request, username=name, password=request.POST.get("password", "")
                )
                if user:
                    attempt.failures = 0
                    attempt.blocked_until = 0
                    attempt.save()
                    login(request, user)
                    return redirect("dashboard")
                attempt.failures += 1
                if attempt.failures >= 5:
                    attempt.blocked_until = clock.now() + 900
                attempt.save()
                error = "Sign-in failed."
    return render(request, "herd/login.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    response = redirect("login")
    response["Clear-Site-Data"] = '"cache", "storage"'
    return response


@login_required
def dashboard(request):
    props = list(properties_for(request.user).prefetch_related("pics"))
    context = {
        "properties": props,
        "property_data": [
            {
                "id": p.pk,
                "name": p.name,
                "pics": [{"id": pic.pk, "number": pic.number} for pic in p.pics.all()],
            }
            for p in props
        ],
    }
    if request.context_ready and request.user.pic_id:
        context["pic_summary"], context["charts"] = home.summary(request.user)
    return render(request, "herd/dashboard.html", context)


@login_required
def action(request, operation):
    if operation in {"sale", "transfer", "death", "edit_animal", "bulk_edit"}:
        from .cattle import workflow
        return workflow(request, operation)
    if operation == "register":
        from .entry import entry
        return entry(request)
    if operation not in FIELDS:
        raise Http404
    if operation in ["account", "purge", "identifier_review"]:
        services.administrator(request.user)
    initial = {k: request.GET[k] for k in request.GET if k in FIELDS[operation]}
    if operation == "move" and request.GET.get("administration"):
        services.administrator(request.user)
        initial["administration"] = True
    form = ActionForm(
        request.user,
        operation,
        (
            request.POST
            if request.method == "POST" and not request.POST.get("confirmed_payload")
            else None
        ),
        initial=initial,
    )
    context = {
        "form": form,
        "operation": operation,
        "picker_cattle": (
            scope(Animal, request.user).filter(status="active", purged=False)
            if operation == "move"
            else []
        ),
        "submission_key": request.POST.get("submission_key") or str(uuid.uuid4()),
    }
    if request.method == "POST":
        try:
            if request.POST.get("confirmed_payload"):
                payload = signing.loads(
                    request.POST["confirmed_payload"],
                    salt="operation:" + str(request.user.pk),
                    max_age=1800,
                )
                if (
                    payload["operation"] != operation
                    or payload.get("context") != request.farm_context
                ):
                    raise ValidationError("Invalid confirmation.")
                result = services.execute(
                    request.user,
                    payload["key"],
                    operation,
                    payload["data"],
                    payload["version"],
                )
                messages.success(request, "Saved and confirmed.")
                return render(
                    request,
                    "herd/saved.html",
                    {"result": result, "submission_key": payload["key"]},
                )
            if form.is_valid():
                data = services.clean(form.cleaned_data)
                if operation == "account":
                    # Passwords must not be embedded in a signed (readable) confirmation or local recovery storage.
                    services.execute(
                        request.user, context["submission_key"], operation, data
                    )
                    messages.success(
                        request, "Account saved. Password material was not logged."
                    )
                    return redirect("accounts")
                reviewed = services.preview(request.user, operation, data)
                context.update(
                    {
                        "effects": reviewed["effects"],
                        "readable_input": json.dumps(data),
                        "confirmation": signing.dumps(
                            {
                                "operation": operation,
                                "context": request.farm_context,
                                "key": context["submission_key"],
                                "data": data,
                                "version": reviewed["version"],
                            },
                            salt="operation:" + str(request.user.pk),
                            compress=True,
                        ),
                    }
                )
        except (
            ValidationError,
            ValueError,
            KeyError,
            signing.BadSignature,
            IntegrityError,
        ) as e:
            message = (
                "Records conflict or input is invalid; no partial submission was saved."
                if isinstance(e, IntegrityError)
                else error_text(e)
            )
            if form.is_bound:
                form.add_error(None, message)
            else:
                context["operation_error"] = message
                if "payload" in locals():
                    initial = dict(payload["data"])
                    if initial.get("effective_at"):
                        local = datetime.fromtimestamp(
                            int(initial["effective_at"]),
                            ZoneInfo(request.user.property.timezone),
                        )
                        initial["effective_at"] = local.replace(tzinfo=None).isoformat(
                            timespec="seconds"
                        )
                        offset = local.strftime("%z")
                        initial["time_offset"] = offset[:3] + ":" + offset[3:]
                    context["form"] = ActionForm(
                        request.user, operation, initial=initial
                    )
    return render(request, "herd/action.html", context)


@login_required
def animals(request):
    from .active import active_table
    return render(request, "herd/animals.html", active_table(request))


@login_required
def animal_detail(request, pk):
    a = get_object_or_404(scope(Animal, request.user), pk=pk, purged=False)
    report = reports.build(request.user, {"filters": {"animal": str(a.id)}})
    return render(
        request,
        "herd/animal.html",
        {
            "animal": a,
            "row": report["rows"][0],
            "events": Event.objects.filter(
                property=request.user.property, participants__animal=a
            ).distinct(),
        },
    )


@login_required
def inventory(request):
    return render(
        request,
        "herd/inventory.html",
        {
            "items": scope(Inventory, request.user)
            .filter(
                **(
                    {"kind": request.GET["kind"]}
                    if request.GET.get("kind") in ["feed", "chemical"]
                    else {}
                )
            )
            .order_by("retired", "kind", "name")
        },
    )


@login_required
def events(request):
    return render(
        request,
        "herd/events.html",
        {
            "events": scope(Event, request.user)
            .select_related("actor")
            .order_by("-submitted_at", "-effective_order")[:300]
        },
    )


@login_required
def report_view(request):
    if request.method == "POST":
        try:
            definition = signing.loads(
                request.POST["report_definition"],
                salt="report:" + str(request.user.pk),
                max_age=3600,
            )
            target = request.POST.get("template_target")
            operation = request.POST.get("template_operation")
            if operation == "delete" and not target:
                raise ValidationError("Select a shared template to delete.")
            if (
                operation != "delete"
                and not request.POST.get("template_name", "").strip()
            ):
                raise ValidationError("Give the shared template a name.")
            services.execute(
                request.user,
                request.POST["submission_key"],
                "template",
                {
                    "template": target or None,
                    "name": request.POST.get("template_name", ""),
                    "definition": definition,
                    "delete": operation == "delete",
                },
            )
            messages.success(
                request, "Shared report template saved/deleted with an audit record."
            )
            return redirect("reports")
        except (ValidationError, signing.BadSignature, KeyError) as e:
            messages.error(request, error_text(e))
            return redirect("reports")
    error = ""
    report = None
    definition = {
        "dataset": request.GET.get("dataset", "animals"),
        "filters": {k: request.GET[k] for k in reports.FILTERS if request.GET.get(k)},
        "attribute_time": request.GET.get("attribute_time", "current"),
        "filter_mode": request.GET.get("filter_mode", "all"),
        "sort": request.GET.get("sort", "animal"),
        "group": request.GET.get("group", ""),
    }
    if request.GET.get("columns"):
        definition["columns"] = [c for c in request.GET.getlist("columns") if c]
    if request.GET.get("template"):
        definition = get_object_or_404(
            ReportTemplate, pk=request.GET["template"], property=request.user.property
        ).definition
    try:
        for key in [
            "as_of",
            "present_from",
            "present_to",
            "activity_from",
            "activity_to",
        ]:
            value = definition.get("filters", {}).get(key)
            if value and not str(value).isdigit():
                definition["filters"][key] = clock.local_timestamp(
                    value, request.user.property.timezone
                )
        report = reports.build(request.user, definition)
        fmt = request.GET.get("format")
        if fmt in ["pdf", "xlsx"]:
            data = reports.pdf(report) if fmt == "pdf" else reports.xlsx(report)
            response = HttpResponse(
                data,
                content_type=(
                    "application/pdf"
                    if fmt == "pdf"
                    else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            )
            response["Content-Disposition"] = (
                f'attachment; filename="StockLOG-{definition.get("dataset", "animals")}.{fmt}"'
            )
            services.audit(
                request.user,
                "report_export",
                definition=definition,
                rows=len(report["rows"]),
            )
            return response
    except (ValidationError, ValueError) as e:
        error = error_text(e)
    return render(
        request,
        "herd/reports.html",
        {
            "report": report,
            "error": error,
            "datasets": reports.DATASETS,
            "columns": reports.FIELDS,
            "mobs": scope(Mob, request.user),
            "templates": ReportTemplate.objects.filter(property=request.user.property),
            "report_definition": signing.dumps(
                definition, salt="report:" + str(request.user.pk)
            ),
            "template_submission_key": str(uuid.uuid4()),
            "export_query": request.GET.urlencode(),
        },
    )


@login_required
def import_view(request):
    from .imports import COLUMNS, mapped_preview, read_upload

    context = {
        "columns": COLUMNS,
        "mobs": scope(Mob, request.user),
    }
    try:
        if request.method == "POST" and request.FILES.get("file"):
            headers, rows = read_upload(request.FILES["file"])
            batch = ImportPreview.objects.create(
                property=request.user.property,
                pic=request.user.pic,
                actor=request.user,
                rows={"headers": headers, "source": rows},
            )
            context.update(
                {"mapping_batch": batch, "headers": list(enumerate(headers))}
            )
        elif request.method == "POST" and request.POST.get("mapping_batch"):
            batch = get_object_or_404(
                scope(ImportPreview, request.user),
                pk=request.POST["mapping_batch"],
                property=request.user.property,
                actor=request.user,
                confirmed=False,
            )
            mapping = {c: request.POST.get("map_" + c, "") for c in COLUMNS}
            shared = {c: request.POST.get("shared_" + c, "") for c in COLUMNS}
            result, errors = mapped_preview(
                request.user,
                batch.rows["headers"],
                batch.rows["source"],
                mapping,
                shared,
            )
            batch.rows = result
            batch.errors = errors
            batch.save()
            context["preview_batch"] = batch
        elif request.method == "POST" and request.POST.get("confirm_batch"):
            batch = get_object_or_404(
                scope(ImportPreview, request.user),
                pk=request.POST["confirm_batch"],
                property=request.user.property,
                actor=request.user,
            )
            selected = [int(i) for i in request.POST.getlist("selected")]
            if not selected:
                raise ValidationError("Select at least one valid row.")
            if not isinstance(batch.rows, list):
                raise ValidationError("Preview the mapped import before confirmation.")
            rows = []
            for i in selected:
                if i < 0 or i >= len(batch.rows) or batch.rows[i]["errors"]:
                    raise ValidationError(
                        "Only explicitly selected valid rows may be confirmed."
                    )
                rows.append(batch.rows[i]["data"])
            with transaction.atomic():
                result = services.execute(
                    request.user,
                    "import-" + str(batch.id),
                    "register",
                    {
                        "rows": rows,
                        "effective_at": min(int(r["effective_at"]) for r in rows),
                    },
                )
                batch.confirmed = True
                batch.save(update_fields=["confirmed"])
            messages.success(
                request,
                f"Confirmed {len(rows)} animals atomically. Excluded rows were not submitted.",
            )
            return render(
                request,
                "herd/saved.html",
                {"result": result, "submission_key": "import-" + str(batch.id)},
            )
    except (ValidationError, ValueError, KeyError, IntegrityError) as e:
        context["error"] = error_text(e)
    return render(request, "herd/import.html", context)


@login_required
def accounts(request):
    services.administrator(request.user)
    return render(
        request,
        "herd/accounts.html",
        {"accounts": Account.objects.all(), "properties": properties_for(request.user).prefetch_related("pics")},
    )


@login_required
def settings_view(request):
    class SettingsForm(forms.Form):
        display_timezone = forms.CharField(max_length=64)
        date_format = forms.ChoiceField(
            choices=[
                ("%d/%m/%Y %H:%M", "Day/month/year, 24-hour"),
                ("%Y-%m-%d %H:%M", "Year-month-day, 24-hour"),
            ]
        )

    form = SettingsForm(
        request.POST or None,
        initial={
            "display_timezone": request.user.display_timezone,
            "date_format": request.user.date_format,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            ZoneInfo(form.cleaned_data["display_timezone"])
            for k, v in form.cleaned_data.items():
                setattr(request.user, k, v)
            request.user.save(update_fields=["display_timezone", "date_format"])
            services.audit(request.user, "settings_change", settings=form.cleaned_data)
            messages.success(request, "Display settings saved.")
        except (KeyError, ValueError):
            form.add_error("display_timezone", "Choose a valid IANA timezone.")
    from stocklog.version import identity

    return render(request, "herd/settings.html", {"form": form, "release": identity()})


@login_required
def backup_latest(request):
    services.administrator(request.user)
    from .backups import latest

    return JsonResponse(latest())


@login_required
def backup_download(request, identity):
    services.administrator(request.user)
    from .backups import archive_path

    path = archive_path(identity)
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)


def health(request):
    from django.db import connection

    with connection.cursor() as c:
        c.execute("SELECT 1")
        c.fetchone()
    from stocklog.version import identity

    return JsonResponse({"status": "ok", **identity()})


def recovery_worker(request):
    from pathlib import Path

    response = HttpResponse(
        (Path(__file__).parent / "static/herd/recovery-worker.js").read_text(),
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response
