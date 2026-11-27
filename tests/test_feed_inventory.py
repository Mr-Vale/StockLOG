"""Inventory enquiry, context-bound selections and display-only rounding."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from herd import clock
from herd.feed_inventory import usage
from herd.models import PIC, Allocation, Audit, Event, Inventory, Participant, Property, StockPosting
from herd.templatetags.display import compact
from tests.test_business_rules import T, setup_mob, stock
from tests.test_feed_workflows import add, client_for, issue
from tests.test_foundations import run

pytestmark = pytest.mark.django_db


def selected(client, context, ids, action="stocktake"):
    return client.post("/inventory/feed/" + action + "/", {
        "farm_context": context, "task": "select", "selected_ids": [str(i) for i in ids],
    })


def preview(client, context, selection_page, rows, action="stocktake", path=None):
    data = {"farm_context": context, "selection_token": selection_page.context["selection_token"], "task": "preview"}
    for identity, values in rows.items():
        data.update({str(identity) + "_" + key: value for key, value in values.items()})
    return client.post(path or "/inventory/feed/" + action + "/", data)


def save(client, context, page, action="stocktake", path=None):
    return client.post(path or "/inventory/feed/" + action + "/", {
        "farm_context": context, "confirmed_payload": page.context["confirmation"],
    })


def test_columns_sorting_and_display_preserve_precision(farm):
    _, _, b, _ = farm
    with clock.at(T):
        a = Inventory.objects.get(pk=add(b, name="Zulu", packages=3, package_size=10, package_price=2,
            home_grown=False, batch="Z", date_kind="DOM", date_value="2020-01-01")["item"])
        z = Inventory.objects.get(pk=add(b, name="Alpha", packages=10, package_size=2, package_price=15,
            feed_type="pellet", home_grown=False, batch="A", date_kind="expiry", date_value="2021-01-01")["item"])
        # Real stocktake, not a mutation that bypasses the stock ledger.
        run(b, "stocktake", {"item": a.pk, "actual": "12.345678901234", "reason": "Count"})
        a.refresh_from_db()
        client, _ = client_for(b)
        response = client.get("/inventory/feed/")
        assert [h["label"] for h in response.context["headings"]] == [
            "Product", "Type", "Units Remaining", "Remaining Stock", "Quantity/Item", "Price/Item",
            "Cost/Stock Unit", "Feed Unit", "Stock Value", "Batch/Date"]
        assert b">Actions<" not in response.content
        assert b"12.35 kg" in response.content
        assert compact(Decimal("12.500000")) == "12.5"
        assert compact(Decimal("-0.001")) == "0"
        for key in ["name", "type", "units", "balance", "size", "price", "cost", "feed_unit", "value", "date"]:
            asc = client.get("/inventory/feed/", {"sort": key}).context["rows"]
            desc = client.get("/inventory/feed/", {"sort": key, "direction": "desc"}).context["rows"]
            assert len(asc) == 2 and len(desc) == 2
            values = [r[key] for r in asc]
            assert values == sorted(values, key=lambda v: v.casefold() if isinstance(v, str) else v)
            if values[0] != values[1]:
                assert [r["identity"] for r in desc] == [r["identity"] for r in asc][::-1]
        assert client.get("/inventory/feed/?sort=date").context["rows"][0]["identity"] == str(a.pk)
        a.refresh_from_db()
        assert a.balance == Decimal("12.345678901234")
        assert a.unit_cost == Decimal(".2")
        assert z.package_price == 15


def test_exact_selected_edits_previews_stale_retry_and_removal(farm):
    _, _, b, _ = farm
    with clock.at(T):
        ids = [add(b, name=name)["item"] for name in ["One", "Two", "Untouched"]]
        client, context = client_for(b)
        assert selected(client, context, []).status_code == 400
        assert selected(client, context, [], "retire").status_code == 400
        assert selected(client, context, [ids[0], ids[0]]).status_code == 400
        page = selected(client, context, ids[:2])
        assert [i.pk for i in page.context["selected_items"]] == ids[:2]
        rows = {i: dict(actual="12.345678901234", retired="", reason="Counted") for i in ids}
        reviewed = preview(client, context, page, rows)
        assert reviewed.context["confirmation"]
        assert b"Current value" in reviewed.content and b"Proposed value" in reviewed.content
        assert "12.35 kg" in reviewed.content.decode()
        assert not Audit.objects.filter(action="feed_adjust").exists()
        assert save(client, context, reviewed).status_code == 302
        assert save(client, context, reviewed).status_code == 302
        assert Inventory.objects.get(pk=ids[0]).balance == Decimal("12.345678901234")
        assert Inventory.objects.get(pk=ids[2]).balance == 35000
        assert Audit.objects.filter(action="feed_adjust").count() == 1
        # A fresh product change invalidates an old reviewed save, retaining entered values.
        stale = preview(client, context, page, rows)
        run(b, "stocktake", dict(item=ids[0], actual=10, reason="New count"))
        failed = save(client, context, stale)
        assert b"changed since preview" in failed.content
        assert failed.context["form"][str(ids[0]) + "_actual"].value() == "12.345678901234"
        removal = selected(client, context, ids[:2], "retire")
        removing = {i: dict(actual=0, retired="on", reason="Removed") for i in ids[:2]}
        reviewed = preview(client, context, removal, removing, "retire")
        assert b"Quantity removed" in reviewed.content and b"Resulting stock balance" in reviewed.content
        before = list(Allocation.objects.values_list("pk", "amount"))
        assert save(client, context, reviewed, "retire").status_code == 302
        assert save(client, context, reviewed, "retire").status_code == 302
        assert Inventory.objects.filter(pk__in=ids[:2], retired=True, balance=0).count() == 2
        assert not Inventory.objects.get(pk=ids[2]).retired
        assert list(Allocation.objects.values_list("pk", "amount")) == before
        event = Event.objects.filter(kind="feed_adjust").last()
        run(b, "reverse", {"original": str(event.pk), "reason": "Restore removal"})
        assert Inventory.objects.get(pk=ids[0]).balance == 10
        assert not Inventory.objects.get(pk=ids[0]).retired


def test_product_details_edit_permission_scope_and_unknown_history(farm):
    p, admin, b, _ = farm
    with clock.at(T):
        mob = setup_mob(b, 2)
        item = Inventory.objects.get(pk=add(b)["item"])
        client, context = client_for(b)
        path = "/inventory/feed/product/" + str(item.pk) + "/"
        page = client.get(path)
        assert page.context["usage"]["cattle"] == 0
        assert page.context["usage"]["held_days"] == 0
        assert b"Not recorded" in page.content
        assert b"retire this product, then add it again with the new price" in page.content
        first = run(b, "feed", issue(b, mob, item))
        item.refresh_from_db()
        run(b, "feed", issue(b, mob, item, quantity=175, mode="measure"))
        other = run(b, "mob", {"name": "Later mob"})["mob"]
        animals = list(Participant.objects.filter(event_id=first["event"]).select_related("animal"))
        run(admin, "move", {"animals": [a.animal.label for a in animals], "destination": other})
        stats = client.get(path).context["usage"]
        assert stats["cattle"] == 2 and stats["total"] == 525 and stats["latest"] == T
        # Other PIC statistics stay scoped, while the stock details remain shared.
        second = PIC.objects.create(property=p, number="0TEST002")
        b.pic = second
        assert usage(b, item)["cattle"] == 0
        b.pic = admin.pic
        reviewed = preview(client, context, page, {item.pk: dict(actual="34000.123456789012", retired="", reason="Count")}, path=path)
        assert reviewed.context["confirmation"]
        assert save(client, context, reviewed, path=path).url == path
        assert Inventory.objects.get(pk=item.pk).balance == Decimal("34000.123456789012")
        assert Audit.objects.filter(action="feed_adjust").count() == 1
        # Historical feed with no cohort or stock posting is unknown, not reconstructed from today's mob.
        Event.objects.create(property=p, pic=admin.pic, actor=b, kind="feed", effective_at=T,
            details={"item": str(item.pk)}, effective_order=999)
        stats = usage(b, item)
        assert stats["cattle"] is None and stats["total"] is None
        foreign = Property.objects.create(name="Other", address="Other", owner="Other")
        private = Inventory.objects.create(property=foreign, kind="feed", name="Private", signature="private",
            unit_cost=1, balance=1, base_per_package=1)
        assert client.get("/inventory/feed/product/" + str(private.pk) + "/").status_code == 404
        assert selected(client, context, [private.pk]).status_code == 400
        chemical = stock(b, kind="chemical")
        assert selected(client, context, [chemical]).status_code == 400
        assert client.get("/inventory/feed/", {"chosen": str(private.pk)}).status_code == 400
        b.properties.clear()
        assert client.get(path).status_code == 302


def test_removal_rules_validation_and_unchanged_historical_costs(farm):
    _, _, b, _ = farm
    with clock.at(T):
        mob = setup_mob(b, 1)
        item = Inventory.objects.get(pk=add(b)["item"])
        run(b, "feed", issue(b, mob, item))
        allocations = list(Allocation.objects.values_list("pk", "amount"))
        client, context = client_for(b)
        page = selected(client, context, [item.pk], "retire")
        invalid = preview(client, context, page, {item.pk: dict(actual=999999, retired="on", reason="")}, "retire")
        assert invalid.context["form"].errors and not invalid.context.get("confirmation")
        assert Inventory.objects.get(pk=item.pk).balance == 34650
        good = preview(client, context, page, {item.pk: dict(actual=34600, retired="on", reason="Removed stock")}, "retire")
        assert save(client, context, good, "retire").status_code == 302
        assert list(Allocation.objects.values_list("pk", "amount")) == allocations
        assert selected(client, context, [item.pk], "retire").status_code == 400
        assert client.get("/inventory/feed/product/" + str(item.pk) + "/").status_code == 200


def test_currency_ui_labels_and_reports_use_symbols(farm):
    from herd import reports
    from herd.feed import FeedEntryForm
    from herd.forms import ActionForm
    from herd.templatetags.display import financial_tree

    _, _, b, _ = farm
    with clock.at(T):
        client, _ = client_for(b)
        add(b)
        for path in ["/inventory/feed/", "/inventory/chemical/", "/inventory/feed/add/", "/reports/", "/action/receipt/"]:
            content = client.get(path).content.decode()
            assert "AUD" not in content and "Australian dollars" not in content
        assert "$" in FeedEntryForm(b).fields["package_price"].label
        assert "$" in ActionForm(b, "receipt").fields["package_price"].label
        assert "AUD" not in reports.build(b, {"dataset": "inventory"})["note"]
        assert financial_tree({"cost": Decimal("12.345")}) == {"cost": "$12.345"}
        stock(b, kind="chemical", stock_unit="L", package_size=20, package_price=250, dose_unit="mL")
        assert "$0.012500000000 / mL" in client.get("/inventory/chemical/").content.decode()


def test_selection_tokens_bind_context_actor_and_action(farm):
    _, admin, b, c = farm
    with clock.at(T):
        identity = add(b)["item"]
        client, context = client_for(b)
        page = selected(client, context, [identity])
        token = page.context["selection_token"]
        forged = {"farm_context": context, "selection_token": token, "task": "preview",
            str(identity) + "_actual": "1", str(identity) + "_reason": "Counted"}
        assert client.post("/inventory/feed/retire/", forged).status_code == 403
        other, other_context = client_for(c)
        assert other.post("/inventory/feed/stocktake/", {**forged, "farm_context": other_context}).status_code == 400
        session = client.session
        session["farm_generation"] = "changed"
        session.save()
        new_context = client.get("/").wsgi_request.farm_context
        assert client.post("/inventory/feed/stocktake/", {**forged, "farm_context": new_context}).status_code == 403
        assert Inventory.objects.get(pk=identity).balance == 35000
