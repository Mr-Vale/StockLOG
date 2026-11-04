"""Desktop/mobile evidence from isolated synthetic cattle; no running server access."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from herd import services
from herd.entry import today
from herd.models import Animal
from tests.test_browser import browser, db_query, sign_in

OUT = Path(__file__).resolve().parents[1] / "docs/testing/cattle-changes-screenshots"


@pytest.mark.django_db(transaction=True)
def test_cattle_forms_and_evidence(farm, live_server):
    p, admin, b, _ = farm
    for n in [1, 2]:
        services.execute(
            admin,
            f"browser-entry-{n}",
            "register",
            dict(
                entry_date=today(admin).isoformat(),
                nlis=f"0TEST001ABC{n:05}",
                rfid=f"{n:015}",
                source_pic="0FROM001",
                nvd="00000001",
                purchase_cost=100,
                breed="Angus",
                sex="F",
                estimated_weeks=12,
            ),
        )
    services.execute(admin, "browser-mob", "mob", {"name": "Home mob"})
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        engine = browser(playwright)
        page = engine.new_page(viewport={"width": 1440, "height": 1000}, locale="en-AU")
        sign_in(page, live_server.url, "A")
        for width, label in [(1440, "desktop"), (390, "mobile")]:
            page.set_viewport_size({"width": width, "height": 1000 if width > 400 else 844})
            for route, name in [
                ("/", "home"),
                ("/animals/", "active"),
                ("/action/bulk_edit/", "bulk-edit"),
                ("/action/edit_animal/?animal=0TEST001ABC00001", "edit-animal"),
            ]:
                page.goto(live_server.url + route)
                expect(page.locator("h1")).to_be_visible()
                if name == "active" and width == 1440:
                    assert page.locator("main").bounding_box()["x"] == 185
                page.screenshot(path=str(OUT / f"{label}-{name}.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.goto(live_server.url + "/workflow/exit/")
            for mode in ["Sale", "Transfer", "Death"]:
                page.get_by_role("button", name=mode, exact=True).click()
                expect(page.get_by_role("heading", name=mode, exact=True)).to_be_visible()
                page.screenshot(path=str(OUT / f"{label}-exit-{mode.lower()}.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(live_server.url + "/action/bulk_edit/")
        page.locator("[name=animals]").select_option(["0TEST001ABC00001", "0TEST001ABC00002"])
        page.locator("[name=update_breed]").check()
        page.locator("[name=breed]").fill("Hereford")
        page.get_by_role("button", name="Preview changes").click()
        expect(page.get_by_role("heading", name="Selected animals (2)")).to_be_visible()
        page.get_by_role("button", name="Confirm and save").click()
        expect(page.get_by_role("heading", name="Active Cattle")).to_be_visible()
        assert db_query(lambda: Animal.objects.filter(breed="Hereford").count()) == 2
        page.goto(live_server.url + "/workflow/exit/")
        page.locator("[name=destination_pic]").fill("0DEST001")
        page.locator("[name=nvd]").fill("00000001")
        page.locator("[name=price]").fill("100.01")
        page.locator("[name=price_mode]").select_option("group")
        page.locator("[name=animals]").select_option(["0TEST001ABC00001", "0TEST001ABC00002"])
        expect(page.locator(".selected-animals li")).to_have_count(2)
        page.get_by_role("button", name="Transfer", exact=True).click()
        expect(page.locator("[name=destination_pic]")).to_have_value("0DEST001")
        page.get_by_role("button", name="Sale", exact=True).click()
        expect(page.locator("[name=price]")).to_have_value("100.01")
        page.get_by_role("button", name="Preview changes").click()
        expect(page.get_by_role("heading", name="Selected animals (2)")).to_be_visible()
        page.screenshot(path=str(OUT / "desktop-exit-preview.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUT / "mobile-exit-preview.png"), full_page=True)
        page.get_by_role("button", name="Confirm and save").click()
        expect(page.get_by_role("heading", name="Active Cattle")).to_be_visible()
        assert db_query(lambda: Animal.objects.filter(status="exited").count()) == 2
        engine.close()
