"""Rendered inventory and feeding flows at desktop/mobile widths, synthetic data only."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from herd.feed import today
from herd.models import Allocation, Audit, Inventory
from tests.test_browser import browser, db_query, sign_in
from tests.test_business_rules import setup_mob, stock
from tests.test_foundations import run

OUT = Path(__file__).resolve().parents[1] / "docs/testing/generated/feed-workflows"


def open_menu(page, name):
    link = page.get_by_role("navigation", name="Main navigation").get_by_role("link", name=name, exact=True)
    if not link.is_visible():
        page.locator(".sidebar > summary").click()
    link.click()


@pytest.mark.django_db(transaction=True)
def test_inventory_entry_source_fields_and_unit_measurement_feeding(farm, live_server):
    p, admin, b, _ = farm
    mob = str(setup_mob(b, 2))
    stock(b, kind="chemical", name="Synthetic chemical")
    current_day = today(b).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        engine = browser(playwright)
        page = engine.new_page(viewport={"width": 1440, "height": 1000}, locale="en-AU")
        sign_in(page, live_server.url)
        page.get_by_role("link", name="Cattle Feeding", exact=True).click()
        expect(page.get_by_text("No feed available. Add feed to Feed Inventory before recording a feeding.", exact=True)).to_be_visible()
        open_menu(page, "Chemical Inventory")
        expect(page.get_by_role("heading", name=p.name + " Chemical Inventory")).to_be_visible()
        expect(page.get_by_role("cell", name="Synthetic chemical", exact=True)).to_be_visible()
        open_menu(page, "Feed Inventory")
        expect(page.get_by_role("heading", name=p.name + " Feed Inventory")).to_be_visible()
        expect(page.get_by_role("cell", name="Synthetic chemical", exact=True)).to_have_count(0)
        page.get_by_role("link", name="Add Feed", exact=True).click()
        expect(page.locator("[name=stored_date]")).to_have_value(current_day)
        expect(page.locator("[name=home_grown]")).to_be_checked()
        expect(page.locator("[name=supplier_name]")).to_be_hidden()
        page.locator("[name=name]").fill("UI hay")
        page.locator("[name=feed_type]").select_option("hay")
        page.locator("[name=packages]").fill("100.9")
        page.locator("[name=package_size]").fill("350.9")
        page.locator("[name=stock_unit]").select_option("kg")
        page.locator("[name=feed_unit]").select_option("kg")
        page.locator("[name=package_price]").fill("70.00")
        page.get_by_role("button", name="Preview", exact=True).click()
        expect(page.locator('dt:has-text("Number of Units") + dd')).to_have_text("100")
        expect(page.locator('dt:has-text("Quantity Per Unit") + dd')).to_have_text("350")
        assert db_query(lambda: Inventory.objects.filter(name="UI hay").count()) == 0
        page.get_by_role("button", name="Save", exact=True).click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/")
        hay = str(db_query(lambda: Inventory.objects.get(name="UI hay").pk))
        page.get_by_role("link", name="Add Feed", exact=True).click()
        page.locator("[name=name]").fill("UI grain")
        page.locator("[name=feed_type]").select_option("grain_mix")
        page.locator("[name=packages]").fill("2")
        page.locator("[name=package_size]").fill("20")
        page.locator("[name=stock_unit]").select_option("kg")
        page.locator("[name=feed_unit]").select_option("unit")
        page.locator("[name=package_price]").fill("10")
        page.locator("[name=home_grown]").uncheck()
        expect(page.locator("[name=supplier_name]")).to_be_visible()
        page.locator("[name=supplier_name]").fill("Synthetic supplier")
        page.locator("[name=origin_text]").fill("Synthetic road")
        page.locator("[name=batch]").fill("bad!")
        page.locator("[name=declaration_reference]").fill("CVD42")
        page.locator("[name=date_kind]").select_option("DOM")
        page.locator("[name=date_value]").fill(current_day)
        expect(page.locator("[name=residue_test_details]")).to_be_hidden()
        page.locator("[name=product_tested]").select_option("yes")
        expect(page.locator("[name=residue_test_details]")).to_be_visible()
        page.locator("[name=residue_test_details]").fill("Synthetic residue test")
        page.get_by_role("button", name="Preview", exact=True).click()
        expect(page.locator('[data-feed-field=batch] .errorlist')).to_be_visible()
        expect(page.locator("[name=supplier_name]")).to_have_value("Synthetic supplier")
        page.locator("[name=batch]").fill("AB42")
        page.get_by_role("button", name="Preview", exact=True).click()
        expect(page.get_by_text("Synthetic residue test", exact=True)).to_be_visible()
        page.get_by_role("button", name="Save", exact=True).click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/")
        assert db_query(lambda: Inventory.objects.get(name="UI grain").date_kind) == "DOM"
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            expect(page.locator(".inventory-actions a")).to_have_text(["Add Feed", "Remove Feed", "Bulk Edit", "Cattle Feeding"])
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(OUT / f"inventory-{width}.png"), full_page=True)
        page.get_by_role("link", name="Cattle Feeding", exact=True).click()
        expect(page).to_have_url(live_server.url + "/workflow/feeding/")
        page.locator("[name=feed_type]").select_option("grain_mix")
        grain = str(db_query(lambda: Inventory.objects.get(name="UI grain").pk))
        page.locator("[name=item]").select_option(grain)
        expect(page.locator("[name=mode] option")).to_have_text(["Unit"])
        page.locator("[name=feed_type]").select_option("hay")
        expect(page.locator("[name=item]")).to_have_value("")
        page.locator("[name=item]").select_option(hay)
        expect(page.locator("[name=mode] option")).to_have_text(["Unit", "kg"])
        page.locator("[name=mob]").select_option(mob)
        page.locator("[name=quantity]").fill("1")
        page.get_by_role("button", name="Preview Effect", exact=True).click()
        expect(page.get_by_text("Amount to be issued:", exact=False)).to_contain_text("350")
        assert db_query(lambda: Inventory.objects.get(pk=hay).balance) == 35000
        # Commit the feeding but drop its response, then retry the same signed save.
        def lose_response(route):
            if route.request.method == "POST" and "confirmed_payload" in (route.request.post_data or ""):
                response = route.fetch()
                assert response.status == 200
                route.abort("connectionreset")
                page.evaluate("window.feedResponseDropped = true")
            else:
                route.continue_()
        page.wait_for_function("() => window.stocklogRecoveryReady === true")
        expect(page.locator("#recovery")).to_be_hidden()
        page.route("**/workflow/feeding/", lose_response)
        page.get_by_role("button", name="Confirm Save", exact=True).click()
        page.wait_for_function("() => window.feedResponseDropped === true")
        expect(page.locator("#recovery")).to_contain_text("Not confirmed")
        assert db_query(lambda: Inventory.objects.get(pk=hay).balance) == 34650
        page.unroute("**/workflow/feeding/", lose_response)
        page.get_by_role("button", name="Retry same submission", exact=True).click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/")
        expect(page.locator("#recovery")).to_be_hidden()
        assert db_query(lambda: Inventory.objects.get(pk=hay).balance) == 34650
        assert db_query(lambda: Allocation.objects.filter(category="feed", amount=-35).count()) == 2
        page.goto(live_server.url + "/")
        page.get_by_role("link", name="Feed Inventory", exact=True).last.click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/")
        page.goto(live_server.url + "/")
        page.get_by_role("link", name="Cattle Feeding", exact=True).click()
        page.locator("[name=feed_type]").select_option("hay")
        page.locator("[name=item]").select_option(hay)
        page.locator("[name=mob]").select_option(mob)
        page.locator("[name=mode]").select_option("measure")
        page.locator("[name=quantity]").fill("175")
        page.get_by_role("button", name="Preview Effect", exact=True).click()
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(OUT / f"preview-{width}.png"), full_page=True)
        page.get_by_role("button", name="Confirm Save", exact=True).click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/")
        assert db_query(lambda: Inventory.objects.get(pk=hay).balance) == 34475
        assert db_query(lambda: Allocation.objects.filter(category="feed", amount=-17.5).count()) == 2
        page.get_by_role("link", name="Cattle Feeding", exact=True).click()
        page.locator("[name=feed_type]").select_option("hay")
        page.locator("[name=item]").select_option(hay)
        page.locator("[name=mob]").select_option(mob)
        page.locator("[name=mode]").select_option("measure")
        page.locator("[name=quantity]").fill("34476")
        page.get_by_role("button", name="Preview Effect", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("below zero")
        page.get_by_role("button", name="Confirm Save", exact=True).click()
        expect(page.get_by_role("cell", name="-1 kg", exact=False)).to_be_visible()
        page.get_by_role("link", name="Cattle Feeding", exact=True).click()
        expect(page.locator("[name=feed_type] option[value=hay]")).to_have_count(0)
        db_query(lambda: run(b, "stocktake", {"item": grain, "actual": 0, "reason": "Synthetic zero"}))
        page.reload()
        expect(page.get_by_text("No feed available. Add feed to Feed Inventory before recording a feeding.", exact=True)).to_be_visible()
        expect(page.locator("[name=quantity]")).to_have_count(0)
        assert db_query(lambda: Audit.objects.filter(action="feed").count()) == 3
        engine.close()
