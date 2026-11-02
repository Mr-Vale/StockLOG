"""Authoritative property/PIC boundary shared by HTTP and domain entry points."""

from django.core.exceptions import PermissionDenied
from .models import Account, Property, PIC


def properties_for(user):
    return Property.objects.all() if user.administrator else user.properties.all()


def validate_context(user):
    fresh = Account.objects.get(pk=user.pk)
    if not fresh.is_active or not user.property_id or not user.pic_id:
        raise PermissionDenied("Select an authorised property and PIC first.")
    if not properties_for(fresh).filter(pk=user.property_id).exists():
        raise PermissionDenied("Property access is no longer available.")
    if not PIC.objects.filter(pk=user.pic_id, property_id=user.property_id).exists():
        raise PermissionDenied("PIC does not belong to this property.")
    return fresh


def scope(model, user):
    validate_context(user)
    qs = model.objects.filter(property_id=user.property_id)
    if model.__name__ in {"Animal", "Mob", "Event", "ImportPreview"}:
        qs = qs.filter(pic_id=user.pic_id)
    return qs
