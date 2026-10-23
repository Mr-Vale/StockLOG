from django.db import migrations


def link_existing_purchase_cycles(apps, schema_editor):
    Allocation = apps.get_model("herd", "Allocation")
    Presence = apps.get_model("herd", "Presence")
    for allocation in (
        Allocation.objects.filter(category="purchase", presence__isnull=True)
        .select_related("event")
        .order_by("pk")
        .iterator()
    ):
        visit = Presence.objects.filter(
            animal_id=allocation.animal_id, arrival_id=allocation.event_id
        ).first()
        if not visit and allocation.event.details.get("original"):
            prior = Allocation.objects.filter(
                event_id=allocation.event.details["original"],
                animal_id=allocation.animal_id,
                category="purchase",
            ).first()
            if prior and prior.presence_id:
                visit = Presence.objects.filter(pk=prior.presence_id).first()
        if not visit:
            visit = (
                Presence.objects.filter(
                    animal_id=allocation.animal_id, start__lte=allocation.event.effective_at
                )
                .order_by("-start")
                .first()
            )
        if visit:
            Allocation.objects.filter(pk=allocation.pk).update(presence=visit)


class Migration(migrations.Migration):
    dependencies = [("herd", "0004_allocation_presence")]
    operations = [migrations.RunPython(link_existing_purchase_cycles, migrations.RunPython.noop)]
