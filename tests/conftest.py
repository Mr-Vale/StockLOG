import pytest

from herd.models import Account, Property, PIC


@pytest.fixture
def farm(db):
    p = Property.objects.create(
        name="Synthetic acceptance property",
        address="Synthetic address",
        owner="Synthetic owner",
        timezone="Australia/Melbourne",
    )
    pic = PIC.objects.create(property=p, number="0TEST001")
    admin = Account.objects.create_user(
        username="A",
        password="Synthetic-Test-Password-2026",
        property=p,
        pic=pic,
        role="admin",
    )
    b = Account.objects.create_user(
        username="B", password="Synthetic-Test-Password-2026", property=p, pic=pic
    )
    c = Account.objects.create_user(
        username="C", password="Synthetic-Test-Password-2026", property=p, pic=pic
    )
    for user in (admin, b, c):
        user.properties.add(p)
    return p, admin, b, c
