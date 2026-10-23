from datetime import datetime
from zoneinfo import ZoneInfo
from django import template
register=template.Library()
@register.filter
def user_time(value,user):
    try:return datetime.fromtimestamp(int(value),ZoneInfo(user.display_timezone)).strftime(user.date_format)
    except (ValueError,TypeError,OverflowError):return value
