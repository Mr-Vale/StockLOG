import subprocess

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from herd import backups, clock
from herd.models import (
    Account,
    Allocation,
    Animal,
    Audit,
    Event,
    Inventory,
    Property,
    ReportTemplate,
)

from .test_business_rules import T, setup_mob, stock
from .test_foundations import run


@pytest.mark.django_db(transaction=True)
def test_encrypted_rotation_failure_and_fresh_database_restore(farm, tmp_path, monkeypatch):
    p, a, b, c = farm
    with clock.at(T):
        mob = setup_mob(b, 2)
        item = stock(b)
        run(b, "feed", {"mob": mob, "item": item, "quantity": 1, "mode": "bales"})
        run(
            c,
            "template",
            {
                "name": "Restore this shared template",
                "definition": {"dataset": "animals"},
            },
        )
    identity = tmp_path / "recovery.key"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.check_output(["age-keygen", "-y", str(identity)], text=True).strip()
    monkeypatch.setenv("STOCKLOG_AGE_RECIPIENT", recipient)
    monkeypatch.setenv("STOCKLOG_BACKUPS", str(tmp_path / "backups"))
    expected = {
        m.__name__: list(m.objects.order_by("pk").values())
        for m in [
            Animal,
            Account,
            Audit,
            Property,
            Event,
            Inventory,
            Allocation,
            ReportTemplate,
        ]
    }
    hashes = []
    for _ in range(4):
        manifest = backups.create_backup()
        hashes.append(manifest["archive_id"])
        assert backups.sha(backups.archive_path(manifest["archive_id"])) == manifest["sha256"]
    folder = backups.backup_dir()
    assert (
        len(list(folder.glob("*.age"))) == 3 and not (folder / (hashes[0] + ".tar.gz.age")).exists()
    )
    assert backups.latest()["archive_id"] == hashes[-1]
    prior = set(folder.glob("*.age"))
    monkeypatch.setenv("STOCKLOG_AGE_RECIPIENT", "invalid")
    with pytest.raises(ValidationError):
        backups.create_backup()
    assert set(folder.glob("*.age")) == prior
    monkeypatch.setenv("STOCKLOG_AGE_RECIPIENT", recipient)
    encrypted = backups.archive_path(hashes[-1])
    with pytest.raises(ValidationError):
        backups.restore_backup(encrypted, identity, connection.settings_dict["NAME"])
    # A distinct empty schema is created/restored/compared; the source stays untouched.
    db_name = "stocklog_restore_test"
    subprocess.run(
        [
            "mariadb",
            "-e",
            f"DROP DATABASE IF EXISTS {db_name}; CREATE DATABASE {db_name} CHARACTER SET utf8mb4; GRANT ALL ON {db_name}.* TO 'stocklog'@'localhost';",
        ],
        check=True,
    )
    original_name = connection.settings_dict["NAME"]
    connection.close()
    connection.settings_dict["NAME"] = db_name
    try:
        restored = backups.restore_backup(encrypted, identity, db_name)
        assert restored["schema_version"] == 1
        for model, rows in [
            (m, expected[m.__name__])
            for m in [
                Animal,
                Account,
                Audit,
                Property,
                Event,
                Inventory,
                Allocation,
                ReportTemplate,
            ]
        ]:
            assert list(model.objects.order_by("pk").values()) == rows, model.__name__
        assert Account.objects.get(username="B").check_password("Synthetic-Test-Password-2026")
    finally:
        connection.close()
        connection.settings_dict["NAME"] = original_name
        subprocess.run(["mariadb", "-e", f"DROP DATABASE {db_name}"], check=True)
