import json

from django.core.management.base import BaseCommand

from herd.backups import create_backup


class Command(BaseCommand):
    help = "Create a consistent encrypted archive; retain exactly three latest successful unique versions."

    def handle(self, **options):
        self.stdout.write(json.dumps(create_backup(), indent=2))
