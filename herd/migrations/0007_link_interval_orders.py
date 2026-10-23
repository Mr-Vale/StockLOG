from django.db import migrations


def populate_interval_orders(apps, schema_editor):
    Presence = apps.get_model("herd", "Presence")
    Membership = apps.get_model("herd", "Membership")
    for row in Presence.objects.select_related("arrival", "departure").iterator():
        row.start_order = row.arrival.effective_order
        row.end_order = row.departure.effective_order if row.departure_id else None
        row.save(update_fields=["start_order", "end_order"])
    for row in Membership.objects.select_related("event").iterator():
        row.start_order = row.event.effective_order
        row.save(update_fields=["start_order"])
    for row in Membership.objects.exclude(end=None).iterator():
        candidates = list(
            Membership.objects.filter(
                animal_id=row.animal_id, start=row.end, start_order__gt=row.start_order
            ).values_list("start_order", flat=True)
        )
        candidates += list(
            Presence.objects.filter(
                animal_id=row.animal_id, end=row.end, end_order__isnull=False
            ).values_list("end_order", flat=True)
        )
        row.end_order = min(candidates) if candidates else 0
        row.save(update_fields=["end_order"])


class Migration(migrations.Migration):
    dependencies = [("herd", "0006_membership_end_order_membership_start_order_and_more")]
    operations = [migrations.RunPython(populate_interval_orders, migrations.RunPython.noop)]
