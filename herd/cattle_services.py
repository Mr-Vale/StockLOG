"""Cattle corrections and same-property exits, within services.execute's property lock."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError

from . import clock
from . import services as s
from .context import properties_for
from .identifiers import validate_identifier
from .models import PIC, Animal, AttributeChange, Event, Membership, Presence

EDIT_FIELDS = {
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
}
BULK_FIELDS = {"entry_date", "breed", "sex", "purchase_cost", "vendor_name", "vendor_address"}


def calendar_date(actor, timestamp):
    return datetime.fromtimestamp(timestamp, ZoneInfo(actor.property.timezone)).date()


def date_timestamp(actor, value):
    day = date.fromisoformat(str(value))
    if day > calendar_date(actor, clock.now()):
        raise ValidationError("Future dates are not accepted.")
    return clock.local_timestamp(day.isoformat() + "T00:00:00", actor.property.timezone)


def exit_timestamp(actor, value, prepared=None):
    """Exit includes the chosen day's activity; today's bound is preparation time."""
    start = date_timestamp(actor, value)
    day = date.fromisoformat(str(value))
    next_start = clock.local_timestamp(
        (day + timedelta(days=1)).isoformat() + "T00:00:00", actor.property.timezone
    )
    if prepared is not None:
        at = int(prepared)
        if not start <= at < next_start or at > clock.now():
            raise ValidationError("Prepared exit time does not match Farm Exit Date.")
        return at
    return min(next_start - 1, clock.now())


def current_visit(a, actor):
    visits = list(a.presence.filter(end__isnull=True).select_related("arrival"))
    if a.status != "active" or a.purged or len(visits) != 1 or visits[0].pic_id != actor.pic_id:
        raise ValidationError("Select active animals currently present on the selected PIC.")
    return visits[0]


def purchase_presence(a, visit):
    """A transfer opens PIC occupancy, never a new acquisition/financial period."""
    seen = set()
    while visit.arrival.kind == "transfer_arrival":
        if visit.pk in seen:
            raise ValidationError("Transfer acquisition history is inconsistent.")
        seen.add(visit.pk)
        source = Event.objects.get(pk=visit.arrival.details["source_event"], property=a.property)
        link = next(r for r in source.details["transfer_links"] if r["animal"] == str(a.pk))
        visit = a.presence.select_related("arrival").get(pk=link["source_presence"])
    return visit


def acquisition(a, visit):
    rows = (
        visit.arrival.details.get("entry_rows")
        or visit.arrival.details.get("rows")
        or [visit.arrival.details]
    )
    tags = set(a.identifiers.values_list("value", flat=True))
    row = next(
        (r for r in rows if r.get("nlis", "").strip().upper() in tags or r.get("rfid") in tags), {}
    )
    origin = purchase_presence(a, visit)
    details = acquisition(a, origin) if origin.pk != visit.pk else dict(row)
    # Corrections are append-only; acquisition records themselves remain immutable.
    for e in Event.objects.filter(
        participants__animal=a, reversed_by__isnull=True, kind__in=["edit_animal", "bulk_edit"]
    ).order_by("effective_order"):
        correction = e.details.get("acquisition_changes", {}).get(str(a.pk), {})
        if correction.get("presence") == visit.pk:
            details.update(correction.get("values", {}))
    return details


def edit(actor, event, data):
    a = s.find_animal(actor, data["animal"])
    visit = current_visit(a, actor)
    fields = set(data.get("update_fields", [k for k in EDIT_FIELDS if k in data]))
    if not fields <= EDIT_FIELDS:
        raise ValidationError("Unsupported animal field.")
    details = acquisition(a, visit)
    before = {
        "animal": str(a.pk),
        "presence": visit.pk,
        "values": {},
        "acquisition": details,
        "memberships": list(
            a.memberships.filter(superseded=False, end__isnull=True).values_list("pk", flat=True)
        ),
        "identifiers": list(a.identifiers.filter(current=True).values("kind", "value")),
    }
    for key in fields & {"source_pic", "nvd"}:
        if str(data.get(key) or "").strip().upper() != str(details.get(key, "")).strip().upper():
            s.administrator(actor)
    for key in fields & {"nlis", "rfid"}:
        saved = a.identifiers.filter(kind=key, current=True).first()
        value = str(data.get(key) or "").strip().upper()
        if value == (saved.value.strip().upper() if saved else ""):
            continue
        if saved:
            s.administrator(actor)
        if value:
            s.attach(event, a, key, value, "Animal details correction")
        elif saved:
            saved.current, saved.retired_at = False, event.effective_at
            saved.save(update_fields=["current", "retired_at"])
    if not a.identifiers.filter(current=True).exists():
        raise ValidationError("Keep at least one current identifier.")
    changed_details = {}
    for key in fields & {"source_pic", "nvd", "vendor_name", "vendor_address"}:
        value = str(data.get(key) or "").strip()
        if key in {"source_pic", "nvd"}:
            if value.upper() == str(details.get(key, "")).strip().upper():
                value = details.get(key, "")
            elif value:
                value = validate_identifier("pic" if key == "source_pic" else "nvd", value)
        changed_details[key] = value
    start = visit.start
    if (
        "entry_date" in fields
        and str(data["entry_date"]) != calendar_date(actor, visit.start).isoformat()
    ):
        start = date_timestamp(actor, data["entry_date"])
    if "entry_date" in fields and start != visit.start:
        previous = a.presence.exclude(pk=visit.pk).order_by("-start").first()
        if previous and (previous.end is None or previous.end > start):
            raise ValidationError("Farm entry overlaps a previous on-farm period.")
        if (
            a.participant_set.exclude(event=event)
            .filter(
                event__reversed_by__isnull=True,
                event__effective_at__gte=visit.start,
                event__effective_at__lt=start,
            )
            .exclude(event=visit.arrival)
            .exists()
        ):
            raise ValidationError("Farm entry cannot move past recorded animal activity.")
        if a.memberships.filter(
            superseded=False, end__isnull=False, start__gte=visit.start, start__lt=start
        ).exists():
            raise ValidationError("Farm entry conflicts with historical mob membership.")
        before["start"] = visit.start
        # Move only membership that started with this arrival; never rewrite history events.
        for m in a.memberships.filter(superseded=False, start=visit.start, end__isnull=True):
            m.start = start
            m.save(update_fields=["start"])
        visit.start = start
        visit.save(update_fields=["start"])
    for key in fields & {"breed", "sex", "estimated_weeks", "dob", "mother_nlis"}:
        value = data.get(key)
        if key in {"dob", "estimated_weeks"}:
            value = (
                None
                if value in [None, ""]
                else (date.fromisoformat(str(value)) if key == "dob" else int(value))
            )
        else:
            value = str(value or "").strip()
        if key == "estimated_weeks" and value is not None and value < 0:
            raise ValidationError("Estimated age must be nonnegative weeks.")
        if key == "sex" and value not in ["", "M", "F", "STEER"]:
            raise ValidationError("Select a supported sex.")
        if key == "breed" and len(value) > 80:
            raise ValidationError("Breed/Description must be at most 80 characters.")
        if key == "mother_nlis" and value and value != a.mother_nlis:
            value = validate_identifier("mother", value)
            if a.identifiers.filter(value=value).exists():
                raise ValidationError("An animal cannot be its own mother.")
            changed_details["mother_identifier_kind"] = "rfid" if len(value) == 15 else "nlis"
        before["values"][key] = getattr(a, key)
        AttributeChange.objects.create(
            event=event,
            animal=a,
            field=key,
            before=str(getattr(a, key) or ""),
            after=str(value or ""),
        )
        setattr(a, key, value)
    earliest = min([start] + list(a.presence.exclude(pk=visit.pk).values_list("start", flat=True)))
    if a.dob and a.dob > calendar_date(actor, earliest):
        raise ValidationError("Date of Birth cannot be later than Farm Entry Date.")
    if "estimated_weeks" in fields and a.estimated_weeks != before["values"].get("estimated_weeks"):
        before["values"]["age_reference"] = a.age_reference
        a.age_reference = start if a.estimated_weeks is not None else None
    elif "start" in before and a.age_reference == before["start"]:
        before["values"]["age_reference"] = a.age_reference
        a.age_reference = start
    if "purchase_cost" in fields:
        # Reuse the existing financial delta and unknown-cost resolution against this cycle.
        price = data.get("purchase_cost")
        cost_visit = purchase_presence(a, visit)
        purchase = a.allocations.filter(
            category="purchase", event=cost_visit.arrival, presence=cost_visit
        ).first()
        if purchase is None:
            raise ValidationError("No acquisition cost exists for this presence cycle.")
        prior = -sum(
            a.allocations.filter(category="purchase", presence=cost_visit).values_list(
                "amount", flat=True
            )
        )
        if price in [None, ""]:
            s.allocate(event, [a], prior, "purchase", unknown=True, presence=cost_visit)
        else:
            price = s.number(price, nonnegative=True)
            s.allocate(event, [a], -(price - prior), "purchase", presence=cost_visit)
        for allocation in a.allocations.filter(
            category="purchase", presence=cost_visit, unknown=True, resolved_by__isnull=True
        ).exclude(event=event):
            allocation.resolved_by = event
            allocation.save(update_fields=["resolved_by"])
    a.save()
    if "mob" in fields:
        existing = a.memberships.filter(superseded=False, end__isnull=True)
        selected = str(data.get("mob") or "")
        if selected != str(existing.values_list("mob_id", flat=True).first() or ""):
            if selected:
                mob = s.scoped(s.Mob, actor, selected)
                if mob.retired:
                    raise ValidationError("Select an eligible mob on the selected PIC.")
            existing.update(end=event.effective_at, end_order=event.effective_order)
            if selected:
                Membership.objects.create(
                    animal=a,
                    mob=mob,
                    start=event.effective_at,
                    start_order=event.effective_order,
                    event=event,
                )
    event.details.setdefault("acquisition_changes", {})[str(a.pk)] = {
        "presence": visit.pk,
        "values": changed_details,
    }
    event.before.setdefault("animal_corrections", []).append(s.clean(before))
    s.participants(event, [a])
    return {"animal": str(a.pk), "animals": [str(a.pk)], "count": 1}


def bulk_edit(actor, event, data):
    s.administrator(actor)
    fields = set(data.get("update_fields", []))
    if not fields or not fields <= BULK_FIELDS:
        raise ValidationError("Choose supported fields to update.")
    animals = s.targets(actor, data, event.effective_at, event.effective_order)
    if not animals:
        raise ValidationError("Select at least one animal.")
    for a in animals:
        edit(actor, event, {**data, "animal": a.label})
    return {"count": len(animals), "animals": [str(a.pk) for a in animals]}


def exit_animals(actor, event, data):
    if data.get("exit_date"):
        at = exit_timestamp(actor, data["exit_date"], data.get("effective_at"))
        if at != event.effective_at:
            raise ValidationError("Exit date does not match the prepared event.")
    animals = s.targets(actor, data, event.effective_at, event.effective_order)
    for a in animals:
        visit = current_visit(a, actor)
        if visit.start > event.effective_at:
            raise ValidationError("Farm Exit Date is before the current Farm Entry Date.")
    if not animals:
        raise ValidationError("Select at least one animal.")
    if "preview_animals" in data and sorted(str(a.pk) for a in animals) != sorted(
        data["preview_animals"]
    ):
        raise ValidationError("Animal selection changed. Refresh the preview.")
    return animals


def transfer(actor, event, data):
    animals = exit_animals(actor, event, data)
    number = validate_identifier("pic", data.get("destination_pic"))
    dest = PIC.objects.filter(number=number, property=actor.property).first()
    if (
        not dest
        or dest.pk == actor.pic_id
        or not properties_for(actor).filter(pk=dest.property_id).exists()
    ):
        raise ValidationError("Choose a different authorised PIC on this same property.")
    if not data.get("nvd"):
        raise ValidationError("NVD Number is required.")
    event.details["nvd"] = validate_identifier("nvd", data["nvd"])
    event.details["destination_pic"] = number
    links = []
    for a in animals:
        if (
            a.participant_set.exclude(event=event)
            .filter(event__effective_at__gt=event.effective_at, event__reversed_by__isnull=True)
            .exists()
        ):
            raise ValidationError("Later animal activity conflicts with this transfer.")
        visit = current_visit(a, actor)
        visit.end, visit.end_order, visit.departure = (
            event.effective_at,
            event.effective_order,
            event,
        )
        visit.save()
        a.memberships.filter(superseded=False, end__isnull=True).update(
            end=event.effective_at, end_order=event.effective_order
        )
        arrival = Event.objects.create(
            property=actor.property,
            pic=dest,
            actor=actor,
            kind="transfer_arrival",
            effective_at=event.effective_at,
            effective_order=event.effective_order,
            details={
                "source_event": str(event.pk),
                "source_pic": actor.pic.number,
                "animal": str(a.pk),
            },
        )
        destination_visit = Presence.objects.create(
            animal=a,
            pic=dest,
            start=event.effective_at,
            start_order=event.effective_order,
            arrival=arrival,
        )
        s.participants(arrival, [a])
        a.pic = dest
        a.save(update_fields=["pic"])
        links.append(
            {
                "animal": str(a.pk),
                "source_presence": visit.pk,
                "destination_presence": destination_visit.pk,
                "destination_event": str(arrival.pk),
            }
        )
    s.participants(event, animals)
    event.details["transfer_links"] = links
    return {
        "count": len(animals),
        "animals": [str(a.pk) for a in animals],
        "destination_pic": number,
    }


def reverse_corrections(actor, event, original):
    s.administrator(actor)
    for row in original.before["animal_corrections"]:
        a = Animal.objects.get(pk=row["animal"])
        visit = Presence.objects.get(pk=row["presence"])
        for key, value in row["values"].items():
            if key in {"dob", "estimated_weeks", "age_reference"} and value in [None, ""]:
                value = None
            if key == "dob" and value:
                value = date.fromisoformat(value)
            setattr(a, key, value)
        if "start" in row:
            a.memberships.filter(superseded=False, start=visit.start, end__isnull=True).update(
                start=row["start"]
            )
            visit.start = row["start"]
            visit.save(update_fields=["start"])
        a.memberships.filter(event=original).update(superseded=True)
        a.memberships.filter(pk__in=row["memberships"]).update(end=None, end_order=None)
        a.identifiers.filter(current=True).update(current=False, retired_at=event.effective_at)
        for tag in row["identifiers"]:
            a.identifiers.filter(kind=tag["kind"], value=tag["value"]).update(
                current=True, retired_at=None
            )
        a.save()
