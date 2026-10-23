import getpass
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from herd.models import Property, Account
class Command(BaseCommand):
    help = 'Create the first property/admin only. Password is read securely from terminal or stdin, never argv.'
    def add_arguments(self, p):
        p.add_argument('--username', required=True)
        p.add_argument('--pic', required=True)
        p.add_argument('--property-name', required=True)
        p.add_argument('--timezone', default='Australia/Melbourne')
        p.add_argument('--password-stdin', action='store_true')
    def handle(self, **o):
        ZoneInfo(o['timezone'])
        with transaction.atomic():
            if Account.objects.exists() or Property.objects.exists():
                raise CommandError('Already initialised. Use authenticated administration; no account was replaced.')
            pw = __import__('sys').stdin.readline().rstrip('\n') if o['password_stdin'] else getpass.getpass('First administrator password: ')
            user = Account(username=o['username'], role='admin')
            validate_password(pw, user)
            prop = Property.objects.create(name=o['property_name'], pic=o['pic'], timezone=o['timezone'])
            user.property = prop
            user.set_password(pw)
            user.save()
        self.stdout.write('First administrator created. No public registration is enabled.')
