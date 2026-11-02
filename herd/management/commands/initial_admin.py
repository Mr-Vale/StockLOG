import getpass
import sys
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from herd.models import Account


class Command(BaseCommand):
    help = "Create the first administrator. Property/PIC setup follows in the browser."

    def add_arguments(self, p):
        p.add_argument("--username")
        p.add_argument("--password-stdin", action="store_true")

    def handle(self, **o):
        if Account.objects.exists():
            raise CommandError("Already initialised. No administrator was replaced.")
        username = o["username"] or input("Initial administrator username: ").strip()
        user = Account(username=username, role="admin")
        try:
            user.full_clean(exclude=["password"])
            if o["password_stdin"]:
                pw = sys.stdin.readline().rstrip("\n")
            else:
                while True:
                    pw = getpass.getpass("Initial administrator password: ")
                    confirm = getpass.getpass("Repeat password: ")
                    if pw != confirm:
                        self.stderr.write("Passwords do not match. Try again.")
                        continue
                    try:
                        validate_password(pw, user)
                    except ValidationError as e:
                        self.stderr.write("; ".join(e.messages))
                        continue
                    break
            validate_password(pw, user)
            with transaction.atomic():
                if Account.objects.exists():
                    raise CommandError("Already initialised.")
                user.set_password(pw)
                user.save()
        except ValidationError as e:
            raise CommandError("; ".join(e.messages)) from e
        self.stdout.write(
            "Administrator created. Log in to add your first property and PIC."
        )
