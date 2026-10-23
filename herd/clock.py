import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from zoneinfo import ZoneInfo
_override = ContextVar('test_clock', default=None)
def now():
    return _override.get() if _override.get() is not None else int(time.time())
@contextmanager
def at(timestamp):
    token = _override.set(int(timestamp))
    try:
        yield
    finally:
        _override.reset(token)
def calendar_days(timestamp, days, timezone):
    from datetime import timedelta
    return int((datetime.fromtimestamp(timestamp, ZoneInfo(timezone)) + timedelta(days=days)).timestamp())
def local_timestamp(value, timezone, fold=None):
    naive = datetime.fromisoformat(value)
    if naive.tzinfo:
        return int(naive.timestamp())
    z = ZoneInfo(timezone)
    aware = naive.replace(tzinfo=z, fold=fold or 0)
    if datetime.fromtimestamp(aware.timestamp(), z).replace(tzinfo=None) != naive:
        raise ValueError('This local time does not exist because of daylight saving.')
    if naive.replace(tzinfo=z, fold=0).utcoffset() != naive.replace(tzinfo=z, fold=1).utcoffset() and fold is None:
        raise ValueError('This local time occurs twice. Supply an explicit UTC offset.')
    return int(aware.timestamp())
