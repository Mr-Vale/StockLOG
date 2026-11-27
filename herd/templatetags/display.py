from datetime import datetime
from zoneinfo import ZoneInfo

from django import template

register = template.Library()


@register.filter
def user_time(value, user):
    try:
        return datetime.fromtimestamp(int(value), ZoneInfo(user.display_timezone)).strftime(
            user.date_format
        )
    except (ValueError, TypeError, OverflowError):
        return value


# Display rounding never changes the Decimal values passed to domain services.
@register.filter
def compact(value):
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
    if value is None or value == "":
        return "Not recorded"
    try:
        with localcontext() as ctx:
            ctx.prec = 60
            amount = Decimal(str(value))
            if not amount.is_finite():
                return "Not recorded"
            rounded = amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            return format(rounded if rounded else Decimal(0), "f").rstrip("0").rstrip(".") if "." in format(rounded, "f") else format(rounded, "f")
    except (InvalidOperation, ValueError, TypeError):
        return value


@register.filter
def money(value):
    return "Not recorded" if value is None or value == "" else "$" + str(compact(value))


@register.filter
def financial_value(value, key):
    monetary = {
        "purchase", "sale", "feed", "chemical", "procedure", "vet", "cost", "revenue",
        "profit", "value", "amount", "package_price", "unit_cost", "purchase_cost",
        "price", "fee", "cost_per_stock_unit", "cost_per_dose_unit",
    }
    if key in monetary and value is not None and not isinstance(value, (dict, list, tuple, bool)):
        from decimal import Decimal, InvalidOperation
        try:
            if Decimal(str(value)).is_finite():
                return money(value)
        except (InvalidOperation, ValueError, TypeError):
            pass
    return value


@register.filter
def financial_tree(value):
    if isinstance(value, dict):
        return {key: financial_tree(financial_value(v, key)) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [financial_tree(v) for v in value]
    return value
