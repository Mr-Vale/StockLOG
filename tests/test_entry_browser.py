"""Responsive entry and navigation checks plus synthetic review evidence."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from herd.models import Animal
from tests.test_browser import browser, db_query, sign_in

OUT = Path(__file__).resolve().parents[1] / "docs/testing/cattle-entry-screenshots"


@pytest.mark.django_db(transaction=True)
def test_entry_modes_review_and_responsive_navigation(farm, live_server):
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        engine = browser(p)
        page = engine.new_page(viewport={"width": 1440, "height": 1000}, locale="en-AU")
        sign_in(page, live_server.url)
        expect(page.locator("#selection-card")).not_to_have_attribute("open", "")
        names = page.locator("nav a").all_text_contents()
        assert names == ["Active Cattle", "Inventory", "Reports", "History", "Import", "Settings"]
        page.screenshot(path=str(OUT / "desktop-home.png"), full_page=True)
        page.get_by_role("link", name="Change selection", exact=True).click()
        expect(page.locator("#selection-card")).to_have_attribute("open", "")
        page.get_by_role("button", name="Save selection", exact=True).click()
        expect(page.locator("#selection-card")).not_to_have_attribute("open", "")
        page.goto(live_server.url + "/workflow/entry/")
        for width, label in [(1440, "desktop"), (390, "mobile")]:
            page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
            page.goto(live_server.url + "/")
            page.screenshot(path=str(OUT / f"{label}-home.png"), full_page=True)
            if width == 390:
                expect(page.locator(".sidebar")).not_to_have_attribute("open", "")
            page.goto(live_server.url + "/workflow/entry/")
            for mode in ["Purchase", "Birth", "Re-Purchase"]:
                page.get_by_role("button", name=mode, exact=True).click()
                expect(page.get_by_role("heading", name=mode, exact=True)).to_be_visible()
                expect(page.get_by_role("link", name="Bulk Import", exact=True)).to_be_visible()
                page.screenshot(path=str(OUT / f"{label}-{mode.lower()}.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("button", name="Birth", exact=True).click()
        page.locator("[name=rfid]").fill("000000000000001")
        page.get_by_role("button", name="Add to list", exact=True).click()
        expect(page.get_by_role("heading", name="Review animals (1)")).to_be_visible()
        assert db_query(lambda: Animal.objects.count()) == 0
        page.get_by_role("button", name="Purchase", exact=True).click()
        expect(page.get_by_role("heading", name="Review animals (1)")).to_be_visible()
        page.locator("[name=nlis]").fill("0000000000000002")
        page.locator("[name=source_pic]").fill("SRC00001")
        page.locator("[name=nvd]").fill("NVD-EXAMPLE")
        page.get_by_role("button", name="Add to list", exact=True).click()
        expect(page.get_by_role("heading", name="Review animals (2)")).to_be_visible()
        page.screenshot(path=str(OUT / "mobile-review.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.screenshot(path=str(OUT / "desktop-review.png"), full_page=True)
        page.get_by_role("button", name="Save animals", exact=True).click()
        expect(page.get_by_role("heading", name="Saved and confirmed")).to_be_visible()
        assert db_query(lambda: Animal.objects.count()) == 2
        for width, label in [(1440, "desktop"), (390, "mobile")]:
            page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
            page.goto(live_server.url + "/animals/")
            expect(page.locator("th")).to_have_count(9)
            expect(page.locator("nav a[aria-current=page]")).to_have_text("Active Cattle")
            page.screenshot(path=str(OUT / f"{label}-active.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        engine.close()
