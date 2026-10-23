"""Independent companion-fixture totals; synthetic data only, real InnoDB services."""

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from herd import clock, reports
from herd import services as s
from herd.models import Allocation, Animal, Event, Inventory, Membership

ZONE = ZoneInfo("Australia/Melbourne")
OUT = Path(__file__).resolve().parents[1] / "docs/testing/generated"


def call(u, kind, data):
    return s.execute(u, uuid.uuid4().hex, kind, data)


def tag(cohort, n):
    return f"TEST{cohort}{n:011d}"


def timestamp(start, day, hour, minute=0):
    return int((start + timedelta(days=day)).replace(hour=hour, minute=minute).timestamp())


@pytest.mark.django_db(transaction=True)
def test_complete_overlapping_cohorts(farm):
    prop, admin, b, c = farm
    assert __import__("django").db.connection.vendor == "mysql"
    jobs = []
    cohorts = {}
    fixture_map = {}
    snapshots = {}
    for label, start, count, males, deaths, ill, scale, user in [
        ("A", datetime(2020, 4, 1, tzinfo=ZONE), 12, 8, 2, 5, 1, b),
        ("B", datetime(2020, 8, 1, tzinfo=ZONE), 24, 16, 4, 10, 2, c),
    ]:
        state = {
            "label": label,
            "start": start,
            "count": count,
            "males": males,
            "deaths": deaths,
            "ill": ill,
            "scale": scale,
            "user": user,
        }
        cohorts[label] = state

        def schedule(day, hour, fn, minute=0):
            jobs.append((timestamp(start, day, hour, minute), len(jobs), fn))

        def setup(st=state):
            st["mob"] = call(
                st["user"], "mob", {"name": "April" if st["label"] == "A" else "August"}
            )["mob"]
            rows = [
                {
                    "nlis": tag(st["label"], n),
                    "rfid": f"{(0 if st['label'] == 'A' else 100) + n:015d}",
                    "source_pic": "SRC00001",
                    "nvd": "TEST-NVD-IN",
                    "purchase_cost": "100",
                    "breed": "Angus",
                    "sex": "M" if n <= st["males"] else "F",
                    "estimated_weeks": 1,
                    "mob": st["mob"],
                }
                for n in range(1, st["count"] + 1)
            ]
            result = call(st["user"], "register", {"rows": rows})
            fixture_map.update(
                {tag(st["label"], n): identity for n, identity in enumerate(result["animals"], 1)}
            )

        schedule(0, 9, setup)

        def receive_milk(st=state, initial=True):
            # Fixture scaling: August refills are two whole bags, matching its explicit 1040 kg receipts anchor.
            spec = {
                "kind": "feed",
                "name": "Synthetic milk " + st["label"],
                "feed_type": "milk",
                "packages": str(12 * st["scale"] if initial else st["scale"]),
                "package_size": "20",
                "package_price": "100",
                "stock_unit": "kg",
                "storage": "Synthetic shed",
                "supplier_name": "Synthetic supplier",
                "origin_text": "Fixture",
                "declaration_reference": "TEST-CVD",
                "signed_by_name": st["user"].username,
            }
            st["milk"] = call(st["user"], "receipt", spec)["item"]

        schedule(0, 9, receive_milk, 5)
        for day in range(68):
            for hour in [10 if day == 0 else 8, 17]:

                def milk(st=state, receive=receive_milk):
                    needed = D("0.350") * len(s.members(st["user"], st["mob"], clock.now()))
                    while Inventory.objects.get(pk=st["milk"]).balance < needed:
                        receive(st, False)
                    call(
                        st["user"],
                        "feed",
                        {
                            "mob": st["mob"],
                            "item": st["milk"],
                            "quantity": "0.350",
                            "mode": "kg_per_head",
                        },
                    )

                schedule(day, hour, milk)
        schedule(
            7,
            9,
            lambda st=state: call(
                st["user"],
                "observation",
                {
                    "animals": [tag(st["label"], n) for n in range(1, st["ill"] + 1)],
                    "notes": "Synthetic illness, no charge",
                },
            ),
        )

        def chemical(st=state):
            st["chemical"] = call(
                st["user"],
                "receipt",
                {
                    "kind": "chemical",
                    "name": "Synthetic treatment " + st["label"],
                    "packages": 1,
                    "package_size": "100",
                    "package_price": "50",
                    "stock_unit": "mL",
                    "dose_unit": "mL",
                    "batch": "TEST-" + st["label"],
                    "date_kind": "expiry",
                    "date_value": "2022-01-01",
                    "restriction_days": 28,
                },
            )["item"]

        schedule(14, 8, chemical, 30)
        for day in range(14, 19):

            def treatment(st=state):
                for n in range(1, st["ill"] + 1):
                    call(
                        st["user"],
                        "treat",
                        {
                            "animal": tag(st["label"], n),
                            "item": st["chemical"],
                            "dose": "2",
                            "dose_unit": "mL",
                            "administered_by": "Synthetic operator",
                            "administered_by_contact": "TEST CONTACT",
                            "adverse_reactions": "None reported",
                            "broken_needle_status": "no",
                            "equipment_cleaned_calibrated": "yes",
                            "equipment_checked_by_name": "Synthetic checker",
                        },
                    )

            schedule(day, 9, treatment)
        schedule(
            18,
            18,
            lambda st=state: call(
                st["user"],
                "death",
                {
                    "animals": [tag(st["label"], n) for n in range(1, st["deaths"] + 1)],
                    "reason": "Synthetic fixture death",
                    "accept_restriction": True,
                },
            ),
        )
        schedule(
            28,
            9,
            lambda st=state: call(
                st["user"],
                "procedure",
                {
                    "animals": [
                        tag(st["label"], n) for n in range(st["deaths"] + 1, st["males"] + 1)
                    ],
                    "procedure": "castration",
                    "fee": "10",
                },
            ),
        )

        def grain(st=state):
            st["grain"] = call(
                st["user"],
                "receipt",
                {
                    "kind": "feed",
                    "name": "Synthetic grain " + st["label"],
                    "feed_type": "grain",
                    "packages": str(20 * st["scale"]),
                    "package_size": "26",
                    "package_price": "26",
                    "stock_unit": "kg",
                },
            )["item"]

        schedule(28, 10, grain)
        for day in range(28, 68):
            schedule(
                day,
                12,
                lambda st=state: call(
                    st["user"],
                    "feed",
                    {
                        "mob": st["mob"],
                        "item": st["grain"],
                        "quantity": str(13 * st["scale"]),
                        "mode": "total_kg",
                    },
                ),
            )

        def hay(st=state):
            st["hay"] = call(
                st["user"],
                "receipt",
                {
                    "kind": "feed",
                    "name": "Synthetic hay " + st["label"],
                    "feed_type": "hay",
                    "packages": str(100 * st["scale"]),
                    "package_size": "330",
                    "package_price": "65",
                    "stock_unit": "kg",
                },
            )["item"]

        schedule(68, 9, hay)
        for week in range(50):
            schedule(
                68 + 7 * week,
                12,
                lambda st=state: call(
                    st["user"],
                    "feed",
                    {
                        "mob": st["mob"],
                        "item": st["hay"],
                        "quantity": str(2 * st["scale"]),
                        "mode": "bales",
                    },
                ),
            )

        def sale(st=state):
            call(
                st["user"],
                "sale",
                {
                    "mob": st["mob"],
                    "destination_pic": "DST00001",
                    "nvd": "TEST-NVD-OUT",
                    "price": "2000",
                    "price_mode": "per_head",
                },
            )
            report = reports.build(
                st["user"],
                {
                    "dataset": "animals",
                    "filters": {"mob": str(st["mob"])},
                    "columns": [
                        "animal",
                        "status",
                        "cost",
                        "revenue",
                        "profit",
                        "financial_complete",
                    ],
                },
            )
            report["note"] = "SYNTHETIC ACCEPTANCE FIXTURE. " + report["note"]
            snapshots[st["label"]] = report
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"{st['label']}-mob-lifetime.pdf").write_bytes(reports.pdf(report))
            (OUT / f"{st['label']}-mob-lifetime.xlsx").write_bytes(reports.xlsx(report))
            survivor = reports.build(
                st["user"],
                {
                    "dataset": "animals",
                    "filters": {"mob": str(st["mob"]), "status": "exited"},
                },
            )
            survivor["note"] = "SYNTHETIC ACCEPTANCE FIXTURE. " + survivor["note"]
            for fmt, fn in [("pdf", reports.pdf), ("xlsx", reports.xlsx)]:
                (OUT / f"{st['label']}-survivors.{fmt}").write_bytes(fn(survivor))

        schedule(412, 12, sale)
    for at, order, fn in sorted(jobs):
        with clock.at(at):
            fn()
    april, august = snapshots["A"], snapshots["B"]
    assert april["totals"] == {"cost": D(10818), "revenue": D(20000), "profit": D(9182)}
    assert august["totals"] == {
        "cost": D(21636),
        "revenue": D(40000),
        "profit": D(18364),
    }
    arows = {r["animal"]: r for r in april["rows"]}
    for n in [1, 2]:
        assert arows[tag("A", n)]["cost"] == D("171.50") and arows[tag("A", n)]["profit"] == -D(
            "171.50"
        )
    for n in [3, 4, 5]:
        assert arows[tag("A", n)]["cost"] == D(1055) and arows[tag("A", n)]["profit"] == D(945)
    for n in [6, 7, 8]:
        assert arows[tag("A", n)]["cost"] == D(1050) and arows[tag("A", n)]["profit"] == D(950)
    for n in [9, 10, 11, 12]:
        assert arows[tag("A", n)]["cost"] == D(1040) and arows[tag("A", n)]["profit"] == D(960)
    assert sum(r["profit"] for r in april["rows"] if r["status"] == "exited") == D(9525)
    assert (
        Animal.objects.count() == 36
        and Animal.objects.filter(status="dead").count() == 6
        and Animal.objects.filter(status="exited").count() == 30
    )
    assert not Membership.objects.filter(end__isnull=True).exists()
    assert Inventory.objects.get(pk=cohorts["A"]["milk"]).balance == D("17.4")
    assert Inventory.objects.get(pk=cohorts["B"]["milk"]).balance == D("34.8")
    for st in cohorts.values():
        assert (
            Inventory.objects.get(pk=st["grain"]).balance == 0
            and Inventory.objects.get(pk=st["hay"]).balance == 0
        )
        receipts = Event.objects.filter(
            kind="receipt", details__name="Synthetic milk " + st["label"]
        )
        assert sum(D(e.details["received"]) for e in receipts) == D(520 * st["scale"])
    assert Inventory.objects.get(pk=cohorts["A"]["chemical"]).balance == 50
    assert Inventory.objects.get(pk=cohorts["B"]["chemical"]).balance == 0
    assert sum(Allocation.objects.values_list("amount", flat=True)) == D(27546)
    # Independent extraction validates actual artifacts, not only in-memory builder totals.
    from openpyxl import load_workbook
    from pypdf import PdfReader

    for label, expected in [("A", "9182"), ("B", "18364")]:
        pdf_text = "\n".join(
            p.extract_text() for p in PdfReader(OUT / f"{label}-mob-lifetime.pdf").pages
        )
        assert expected in pdf_text and "SYNTHETIC ACCEPTANCE" in pdf_text
        workbook = load_workbook(OUT / f"{label}-mob-lifetime.xlsx", data_only=False)
        values = list(workbook.active.values)
        assert expected in str(values) and "dead" in str(values)
        assert len(values) == cohorts[label]["count"] + 5
    (OUT / "fixture-identities.json").write_text(json.dumps(fixture_map, indent=2) + "\n")
    (OUT / "reconciliation.json").write_text(
        json.dumps(
            {
                "scope": "Synthetic integration fixture; production MariaDB engine, not owner data",
                "april": april["totals"],
                "august": august["totals"],
                "combined_cost": "32454",
                "combined_revenue": "60000",
                "combined_profit": "27546",
                "original_animals": 36,
                "deaths": 6,
                "sales": 30,
                "source_fixture": "docs/testing/StockLOG_acceptance_scenario.md",
            },
            default=str,
            indent=2,
        )
        + "\n"
    )
