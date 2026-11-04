"""Synthetic regressions for date-only corrections, strict identifiers and atomic exits."""

import uuid
from decimal import Decimal

import pytest
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client

from herd import clock
from herd import services as s
from herd.cattle import EditForm, ExitForm
from herd.cattle_services import acquisition, current_visit
from herd.identifiers import validate_identifier
from herd.models import (
    PIC,
    Allocation,
    Animal,
    Audit,
    Event,
    Identifier,
    Presence,
    Restriction,
)

pytestmark = pytest.mark.django_db
T = clock.local_timestamp("2026-11-05T12:00:00", "Australia/Melbourne")


def run(user, kind, data, **kw):
    return s.execute(user, uuid.uuid4().hex, kind, data, **kw)


def animal(user, n=1, **kw):
    kw.setdefault("entry_date", "2026-11-05")
    payload = dict(
        nlis=f"0TEST001ABC{n:05}",
        rfid=f"{n:015}",
        source_pic="0FROM001",
        nvd="00000001",
        purchase_cost=100,
        **kw,
    )
    result = run(user, "register", payload)
    return Animal.objects.get(pk=result["animals"][0])


def client_for(user):
    client = Client()
    client.force_login(user)
    token = client.get("/").wsgi_request.farm_context
    return client, token


@pytest.mark.parametrize(
    "kind,value,want",
    [
        ("pic", " 0test001 ", "0TEST001"),
        ("nlis", "0test001abc00001", "0TEST001ABC00001"),
        ("rfid", "000000000000001", "000000000000001"),
        ("nvd", "00000001", "00000001"),
        ("mother", "000000000000001", "000000000000001"),
        ("mother", "0test001abc00001", "0TEST001ABC00001"),
    ],
)
def test_formats(kind, value, want):
    assert validate_identifier(kind, value) == want


@pytest.mark.parametrize(
    "kind,value",
    [
        ("pic", "TEST0001"),
        ("pic", "0TES1001"),
        ("nlis", "A" * 16),
        ("nlis", "0TEST001ABC0000!"),
        ("rfid", "０" * 15),
        ("rfid", "0" * 14),
        ("rfid", "0" * 16),
        ("nvd", "0000 001"),
        ("nvd", "00000001\nX"),
        ("pic", "0TE ST001"),
    ],
)
def test_reject_wrong_format(kind, value):
    with pytest.raises(ValidationError):
        validate_identifier(kind, value)


def test_entry_import_server_format_and_normalisation(farm):
    _, a, b, _ = farm
    with clock.at(T):
        for key, value in [("nlis", "N" * 16), ("source_pic", "SRC00001"), ("nvd", "NVD")]:
            data = dict(nlis="0TEST001ABC00001", source_pic="0FROM001", nvd="00000001")
            data[key] = value
            with pytest.raises(ValidationError):
                run(b, "register", {"rows": [data]})
        x = animal(b)
        assert x.label == "0TEST001ABC00001"
        with pytest.raises(ValidationError):
            animal(b)
        assert Animal.objects.count() == 1


def test_bulk_atomic_financial_delta_clear_and_permissions(farm):
    _, a, b, _ = farm
    with clock.at(T):
        x, y = animal(b, 1), animal(b, 2)
        data = dict(
            animals=[x.label, y.label],
            update_fields=["breed", "purchase_cost"],
            breed="Angus",
            purchase_cost="125",
        )
        with pytest.raises(PermissionDenied):
            run(b, "bulk_edit", data)
        result = run(a, "bulk_edit", data)
        assert result["count"] == 2
        assert Audit.objects.filter(action="bulk_edit").count() == 1
        for x in [x, y]:
            x.refresh_from_db()
            assert x.breed == "Angus" and x.sex == ""
            assert -sum(x.allocations.values_list("amount", flat=True)) == Decimal(125)
        bad = {**data, "animals": [x.label, "missing"], "breed": "No"}
        before = Event.objects.count()
        with pytest.raises(ValidationError):
            run(a, "bulk_edit", bad)
        assert Event.objects.count() == before
        run(a, "bulk_edit", {**data, "breed": "", "purchase_cost": ""})
        x.refresh_from_db()
        assert (
            x.breed == "" and x.allocations.filter(unknown=True, resolved_by__isnull=True).exists()
        )
        assert -sum(x.allocations.values_list("amount", flat=True)) == 0
    client, token = client_for(b)
    assert client.get("/action/bulk_edit/").status_code == 403
    assert client.post("/action/bulk_edit/", {"farm_context": token}).status_code == 403


def test_edit_saved_identifier_permissions_concurrency_and_legacy(farm):
    _, a, b, _ = farm
    with clock.at(T):
        x = animal(b)
        x.identifiers.filter(kind="rfid").update(current=False)
        run(b, "edit_animal", dict(animal=x.label, update_fields=["rfid"], rfid="000000000000099"))
        with pytest.raises(PermissionDenied):
            run(
                b,
                "edit_animal",
                dict(animal=x.label, update_fields=["rfid"], rfid="000000000000098"),
            )
        with pytest.raises(PermissionDenied):
            run(
                b,
                "edit_animal",
                dict(animal=x.label, update_fields=["source_pic"], source_pic="0FROM002"),
            )
        run(
            b,
            "edit_animal",
            dict(animal=x.label, update_fields=["vendor_name"], vendor_name="New source"),
        )
        visit = current_visit(x, b)
        assert acquisition(x, visit)["vendor_name"] == "New source"
        x.identifiers.filter(kind="nlis", current=True).update(value="A" * 16)
        x.refresh_from_db()
        form = EditForm(b, "edit_animal", x)
        assert form.fields["nlis"].disabled
        assert "pattern" not in form.fields["nlis"].widget.attrs
        run(
            b,
            "edit_animal",
            dict(animal=x.label, update_fields=["nlis", "breed"], nlis="A" * 16, breed="Hereford"),
        )
        with pytest.raises(ValidationError):
            run(a, "edit_animal", dict(animal=x.label, update_fields=["nlis"], nlis="B" * 16))


def test_date_age_reference_and_current_acquisition(farm):
    _, a, b, _ = farm
    with clock.at(T):
        x = animal(a, estimated_weeks=12)
        original_ref = x.age_reference
        run(a, "sale", dict(animal=x.label, destination_pic="0DEST001", nvd="00000002", price=200))
    with clock.at(T + 86400):
        run(
            a,
            "register",
            dict(entry_source="repurchase", nlis=x.label, source_pic="0FROM001", nvd="00000003"),
        )
        x.refresh_from_db()
        assert x.age_reference == original_ref
        run(
            b,
            "edit_animal",
            dict(
                animal=x.label,
                update_fields=["estimated_weeks", "purchase_cost"],
                estimated_weeks=12,
                purchase_cost=150,
            ),
        )
        x.refresh_from_db()
        assert x.age_reference == original_ref
        visits = list(x.presence.order_by("start"))
        assert (
            -sum(
                x.allocations.filter(presence=visits[0], category="purchase").values_list(
                    "amount", flat=True
                )
            )
            == 100
        )
        assert (
            -sum(
                x.allocations.filter(presence=visits[1], category="purchase").values_list(
                    "amount", flat=True
                )
            )
            == 150
        )
        with pytest.raises(ValidationError):
            run(b, "edit_animal", dict(animal=x.label, update_fields=["dob"], dob="2026-11-07"))
        with pytest.raises(ValidationError):
            run(
                a,
                "edit_animal",
                dict(animal=x.label, update_fields=["entry_date"], entry_date="2026-11-04"),
            )


def test_exit_preview_sale_exact_total_retries_and_stale(farm):
    _, a, b, _ = farm
    with clock.at(T):
        x, y = animal(b, 1), animal(b, 2)
        client, token = client_for(b)
        payload = dict(
            farm_context=token,
            mode="sale",
            task="preview",
            exit_date="2026-11-05",
            destination_pic="0DEST001",
            nvd="00000001",
            animals=[x.label, y.label],
            price="100.01",
            price_mode="group",
        )
        response = client.post("/workflow/exit/", payload)
        assert response.context["effects"]["count"] == 2
        assert Decimal(response.context["effects"]["revenue"]) == Decimal("100.01")
        signed = response.context["confirmation"]
        final = dict(farm_context=token, mode="sale", confirmed_payload=signed)
        assert client.post("/workflow/exit/", final).status_code == 302
        assert client.post("/workflow/exit/", final).status_code == 302
        assert Allocation.objects.filter(category="sale").count() == 2
        assert sum(
            Allocation.objects.filter(category="sale").values_list("amount", flat=True)
        ) == Decimal("100.01")
        assert not Presence.objects.filter(end__isnull=True).exists()


def test_transfer_and_death_lifecycle(farm):
    p, a, b, _ = farm
    destination = PIC.objects.create(property=p, number="0TEST002")
    with clock.at(T):
        x = animal(b)
        before = Allocation.objects.count()
        result = run(
            b,
            "transfer",
            dict(
                animal=x.label,
                destination_pic=destination.number,
                nvd="00000001",
                exit_date="2026-11-05",
            ),
        )
        x.refresh_from_db()
        assert x.status == "active" and x.pic == destination
        assert x.presence.filter(end__isnull=True).count() == 1
        assert Event.objects.filter(kind="transfer_arrival").count() == 1
        assert Allocation.objects.count() == before
        assert Event.objects.get(pk=result["event"]).details["transfer_links"]
        b.pic = destination
        b.save()
        run(b, "death", dict(animal=x.label, reason="Illness", exit_date="2026-11-05"))
        x.refresh_from_db()
        assert x.status == "dead"
        for user in [a, b]:
            user.pic = destination
            with pytest.raises(ValidationError):
                run(
                    user,
                    "register",
                    dict(
                        entry_source="repurchase",
                        nlis=x.label,
                        source_pic="0FROM001",
                        nvd="00000001",
                    ),
                )
        assert Allocation.objects.count() == before


def test_exit_dst_backdating_restrictions_and_context(farm):
    _, a, b, _ = farm
    with clock.at(T):
        x = animal(a, entry_date="2026-10-01")
        treatment = Event.objects.create(
            property=a.property, pic=a.pic, actor=a, kind="treat", effective_at=T - 86400
        )
        Restriction.objects.create(
            event=treatment,
            animal=x,
            starts_at=T - 86400 * 2,
            ends_at=T + 86400 * 7,
            days=8,
            timezone=a.property.timezone,
        )
        client, token = client_for(b)
        data = dict(
            farm_context=token,
            mode="sale",
            task="preview",
            exit_date="2026-11-04",
            destination_pic="0DEST001",
            nvd="00000001",
            animals=[x.label],
            price=100,
        )
        response = client.post("/workflow/exit/", data)
        assert response.context["warnings"] and response.context["confirmation"]
        signed = response.context["confirmation"]
        run(a, "observation", dict(animal=x.label, notes="changed"))
        response = client.post(
            "/workflow/exit/",
            dict(
                farm_context=token, mode="sale", confirmed_payload=signed, accept_restriction="on"
            ),
        )
        assert "changed since preview" in response.context["error"]
        assert response.context["form"]["exit_date"].value() == "2026-11-04"
        for day in ["2026-10-04", "2026-04-05"]:
            form = ExitForm(b, "death", dict(exit_date=day, animals=[x.label], reason="Illness"))
            assert form.is_valid(), form.errors
            assert calendar_day(b, form.cleaned_data["effective_at"]) == day


def calendar_day(user, at):
    from herd.cattle_services import calendar_date

    return calendar_date(user, at).isoformat()


def test_bulk_preview_membership_change_and_context_binding(farm):
    _, a, b, _ = farm
    with clock.at(T):
        mob = run(b, "mob", {"name": "Sale mob"})["mob"]
        _x, y = animal(b, 1, mob=mob), animal(b, 2)
        client, token = client_for(b)
        data = dict(
            farm_context=token,
            mode="sale",
            task="preview",
            exit_date="2026-11-05",
            mob=mob,
            destination_pic="0DEST001",
            nvd="00000001",
            price="100",
        )
        response = client.post("/workflow/exit/", data)
        assert response.context["effects"]["count"] == 1
        signed = response.context["confirmation"]
        run(
            a,
            "move",
            {
                "animals": [y.label],
                "destination": mob,
                "administration": True,
                "effective_at": clock.local_timestamp("2026-11-05T00:00:00", a.property.timezone),
            },
        )
        response = client.post(
            "/workflow/exit/", dict(farm_context=token, mode="sale", confirmed_payload=signed)
        )
        assert "changed since preview" in response.context["error"]
        assert Animal.objects.filter(status="active").count() == 2
        state = signing.loads(signed, salt="cattle:" + str(b.pk))
        with pytest.raises(ValidationError, match="selection changed"):
            run(b, "sale", state["data"])
        session = client.session
        session["farm_generation"] = "changed"
        session.save()
        new_token = client.get("/").wsgi_request.farm_context
        assert (
            client.post(
                "/workflow/exit/",
                dict(farm_context=new_token, mode="sale", confirmed_payload=signed),
            ).status_code
            == 403
        )


def test_restrictions_overlapping_reversed_superseded_and_acceptance(farm):
    _, a, b, _ = farm
    from herd.cattle import restriction_warnings

    with clock.at(T):
        x = animal(a, entry_date="2026-10-01")
        events = [
            Event.objects.create(
                property=a.property, pic=a.pic, actor=a, kind="treat", effective_at=T - 86400
            )
            for _ in range(4)
        ]
        for e, days in zip(events, [3, 10, 20, 30]):
            Restriction.objects.create(
                event=e,
                animal=x,
                starts_at=T - 86400 * 2,
                ends_at=T + 86400 * days,
                days=days + 2,
                timezone=a.property.timezone,
            )
        events[2].reversed_by = events[0]
        events[2].save()
        Restriction.objects.filter(event=events[3]).update(superseded_by=events[0])
        data = dict(
            animals=[x.label], effective_at=T, destination_pic="0DEST001", nvd="00000001", price=10
        )
        warning = restriction_warnings(b, data)
        assert warning[0]["safe_date"] == "2026-11-15"
        with pytest.raises(ValidationError, match="Explicit acceptance"):
            run(b, "sale", data)
        x.refresh_from_db()
        assert x.status == "active"
        run(b, "sale", {**data, "accept_restriction": True})


def test_transfer_failure_is_atomic_and_preserves_reference_and_mob(farm):
    p, a, b, _ = farm
    with clock.at(T):
        x, y = animal(a, 1, estimated_weeks=10), animal(a, 2)
        mob = run(b, "mob", {"name": "Source mob"})["mob"]
        run(b, "move", {"animals": [x.label, y.label], "destination": mob})
        reference = x.age_reference
        other = PIC.objects.create(property=p, number="0TEST002")
        with pytest.raises(ValidationError):
            run(
                b,
                "transfer",
                dict(animals=[x.label, "missing"], destination_pic=other.number, nvd="00000001"),
            )
        assert Presence.objects.filter(end__isnull=True).count() == 2
        assert Event.objects.filter(kind="transfer_arrival").count() == 0
        run(
            b,
            "transfer",
            dict(animals=[x.label, y.label], destination_pic=other.number, nvd="00000001"),
        )
        x.refresh_from_db()
        assert x.age_reference == reference
        assert not x.memberships.filter(end__isnull=True, superseded=False).exists()
        assert not Animal.objects.filter(pic=b.pic, status="active").exists()


def test_bulk_and_edit_reversal_restore_history_finances_identifiers(farm):
    _, a, b, _ = farm
    with clock.at(T):
        x = animal(b)
        result = run(
            a,
            "bulk_edit",
            dict(
                animals=[x.label],
                update_fields=["breed", "purchase_cost"],
                breed="New",
                purchase_cost=125,
            ),
        )
        run(a, "reverse", dict(original=result["event"], reason="Wrong batch"))
        x.refresh_from_db()
        assert x.breed == "" and -sum(x.allocations.values_list("amount", flat=True)) == 100
        old = x.label
        result = run(
            a,
            "edit_animal",
            dict(
                animal=x.label,
                update_fields=["nlis", "dob"],
                nlis="0TEST001ABC99999",
                dob="2026-01-01",
            ),
        )
        run(a, "reverse", dict(original=result["event"], reason="Wrong tag"))
        x.refresh_from_db()
        assert x.label == old and x.dob is None
        assert Identifier.objects.filter(value="0TEST001ABC99999", current=False).exists()


def test_edit_preview_identifier_race_and_role_revocation(farm):
    _, a, b, _ = farm
    with clock.at(T):
        x = animal(b)
        x.identifiers.filter(kind="rfid").update(current=False)
        client, token = client_for(b)
        form = EditForm(b, "edit_animal", x)
        data = {k: v for k, v in form.initial.items() if v is not None}
        data.update(
            farm_context=token, task="preview", animal_reference=x.label, rfid="000000000000099"
        )
        response = client.post("/action/edit_animal/", data)
        signed = response.context["confirmation"]
        run(a, "edit_animal", dict(animal=x.label, update_fields=["rfid"], rfid="000000000000098"))
        response = client.post(
            "/action/edit_animal/",
            dict(farm_context=token, animal_reference=x.label, confirmed_payload=signed),
        )
        assert "changed since preview" in response.context["error"]
        assert x.identifiers.get(kind="rfid", current=True).value == "000000000000098"
        # Administrator access must be checked again from the saved account, not stale actor state.
        a.__class__.objects.filter(pk=a.pk).update(role="standard")
        with pytest.raises(PermissionDenied):
            run(a, "bulk_edit", dict(animals=[x.label], update_fields=["breed"], breed="No"))


def test_home_text_and_edit_field_order_and_no_time(farm):
    _, a, b, _ = farm
    from herd.cattle import EDIT_ORDER

    with clock.at(T):
        x = animal(b)
        client, token = client_for(b)
        home = client.get("/").content.decode()
        assert "Age boundaries are" not in home and "Current mobs include" not in home
        response = client.get("/action/edit_animal/", {"animal": x.label})
        assert list(response.context["form"].fields) == EDIT_ORDER
        html = response.content.decode()
        assert 'type="date"' in html and "time_offset" not in html and "datetime-local" not in html
        assert "Review and update the animal’s details below" in html
        assert response.context["form"].fields["nlis"].disabled
        assert response.context["form"].fields["source_pic"].disabled


def test_transfer_purchase_correction_follows_original_acquisition(farm):
    p, a, b, _ = farm
    with clock.at(T):
        x = animal(b)
        original_visit = current_visit(x, b)
        dest = PIC.objects.create(property=p, number="0TEST002")
        run(b, "transfer", dict(animal=x.label, destination_pic=dest.number, nvd="00000001"))
        b.pic = dest
        b.save()
        run(
            b,
            "edit_animal",
            dict(animal=x.label, update_fields=["purchase_cost"], purchase_cost=150),
        )
        assert (
            -sum(
                x.allocations.filter(presence=original_visit, category="purchase").values_list(
                    "amount", flat=True
                )
            )
            == 150
        )
        assert (
            x.allocations.filter(
                presence=x.presence.get(end__isnull=True), category="purchase"
            ).count()
            == 0
        )
        x.refresh_from_db()
        form = EditForm(b, "edit_animal", x)
        assert form.initial["purchase_cost"] == 150
        form = EditForm(
            b,
            "edit_animal",
            x,
            data={k: (v if v is not None else "") for k, v in form.initial.items()},
        )
        assert form.is_valid(), form.errors
        preview = s.preview(b, "edit_animal", s.clean(form.cleaned_data))
        assert preview["effects"]["count"] == 1


def test_birth_on_legacy_pic_and_reversal_of_unknown_price_correction(farm):
    _, a, b, _ = farm
    from herd import reports

    with clock.at(T):
        b.pic.number = "TEST0001"
        b.pic.save()
        run(b, "register", dict(entry_source="birth", nlis="0TEST001ABC00001"))
        x = Animal.objects.get()
        result = run(
            a,
            "bulk_edit",
            dict(animals=[x.label], update_fields=["purchase_cost"], purchase_cost=""),
        )
        assert not reports.build(b, {})["rows"][0]["financial_complete"]
        run(a, "reverse", dict(original=result["event"], reason="Known zero cost"))
        assert reports.build(b, {})["rows"][0]["financial_complete"]
