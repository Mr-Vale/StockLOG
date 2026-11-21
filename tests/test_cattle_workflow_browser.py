"""Repeatable browser checks for entry buttons, list selection and selected workflows."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from herd.entry import today
from herd.models import Animal
from tests.test_animal_detail_browser import button_style
from tests.test_browser import browser, db_query, sign_in
from tests.test_business_rules import stock
from tests.test_cattle_changes import animal, run

OUT = Path(__file__).resolve().parents[1] / "docs/testing/generated/cattle-workflows"


@pytest.mark.django_db(transaction=True)
def test_entry_buttons_bulk_alignment_and_both_exit_entry_points(farm, live_server):
    _, admin, b, _ = farm
    x, y = animal(b, 1, entry_date=None), animal(b, 2, entry_date=None)
    x_id, y_id, x_label, y_label = str(x.pk), str(y.pk), x.label, y.label
    mob = str(run(admin, "mob", {"name": "Selected cattle"})["mob"])
    chemical = stock(b, kind="chemical", restriction_days=7)
    run(b, "treat", {"animal": x_label, "item": chemical, "dose": 1})
    day = today(admin).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        engine = browser(p)
        context = engine.new_context(viewport={"width": 1440, "height": 1000}, locale="en-AU")
        page = context.new_page()
        sign_in(page, live_server.url, "A")
        page.get_by_role("link", name="Cattle Entry", exact=True).click()
        page.locator("[name=nlis]").fill("0TEST001ABC00009")
        page.locator("[name=source_pic]").fill("0FROM001")
        page.locator("[name=nvd]").fill("00000001")
        page.get_by_role("button", name="Add to list", exact=True).click()
        page.get_by_role("button", name="Save animals", exact=True).click()
        expect(page.get_by_role("heading", name="Saved and confirmed")).to_be_visible()
        buttons = page.locator(".confirmation-actions a")
        assert buttons.all_text_contents() == [
            "View recorded history", "Return to property", "Return to Active Cattle"
        ]
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            for state in ["normal", "hover", "focus"]:
                styles = []
                for link in buttons.all():
                    page.locator("h1").click()
                    page.mouse.move(0, 0)
                    if state == "hover":
                        link.hover()
                    elif state == "focus":
                        link.focus()
                        page.keyboard.press("Tab")
                        page.keyboard.press("Shift+Tab")
                    styles.append(button_style(link))
                assert styles[0] == styles[1] == styles[2]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(OUT / f"saved-{width}.png"), full_page=True)
        expected_paths = ["/events/", "/", "/animals/"]
        for link, path in zip(buttons.all(), expected_paths):
            assert link.get_attribute("href") == path
            target = page.context.new_page()
            response = target.goto(live_server.url + path)
            assert response.status == 200
            expect(target.locator(".title-context")).to_contain_text("0TEST001")
            target.close()
        page.get_by_role("link", name="Return to Active Cattle").click()
        expect(page).to_have_url(live_server.url + "/animals/")
        expect(page.get_by_role("link", name="0TEST001ABC00009", exact=True)).to_be_visible()
        page.get_by_role("link", name="Bulk Edit", exact=True).click()
        expect(page.get_by_role("heading", name="Active Cattle")).to_be_visible()
        expect(page.get_by_role("button", name="Next", exact=True)).to_be_disabled()
        expect(page.get_by_role("link", name="Cattle Entry", exact=True)).to_be_disabled()
        expect(page.get_by_role("link", name="Cattle Exit", exact=True)).to_be_disabled()
        for animal_id in [x_id, y_id]:
            page.locator(f'[name=selected_ids][value="{animal_id}"]').check()
        expect(page.get_by_role("button", name="Next", exact=True)).to_be_enabled()
        page.get_by_role("button", name="Next", exact=True).click()
        expect(page.get_by_role("heading", name="Bulk Edit", exact=True)).to_be_visible()
        assert set(page.locator(".selected-animals li").all_text_contents()) == {x_label, y_label}
        expect(page.locator("[data-animal-selection]")).to_have_count(0)
        expect(page.locator("[name=mob]")).to_be_disabled()
        page.locator("[name=update_mob]").check()
        page.locator("[name=mob]").select_option(mob)
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            groups = page.locator(".bulk-field")
            for group in groups.all():
                checkbox = group.locator("[name^=update_]").bounding_box()
                field = group.locator("input:not([type=checkbox]),select").bounding_box()
                box = group.bounding_box()
                assert box["y"] <= checkbox["y"] < field["y"] < box["y"] + box["height"]
            assert page.locator(".selected-animals").bounding_box()["y"] < groups.first.bounding_box()["y"]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(OUT / f"bulk-{width}.png"), full_page=True)
        page.get_by_role("button", name="Preview changes").click()
        page.get_by_role("button", name="Confirm and save").click()
        assert db_query(lambda: x.memberships.filter(end__isnull=True, superseded=False, mob_id=mob).exists())
        assert db_query(lambda: y.memberships.filter(end__isnull=True, superseded=False, mob_id=mob).exists())
        assert db_query(lambda: Animal.objects.get(identifiers__value="0TEST001ABC00009").memberships.filter(end__isnull=True).count()) == 0
        # Active Cattle entry point carries exactly the checked animal.
        page.get_by_role("link", name="Cattle Exit", exact=True).click()
        page.locator(f'[name=selected_ids][value="{y_id}"]').check()
        page.get_by_role("button", name="Next", exact=True).click()
        assert page.locator(".selected-animals li").all_text_contents() == [y_label]
        # Home entry point opens the same selection screen, including disabled Next.
        page.goto(live_server.url + "/")
        page.get_by_role("link", name="Cattle Exit", exact=True).click()
        expect(page).to_have_url(live_server.url + "/animals/?select=exit")
        expect(page.get_by_role("button", name="Next", exact=True)).to_be_disabled()
        page.locator(f'[name=selected_ids][value="{x_id}"]').check()
        page.get_by_role("button", name="Next", exact=True).click()
        assert page.locator(".selected-animals li").all_text_contents() == [x_label]
        page.locator("[name=exit_date]").fill(day)
        page.locator("[name=destination_pic]").fill("0DEST001")
        page.locator("[name=nvd]").fill("00000002")
        page.locator("[name=price]").fill("100")
        page.get_by_role("button", name="Preview changes").click()
        expect(page.get_by_role("alert")).to_contain_text("before safe sale date")
        page.locator("[name=accept_restriction]").check()
        page.get_by_role("button", name="Confirm and save").click()
        assert db_query(lambda: Animal.objects.get(pk=x_id).status) == "exited"
        assert db_query(lambda: Animal.objects.get(pk=y_id).status) == "active"
        engine.close()
