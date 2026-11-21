"""Context-bound cattle selections; domain callers recheck them under the property lock."""

import uuid

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError

from .context import scope
from .models import Animal


def selected_animals(actor, ids, presence_ids=None):
    from . import clock, services
    from .cattle_services import current_visit

    try:
        ids = [str(uuid.UUID(str(value))) for value in ids]
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Select eligible cattle from Active Cattle.")
    if not ids or len(ids) > 2000 or len(set(ids)) != len(ids):
        raise ValidationError("Select one or more distinct cattle from Active Cattle.")
    animals = list(scope(Animal, actor).filter(pk__in=ids, status="active", purged=False).order_by("pk"))
    if len(animals) != len(ids):
        raise ValidationError("Selected cattle are no longer eligible on this property and PIC. Select again.")
    for animal in animals:
        visit = current_visit(animal, actor)
        services.require_present(animal, clock.now())
        if not animal.identifiers.filter(current=True).exists():
            raise ValidationError("Selected cattle must have a current identifier.")
        if presence_ids is not None and presence_ids.get(str(animal.pk)) != visit.pk:
            raise ValidationError("A selected animal's farm period changed. Select cattle again.")
    return animals


def create_selection(request, purpose, ids):
    from .cattle_services import current_visit

    animals = selected_animals(request.user, ids)
    state = {
        "ids": [str(a.pk) for a in animals],
        "presence_ids": {str(a.pk): current_visit(a, request.user).pk for a in animals},
        "context": request.farm_context,
        "purpose": purpose,
        "key": uuid.uuid4().hex,
    }
    return signing.dumps(state, salt="cattle-selection:" + str(request.user.pk), compress=True)


def read_selection(request, purpose, token):
    state = signing.loads(token, salt="cattle-selection:" + str(request.user.pk), max_age=3600)
    if state["context"] != request.farm_context or state["purpose"] != purpose:
        raise PermissionDenied("Property/PIC or selection workflow changed. Select cattle again.")
    animals = selected_animals(request.user, state["ids"], state["presence_ids"])
    return state, animals


def targets(actor, event, data, *, assignment=False):
    """The signed UUIDs are authoritative; a destination mob is never a source cohort."""
    from . import services

    if "selected_ids" in data:
        animals = selected_animals(actor, data["selected_ids"], data["selected_presence_ids"])
        for animal in animals:
            services.require_present(animal, event.effective_at, event.effective_order)
        return animals
    # Preserve domain callers that target a source mob, except when mob is an update value.
    return services.targets(
        actor, {**data, "mob": None} if assignment else data,
        event.effective_at, event.effective_order,
    )
