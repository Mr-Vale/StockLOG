"""Rendered selection, sorting and preview/save at desktop and phone widths."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from herd.models import Allocation, Audit, Inventory
from tests.test_browser import browser, db_query, sign_in
from tests.test_feed_workflows import add

OUT = Path(__file__).resolve().parents[1] / "docs/testing/generated/feed-inventory"


@pytest.mark.django_db(transaction=True)
def test_selection_sort_details_bulk_and_removal(farm, live_server):
    _, _, b, _ = farm
    first = str(add(b, name="Alpha feed", packages=10, package_size=10)["item"])
    second = str(add(b, name="Zulu feed", packages=20, package_size=10)["item"])
    third = str(add(b, name="Untouched feed", packages=5, package_size=10)["item"])
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        engine = browser(p)
        page = engine.new_page(viewport={"width": 1440, "height": 1000})
        sign_in(page, live_server.url)
        page.get_by_role("link", name="Feed Inventory", exact=True).last.click()
        expected = ["Product", "Type", "Units Remaining", "Remaining Stock", "Quantity/Item",
            "Price/Item", "Cost/Stock Unit", "Feed Unit", "Stock Value", "Batch/Date"]
        headers = page.locator("main table thead th")
        assert [t.replace(" ▲", "").replace(" ▼", "") for t in headers.all_text_contents()] == expected
        assert page.locator('th[aria-sort=ascending]').inner_text() == "Product ▲"
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(OUT / f"table-{width}.png"), full_page=True)
        page.get_by_role("link", name="Bulk Edit", exact=True).click()
        expect(page.get_by_role("button", name="Next", exact=True)).to_be_disabled()
        for label in ["Add Feed", "Remove Feed", "Cattle Feeding"]:
            link = page.get_by_role("link", name=label, exact=True)
            expect(link).to_have_attribute("aria-disabled", "true")
            assert link.get_attribute("href") is None
        page.get_by_role("checkbox", name="Select Alpha feed", exact=True).check()
        page.get_by_role("checkbox", name="Select Zulu feed", exact=True).check()
        page.get_by_role("link", name="Remaining Stock", exact=True).click()
        expect(page.get_by_role("checkbox", name="Select Alpha feed", exact=True)).to_be_checked()
        expect(page.get_by_role("checkbox", name="Select Zulu feed", exact=True)).to_be_checked()
        expect(page.get_by_role("checkbox", name="Select Untouched feed", exact=True)).not_to_be_checked()
        expect(page.locator("th[aria-sort=ascending]")).to_contain_text("Remaining Stock")
        page.get_by_role("link", name="Remaining Stock ▲", exact=True).click()
        expect(page.locator("th[aria-sort=descending]")).to_contain_text("▼")
        page.get_by_role("button", name="Next", exact=True).click()
        expect(page.get_by_role("heading", name="Bulk Edit Feed", exact=True)).to_be_visible()
        expect(page.locator("fieldset legend")).to_have_text(["Alpha feed", "Zulu feed"])
        page.locator('[name="' + first + '_actual"]').fill("12.345678901234")
        page.locator('[name="' + first + '_reason"]').fill("Counted Alpha")
        page.locator('[name="' + second + '_actual"]').fill("123.456789012345")
        page.locator('[name="' + second + '_reason"]').fill("Counted Zulu")
        page.get_by_role("button", name="Preview", exact=True).click()
        expect(page.get_by_role("columnheader", name="Current value")).to_be_visible()
        expect(page.get_by_role("cell", name="12.35 kg", exact=True)).to_be_visible()
        assert db_query(lambda: Inventory.objects.get(pk=first).balance) == 100
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(OUT / f"edit-preview-{width}.png"), full_page=True)
        page.get_by_role("button", name="Save", exact=True).click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/")
        assert str(db_query(lambda: Inventory.objects.get(pk=first).balance)) == "12.345678901234"
        assert db_query(lambda: Inventory.objects.get(pk=third).balance) == 50
        page.get_by_role("link", name="Alpha feed", exact=True).click()
        expect(page.get_by_role("heading", name="Recorded feeding activity", exact=False)).to_be_visible()
        expect(page.get_by_text("To change the price, retire this product, then add it again with the new price.", exact=True)).to_be_visible()
        page.locator('[name="' + first + '_actual"]').fill("12")
        page.locator('[name="' + first + '_reason"]').fill("Individual correction")
        page.get_by_role("button", name="Preview", exact=True).click()
        page.get_by_role("button", name="Save", exact=True).click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/product/" + first + "/")
        expect(page.get_by_role("button", name="Preview", exact=True)).to_be_visible()
        assert db_query(lambda: Inventory.objects.get(pk=first).balance) == 12
        page.get_by_role("link", name="Return to Feed Inventory", exact=True).click()
        page.get_by_role("link", name="Remove Feed", exact=True).click()
        expect(page.get_by_role("button", name="Next", exact=True)).to_be_disabled()
        page.get_by_role("checkbox", name="Select Alpha feed", exact=True).check()
        page.get_by_role("checkbox", name="Select Zulu feed", exact=True).check()
        page.get_by_role("button", name="Next", exact=True).click()
        expect(page.locator('[name="' + first + '_retired"]')).to_be_checked()
        page.locator('[name="' + first + '_actual"]').fill("0")
        page.locator('[name="' + first + '_reason"]').fill("Used elsewhere")
        page.locator('[name="' + second + '_reason"]').fill("Retire unchanged")
        page.get_by_role("button", name="Preview", exact=True).click()
        expect(page.get_by_role("columnheader", name="Quantity removed")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Resulting stock balance")).to_be_visible()
        assert db_query(lambda: Inventory.objects.filter(retired=True).count()) == 0
        page.get_by_role("button", name="Save", exact=True).click()
        expect(page).to_have_url(live_server.url + "/inventory/feed/")
        assert db_query(lambda: Inventory.objects.filter(retired=True).count()) == 2
        assert db_query(lambda: Inventory.objects.get(pk=first).balance) == 0
        assert not db_query(lambda: Allocation.objects.exists())
        assert db_query(lambda: Audit.objects.filter(action="feed_adjust").count()) == 3
        assert "AUD" not in page.locator("body").inner_text()
        engine.close()
