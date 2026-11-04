"""Entry review, date-only and active enquiry regressions using synthetic animals."""

import uuid
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, RequestFactory

from herd import clock, services
from herd.active import COLUMNS, active_table
from herd.entry import ORDER, EntryForm
from herd.models import PIC, Allocation, Animal, Event, Mob, Restriction, Submission

pytestmark = pytest.mark.django_db
T = clock.local_timestamp("2026-11-04T12:00:00", "Australia/Melbourne")


def run(actor, data, key=None):
    return services.execute(actor, key or uuid.uuid4().hex, "register", data)


def purchase(**kw):
    return dict(nlis="0000000000000001", source_pic="SRC00001", nvd="NVD", **kw)


def client_for(user):
    c = Client()
    c.force_login(user)
    token = c.get("/").wsgi_request.farm_context
    return c, token


def stage(c, token, **kw):
    response = c.get("/workflow/entry/")
    payload = dict(
        farm_context=token,
        review_state=response.context["review_state"],
        task="add",
        mode="purchase",
        farm_entry_date="2026-11-04",
        **purchase(),
    )
    payload.update(kw)
    return c.post("/workflow/entry/", payload)


def test_mode_fields_optional_birth_and_locks(farm):
    p, a, b, _ = farm
    for mode in ORDER:
        f = EntryForm(b, mode)
        assert list(f.fields) == ORDER[mode]
    with clock.at(T):
        f = EntryForm(
            b,
            "birth",
            dict(
                farm_entry_date="2026-11-04",
                rfid="000000000000001",
                source_pic="FORGED",
                source_name="FORGED",
                purchase_cost="999",
            ),
        )
        assert f.is_valid(), f.errors
        assert f.cleaned_data["purchase_cost"] == 0
        run(b, f.payload())
        animal = Animal.objects.get()
        assert animal.dob is None and animal.mother_nlis == ""
        alloc = Allocation.objects.get()
        assert not alloc.unknown and alloc.amount == 0
        e = Event.objects.get(kind="register")
        assert e.details["birth_sources"][0]["source_pic"] == b.pic.number
        assert e.details["birth_sources"][0]["source_name"] == p.name
        f = EntryForm(b, "purchase", dict(farm_entry_date="2026-11-04", **purchase()))
        assert f.is_valid(), f.errors
        run(b, f.payload())
        assert Allocation.objects.filter(unknown=True).count() == 1


@pytest.mark.parametrize("mother", ["A" * 16, "000000000000009"])
def test_mother_either_identifier_retained(farm, mother):
    _, a, b, _ = farm
    with clock.at(T):
        run(b, dict(entry_source="birth", nlis="B" * 16, mother_nlis=mother))
    assert Animal.objects.get().mother_nlis == mother
    source = Event.objects.get().details["birth_sources"][0]
    assert source["mother_identifier_kind"] == ("rfid" if len(mother) == 15 else "nlis")


@pytest.mark.parametrize("day", ["2026-04-05", "2026-10-04"])
def test_date_only_dst_roundtrip_and_backdate_permissions(farm, day):
    _, a, b, _ = farm
    with clock.at(T):
        f = EntryForm(a, "purchase", dict(farm_entry_date=day, **purchase()))
        assert f.is_valid(), f.errors
        run(a, f.payload())
        start = Animal.objects.get().presence.get().start
        assert (
            datetime.fromtimestamp(start, ZoneInfo(a.property.timezone))
            .isoformat()
            .startswith(day + "T00:00:00")
        )
        f = EntryForm(b, "purchase", dict(farm_entry_date=day, **purchase()))
        assert not f.is_valid()
        with pytest.raises(PermissionDenied):
            run(b, dict(farm_entry_date=day, **purchase()))


def test_date_future_chronology_and_identifier_validation(farm):
    _, a, b, _ = farm
    with clock.at(T):
        for row in [
            dict(farm_entry_date="2026-11-05", **purchase()),
            dict(farm_entry_date="2026-11-04", rfid="１" * 15, source_pic="SRC", nvd="N"),
            dict(farm_entry_date="2026-11-04", nlis="short", source_pic="SRC", nvd="N"),
        ]:
            assert not EntryForm(b, "purchase", row).is_valid()
        f = EntryForm(
            b,
            "birth",
            dict(farm_entry_date="2026-11-04", nlis="A" * 16, dob="2026-11-05"),
        )
        assert not f.is_valid()
        with pytest.raises(ValidationError, match="later than arrival"):
            run(a, dict(entry_source="birth", nlis="A" * 16, dob="2026-11-05"))


def test_review_edit_remove_modes_atomic_save_and_retry(farm):
    _, a, b, _ = farm
    c, token = client_for(b)
    with clock.at(T):
        r = stage(c, token)
        assert len(r.context["reviews"]) == 1 and not Animal.objects.exists()

        def post(task, **kw):
            return c.post(
                "/workflow/entry/",
                dict(
                    farm_context=token,
                    review_state=r.context["review_state"],
                    mode=r.context["mode"],
                    task=task,
                    **kw,
                ),
            )

        r = c.post(
            "/workflow/entry/",
            dict(farm_context=token, review_state=r.context["review_state"], mode="birth"),
        )
        assert r.context["mode"] == "birth" and len(r.context["reviews"]) == 1
        r = post("edit:0")
        assert r.context["mode"] == "purchase"
        r = post("add", editing="0", farm_entry_date="2026-11-04", **purchase(breed="Angus"))
        # Explicitly choose purchase when correcting a purchase row.
        if r.context["error"] or len(r.context["reviews"]) != 1:
            pytest.fail(str(r.context["error"]))
        saved_state = r.context["review_state"]
        r = post("save")
        assert Animal.objects.count() == 1
        c.post(
            "/workflow/entry/",
            dict(
                farm_context=token,
                review_state=saved_state,
                task="save",
                mode="purchase",
            ),
        )
        assert Animal.objects.count() == 1 and Submission.objects.count() == 1


def test_duplicate_batch_rollback_and_reserved_history(farm):
    _, a, b, _ = farm
    with clock.at(T):
        with pytest.raises(ValidationError, match="Row 2"):
            run(b, {"rows": [purchase(), purchase()]})
        assert not Animal.objects.exists() and not Event.objects.exists()
        run(b, purchase(rfid="000000000000001"))
        services.execute(
            b,
            "tag",
            "replace_tag",
            dict(animal="0000000000000001", nlis="0" * 15 + "2", reason="replacement"),
        )
        with pytest.raises(ValidationError, match="reserved"):
            run(b, purchase())
        with pytest.raises(ValidationError):
            run(
                b,
                dict(nlis="Z" * 16, rfid="000000000000001", source_pic="SRC", nvd="N"),
            )


def test_staged_errors_and_context_change_do_not_redirect(farm):
    p, a, b, _ = farm
    c, token = client_for(b)
    with clock.at(T):
        r = stage(c, token)
        state = r.context["review_state"]
        run(b, purchase())  # Another submission reserves the staged identifier.
        r = c.post(
            "/workflow/entry/",
            dict(farm_context=token, review_state=state, task="save", mode="purchase"),
        )
        assert len(r.context["reviews"]) == 1 and "Row 1" in r.context["error"]
        second = PIC.objects.create(property=p, number="TEST0002")
        with patch("time.time", return_value=1000):
            c.post("/context/select/", dict(property=p.pk, pic=second.pk))
        with patch("time.time", return_value=1005):
            r = c.post(
                "/workflow/entry/",
                dict(farm_context=token, review_state=state, task="save", mode="purchase"),
            )
            assert not r.context["context_matches"] and len(r.context["reviews"]) == 1
            assert Animal.objects.count() == 1
            r = c.post(
                "/workflow/entry/",
                dict(
                    farm_context=r.wsgi_request.farm_context,
                    review_state=state,
                    task="restart",
                    mode="purchase",
                ),
            )
            assert r.context["context_matches"] and not r.context["reviews"]


def test_active_columns_sort_ages_restrictions_and_lifetime(farm):
    p, a, b, _ = farm
    with clock.at(T):
        run(
            b,
            purchase(
                purchase_cost="900",
                dob="2025-08-04",
                sex="STEER",
                rfid="000000000000001",
            ),
        )
        run(
            b,
            dict(
                nlis="0" * 15 + "2",
                source_pic="SRC",
                nvd="N",
                age_weeks=26,
                purchase_cost="100",
            ),
        )
        run(b, dict(nlis="0" * 15 + "3", source_pic="SRC", nvd="N"))
        animal = Animal.objects.order_by("dob").filter(dob__isnull=False).get()
        event = Event.objects.get(participants__animal=animal, kind="register")
        for days in [30, 5]:
            Restriction.objects.create(
                event=event,
                animal=animal,
                starts_at=T,
                ends_at=T + days * 86400,
                days=days,
                timezone=p.timezone,
            )
        request = RequestFactory().get("/animals/?sort=cost&direction=desc")
        request.user = b
        table = active_table(request)
        assert len(COLUMNS) == 9 and len(table["rows"]) == 3
        first = table["rows"][0]
        assert (
            first["sex"] == "S"
            and first["age_text"] == "3-1"
            and first["nlis"] == "0000000000000001"
            and first["rfid"] == "000000000000001"
        )
        assert first["safe"] == date(2026, 12, 4)
        assert table["rows"][-1]["complete"] is False
        assert "biological age unknown" in table["rows"][-1]["age_origin"]
        Restriction.objects.filter(days=30).update(superseded_by=event)
        assert active_table(request)["rows"][0]["safe"] == date(2026, 11, 9)
        Event.objects.filter(pk=event.pk).update(reversed_by=event)
        assert active_table(request)["rows"][0]["safe"] == date(2026, 11, 4)


def test_retired_foreign_mobs_and_conflicting_links(farm):
    p, a, b, _ = farm
    second = PIC.objects.create(property=p, number="TEST0002")
    foreign = Mob.objects.create(property=p, pic=second, name="Other PIC")
    retired = Mob.objects.create(property=p, pic=b.pic, name="Retired", retired=True)
    with clock.at(T):
        for mob in [foreign, retired]:
            with pytest.raises(ValidationError):
                run(b, purchase(mob=mob.pk))
        assert Animal.objects.count() == 0
        run(b, purchase())
        run(b, dict(rfid="000000000000002", source_pic="SRC", nvd="N"))
        with pytest.raises(ValidationError, match="different animals"):
            run(b, purchase(rfid="000000000000002", entry_source="repurchase"))


def test_repurchase_preserves_descriptions_costs_and_current_tags(farm):
    p, a, b, _ = farm
    with clock.at(T):
        run(
            b,
            purchase(
                purchase_cost="100",
                breed="Angus",
                sex="M",
                dob="2025-01-01",
                rfid="000000000000001",
            ),
        )
        animal = Animal.objects.get()
        services.execute(
            b,
            "retag",
            "replace_tag",
            dict(animal=animal.label, nlis="A" * 16, reason="tag"),
        )
        services.execute(
            b,
            "exit",
            "sale",
            dict(
                animal=animal.label,
                animals=[animal.label],
                destination_pic="DST",
                nvd="N",
                price="200",
            ),
        )
    with clock.at(T + 86400):
        run(
            b, purchase(entry_source="repurchase")
        )  # Historical lookup tag does not become current again.
        animal.refresh_from_db()
        assert (
            animal.label == "A" * 16 and animal.breed == "Angus" and animal.dob == date(2025, 1, 1)
        )
        assert Animal.objects.count() == 1 and animal.presence.count() == 2
        r = RequestFactory().get("/animals/")
        r.user = b
        row = active_table(r)["rows"][0]
        assert row["entry"] == datetime.fromtimestamp(T + 86400, ZoneInfo(p.timezone)).date()
        assert row["cost"] == 100 and not row["complete"]


@pytest.mark.parametrize("key", [k for k, _ in COLUMNS])
def test_every_active_sort_toggles_and_retains_missing_last(farm, key):
    _, a, b, _ = farm
    with clock.at(T):
        run(
            b,
            purchase(
                purchase_cost="900",
                breed="Zulu",
                sex="M",
                dob="2025-01-01",
                rfid="000000000000009",
            ),
        )
        run(
            b,
            dict(
                nlis="0" * 15 + "2",
                purchase_cost="100",
                breed="Angus",
                sex="F",
                dob="2026-01-01",
                source_pic="SRC",
                nvd="N",
                rfid="000000000000002",
            ),
        )
        first = []
        for direction in ["asc", "desc"]:
            request = RequestFactory().get(f"/animals/?sort={key}&direction={direction}")
            request.user = b
            table = active_table(request)
            assert len(table["rows"]) == 2
            assert table["headings"][[k for k, _ in COLUMNS].index(key)]["active"]
            first.append(table["rows"][0]["identity"])
        if key in ["nlis", "rfid", "breed", "sex", "cost", "age"]:
            assert first[0] != first[1]


def test_review_removal_date_preference_and_next_day_confirmed_retry(farm):
    _, a, b, _ = farm
    b.date_format = "%Y-%m-%d %H:%M"
    b.save(update_fields=["date_format"])
    c, token = client_for(b)
    with clock.at(T):
        r = stage(c, token)
        assert ("Event Date", "2026-11-04") in r.context["reviews"][0]["fields"]
        state = r.context["review_state"]
        removed = c.post(
            "/workflow/entry/",
            dict(farm_context=token, review_state=state, task="remove:0", mode="purchase"),
        )
        assert not removed.context["reviews"] and not Animal.objects.exists()
        saved = c.post(
            "/workflow/entry/",
            dict(farm_context=token, review_state=state, task="save", mode="purchase"),
        )
        assert saved.status_code == 200 and Animal.objects.count() == 1
    with clock.at(T + 86400):
        retried = c.post(
            "/workflow/entry/",
            dict(farm_context=token, review_state=state, task="save", mode="purchase"),
        )
        assert "Saved 1 animals" in retried.content.decode()
        assert Animal.objects.count() == 1 and Submission.objects.count() == 1


def test_staged_mob_review_uses_pic_mob_name(farm):
    p, a, b, _ = farm
    mob = Mob.objects.create(property=p, pic=b.pic, name="MOB-017A")
    c, token = client_for(b)
    with clock.at(T):
        r = stage(c, token, mob=str(mob.pk))
        assert ("MOB Number", "MOB-017A") in r.context["reviews"][0]["fields"]
        c.post(
            "/workflow/entry/",
            dict(
                farm_context=token,
                review_state=r.context["review_state"],
                task="save",
                mode="purchase",
            ),
        )
        assert Animal.objects.get().memberships.get().mob == mob
