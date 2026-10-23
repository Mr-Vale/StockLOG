import json

from django.core.management.base import BaseCommand

from herd.backups import restore_backup


class Command(BaseCommand):
    help = "Restore to an EMPTY isolated database. Requires protected local recovery key and explicit target."

    def add_arguments(self, p):
        p.add_argument("archive")
        p.add_argument("--identity", required=True)
        p.add_argument("--confirm-database", required=True)

    def handle(self, **o):
        self.stdout.write(
            json.dumps(
                restore_backup(o["archive"], o["identity"], o["confirm_database"]),
                indent=2,
            )
        )
