"""Read-only summary of the selected animal's current/latest farm period."""

from django.db.models import Sum

from . import reports
from .cattle_services import acquisition, calendar_date, purchase_presence
from .models import Event


def summary(actor, animal):
    row = reports.build(actor, {"filters": {"animal": str(animal.pk)}})["rows"][0]
    tags = dict(animal.identifiers.filter(current=True).values_list("kind", "value"))
    visit = (
        animal.presence.select_related("arrival", "departure")
        .order_by("-start", "-start_order", "-pk")
        .first()
    )
    details = acquisition(animal, visit) if visit else {}
    origin = purchase_presence(animal, visit) if visit else None
    departure = visit.departure if visit else None
    mob = (
        animal.memberships.filter(end__isnull=True, superseded=False).select_related("mob").first()
    )
    treatment = (
        Event.objects.filter(
            property=actor.property,
            participants__animal=animal,
            kind="treat",
            reversed_by__isnull=True,
        )
        .order_by("-effective_at", "-effective_order")
        .first()
    )
    return {
        "animal": animal,
        "summary": {
            "visual_id": tags.get("nlis"),
            "rfid": tags.get("rfid"),
            "status": "Active" if animal.status == "active" else "Deactive",
            "mob": mob.mob.name if mob else None,
            "entry_date": calendar_date(actor, visit.start) if visit else None,
            "purchased": not origin or acquisition(animal, origin).get("entry_source") != "birth",
            "source_pic": details.get("source_pic"),
            "source_name": details.get("vendor_name"),
            "source_address": details.get("vendor_address"),
            "incoming_nvd": details.get("nvd"),
            "cost": row["cost"],
            "financial_complete": row["financial_complete"],
            "treatment_date": calendar_date(actor, treatment.effective_at) if treatment else None,
            "exit_date": calendar_date(actor, visit.end)
            if visit and visit.end is not None
            else None,
            "destination_applicable": not departure or departure.kind != "death",
            "destination_pic": departure.details.get("destination_pic") if departure else None,
            "destination_name": departure.details.get("destination_name") if departure else None,
            "destination_address": departure.details.get("destination_address")
            if departure
            else None,
            "outgoing_nvd": departure.details.get("nvd") if departure else None,
            "sale": bool(departure and departure.kind == "sale"),
            # A group sale's entered price is not this animal's allocated sale price.
            "sale_price": animal.allocations.filter(event=departure, category="sale").aggregate(
                total=Sum("amount")
            )["total"]
            if departure and departure.kind == "sale"
            else None,
        },
    }
