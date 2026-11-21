"""Server regressions for exact, context-bound selection and direct saving."""

import uuid

import pytest
from django.core import signing
from django.core.exceptions import ValidationError

from herd import clock
from herd.models import PIC, Animal, Audit, Event, Mob, Property, Restriction
from tests.test_cattle_changes import T, animal, client_for, run, select_token

pytestmark = pytest.mark.django_db


def preview(client, token, selection, operation="bulk_edit", **data):
    route = "/action/bulk_edit/" if operation == "bulk_edit" else "/workflow/exit/"
    return client.post(route, {
        "farm_context": token, "selection_token": selection, "task": "preview", **data,
    })


def confirm(client, token, selection, response, operation="bulk_edit", **data):
    route = "/action/bulk_edit/" if operation == "bulk_edit" else "/workflow/exit/"
    return client.post(route, {
        "farm_context": token, "selection_token": selection,
        "confirmed_payload": response.context["confirmation"], **data,
    })


def mob_of(a):
    return a.memberships.filter(end__isnull=True, superseded=False).values_list("mob_id", flat=True).first()


def test_selection_exactness_mob_assignment_and_unchecked_preservation(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        source = run(admin, "mob", {"name": "Source"})["mob"]
        destination = run(admin, "mob", {"name": "Destination"})["mob"]
        x, y, z = [animal(admin, n, mob=source) for n in [1, 2, 3]]
        client, token = client_for(admin)
        selected = client.post("/action/bulk_edit/", {
            "farm_context": token, "task": "select", "selected_ids": [str(x.pk), str(y.pk)],
        })
        assert selected.status_code == 200
        assert {a.pk for a in selected.context["selected_animals"]} == {x.pk, y.pk}
        assert "animals" not in selected.context["form"].fields
        assert selected.context["form"].fields["mob"].label == "Mob"
        selection = selected.context["selection_token"]
        response = preview(client, token, selection, update_mob="on", mob=destination)
        assert response.context["effects"]["count"] == 2
        assert mob_of(x) == source  # Preview remains transactional and reversible.
        assert confirm(client, token, selection, response).status_code == 302
        assert mob_of(x) == destination and mob_of(y) == destination and mob_of(z) == source
        selection = select_token(client, token, [x, z], "bulk_edit")
        response = preview(client, token, selection, update_breed="on", breed="Angus", mob=source)
        assert confirm(client, token, selection, response).status_code == 302
        assert mob_of(x) == destination and mob_of(z) == source
        assert Audit.objects.filter(action="bulk_edit").count() == 2
        x.refresh_from_db()
        z.refresh_from_db()
        y.refresh_from_db()
        assert x.breed == z.breed == "Angus" and y.breed == ""
        assert client_for(b)[0].get("/animals/?select=bulk_edit").status_code == 403


@pytest.mark.parametrize("purpose", ["exit", "bulk_edit"])
def test_empty_invalid_inactive_and_out_of_scope_selections(farm, purpose):
    p, admin, b, _ = farm
    with clock.at(T):
        x = animal(admin)
        old = animal(admin, 2)
        run(admin, "sale", dict(animal=old.label, destination_pic="0DEST001", nvd="00000001", price=0))
        foreign_pic = PIC.objects.create(property=p, number="0TEST002")
        other = Animal.objects.create(property=p, pic=foreign_pic)
        foreign_property = Property.objects.create(name="Other", owner="Other", address="Other")
        another_pic = PIC.objects.create(property=foreign_property, number="0TEST003")
        foreign = Animal.objects.create(property=foreign_property, pic=another_pic)
        purged = Animal.objects.create(property=p, pic=admin.pic, purged=True)
        client, token = client_for(admin)
        route = "/workflow/exit/" if purpose == "exit" else "/action/bulk_edit/"
        before = Event.objects.count()
        for ids in [[], ["bad"], [str(uuid.uuid4())], [str(x.pk), str(x.pk)],
                    [str(old.pk)], [str(other.pk)], [str(foreign.pk)], [str(purged.pk)]]:
            response = client.post(route, {"farm_context": token, "task": "select", "selected_ids": ids})
            assert response.status_code == 400
        assert Event.objects.count() == before
        assert client.post(route, {"farm_context": token, "task": "preview"}).status_code == 400


def test_selection_is_bound_to_actor_context_purpose_and_preview(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        x, y = animal(admin), animal(admin, 2)
        client, token = client_for(admin)
        first = select_token(client, token, [x], "bulk_edit")
        second = select_token(client, token, [y], "bulk_edit")
        response = preview(client, token, first, update_breed="on", breed="Angus")
        assert "Animal selection changed" in confirm(client, token, second, response).context["error"]
        assert client.post("/workflow/exit/", {"farm_context": token, "selection_token": first}).status_code == 403
        other_client, other_token = client_for(b)
        assert other_client.post("/workflow/exit/", {
            "farm_context": other_token, "selection_token": first,
        }).status_code == 400
        session = client.session
        session["farm_generation"] = "changed"
        session.save()
        token = client.get("/").wsgi_request.farm_context
        assert preview(client, token, first, update_breed="on", breed="Angus").status_code == 403
        assert not Event.objects.filter(kind="bulk_edit").exists()


def test_stale_presence_and_eligibility_are_checked_inside_service(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        x, y = animal(admin), animal(admin, 2)
        client, token = client_for(admin)
        selection = select_token(client, token, [x, y], "bulk_edit")
        response = preview(client, token, selection, update_breed="on", breed="Angus")
        state = signing.loads(response.context["confirmation"], salt="cattle:" + str(admin.pk))
        run(admin, "sale", dict(animal=y.label, destination_pic="0DEST001", nvd="00000001", price=1))
        assert confirm(client, token, selection, response).status_code == 400
        before = Event.objects.count()
        with pytest.raises(ValidationError):
            run(admin, "bulk_edit", state["data"])
        assert Event.objects.count() == before
        x.refresh_from_db()
        assert x.breed == ""
    with clock.at(T + 1):
        run(admin, "register", dict(entry_source="repurchase", nlis=y.label, source_pic="0FROM001", nvd="00000002"))
        assert preview(client, token, selection, update_breed="on", breed="Angus").status_code == 400
        with pytest.raises(ValidationError, match="farm period changed"):
            run(admin, "bulk_edit", state["data"])


def test_selected_exit_warnings_exact_cohort_and_retries(farm):
    _, admin, b, _ = farm
    with clock.at(T):
        x, y = animal(b), animal(b, 2)
        treatment = Event.objects.create(property=b.property, pic=b.pic, actor=b, kind="treat", effective_at=T)
        Restriction.objects.create(event=treatment, animal=x, starts_at=T-1, ends_at=T+86400,
                                   days=1, timezone=b.property.timezone)
        client, token = client_for(b)
        selection = select_token(client, token, [x])
        response = preview(client, token, selection, "exit", mode="sale", exit_date="2026-11-05",
                           destination_pic="0DEST001", nvd="00000001", price="100")
        assert response.context["warnings"][0]["animal"] == x.label
        rejected = confirm(client, token, selection, response, "exit", mode="sale")
        assert "Explicit acceptance" in rejected.context["error"]
        assert confirm(client, token, selection, response, "exit", mode="sale", accept_restriction="on").status_code == 302
        assert confirm(client, token, selection, response, "exit", mode="sale", accept_restriction="on").status_code == 302
        x.refresh_from_db()
        y.refresh_from_db()
        assert x.status == "exited" and y.status == "active"
        assert Audit.objects.filter(action="sale").count() == 1


def test_retired_foreign_mob_and_role_revocation(farm):
    p, admin, b, _ = farm
    with clock.at(T):
        x = animal(b)
        client, token = client_for(admin)
        selection = select_token(client, token, [x], "bulk_edit")
        retired = Mob.objects.create(property=p, pic=b.pic, name="Retired", retired=True)
        another_pic = PIC.objects.create(property=p, number="0TEST002")
        foreign = Mob.objects.create(property=p, pic=another_pic, name="Other PIC")
        for mob in [retired, foreign]:
            response = preview(client, token, selection, update_mob="on", mob=mob.pk)
            assert response.context["form"].errors["mob"]
        response = preview(client, token, selection, update_breed="on", breed="Angus")
        admin.__class__.objects.filter(pk=admin.pk).update(role="standard")
        assert confirm(client, token, selection, response).status_code == 403
        assert not Event.objects.filter(kind="bulk_edit").exists()
