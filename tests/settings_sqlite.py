"""Portable functional checks only; MariaDB concurrency/backup tests require production engine."""

from stocklog.settings import *
from django.db.backends.signals import connection_created

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/stocklog-dev.sqlite3",
    }
}


def collations(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        connection.connection.create_collation(
            "utf8mb4_bin", lambda a, b: (a > b) - (a < b)
        )


connection_created.connect(collations)
