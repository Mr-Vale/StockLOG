"""Chromium verification of the combined animal experience on desktop and mobile."""

import pytest
from playwright.sync_api import expect, sync_playwright

from herd.models import Animal, Audit, Event
from tests.test_animal_detail import history_url, url
from tests.test_browser import browser, db_query, sign_in
from tests.test_cattle_changes import animal, run


def button_style(locator):
    return locator.evaluate("""el => {
        const s = getComputedStyle(el);
        return Object.fromEntries(['backgroundColor', 'color', 'padding', 'borderRadius',
          'fontFamily', 'fontSize', 'fontWeight', 'outlineStyle', 'outlineColor',
          'outlineWidth', 'outlineOffset', 'margin'].map(k => [k, s[k]]));
    }""")


@pytest.mark.django_db(transaction=True)
def test_combined_summary_edit_actions_and_history(farm, live_server, tmp_path):
    _, admin, b, _ = farm
    # Entry's business rules require source PIC/NVD; source name/address and cost can be missing.
    x = animal(b, entry_date=None, purchase_cost=None)
    animal(b, 2, entry_date=None, vendor_name="Other animal only")
    label = x.label
    with sync_playwright() as p:
        engine = browser(p)
        page = engine.new_page(viewport={"width": 1440, "height": 1000})
        sign_in(page, live_server.url)
        home_button = page.get_by_role("link", name="Cattle Entry", exact=True)
        page.mouse.move(0, 0)
        normal = button_style(home_button)
        home_button.hover()
        hover = button_style(home_button)
        page.mouse.move(0, 0)
        home_button.focus()
        page.keyboard.press("Tab")
        page.keyboard.press("Shift+Tab")
        focus = button_style(home_button)
        assert focus["outlineStyle"] == "solid" and focus["outlineWidth"] == "3px"
        page.get_by_role("link", name="Active Cattle", exact=True).last.click()
        page.get_by_role("link", name=label, exact=True).click()
        expect(page.get_by_role("heading", name=label, exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Edit Animal", exact=True)).to_be_visible()
        summary = page.get_by_role("region", name="Animal summary")
        expect(summary.get_by_text("Active", exact=True)).to_be_visible()
        expect(summary.get_by_text("Not recorded", exact=True)).to_have_count(6)
        expect(page.locator("pre")).to_have_count(0)
        expect(page.get_by_role("heading", name="Lifetime history", exact=True)).to_have_count(0)
        expect(page.locator("[name=source_pic]")).to_be_disabled()
        expect(page.locator("[name=rfid]")).to_be_disabled()
        expect(page.locator("[name=vendor_name]")).to_be_enabled()
        for target in [
            page.get_by_role("button", name="Preview changes"),
            page.get_by_role("link", name="View lifetime history"),
        ]:
            page.locator("h1").click()
            page.mouse.move(0, 0)
            assert button_style(target) == normal
            target.hover()
            assert button_style(target) == hover
            page.mouse.move(0, 0)
            target.focus()
            page.keyboard.press("Tab")
            page.keyboard.press("Shift+Tab")
            assert button_style(target) == focus
        page.locator("[name=vendor_name]").fill("Completed source")
        page.get_by_role("button", name="Preview changes").click()
        expect(page.get_by_role("button", name="Confirm and save")).to_be_visible()
        assert db_query(lambda: Event.objects.filter(kind="edit_animal").count()) == 0
        page.get_by_role("button", name="Confirm and save").click()
        expect(page).to_have_url(live_server.url + url(x))
        expect(summary.get_by_text("Completed source", exact=True)).to_be_visible()
        assert db_query(lambda: Audit.objects.filter(action="edit_animal").count()) == 1
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            expect(page.get_by_role("button", name="Preview changes")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(tmp_path / f"animal-detail-{width}.png"), full_page=True)
        page.get_by_role("link", name="View lifetime history").click()
        expect(page).to_have_url(live_server.url + history_url(x))
        expect(page.get_by_role("heading", name="Lifetime history — " + label)).to_be_visible()
        expect(page.locator("pre").filter(has_text="Completed source")).to_have_count(1)
        expect(page.get_by_text("Other animal only", exact=False)).to_have_count(0)
        page.get_by_role("link", name="Return to animal details").click()
        expect(page.locator("pre")).to_have_count(0)
        # Exercise the rendered sale summary after the actual service closes this presence.
        db_query(
            lambda: run(
                b, "sale", dict(animal=label, destination_pic="0DEST001", nvd="00000002", price=0)
            )
        )
        page.reload()
        expect(summary.get_by_text("Deactive", exact=True)).to_be_visible()
        expect(summary.get_by_text("0.00 AUD", exact=True)).to_have_count(2)
        expect(summary.get_by_text("Sale price", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Preview changes")).to_have_count(0)
        assert db_query(lambda: Animal.objects.get(pk=x.pk).status) == "exited"
        engine.close()
