"""Feed receipt/feeding regressions on real property-scoped transactions."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import Client

from herd import clock, services
from herd.feed import FeedEntryForm, FeedingForm, today, unit_for
from herd.models import PIC, Allocation, Audit, Event, Inventory, Property, StockPosting
from tests.test_business_rules import T, setup_mob, stock
from tests.test_foundations import run

pytestmark = pytest.mark.django_db


def client_for(user):
    client = Client()
    client.force_login(user)
    token = client.get("/").wsgi_request.farm_context
    return client, token


def receipt_data(user, **changes):
    return {
        "stored_date": today(user).isoformat(), "name": "New hay", "feed_type": "hay",
        "packages": "100", "package_size": "350", "stock_unit": "kg",
        "feed_unit": "kg", "package_price": "70.00", "home_grown": True, **changes,
    }


def add(user, **changes):
    form = FeedEntryForm(user, receipt_data(user, **changes))
    assert form.is_valid(), form.errors
    return run(user, "receipt", form.payload())


def issue(user, mob, item, **changes):
    data = {
        "feed_date": today(user).isoformat(), "mob": str(mob), "feed_type": item.feed_type or "__other__",
        "item": str(item.pk), "quantity": "1", "mode": "unit", **changes,
    }
    form = FeedingForm(user, data)
    assert form.is_valid(), form.errors
    return form.payload()


def test_separate_pages_same_property_pics_and_chemical_integrations(farm):
    p, admin, b, _ = farm
    with clock.at(T):
        hay = stock(b)
        chemical = stock(b, kind="chemical")
        client, token = client_for(b)
        feed = client.get("/inventory/feed/")
        chemicals = client.get("/inventory/chemical/")
        assert feed.context["title"] == p.name + " Feed Inventory"
        assert chemicals.context["title"] == p.name + " Chemical Inventory"
        assert [i.pk for i in feed.context["items"]] == [hay]
        assert [i.pk for i in chemicals.context["items"]] == [chemical]
        assert "Stocktake / correction" in chemicals.content.decode()
        assert "Cattle Treatment" in chemicals.content.decode()
        second = PIC.objects.create(property=p, number="0TEST002")
        b.pic = second
        b.save()
        other_client, _ = client_for(b)
        assert [i.pk for i in other_client.get("/inventory/feed/").context["items"]] == [hay]
        assert [i.pk for i in other_client.get("/inventory/chemical/").context["items"]] == [chemical]
        own = services.execute(b, uuid.uuid4().hex, "mob", {"name": "Second PIC mob"})["mob"]
        first_mob = services.execute(admin, uuid.uuid4().hex, "mob", {"name": "First PIC mob"})["mob"]
        choices = dict(FeedingForm(b).fields["mob"].choices)
        assert str(first_mob) not in choices  # An empty mob is not eligible either.
        assert str(own) not in choices
        foreign_property = Property.objects.create(name="Other", address="Other", owner="Other")
        foreign_pic = PIC.objects.create(property=foreign_property, number="0TEST003")
        outsider = Inventory.objects.create(property=foreign_property, kind="feed", name="Private",
            unit_cost=1, balance=100, base_per_package=1, signature="private")
        assert outsider.pk not in [i.pk for i in client.get("/inventory/feed/").context["items"]]
        with pytest.raises(ValidationError):
            run(b, "stocktake", {"item": outsider.pk, "actual": 0, "reason": "No access"})
        b.properties.clear()
        assert other_client.get("/inventory/feed/").status_code == 302
        assert client.post("/inventory/feed/add/", {"farm_context": token}).status_code == 302
        assert foreign_pic.property_id == foreign_property.pk


def test_add_rounding_defaults_preview_save_duplicate_and_metadata(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        client, token = client_for(b)
        page = client.get("/inventory/feed/add/")
        assert page.context["form"].initial["stored_date"] == today(b)
        assert page.context["form"].initial["home_grown"] is True
        data = receipt_data(b, packages="12.9", package_size="350.9")
        preview = client.post("/inventory/feed/add/", {**data, "farm_context": token, "task": "preview"})
        assert preview.context["confirmation"]
        assert dict(preview.context["details"])["Number of Units (No. Bales/Bags)"] == Decimal(12)
        assert dict(preview.context["details"])["Quantity Per Unit (Bag or Bale Kg)"] == Decimal(350)
        assert not Inventory.objects.exists() and not StockPosting.objects.exists()
        response = client.post("/inventory/feed/add/", {"farm_context": token,
            "confirmed_payload": preview.context["confirmation"]})
        assert response.status_code == 302 and response.url == "/inventory/feed/"
        item = Inventory.objects.get()
        assert item.balance == 4200 and item.base_per_package == 350 and item.feed_unit == "kg"
        assert Audit.objects.filter(action="receipt").count() == 1
        assert client.post("/inventory/feed/add/", {"farm_context": token,
            "confirmed_payload": preview.context["confirmation"]}).status_code == 302
        assert StockPosting.objects.count() == 1
        duplicate = FeedEntryForm(b, receipt_data(b, name=" new HAY "))
        assert not duplicate.is_valid() and "name" in duplicate.errors
        off = receipt_data(b, name="Introduced", home_grown=False, supplier_name="Supplier",
            origin_text="Test road", batch="AB123", declaration_reference="CVD42",
            date_kind="DOM", date_value="2020-01-01", product_tested="yes", residue_test_details="Test result")
        form = FeedEntryForm(b, off)
        assert form.is_valid(), form.errors
        result = run(b, "receipt", form.payload())
        record = Inventory.objects.get(pk=result["item"])
        event = Event.objects.get(pk=result["event"])
        assert record.date_kind == "DOM" and record.date_value.isoformat() == "2020-01-01"
        assert event.details["supplier_name"] == "Supplier" and event.details["origin_text"] == "Test road"
        assert event.details["declaration_reference"] == "CVD42"
        assert event.details["residue_test_details"] == "Test result"
        for key in ["batch", "declaration_reference"]:
            invalid = FeedEntryForm(b, {**off, "name": "Invalid", key: "bad!"})
            assert not invalid.is_valid() and key in invalid.errors
        form = FeedEntryForm(b, {**off, "name": "Not tested", "product_tested": "no"})
        assert form.is_valid(), form.errors
        assert form.payload()["residue_test_details"] == ""


@pytest.mark.parametrize("changes,field", [
    ({"package_price": "10000000000"}, "package_price"),
    ({"package_price": "1.234"}, "package_price"),
    ({"packages": ".9"}, "packages"), ({"package_size": "-1.9"}, "package_size"),
    ({"stock_unit": "kg", "feed_unit": "L"}, "feed_unit"),
])
def test_feed_entry_limits(farm, changes, field):
    _, _, b, _ = farm
    with clock.at(T):
        form = FeedEntryForm(b, receipt_data(b, **changes))
        assert not form.is_valid() and field in form.errors


def test_dates_permissions_and_legacy_default_units(farm):
    _, _, b, _ = farm
    with clock.at(T):
        past = (today(b) - timedelta(days=1)).isoformat()
        form = FeedEntryForm(b, receipt_data(b, stored_date=past))
        assert form.is_valid(), form.errors  # Existing inventory rules permit earlier receipts.
        future = (today(b) + timedelta(days=1)).isoformat()
        form = FeedEntryForm(b, receipt_data(b, stored_date=future))
        assert not form.is_valid() and "stored_date" in form.errors
        legacy = Inventory.objects.get(pk=stock(b))
        assert legacy.feed_unit == "" and unit_for(legacy) == "kg"
        mob = setup_mob(b, 2)
        payload = issue(b, mob, legacy)
        assert payload["feed_date"] == today(b).isoformat()
        invalid = FeedingForm(b, {**payload, "feed_date": future})
        assert not invalid.is_valid() and "feed_date" in invalid.errors


def test_units_350kg_bale_and_half_bale_costs_and_atomic_previews(farm):
    _, _, b, _ = farm
    with clock.at(T):
        mob = setup_mob(b, 2)
        item = Inventory.objects.get(pk=add(b)["item"])
        original = item.balance
        unit_data = issue(b, mob, item)
        preview = services.preview(b, "feed", unit_data)
        assert Decimal(preview["effects"]["consumed"]) == 350
        assert Decimal(preview["effects"]["cost"]) == 70
        item.refresh_from_db()
        assert item.balance == original and not Allocation.objects.filter(category="feed").exists()
        first = services.execute(b, "unit-feeding", "feed", unit_data, preview["version"])
        item.refresh_from_db()
        assert item.balance == 34650
        measured = issue(b, mob, item, quantity="175", mode="measure")
        second = run(b, "feed", measured)
        item.refresh_from_db()
        assert item.balance == 34475
        assert sum(Allocation.objects.filter(event_id=first["event"]).values_list("amount", flat=True)) == -70
        assert sum(Allocation.objects.filter(event_id=second["event"]).values_list("amount", flat=True)) == -35
        assert Allocation.objects.filter(event_id=second["event"], amount=-Decimal("17.5")).count() == 2
        form = FeedingForm(b, {**measured, "mode": "unit", "quantity": ".5"})
        assert not form.is_valid() and "quantity" in form.errors


@pytest.mark.parametrize("item_unit,feed_unit,size,quantity,consumed", [
    ("g", "kg", "1000", ".5", ".5"), ("kg", "g", "1", "500", ".5"),
    ("L", "mL", "2", "500", "500"), ("mL", "L", "1000", ".5", "500"),
])
def test_measurement_conversion(farm, item_unit, feed_unit, size, quantity, consumed):
    _, _, b, _ = farm
    with clock.at(T):
        mob = setup_mob(b, 1)
        item = Inventory.objects.get(pk=add(b, stock_unit=item_unit, feed_unit=feed_unit,
                                         package_size=size, packages=10)["item"])
        result = run(b, "feed", issue(b, mob, item, quantity=quantity, mode="measure"))
        assert Decimal(result["consumed"]) == Decimal(consumed)


def test_no_feed_and_filters_unit_only_and_negative_crossing_retry(farm):
    _, _, b, _ = farm
    with clock.at(T):
        client, token = client_for(b)
        assert client.get("/workflow/feeding/").context["no_feed"]
        mob = setup_mob(b, 1)
        item = Inventory.objects.get(pk=add(b, packages=1)["item"])
        grain = Inventory.objects.get(pk=add(b, name="Grain", feed_type="grain_mix", feed_unit="unit")["item"])
        form = FeedingForm(b, issue(b, mob, grain))
        assert form.fields["mode"].choices == [("unit", "Unit")]
        payload = issue(b, mob, item, quantity="351", mode="measure")
        preview = client.post("/workflow/feeding/", {**payload, "farm_context": token, "task": "preview"})
        assert preview.context["negative_balance"]
        assert "will take stock below zero" in preview.content.decode()
        final = {"farm_context": token, "confirmed_payload": preview.context["confirmation"]}
        assert client.post("/workflow/feeding/", final).status_code == 302
        assert client.post("/workflow/feeding/", final).status_code == 302
        item.refresh_from_db()
        assert item.balance == -1
        assert StockPosting.objects.filter(item=item, event__kind="feed").count() == 1
        assert item.pk not in [i.pk for i in FeedingForm(b).products]
        with pytest.raises(ValidationError):
            run(b, "feed", payload)
        run(b, "stocktake", {"item": grain.pk, "actual": 0, "reason": "Counted zero"})
        assert client.get("/workflow/feeding/").context["no_feed"]
        assert "-1" in client.get("/inventory/feed/").content.decode()
        run(b, "stocktake", {"item": item.pk, "actual": 10, "reason": "Replenished"})
        assert not client.get("/workflow/feeding/").context["no_feed"]


def test_stale_preview_context_and_locked_snapshot_checks(farm):
    p, admin, b, _ = farm
    with clock.at(T):
        mob = setup_mob(b, 1)
        item = Inventory.objects.get(pk=add(b)["item"])
        client, token = client_for(b)
        payload = issue(b, mob, item)
        response = client.post("/workflow/feeding/", {**payload, "farm_context": token, "task": "preview"})
        state = signing.loads(response.context["confirmation"], salt="feed-workflow:" + str(b.pk))
        # A direct balance change without the property version is also caught by the reviewed snapshot.
        Inventory.objects.filter(pk=item.pk).update(balance=item.balance-1)
        with pytest.raises(ValidationError, match="changed"):
            services.execute(b, "stale", "feed", state["data"], state["version"])
        assert not Allocation.objects.filter(category="feed").exists()
        Inventory.objects.filter(pk=item.pk).update(balance=item.balance)
        # A real audited event invalidates the property preview version, even at the same balance.
        run(b, "stocktake", {"item": item.pk, "actual": 35000, "reason": "Verified"})
        failed = client.post("/workflow/feeding/", {"farm_context": token, "confirmed_payload": response.context["confirmation"]})
        assert "changed since preview" in failed.context["error"]
        session = client.session
        session["farm_generation"] = "new"
        session.save()
        new_token = client.get("/").wsgi_request.farm_context
        assert client.post("/workflow/feeding/", {"farm_context": new_token,
            "confirmed_payload": response.context["confirmation"]}).status_code == 403
        assert p.pk == admin.property_id


def test_bulk_stock_correction_removal_reversal_and_existing_treatment(farm):
    _, _, b, _ = farm
    with clock.at(T):
        mob = setup_mob(b, 1)
        x = Inventory.objects.get(pk=add(b)["item"])
        y = Inventory.objects.get(pk=add(b, name="Second")["item"])
        event = run(b, "feed_adjust", {"action": "stocktake", "reason": "Count",
            "rows": [{"item": x.pk, "actual": -5}, {"item": y.pk, "actual": 10}]})
        x.refresh_from_db()
        y.refresh_from_db()
        assert x.balance == -5 and y.balance == 10
        assert not Allocation.objects.filter(event_id=event["event"]).exists()
        run(b, "reverse", {"original": event["event"], "reason": "Wrong count"})
        x.refresh_from_db()
        assert x.balance == 35000
        removal = run(b, "feed_adjust", {"action": "retire", "reason": "Remove",
                                        "rows": [{"item": x.pk}, {"item": y.pk}]})
        assert Inventory.objects.filter(retired=True).count() == 2
        run(b, "reverse", {"original": removal["event"], "reason": "Restore"})
        assert not Inventory.objects.filter(retired=True).exists()
        chemical = stock(b, kind="chemical")
        before = Inventory.objects.get(pk=chemical).balance
        run(b, "treat", {"mob": mob, "item": chemical, "dose": 1})
        assert Inventory.objects.get(pk=chemical).balance == before-1
        assert Inventory.objects.filter(pk=x.pk).exists()
