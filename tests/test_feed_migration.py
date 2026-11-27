"""Additive feed-unit migration preserves legacy identity, stock and ledger links."""

from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_legacy_inventory_and_history_survive_feed_unit_migration():
    executor = MigrationExecutor(connection)
    old = [("herd", "0001_initial")]
    latest = [("herd", "0002_inventory_feed_unit")]
    executor.migrate(old)
    try:
        apps = executor.loader.project_state(old).apps
        prop = apps.get_model("herd", "Property").objects.create(name="Migration farm", owner="Owner", address="Road")
        pic = apps.get_model("herd", "PIC").objects.create(property=prop, number="0TEST001")
        actor = apps.get_model("herd", "Account").objects.create(username="migration-user", property=prop, pic=pic)
        event = apps.get_model("herd", "Event").objects.create(property=prop, pic=pic, actor=actor,
            kind="receipt", effective_at=1600000000, details={"supplier_name": "Legacy source"})
        item = apps.get_model("herd", "Inventory").objects.create(property=prop, kind="feed", name="Legacy hay",
            feed_type="hay", package_size=350, package_price=70, stock_unit="kg", base_unit="kg",
            base_per_package=350, unit_cost=Decimal(".2"), balance=700, signature="migration-legacy")
        chemical = apps.get_model("herd", "Inventory").objects.create(property=prop, kind="chemical",
            name="Legacy treatment", package_size=100, package_price=50, stock_unit="mL", base_unit="mL",
            base_per_package=100, unit_cost=Decimal(".5"), balance=50, signature="migration-chemical")
        posting = apps.get_model("herd", "StockPosting").objects.create(item=item, event=event, quantity=700, value=140)
        animal = apps.get_model("herd", "Animal").objects.create(property=prop, pic=pic)
        presence = apps.get_model("herd", "Presence").objects.create(animal=animal, pic=pic, start=1600000000, arrival=event)
        allocation = apps.get_model("herd", "Allocation").objects.create(event=event, animal=animal,
            category="feed", amount=-35, presence=presence)
        audit = apps.get_model("herd", "Audit").objects.create(property=prop, actor=actor, event=event,
            action="receipt", details={"legacy": True})
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        from herd.models import Allocation, Audit, Event, Inventory, StockPosting
        saved = Inventory.objects.get(pk=item.pk)
        assert saved.feed_unit == "" and saved.balance == 700 and saved.unit_cost == Decimal(".2")
        assert saved.signature == "migration-legacy" and saved.base_per_package == 350
        assert Inventory.objects.get(pk=chemical.pk).balance == 50
        assert StockPosting.objects.get(pk=posting.pk).item_id == item.pk
        assert Allocation.objects.get(pk=allocation.pk).presence_id == presence.pk
        assert Allocation.objects.get(pk=allocation.pk).amount == -35
        assert Event.objects.get(pk=event.pk).details["supplier_name"] == "Legacy source"
        assert Audit.objects.get(pk=audit.pk).details == {"legacy": True}
    finally:
        MigrationExecutor(connection).migrate(latest)
