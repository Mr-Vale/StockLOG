"""Read-only inventory of nonconforming identifiers; never repairs or rewrites data."""

from collections import Counter

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from herd.identifiers import validate_identifier
from herd.models import PIC, Animal, Event, Identifier


class Command(BaseCommand):
    help = "Count legacy nonconforming identifiers without changing data."

    def handle(self, **options):
        counts = Counter()

        def check(kind, value, category):
            if value in [None, ""]:
                return
            try:
                normal = validate_identifier(kind, value)
                if normal != value:
                    counts[category + " (requires normalisation)"] += 1
            except ValidationError:
                counts[category] += 1

        for pic in PIC.objects.iterator():
            check("pic", pic.number, "PIC")
        for tag in Identifier.objects.iterator():
            check(tag.kind, tag.value, "Identifier " + tag.kind)
        for a in Animal.objects.exclude(mother_nlis="").iterator():
            check("mother", a.mother_nlis, "Mother identification")
        for event in Event.objects.iterator():
            rows = event.details.get("entry_rows") or event.details.get("rows") or [event.details]
            for row in rows:
                for key, kind in [
                    ("source_pic", "pic"),
                    ("destination_pic", "pic"),
                    ("nvd", "nvd"),
                ]:
                    check(kind, row.get(key), "Event " + key)
        self.stdout.write(str(dict(sorted(counts.items()))))
        self.stdout.write(
            "Read-only scan complete. Counts include historical event occurrences; no values changed."
        )
