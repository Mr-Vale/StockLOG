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
    entry_date = x.presence.get(end__isnull=True).arrival.details["entry_rows"][0]["effective_at"]
    from herd.cattle_services import calendar_date

    entry_date = calendar_date(b, int(entry_date)).isoformat()
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
        edit = page.locator("details.animal-edit")
        expect(edit).not_to_have_attribute("open", "")
        expect(page.locator("[name=vendor_name]")).to_be_hidden()
        edit.locator("summary").click()
        expect(page).to_have_url(live_server.url + url(x))
        expect(page.locator("[name=vendor_name]")).to_be_visible()
        # A server-side field error must keep the disclosure open and retain input.
        page.locator("[name=vendor_name]").fill("Pending source")
        page.locator("[name=entry_date]").fill("")
        page.locator("[data-cattle-form]").evaluate("form => form.noValidate = true")
        page.get_by_role("button", name="Preview changes").click()
        expect(edit).to_have_attribute("open", "")
        expect(page.locator(".errorlist").first).to_be_visible()
        expect(page.locator("[name=vendor_name]")).to_have_value("Pending source")
        page.locator("[name=entry_date]").fill(entry_date)
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
        expect(edit).to_have_attribute("open", "")
        assert db_query(lambda: Event.objects.filter(kind="edit_animal").count()) == 0
        page.get_by_role("button", name="Confirm and save").click()
        expect(page).to_have_url(live_server.url + url(x))
        expect(summary.get_by_text("Completed source", exact=True)).to_be_visible()
        assert db_query(lambda: Audit.objects.filter(action="edit_animal").count()) == 1
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            expect(edit).not_to_have_attribute("open", "")
            expect(page.get_by_role("button", name="Preview changes")).to_be_hidden()
            check_layout(page, width, active=True)
            edit.locator("summary").click()
            expect(page.get_by_role("button", name="Preview changes")).to_be_visible()
            edit.locator("summary").click()
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
        for width in [1440, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            check_layout(page, width, active=False)
            page.screenshot(path=str(tmp_path / f"animal-exited-{width}.png"), full_page=True)
        assert db_query(lambda: Animal.objects.get(pk=x.pk).status) == "exited"
        engine.close()


def check_layout(page, width, *, active):
    visual_label = page.get_by_text("NLIS Visual ID", exact=True)
    rfid_label = page.get_by_text("NLIS RFID", exact=True)
    expect(visual_label).to_be_visible()
    expect(rfid_label).to_be_visible()
    actions = page.get_by_role("region", name="Animal actions")
    assert actions.locator("a").all_text_contents() == [
        "Replace ear tag",
        "Treat",
        "Procedure",
        "Record observation",
        "View lifetime history",
    ]
    cards = page.locator(".animal-summary-card")
    expect(cards).to_have_count(4)
    assert visual_label.bounding_box()["y"] < rfid_label.bounding_box()["y"]
    assert rfid_label.bounding_box()["y"] < actions.bounding_box()["y"]
    assert (
        actions.bounding_box()["y"] + actions.bounding_box()["height"]
        <= cards.first.bounding_box()["y"]
    )
    boxes = [card.bounding_box() for card in cards.all()]
    if width > 720:
        assert len({round(box["y"]) for box in boxes}) == 1
        assert boxes[0]["x"] < boxes[-1]["x"]
    else:
        assert len({round(box["x"]) for box in boxes}) == 1
        assert all(a["y"] + a["height"] <= b["y"] for a, b in zip(boxes, boxes[1:]))
    exit_card = page.get_by_role("region", name="Farm exit", exact=True)
    expect(exit_card.get_by_role("heading", name="Farm exit", exact=True)).to_be_visible()
    if active:
        expect(exit_card.locator(".summary-card-body")).to_have_text("")
    else:
        for label in ["Farm exit date", "Destination PIC", "Outgoing NVD number", "Sale price"]:
            expect(exit_card.get_by_text(label, exact=True)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
