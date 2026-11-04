"""Real Chromium, live Django and MariaDB: responsive and loss/retry workflows."""

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from herd.models import Animal, Mob, Submission

OUT = Path(__file__).resolve().parents[1] / "docs/testing/generated"


def db_query(fn):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connections

    def work():
        try:
            return fn()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(work).result()


def sign_in(page, url, user="B"):
    page.goto(url + "/login/")
    page.locator("[name=username]").fill(user)
    page.locator("[name=password]").fill("Synthetic-Test-Password-2026")
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(
        page.get_by_role(
            "heading", name="Synthetic acceptance property Property Summary"
        )
    ).to_be_visible()


def browser(p, **kwargs):
    return p.chromium.launch(
        executable_path="/usr/bin/chromium",
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
        **kwargs,
    )


@pytest.mark.django_db(transaction=True)
def test_phone_registration_desktop_reports_and_admin_boundaries(farm, live_server):
    with sync_playwright() as p:
        engine = browser(p)
        context = engine.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        sign_in(page, live_server.url)
        assert not page.get_by_role("link", name="Administration", exact=True).count()
        page.goto(live_server.url + "/action/register/")
        page.locator("[name=nlis]").fill("0TEST000BRO00001")
        page.locator("[name=source_pic]").fill("0FROM001")
        page.locator("[name=nvd]").fill("00000001")
        page.locator("[name=purchase_cost]").fill("100")
        page.locator("[name=sex]").select_option("M")
        page.get_by_role("button", name="Add to list").click()
        expect(page.get_by_role("heading", name="Review animals (1)")).to_be_visible()
        page.get_by_role("button", name="Save animals", exact=True).click()
        expect(page.get_by_role("heading", name="Saved and confirmed")).to_be_visible()
        assert db_query(lambda: Animal.objects.count()) == 1
        page.goto(live_server.url + "/animals/")
        expect(page.get_by_role("link", name="0TEST000BRO00001")).to_be_visible()
        OUT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUT / "phone-animals.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.goto(live_server.url + "/reports/")
        expect(page.get_by_role("heading", name="Reports", exact=True)).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role("link", name="Download Excel").click()
        assert download.value.suggested_filename.endswith(".xlsx")
        page.screenshot(path=str(OUT / "desktop-reports.png"), full_page=True)
        context.close()
        engine.close()


@pytest.mark.django_db(transaction=True)
def test_offline_reload_download_and_lost_commit_retry_once(farm, live_server):
    with sync_playwright() as p:
        engine = browser(p)
        context = engine.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        sign_in(page, live_server.url)
        page.evaluate("navigator.serviceWorker.ready")
        page.reload()
        page.wait_for_function("navigator.serviceWorker.controller !== null")
        page.goto(live_server.url + "/action/mob/")
        page.locator("[name=name]").fill("Recovered mob")
        context.set_offline(True)
        page.get_by_role("button", name="Preview effects").click()
        expect(page.locator("#recovery")).to_contain_text("Not confirmed")
        raw = page.evaluate('Object.values(localStorage).join(" ")')
        assert "Recovered mob" not in raw  # encrypted account-scoped payload
        page.reload()
        expect(
            page.get_by_role("heading", name="Connection unavailable")
        ).to_be_visible()
        expect(page.locator("#recovery")).to_contain_text("Recovered mob")
        with page.expect_download() as download:
            page.get_by_role("button", name="Download readable input").click()
        assert "Recovered mob" in Path(download.value.path()).read_text()
        context.set_offline(False)
        page.get_by_role("button", name="Retry same submission").click()
        expect(
            page.get_by_role("heading", name="Review before confirming")
        ).to_be_visible()
        page.wait_for_function("window.stocklogRecoveryReady === true")

        # Commit reaches Django; transport drops the response afterward.
        def lose_response(route):
            if route.request.method == "POST" and "confirmed_payload" in (
                route.request.post_data or ""
            ):
                response = route.fetch()
                assert response.status == 200
                route.abort("connectionreset")
            else:
                route.continue_()

        page.route("**/action/mob/", lose_response)
        with page.expect_event(
            "requestfailed",
            predicate=lambda req: req.method == "POST" and "/action/mob/" in req.url,
        ):
            page.get_by_role("button", name="Confirm and save").click()
        expect(page.locator("#recovery")).to_contain_text("Not confirmed")
        assert db_query(lambda: Mob.objects.filter(name="Recovered mob").count()) == 1
        page.unroute("**/action/mob/", lose_response)
        page.get_by_role("button", name="Retry same submission").click()
        expect(page.get_by_role("heading", name="Saved and confirmed")).to_be_visible()
        assert db_query(lambda: Mob.objects.filter(name="Recovered mob").count()) == 1
        assert (
            db_query(lambda: Submission.objects.filter(actor_id=farm[2].id).count())
            == 1
        )
        context.close()
        engine.close()


@pytest.mark.django_db(transaction=True)
def test_pending_input_is_not_shown_to_another_account(farm, live_server):
    with sync_playwright() as p:
        engine = browser(p)
        context = engine.new_context()
        page = context.new_page()
        sign_in(page, live_server.url)
        page.goto(live_server.url + "/action/mob/")
        page.locator("[name=name]").fill("B private pending")
        context.set_offline(True)
        page.get_by_role("button", name="Preview effects").click()
        expect(page.locator("#recovery")).to_contain_text("B private pending")
        context.set_offline(False)
        page.get_by_role("button", name="Discard local input").click()
        page.goto(live_server.url + "/")
        page.get_by_role("button", name="Sign out B").click()
        sign_in(page, live_server.url, "C")
        assert "B private pending" not in page.content()
        assert not page.evaluate(
            'Object.keys(localStorage).some(k=>k.includes("stocklog.pending"))'
        )
        context.close()
        engine.close()


@pytest.mark.django_db(transaction=True)
def test_property_homepage_screenshots_and_transition(farm, live_server):
    from herd.models import PIC

    p, admin, b, _ = farm
    second = PIC.objects.create(property=p, number="0TEST002")
    from datetime import date, timedelta
    from .test_foundations import arrival, run

    first_mob = run(admin, "mob", {"name": "First PIC mob"})["mob"]
    arrival(
        admin,
        tag="0TEST000HOM00001",
        breed="Angus",
        sex="F",
        mob=first_mob,
        dob=(date.today() - timedelta(days=30)).isoformat(),
    )
    admin.pic = second
    second_mob = run(admin, "mob", {"name": "Second PIC mob"})["mob"]
    for i, (breed, sex, days) in enumerate(
        [
            ("Angus", "M", 60),
            ("Angus", "F", 180),
            ("Hereford", "STEER", 500),
            ("Hereford", "F", 900),
        ],
        start=2,
    ):
        arrival(
            admin,
            tag=f"0TEST000HOM{i:05d}",
            breed=breed,
            sex=sex,
            mob=second_mob,
            dob=(date.today() - timedelta(days=days)).isoformat(),
        )
    # Unsaved users must select first. Admin fixtures keep a valid saved default.
    b.property = None
    b.pic = None
    b.save(update_fields=["property", "pic"])
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        engine = browser(playwright)
        page = engine.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(live_server.url + "/login/")
        page.locator("[name=username]").fill("B")
        page.locator("[name=password]").fill("Synthetic-Test-Password-2026")
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(
            page.get_by_role("heading", name="Choose your property and PIC")
        ).to_be_visible()
        page.screenshot(
            path=str(OUT / "property-selection-desktop.png"), full_page=True
        )
        page.locator("#property-select").select_option(str(p.pk))
        # Exercise the client timer without waiting in real time. Server deadline is separately tested.
        page.clock.install()
        page.locator("#pic-select").select_option(str(second.pk))
        expect(page.locator("#switching")).to_be_visible()
        expect(page.locator("#farm-data")).to_be_hidden()
        expect(page.locator("#property-select")).to_be_enabled()
        page.clock.fast_forward(4000)
        expect(page.locator("#switching")).to_be_visible()
        # Advance server session deadline as well; no production test hook is introduced.
        session = page.context.cookies()
        cookie = next(c["value"] for c in session if c["name"] == "sessionid")

        def release():
            from django.contrib.sessions.backends.db import SessionStore

            s = SessionStore(session_key=cookie)
            s["farm_ready_at"] = 0
            s.save()

        db_query(release)
        page.clock.fast_forward(2000)
        expect(
            page.get_by_role(
                "heading", name="Synthetic acceptance property Property Summary"
            )
        ).to_be_visible()
        page.screenshot(path=str(OUT / "property-home-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUT / "property-home-mobile.png"), full_page=True)
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        engine.close()
