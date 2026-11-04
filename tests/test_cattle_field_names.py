"""Stored cattle names, legacy input compatibility, and age-column preservation."""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from herd import clock, reports, services
from herd.imports import COLUMNS, mapped_preview
from herd.models import Animal, Event

T = 1793782800


@pytest.mark.django_db
def test_canonical_cattle_fields_and_legacy_retry(farm):
    _, admin, _, _ = farm
    old = dict(
        nlis="A" * 16,
        source_pic="SRC00001",
        nvd="N1",
        effective_at=T,
        estimated_weeks=26,
        vendor_name="Source farm",
        vendor_address="Source address",
    )
    new = dict(
        nlis="A" * 16,
        source_pic="SRC00001",
        nvd="N1",
        farm_entry_date=T,
        age_weeks=26,
        source_name="Source farm",
        source_address="Source address",
    )
    key = uuid.uuid4().hex
    with clock.at(T):
        result = services.execute(admin, key, "register", old)
        assert services.execute(admin, key, "register", new) == result
        event = Event.objects.get(pk=result["event"])
        assert all(event.details[k] == v for k, v in new.items())
        assert not set(old).difference(new).intersection(event.details)
        assert Animal.objects.get().age_weeks == 26
        assert Animal.objects.get().presence.get().start == T
        with pytest.raises(ValidationError, match="Conflicting"):
            services.execute(admin, "conflict", "register", {**new, "estimated_weeks": 99})
        # Old audit payloads remain readable without rewriting their history.
        event.details = old
        event.save(update_fields=["details"])
        report = reports.build(
            admin, {"dataset": "lpa5A", "columns": ["vendor_name", "vendor_address"]}
        )
        assert report["rows"][0]["source_name"] == "Source farm"
        assert report["rows"][0]["source_address"] == "Source address"


@pytest.mark.django_db
def test_import_uses_new_names_and_keeps_unix_dates(farm):
    _, admin, _, _ = farm
    fields = [
        "nlis",
        "farm_entry_date",
        "source_pic",
        "nvd",
        "age_weeks",
        "source_name",
        "source_address",
    ]
    assert set(fields) <= set(COLUMNS)
    with clock.at(T):
        rows, errors = mapped_preview(
            admin,
            fields,
            [["B" * 16, str(T), "SRC00001", "N1", "12", "Farm", "Road"]],
            {key: str(index) for index, key in enumerate(fields)},
            {},
        )
        assert errors == [[]]
        result = services.execute(admin, "import-new", "register", {"rows": [rows[0]["data"]]})
    event = Event.objects.get(pk=result["event"])
    assert event.details["rows"][0]["farm_entry_date"] == T
    assert Animal.objects.get().age_weeks == 12


@pytest.mark.django_db(transaction=True)
def test_age_column_rename_preserves_values():
    executor = MigrationExecutor(connection)
    old_target = [("herd", "0001_initial")]
    new_target = [("herd", "0002_rename_animal_age_weeks")]
    executor.migrate(old_target)
    try:
        old_apps = executor.loader.project_state(old_target).apps
        prop = old_apps.get_model("herd", "Property").objects.create(name="Age migration")
        pic = old_apps.get_model("herd", "PIC").objects.create(property=prop, number="TEST0099")
        animal = old_apps.get_model("herd", "Animal").objects.create(
            property=prop, pic=pic, estimated_weeks=37
        )
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        new_apps = executor.loader.project_state(new_target).apps
        assert new_apps.get_model("herd", "Animal").objects.get(pk=animal.pk).age_weeks == 37
    finally:
        MigrationExecutor(connection).migrate(new_target)
