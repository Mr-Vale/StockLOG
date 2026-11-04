import threading
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections

from herd import clock
from herd import services as s
from herd.models import Account, Allocation, Animal, Inventory

from .test_business_rules import T, setup_mob, stock


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["feed", "chemical"])
def test_two_sessions_serialize_stock_without_partial_allocations(farm, kind):
    _, a, b, c = farm
    with clock.at(T):
        mob = setup_mob(b, 1)
        item = stock(
            b,
            kind=kind,
            packages=1,
            package_size=10,
            package_price=10,
            stock_unit="kg" if kind == "feed" else "mL",
        )
    barrier = threading.Barrier(2)
    outcomes = []

    def submit(pk):
        close_old_connections()
        try:
            user = Account.objects.get(pk=pk)
            barrier.wait(timeout=10)
            with clock.at(T + 1):
                payload = (
                    {"mob": mob, "item": item, "quantity": "12", "mode": "total_kg"}
                    if kind == "feed"
                    else {"mob": mob, "item": item, "dose": "8", "dose_unit": "mL"}
                )
                s.execute(
                    user,
                    uuid.uuid4().hex,
                    "feed" if kind == "feed" else "treat",
                    payload,
                )
            outcomes.append("saved")
        except ValidationError:
            outcomes.append("rejected")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=submit, args=(u.id,)) for u in [b, c]]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
        assert not t.is_alive()
    assert sorted(outcomes) == ["rejected", "saved"]
    assert Inventory.objects.get(pk=item).balance == (-2 if kind == "feed" else 2)
    assert Allocation.objects.filter(category="feed" if kind == "feed" else "chemical").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_submission_returns_same_event(farm):
    _, a, b, c = farm
    barrier = threading.Barrier(2)
    ids = []

    def submit():
        close_old_connections()
        try:
            user = Account.objects.get(pk=b.pk)
            barrier.wait(timeout=10)
            with clock.at(T):
                r = s.execute(
                    user,
                    "same-request",
                    "register",
                    {"nlis": "0TEST000ZZZ00000", "source_pic": "0FROM001", "nvd": "00000001"},
                )
            ids.append(r["event"])
        finally:
            connections.close_all()

    ts = [threading.Thread(target=submit) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(20)
        assert not t.is_alive()
    assert len(ids) == 2 and ids[0] == ids[1] and Animal.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_entries_cannot_duplicate_identity_or_occupancy(farm):
    from django.db import IntegrityError

    from herd.models import Presence

    _, a, b, c = farm
    barrier = threading.Barrier(2)
    outcomes = []

    def submit(pk):
        close_old_connections()
        try:
            user = Account.objects.get(pk=pk)
            barrier.wait(timeout=10)
            with clock.at(T):
                s.execute(
                    user,
                    uuid.uuid4().hex,
                    "register",
                    {"nlis": "0TEST000CON00001", "source_pic": "0FROM001", "nvd": "00000001"},
                )
            outcomes.append("saved")
        except (ValidationError, IntegrityError):
            outcomes.append("rejected")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=submit, args=(u.pk,)) for u in [b, c]]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
        assert not t.is_alive()
    assert sorted(outcomes) == ["rejected", "saved"]
    assert Animal.objects.count() == 1 and Presence.objects.filter(end__isnull=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_sessions_cannot_replace_a_just_populated_identifier(farm):
    from django.core.exceptions import PermissionDenied

    from .test_foundations import arrival

    _, admin, b, c = farm
    with clock.at(T):
        identity = arrival(b)["animals"][0]
    label = Animal.objects.get(pk=identity).label
    barrier = threading.Barrier(2)
    outcomes = []

    def fill(pk, value):
        close_old_connections()
        try:
            actor = Account.objects.get(pk=pk)
            barrier.wait(timeout=10)
            with clock.at(T + 1):
                s.execute(
                    actor,
                    uuid.uuid4().hex,
                    "edit_animal",
                    {
                        "animal": label,
                        "update_fields": ["rfid"],
                        "rfid": value,
                    },
                )
            outcomes.append("saved")
        except PermissionDenied:
            outcomes.append("denied")
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=fill, args=(user.pk, f"{n:015}")) for user, n in [(b, 11), (c, 12)]
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
        assert not thread.is_alive()
    assert sorted(outcomes) == ["denied", "saved"]
    assert (
        Animal.objects.get(pk=identity).identifiers.filter(kind="rfid", current=True).count() == 1
    )
