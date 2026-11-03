"""Active PIC enquiry; financial totals remain the reconciled lifetime ledger totals."""

from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from . import clock, reports
from .context import scope
from .home import months_after
from .models import Animal

COLUMNS = [
    ("entry", "FARM ENTRY DATE"),
    ("nlis", "NLIS ID NO."),
    ("rfid", "NLIS RFID NO."),
    ("breed", "BREED/DESCRIPTION"),
    ("sex", "SEX"),
    ("mob", "MOB NUMBER"),
    ("cost", "TOTAL VALUE"),
    ("age", "AGE M-Y"),
    ("safe", "SAFE SALE DATE"),
]


def active_table(request):
    user = request.user
    zone = ZoneInfo(user.property.timezone)
    today = datetime.fromtimestamp(clock.now(), zone).date()
    financials = {
        r["identity"]: r for r in reports.build(user, {"filters": {"status": "active"}})["rows"]
    }
    animals = (
        scope(Animal, user)
        .filter(status="active", purged=False)
        .prefetch_related("identifiers", "presence", "memberships__mob")
    )
    q = request.GET.get("q", "").strip().upper()
    rows = []
    for a in animals:
        tags = list(a.identifiers.all())
        if q and q != str(a.pk).upper() and not any(t.value == q for t in tags):
            continue
        visit = (
            a.presence.filter(pic=user.pic, end__isnull=True)
            .order_by("-start", "-start_order")
            .first()
        )
        entry = datetime.fromtimestamp(visit.start, zone).date() if visit else None
        born = a.dob
        origin = "Date of birth"
        if born is None and a.estimated_weeks is not None and a.age_reference is not None:
            born = datetime.fromtimestamp(a.age_reference, zone).date() - timedelta(
                weeks=a.estimated_weeks
            )
            origin = "Estimated from recorded weeks and reference date"
        if born is None:
            born, origin = entry, "Time since current farm entry; biological age unknown"
        months = None
        if born:
            months = max(0, (today.year - born.year) * 12 + today.month - born.month)
            if months_after(born, months) > today:
                months = max(0, months - 1)
        f = financials[str(a.pk)]
        restriction = (
            a.restrictions.filter(
                event__reversed_by__isnull=True,
                superseded_by__isnull=True,
                starts_at__lte=clock.now(),
            )
            .order_by("-ends_at")
            .first()
        )
        safe = (
            max(today, datetime.fromtimestamp(restriction.ends_at, zone).date())
            if restriction
            else today
        )
        mob = (
            a.memberships.filter(superseded=False, end__isnull=True, start__lte=clock.now())
            .select_related("mob")
            .first()
        )
        row = dict(
            identity=a.pk,
            entry=entry,
            nlis=next((t.value for t in tags if t.current and t.kind == "nlis"), ""),
            rfid=next((t.value for t in tags if t.current and t.kind == "rfid"), ""),
            breed=a.breed,
            sex={"STEER": "S", "Steer": "S"}.get(a.sex, a.sex),
            mob=mob.mob.name if mob else "",
            cost=f["cost"],
            complete=f["financial_complete"],
            age=(today - born).days if born else None,
            age_text=f"{months % 12}-{months // 12}" if months is not None else "—",
            age_origin=origin,
            safe=safe,
        )
        rows.append(row)
    sort = request.GET.get("sort", "entry")
    if sort not in dict(COLUMNS):
        sort = "entry"
    descending = request.GET.get("direction") == "desc"

    def value(r):
        v = r[sort]
        return v.casefold() if isinstance(v, str) else v

    # Missing values always last, in either direction; stable identity resolves ties.
    rows.sort(key=lambda r: str(r["identity"]))
    present = [r for r in rows if r[sort] not in (None, "")]
    missing = [r for r in rows if r[sort] in (None, "")]
    present.sort(key=value, reverse=descending)
    headings = [
        dict(
            label=label,
            active=key == sort,
            direction="descending" if descending else "ascending",
            arrow=(" ▼" if descending else " ▲") if key == sort else "",
            url="?"
            + urlencode(
                dict(
                    q=request.GET.get("q", ""),
                    sort=key,
                    direction="asc"
                    if key == sort and descending
                    else "desc"
                    if key == sort
                    else "asc",
                )
            ),
        )
        for key, label in COLUMNS
    ]
    return {"rows": present + missing, "headings": headings}
