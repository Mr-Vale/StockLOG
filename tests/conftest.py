import pytest

from herd.models import Account, Property


@pytest.fixture
def farm(db):
    p = Property.objects.create(
        name="Synthetic acceptance property",
        pic="TEST0001",
        timezone="Australia/Melbourne",
    )
    admin = Account.objects.create_user(
        username="A", password="Synthetic-Test-Password-2026", property=p, role="admin"
    )
    b = Account.objects.create_user(
        username="B", password="Synthetic-Test-Password-2026", property=p
    )
    c = Account.objects.create_user(
        username="C", password="Synthetic-Test-Password-2026", property=p
    )
    return p, admin, b, c
