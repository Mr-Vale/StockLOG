"""Combined detail/edit regressions using synthetic animals and the real service layer."""

from decimal import Decimal

import pytest
from django.core import signing
from django.urls import reverse

from herd import clock
from herd.models import PIC, Animal, Audit, Event, Property
from tests.test_cattle_changes import T, animal, client_for, run

pytestmark = pytest.mark.django_db


def url(x):
    return reverse("animal", args=[x.pk])


def history_url(x):
    return reverse("animal_history", args=[x.pk])


def preview_data(response, token, **changes):
    return {
        **{k: v for k, v in response.context["form"].initial.items() if v is not None},
        "farm_context": token,
        "task": "preview",
        **changes,
    }


def test_summary_gaps_preview_save_and_selected_history(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        x = animal(b, purchase_cost=None, nlis="")
        y = animal(b, 2, vendor_name="Other animal")
        client, token = client_for(b)
        response = client.get(url(x))
        html = response.content.decode()
        assert "<h1>Animal details</h1>" in html
        assert "<strong>NLIS Visual ID</strong>: Not recorded" in html
        for label in [
            "Source name",
            "Source address",
            "Breed or description",
            "Sex",
            "Current mob number",
            "Latest treatment date",
        ]:
            assert f"<dt>{label}</dt><dd>Not recorded</dd>" in html
        assert "<dd>Active</dd>" in html
        assert "<dt>Total cost to date</dt><dd>0.00 AUD</dd>" in html
        assert "Some costs are not recorded" in html
        assert "Complete or correct details" not in html
        assert "<h2>Lifetime history" not in html and "<pre>" not in html
        assert "Revenue" not in html and "P/L" not in html and "P&L" not in html
        assert 'id="farm-exit-heading">Farm exit</h2>' in html
        assert "<dt>Farm exit date</dt>" not in html
        assert "View lifetime history" in html
        form = response.context["form"]
        assert form.fields["source_pic"].disabled and form.fields["nvd"].disabled
        assert form.fields["rfid"].disabled and not form.fields["nlis"].disabled
        payload = preview_data(response, token, vendor_name="Recorded source", purchase_cost="0")
        payload.update(source_pic="0EVIL001", rfid="999999999999999")
        before = Event.objects.count()
        response = client.post(url(x), payload)
        signed = response.context["confirmation"]
        assert Event.objects.count() == before  # Preview rolls back every mutation.
        response = client.post(url(x), {"farm_context": token, "confirmed_payload": signed})
        assert response.status_code == 302 and response.url == url(x)
        response = client.get(response.url)
        assert response.context["summary"]["source_name"] == "Recorded source"
        assert response.context["summary"]["source_pic"] == "0FROM001"
        assert response.context["summary"]["financial_complete"]
        assert response.context["summary"]["cost"] == 0
        assert x.identifiers.get(kind="rfid", current=True).value == "000000000000001"
        assert Audit.objects.filter(action="edit_animal").count() == 1
        history = client.get(history_url(x)).content.decode()
        assert "edit_animal" in history and "Recorded source" in history
        assert "Other animal" not in history and str(y.pk) not in history
        # Old edit links lead to the combined page.
        assert client.get("/action/edit_animal/", {"animal": x.label}).url == url(x)


def test_cost_exit_and_repurchase_use_animal_lifetime_not_group_or_net(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        x, y = animal(b), animal(b, 2, purchase_cost=300)
        run(b, "procedure", dict(animal=x.label, procedure="Examination", fee=25))
        run(
            b,
            "sale",
            dict(
                animals=[x.label, y.label],
                destination_pic="0DEST001",
                destination_name="Buyer",
                nvd="00000002",
                price="400.02",
                price_mode="group",
            ),
        )
        client, token = client_for(b)
        response = client.get(url(x))
        summary = response.context["summary"]
        assert summary["status"] == "Deactive"
        assert summary["cost"] == Decimal("125")
        assert summary["sale_price"] == Decimal("200.01")
        assert summary["destination_pic"] == "0DEST001" and summary["outgoing_nvd"] == "00000002"
        html = response.content.decode()
        assert "<dt>Destination address</dt><dd>Not recorded</dd>" in html
        assert "<dt>Sale price</dt><dd>200.01 AUD</dd>" in html
        assert "Revenue" not in html and "P/L" not in html
        assert "form" not in response.context
        assert client.post(url(x), {"farm_context": token, "task": "preview"}).status_code == 200
        assert Event.objects.filter(kind="edit_animal").count() == 0
    with clock.at(T + 86400):
        run(
            admin,
            "register",
            dict(
                entry_source="repurchase",
                nlis=x.label,
                source_pic="0FROM002",
                nvd="00000003",
                purchase_cost=50,
            ),
        )
        response = client.get(url(x))
        assert response.context["summary"]["cost"] == Decimal("175")
        assert response.context["summary"]["status"] == "Active"
        assert response.context["summary"]["source_pic"] == "0FROM002"
        assert 'id="farm-exit-heading">Farm exit</h2>' in response.content.decode()
        assert "<dt>Farm exit date</dt>" not in response.content.decode()


def test_birth_death_zero_sale_and_transfer_acquisition(farm):
    p, admin, b, _ = farm
    with clock.at(T):
        result = run(b, "register", dict(entry_source="birth", rfid="000000000000007"))
        born = Animal.objects.get(pk=result["animals"][0])
        client, _ = client_for(b)
        response = client.get(url(born))
        assert not response.context["summary"]["purchased"]
        assert "purchase source and incoming NVD do not apply" in response.content.decode()
        assert response.context["summary"]["financial_complete"]
        run(b, "death", dict(animal=born.label, reason="Illness"))
        response = client.get(url(born))
        assert response.context["summary"]["status"] == "Deactive"
        assert not response.context["summary"]["destination_applicable"]
        assert "destination, outgoing NVD and sale price do not apply" in response.content.decode()
        x = animal(b)
        run(b, "sale", dict(animal=x.label, destination_pic="0DEST001", nvd="00000002", price=0))
        assert "<dt>Sale price</dt><dd>0.00 AUD</dd>" in client.get(url(x)).content.decode()
        moved = animal(b, 2)
        dest = PIC.objects.create(property=p, number="0TEST002")
        run(b, "transfer", dict(animal=moved.label, destination_pic=dest.number, nvd="00000003"))
        assert client.get(url(moved)).status_code == 404
        b.pic = dest
        b.save()
        other_client, _ = client_for(b)
        response = other_client.get(url(moved))
        assert response.context["summary"]["status"] == "Active"
        assert response.context["summary"]["source_pic"] == "0FROM001"
        assert response.context["summary"]["cost"] == 100


def test_detail_and_history_access_and_confirmation_binding(farm):
    p, admin, b, _ = farm
    with clock.at(T):
        x, y = animal(b), animal(b, 2)
        client, token = client_for(admin)
        response = client.get(url(x))
        assert not response.context["form"].fields["source_pic"].disabled
        response = client.post(url(x), preview_data(response, token, source_pic="0FROM002"))
        signed = response.context["confirmation"]
        other = client.post(url(y), {"farm_context": token, "confirmed_payload": signed})
        assert "Animal changed" in other.context["error"]
        state = signing.loads(signed, salt="cattle:" + str(admin.pk))
        assert state["data"]["animal"] == x.label
        # Recheck privileges at confirmation, including a role change after preview.
        admin.__class__.objects.filter(pk=admin.pk).update(role="standard")
        assert (
            client.post(url(x), {"farm_context": token, "confirmed_payload": signed}).status_code
            == 403
        )
        assert not Event.objects.filter(kind="edit_animal").exists()
        client, token = client_for(b)
        assert client.post(url(x), {"farm_context": "wrong", "task": "preview"}).status_code == 403
        wrong_pic = PIC.objects.create(property=p, number="0TEST002")
        outsider = Animal.objects.create(property=p, pic=wrong_pic)
        other_property = Property.objects.create(name="Other", address="Other", owner="Other")
        other_pic = PIC.objects.create(property=other_property, number="0TEST003")
        foreign = Animal.objects.create(property=other_property, pic=other_pic)
        purged = Animal.objects.create(property=p, pic=b.pic, purged=True)
        for hidden in [outsider, foreign, purged]:
            assert client.get(url(hidden)).status_code == 404
            assert client.get(history_url(hidden)).status_code == 404
            assert client.post(url(hidden), {"farm_context": token}).status_code == 404
        b.properties.clear()
        assert client.get(url(x)).status_code == 302
        assert client.get(history_url(x)).status_code == 302


def test_missing_source_completion_identifier_history_and_stale_preview(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        x = animal(b)
        # Existing corrections can deliberately clear legacy/missing acquisition fields.
        run(
            admin,
            "edit_animal",
            dict(animal=x.label, update_fields=["source_pic", "nvd"], source_pic="", nvd=""),
        )
        client, token = client_for(admin)
        response = client.get(url(x))
        html = response.content.decode()
        for key in ["Source PIC", "Incoming NVD number"]:
            assert f"<dt>{key}</dt><dd>Not recorded</dd>" in html
        payload = preview_data(
            response, token, source_pic="0FROM002", nvd="00000002", nlis="0TEST001ABC99999"
        )
        preview = client.post(url(x), payload)
        signed = preview.context["confirmation"]
        # An intervening event invalidates the signed preview and keeps the entered form.
        run(b, "observation", dict(animal=x.label, notes="Intervening activity"))
        response = client.post(url(x), {"farm_context": token, "confirmed_payload": signed})
        assert "changed since preview" in response.context["error"]
        assert '<details class="animal-edit" open>' in response.content.decode()
        assert response.context["form"]["source_pic"].value() == "0FROM002"
        assert response.context["summary"]["source_pic"] == ""
        preview = client.post(url(x), payload)
        response = client.post(
            url(x), {"farm_context": token, "confirmed_payload": preview.context["confirmation"]}
        )
        assert response.url == url(x)
        response = client.get(response.url)
        assert response.context["summary"]["visual_id"] == "0TEST001ABC99999"
        assert response.context["summary"]["source_pic"] == "0FROM002"
        assert response.context["summary"]["incoming_nvd"] == "00000002"
        assert x.identifiers.filter(value="0TEST001ABC00001", current=False).exists()
        history = client.get(history_url(x)).content.decode()
        assert "0TEST001ABC00001" in history and "0TEST001ABC99999" in history


def test_latest_treatment_and_cost_compensation(farm):
    from herd.cattle_services import calendar_date
    from tests.test_business_rules import stock

    _, admin, b, _ = farm
    with clock.at(T):
        x = animal(b)
        item = stock(b, kind="chemical")
        run(b, "treat", dict(animal=x.label, item=item, dose=2))
    with clock.at(T + 86400):
        recent = run(b, "treat", dict(animal=x.label, item=item, dose=4))
        client, _ = client_for(b)
        response = client.get(url(x))
        assert response.context["summary"]["treatment_date"] == calendar_date(b, T + 86400)
        assert response.context["summary"]["cost"] == Decimal("103")
        run(b, "reverse", dict(original=recent["event"], reason="Wrong treatment"))
        response = client.get(url(x))
        assert response.context["summary"]["treatment_date"] == calendar_date(b, T)
        assert response.context["summary"]["cost"] == Decimal("101")


def test_edit_disclosure_opens_for_field_and_confirmation_errors(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        x = animal(b)
        client, token = client_for(b)
        response = client.get(url(x))
        assert '<details class="animal-edit" open>' not in response.content.decode()
        response = client.post(url(x), preview_data(response, token, entry_date=""))
        assert response.context["form"].errors["entry_date"]
        assert '<details class="animal-edit" open>' in response.content.decode()
        response = client.post(url(x), {"farm_context": token, "confirmed_payload": "invalid"})
        assert response.context["error"]
        assert '<details class="animal-edit" open>' in response.content.decode()
