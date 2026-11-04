import io
import time
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client
from herd import services, clock, reports
from herd.home import summary, months_after
from herd.models import Account, Property, PIC, Animal, Mob, Inventory, Audit
from .test_foundations import run
from .test_business_rules import T, setup_mob, stock

pytestmark = pytest.mark.django_db


def another_property():
    p = Property.objects.create(name="Timberley", address="Test road", owner="Test owner")
    return p, PIC.objects.create(property=p, number="0TEST003")


def token(client, path="/"):
    return client.get(path).wsgi_request.farm_context


def ready(client):
    session = client.session
    session["farm_ready_at"] = 0
    session.save()


def test_no_context_first_admin_and_property_creation():
    with patch("sys.stdin", io.StringIO("Unique-Setup-Passphrase-2026\n")):
        call_command("initial_admin", username="owner", password_stdin=True)
    admin = Account.objects.get(username="owner")
    client = Client()
    client.force_login(admin)
    assert client.get("/").status_code == 200
    assert client.get("/animals/").status_code == 302
    form = {
        "name": "Pinefield",
        "address": "Test address",
        "owner": "Owner",
        "manager": "",
        "number": "0TEST001",
    }
    assert client.post("/properties/add/", form).status_code == 302
    assert Property.objects.count() == PIC.objects.count() == 1
    client.post("/properties/add/", {**form, "name": "Duplicate PIC"})
    assert Property.objects.count() == 1  # atomic failure
    assert Audit.objects.filter(action="property_create").count() == 1


def test_selection_saved_default_revocation_and_wrong_pic(farm):
    p, a, b, _ = farm
    second = PIC.objects.create(property=p, number="0TEST002")
    other, other_pic = another_property()
    c = Client()
    c.force_login(b)
    page = c.get("/")
    assert b"Timberley" not in page.content
    assert (
        c.post("/context/select/", {"property": other.pk, "pic": other_pic.pk}).status_code == 400
    )
    assert c.post("/context/select/", {"property": p.pk, "pic": other_pic.pk}).status_code == 400
    response = c.post("/context/select/", {"property": p.pk, "pic": second.pk})
    assert 4000 <= response.json()["wait_ms"] <= 5000
    assert c.get("/animals/").status_code == 302
    b.refresh_from_db()
    assert b.pic_id != second.pk
    ready(c)
    c.post("/context/select/", {"property": p.pk, "pic": second.pk, "save": "1"})
    b.refresh_from_db()
    assert b.pic_id == second.pk
    c2 = Client()
    c2.force_login(b)
    assert c2.get("/").wsgi_request.user.pic_id == second.pk
    b.properties.clear()
    assert c2.get("/animals/").status_code == 302
    assert b"No properties are available" in c2.get("/").content
    with pytest.raises(PermissionDenied):
        services.execute(b, "revoked", "mob", {"name": "forbidden"})


def test_shared_inventory_and_isolated_pic_and_property(farm):
    p, a, b, _ = farm
    first = b.pic
    second = PIC.objects.create(property=p, number="0TEST002")
    with clock.at(T):
        mob = setup_mob(b, 1)
        hay = stock(b)
        animal = Animal.objects.first()
        b.pic = second
        second_mob = run(b, "mob", {"name": "Second PIC"})["mob"]
        with pytest.raises(ValidationError):
            run(b, "feed", {"mob": mob, "item": hay, "quantity": 1, "mode": "bales"})
        with pytest.raises(ValidationError):
            services.find_animal(b, animal.label)
        run(
            b,
            "register",
            {
                "nlis": "0TEST000YYY00000",
                "source_pic": "0FROM001",
                "nvd": "00000001",
                "mob": second_mob,
                "purchase_cost": 100,
            },
        )
        run(b, "feed", {"mob": second_mob, "item": hay, "quantity": 1, "mode": "bales"})
        assert len(reports.build(b, {})["rows"]) == 1
        other, other_pic = another_property()
        b.property, b.pic = other, other_pic
        b.properties.add(other)
        with pytest.raises(ValidationError):
            run(b, "stocktake", {"item": hay, "actual": 1, "reason": "cross property"})
        assert reports.build(b, {"dataset": "inventory"})["rows"] == []


def test_stale_form_rejected_after_pic_switch(farm):
    p, a, b, _ = farm
    second = PIC.objects.create(property=p, number="0TEST002")
    c = Client()
    c.force_login(b)
    old = token(c, "/action/mob/")
    preview = c.post(
        "/action/mob/",
        {"farm_context": old, "name": "Old context", "submission_key": "old"},
    )
    assert preview.context["confirmation"]
    c.post("/context/select/", {"property": p.pk, "pic": second.pk})
    ready(c)
    assert (
        c.post(
            "/action/mob/",
            {"farm_context": old, "name": "Bad", "submission_key": "bad"},
        ).status_code
        == 403
    )
    new = token(c)
    response = c.post(
        "/action/mob/",
        {
            "farm_context": new,
            "confirmed_payload": preview.context["confirmation"],
            "submission_key": "old",
        },
    )
    assert b"Invalid confirmation" in response.content
    assert not Mob.objects.filter(name="Old context").exists()


def test_summary_chart_boundaries_and_preferences(farm):
    from datetime import date, datetime, timezone

    p, a, b, _ = farm
    today = date(2026, 11, 2)
    for i, (dob, age) in enumerate(
        [
            (date(2026, 8, 3), None),
            (date(2026, 8, 2), None),
            (date(2025, 11, 2), None),
            (date(2024, 11, 2), None),
            (None, None),
        ]
    ):
        Animal.objects.create(
            property=p,
            pic=b.pic,
            dob=dob,
            sex="STEER" if i == 0 else "F",
            breed="Angus",
        )
    with clock.at(int(datetime(2026, 11, 2, 1, tzinfo=timezone.utc).timestamp())):
        pics, charts = summary(b)
    assert pics[0]["cattle"] == 5
    ages = {r["label"]: r["count"] for r in charts[2]["rows"]}
    assert ages == {
        "Under 3 months": 1,
        "3–12 months": 1,
        "12–24 months": 1,
        "24 months and over": 1,
        "Unknown age": 1,
    }
    c = Client()
    c.force_login(b)
    t = token(c)
    assert (
        c.post(
            "/charts/", {"farm_context": t, "sex": "bar", "breed": "pie", "age": "bar"}
        ).status_code
        == 302
    )
    b.refresh_from_db()
    assert b.chart_preferences["sex"] == "bar"


def test_administration_roles_and_access_log(farm):
    p, a, b, _ = farm
    other, _ = another_property()
    c = Client()
    c.force_login(b)
    assert c.get("/properties/add/").status_code == 403
    c.force_login(a)
    assert c.post("/access/", {"account": b.pk, "properties": [other.pk]}).status_code == 302
    assert list(b.properties.values_list("pk", flat=True)) == [other.pk]
    assert Audit.objects.filter(action="property_access").count() == 2


def test_transition_deadline_and_malformed_selection(farm):
    p, a, b, _ = farm
    second = PIC.objects.create(property=p, number="0TEST002")
    c = Client()
    c.force_login(b)
    c.get("/")
    assert c.post("/context/select/", {"property": "invalid", "pic": "bad"}).status_code == 400
    with patch("time.time", return_value=1000):
        assert (
            c.post("/context/select/", {"property": p.pk, "pic": second.pk}).json()["wait_ms"]
            == 5000
        )
        assert c.get("/context/ready/").json()["ready"] is False
    with patch("time.time", return_value=1004):
        assert c.get("/animals/").status_code == 302
    with patch("time.time", return_value=1005):
        assert c.get("/context/ready/").json()["ready"] is True
        assert c.get("/animals/").status_code == 200


def test_repurchase_to_another_pic_rejected(farm):
    p, a, b, _ = farm
    second = PIC.objects.create(property=p, number="0TEST002")
    with clock.at(T):
        mob = setup_mob(b, 1)
        animal = Animal.objects.first()
        run(b, "sale", {"mob": mob, "destination_pic": "0DEST001", "nvd": "00000001", "price": 200})
    with clock.at(T + 1):
        b.pic = second
        with pytest.raises(ValidationError, match="does not qualify"):
            run(
                b,
                "register",
                {
                    "entry_source": "repurchase",
                    "nlis": animal.label,
                    "source_pic": "0FROM001",
                    "nvd": "00000001",
                },
            )
    animal.refresh_from_db()
    assert animal.status == "exited" and animal.presence.count() == 1


def test_mob_retirement_preserves_history_and_can_be_undone(farm):
    _, a, b, _ = farm
    with clock.at(T):
        result = run(b, "mob", {"name": "Empty mob"})
        mob = Mob.objects.get(pk=result["mob"])
        retired = run(b, "mob", {"retire_mob": mob.pk})
        mob.refresh_from_db()
        assert mob.retired
        run(
            b,
            "reverse",
            {"original": retired["event"], "reason": "Retired the wrong mob"},
        )
        mob.refresh_from_db()
        assert not mob.retired
        assert Audit.objects.filter(event_id=retired["event"]).exists()
