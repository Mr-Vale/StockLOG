"""Authorised, property-serialised business transactions; no UI/database shortcuts."""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q, Sum
from . import clock
from .models import (Property, Account, Event, Submission, Animal, Identifier, Presence, Mob, Membership, Participant, Allocation, AttributeChange, Inventory, StockPosting, Restriction, Audit, ReportTemplate, ImportPreview)
QTY = Decimal('0.000000000001')

def clean(value):
    return json.loads(json.dumps(value, default=str, sort_keys=True))

def number(value, *, positive=False, nonnegative=False):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Enter a valid decimal number.')
    if not d.is_finite() or abs(d) >= Decimal('1e17') or d.as_tuple().exponent < -12:
        raise ValidationError('Number must be finite, within supported bounds and at most 12 decimal places.')
    if positive and d <= 0 or nonnegative and d < 0:
        raise ValidationError('Quantity must be positive.' if positive else 'Value cannot be negative.')
    return d

def rounded(value):
    with localcontext() as c:
        c.prec = 60
        return Decimal(value).quantize(QTY, rounding=ROUND_HALF_UP)

def split(total, animals):
    ordered = sorted(animals, key=lambda a: str(a.id))
    if not ordered:
        raise ValidationError('No eligible animals at this event time.')
    with localcontext() as c:
        c.prec = 60
        units = int(rounded(abs(total)) / QTY)
        per, remainder = divmod(units, len(ordered))
        sign = -1 if total < 0 else 1
        return [(a, sign * (per + (i < remainder)) * QTY) for i, a in enumerate(ordered)]

def audit(actor, action, event=None, **details):
    return Audit.objects.create(property=actor.property, actor=actor, action=action, event=event, details=clean(details))

def administrator(actor):
    if not actor.administrator:
        raise PermissionDenied('Administrator access is required.')

def scoped(model, actor, pk):
    try:
        return model.objects.get(property=actor.property, pk=pk)
    except (model.DoesNotExist, ValueError, ValidationError):
        raise ValidationError('Record is unavailable in this property.')

def instant(event):
    return event.effective_at

def present(animal, at):
    return animal.presence.filter(start__lte=at).filter(Q(end__isnull=True) | Q(end__gt=at)).exists()

def require_present(animal, at):
    if animal.purged or not present(animal, at):
        raise ValidationError(f'{animal.label} was off-property or dead at the event time.')

def find_animal(actor, identifier):
    value = str(identifier).strip().upper()
    found = Identifier.objects.filter(value=value, animal__property=actor.property).select_related('animal').first()
    if not found or found.animal.purged:
        raise ValidationError('Animal identifier was not found.')
    return found.animal

def members(actor, mob_id, at):
    mob = scoped(Mob, actor, mob_id)
    ids = Membership.objects.filter(mob=mob, start__lte=at, superseded=False).filter(Q(end__isnull=True) | Q(end__gt=at)).values_list('animal_id', flat=True)
    animals = list(Animal.objects.filter(property=actor.property, id__in=ids, purged=False).order_by('id'))
    for a in animals:
        require_present(a, at)
    if not animals:
        raise ValidationError('No eligible mob members at the event time.')
    return animals

def targets(actor, data, at):
    if data.get('mob'):
        return members(actor, data['mob'], at)
    values = data.get('animals') or [data.get('animal')]
    animals = []
    for v in values:
        if not v:
            raise ValidationError('Select an animal or a mob.')
        a = find_animal(actor, v)
        require_present(a, at)
        if a not in animals:
            animals.append(a)
    return animals

def participants(event, animals):
    for a in animals:
        Participant.objects.get_or_create(event=event, animal=a, defaults={'snapshot': {'label': a.label, 'breed': a.breed, 'sex': a.sex}})

def allocate(event, animals, total, category, unknown=False):
    participants(event, animals)
    for animal, amount in split(total, animals):
        Allocation.objects.create(event=event, animal=animal, amount=amount, category=category, unknown=unknown)

def validate_identifier(kind, value):
    value = str(value or '').strip().upper()
    if kind == 'nlis' and len(value) != 16 or kind == 'rfid' and not re.fullmatch(r'[0-9]{15}', value):
        raise ValidationError('NLIS must be exactly 16 characters; RFID exactly 15 ASCII digits.')
    return value

def attach(event, animal, kind, value, reason=''):
    value = validate_identifier(kind, value)
    old = Identifier.objects.filter(kind=kind, value=value).first()
    if old and old.animal_id != animal.id:
        raise ValidationError('Identifier is permanently reserved to another animal. Administrator conflict review required; animals are never merged.')
    Identifier.objects.filter(animal=animal, kind=kind, current=True).exclude(value=value).update(current=False, retired_at=event.effective_at)
    if old:
        old.current, old.retired_at = True, None
        old.save(update_fields=['current', 'retired_at'])
    else:
        Identifier.objects.create(animal=animal, kind=kind, value=value, effective_at=event.effective_at, event=event, reason=reason)

def execute(actor, key, kind, data, expected_version=None):
    if not actor.is_active or not actor.property_id:
        raise PermissionDenied('An active property account is required.')
    if not key or len(str(key)) > 80:
        raise ValidationError('A stable submission identifier is required.')
    payload = clean(data)
    digest = hashlib.sha256(json.dumps({'kind': kind, 'data': payload}, sort_keys=True).encode()).hexdigest()
    with transaction.atomic(), localcontext() as ctx:
        ctx.prec = 60
        prop = Property.objects.select_for_update().get(pk=actor.property_id)
        prior = Submission.objects.filter(property=prop, actor=actor, key=str(key)).first()
        if prior:
            if prior.digest != digest:
                raise ValidationError('This submission identifier belongs to different input. Start a new reviewed submission.')
            return prior.result
        if expected_version is not None and int(expected_version) != prop.version:
            raise ValidationError('Property records changed since preview. Review the updated stock, membership and effects before confirming.')
        at = int(payload.get('effective_at', clock.now()))
        if at > clock.now():
            raise ValidationError('Future-dated business events are not accepted.')
        handler = HANDLERS.get(kind)
        if not handler:
            raise ValidationError('Unknown operation.')
        event = Event.objects.create(property=prop, actor=actor, kind=kind, effective_at=at, effective_order=prop.version + 1, details=payload)
        result = handler(actor, event, payload) or {}
        event.details = clean({**payload, **result})
        event.save()
        prop.version += 1
        prop.save(update_fields=['version'])
        result = clean({**result, 'event': event.id, 'version': prop.version})
        Submission.objects.create(property=prop, actor=actor, key=str(key), digest=digest, event=event, result=result)
        audit(actor, kind, event, input=payload, effects=result)
        return result

def preview(actor, kind, data):
    with transaction.atomic():
        prop = Property.objects.select_for_update().get(pk=actor.property_id)
        version = prop.version
        result = execute(actor, 'preview-' + __import__('uuid').uuid4().hex, kind, data, version)
        result['allocations'] = list(Allocation.objects.filter(event_id=result['event']).values('animal_id', 'category', 'amount'))
        result['stock'] = list(StockPosting.objects.filter(event_id=result['event']).values('item_id', 'quantity', 'value'))
        transaction.set_rollback(True)
    return {'version': version, 'effects': clean(result)}

def register(actor, event, data):
    rows = data.get('rows') or [data]
    if not rows or len(rows) > 2000:
        raise ValidationError('Import must contain 1–2000 selected rows.')
    result = []
    seen = set()
    for row in rows:
        nlis, rfid = row.get('nlis', ''), row.get('rfid', '')
        if not (nlis or rfid):
            raise ValidationError('At least one animal identifier is required.')
        for kind, val in [('nlis', nlis), ('rfid', rfid)]:
            if val:
                v = validate_identifier(kind, val)
                if (kind, v) in seen:
                    raise ValidationError('Duplicate identifier within the selected import.')
                seen.add((kind, v))
        at = int(row.get('effective_at', event.effective_at))
        if at > clock.now():
            raise ValidationError('Arrival cannot be future-dated.')
        source = row.get('entry_source', 'purchase')
        if source not in ['purchase', 'birth', 'repurchase']:
            raise ValidationError('Choose purchase, birth or repurchase.')
        if source != 'birth' and (not row.get('source_pic') or not row.get('nvd')):
            raise ValidationError('Purchased arrivals require source PIC and NVD.')
        if source == 'birth':
            validate_identifier('nlis', row.get('mother_nlis', ''))
            cost = Decimal(0)
        else:
            cost = number(row['purchase_cost'], nonnegative=True) if row.get('purchase_cost') not in [None, ''] else None
        linked = list(Identifier.objects.filter(Q(kind='nlis', value=str(nlis).strip().upper()) | Q(kind='rfid', value=str(rfid).strip())).values_list('animal_id', flat=True).distinct())
        if len(linked) > 1:
            raise ValidationError('The supplied tags belong to different animals. Administrator resolution required.')
        if linked:
            if source != 'repurchase':
                raise ValidationError('An identifier is already permanently reserved; choose repurchase only for the same exited animal.')
            a = scoped(Animal, actor, linked[0])
            if a.status != 'exited' or a.presence.filter(Q(end__isnull=True) | Q(end__gte=at)).exists():
                raise ValidationError('Only a previously sold animal may be repurchased after its latest exit.')
        else:
            if source == 'repurchase':
                raise ValidationError('Repurchase requires an existing animal identity.')
            a = Animal.objects.create(property=actor.property)
        for field in ['breed', 'sex', 'mother_nlis']:
            if row.get(field):
                setattr(a, field, row[field])
        if row.get('dob'):
            a.dob = date.fromisoformat(str(row['dob']))
        if row.get('estimated_weeks') not in [None, '']:
            weeks = int(row['estimated_weeks'])
            if weeks < 0:
                raise ValidationError('Age cannot be negative.')
            a.estimated_weeks, a.age_reference = weeks, at
        a.status = 'active'
        a.save()
        if nlis:
            attach(event, a, 'nlis', nlis)
        if rfid:
            attach(event, a, 'rfid', rfid)
        Presence.objects.create(animal=a, start=at, arrival=event)
        allocate(event, [a], -(cost or 0), 'purchase', unknown=cost is None)
        if row.get('mob'):
            mob = scoped(Mob, actor, row['mob'])
            Membership.objects.create(animal=a, mob=mob, start=at, event=event)
        result.append(str(a.id))
    return {'animals': result, 'count': len(result)}

def mob_create(actor, event, data):
    name = str(data.get('name', '')).strip()
    if not name:
        raise ValidationError('Mob name is required.')
    m = Mob.objects.create(property=actor.property, name=name)
    return {'mob': m.id, 'name': m.name}

def move(actor, event, data):
    at = event.effective_at
    historical = at < clock.now()
    if historical:
        administrator(actor)
        if not data.get('administration'):
            raise ValidationError('Use the historical administration workflow.')
    destination = scoped(Mob, actor, data['destination']) if data.get('destination') else None
    animals = targets(actor, data, at)
    before = []
    for a in animals:
        rows = list(a.memberships.filter(superseded=False).filter(Q(end__isnull=True) | Q(end__gt=at)).order_by('start'))
        before.extend([{'id': r.id, 'animal': str(a.id), 'mob': r.mob_id, 'start': r.start, 'end': r.end} for r in rows])
        next_start = min([r.start for r in rows if r.start > at], default=None)
        for r in rows:
            if r.start <= at:
                r.end = at
                r.save(update_fields=['end'])
        if destination:
            Membership.objects.create(animal=a, mob=destination, start=at, end=next_start, event=event)
    event.before = {'memberships': before}
    participants(event, animals)
    affected = reconcile_membership(actor, event) if historical else []
    return {'animals': [str(a.id) for a in animals], 'historical': historical, 'corrected_events': affected}

def replace_tag(actor, event, data):
    if not data.get('reason') or not (data.get('nlis') or data.get('rfid')):
        raise ValidationError('New tag and replacement reason are required.')
    a = find_animal(actor, data['animal'])
    require_present(a, event.effective_at)
    event.before = {'identifiers': list(a.identifiers.filter(current=True).values('kind', 'value'))}
    for kind in ['nlis', 'rfid']:
        if data.get(kind):
            attach(event, a, kind, data[kind], data['reason'])
    participants(event, [a])
    return {'animal': str(a.id), 'current': list(a.identifiers.filter(current=True).values('kind', 'value'))}

def edit_animal(actor, event, data):
    a = find_animal(actor, data['animal'])
    require_present(a, event.effective_at)
    changed = {}
    for field in ['breed', 'sex', 'estimated_weeks', 'dob']:
        if data.get(field) not in [None, '']:
            before = getattr(a, field)
            after = int(data[field]) if field == 'estimated_weeks' else date.fromisoformat(data[field]) if field == 'dob' else str(data[field])
            if field == 'estimated_weeks' and after < 0:
                raise ValidationError('Age cannot be negative.')
            setattr(a, field, after)
            changed[field] = str(before or '')
            AttributeChange.objects.create(event=event, animal=a, field=field, before=str(before or ''), after=str(after))
    if 'estimated_weeks' in changed:
        changed['age_reference'] = a.age_reference
        a.age_reference = event.effective_at
    if data.get('purchase_cost') not in [None, '']:
        price = number(data['purchase_cost'], nonnegative=True)
        presence = a.presence.filter(start__lte=event.effective_at).order_by('-start').first()
        purchase = a.allocations.filter(category='purchase', event=presence.arrival).first()
        if purchase is None:
            raise ValidationError('No purchase record is available for this presence cycle.')
        prior = -sum(a.allocations.filter(category='purchase', event__effective_at__gte=presence.start).values_list('amount', flat=True))
        allocate(event, [a], -(price-prior), 'purchase')
        changed['purchase_cost'] = str(prior)
        if purchase.unknown and purchase.resolved_by_id is None:
            purchase.resolved_by = event
            purchase.save(update_fields=['resolved_by'])
    a.save()
    event.before = changed
    participants(event, [a])
    return {'animal': str(a.id)}

def depart(actor, event, data):
    animals = targets(actor, data, event.effective_at)
    death = event.kind == 'death'
    if death and not data.get('reason'):
        raise ValidationError('Death reason is required.')
    if not death and (not data.get('destination_pic') or not data.get('nvd') or data.get('price') in [None, '']):
        raise ValidationError('Sales require price, destination PIC and NVD.')
    restrictions = []
    before = []
    for a in animals:
        later = Participant.objects.filter(animal=a, event__effective_at__gt=event.effective_at, event__reversed_by__isnull=True).exclude(event=event)
        if later.exists():
            raise ValidationError('Later events conflict with this departure. Review a coherent correction first.')
        active = a.restrictions.filter(event__reversed_by__isnull=True, superseded_by__isnull=True, starts_at__lte=event.effective_at, ends_at__gt=event.effective_at)
        if active.exists():
            restrictions.append(a.label)
        p = a.presence.get(start__lte=event.effective_at, end__isnull=True)
        before.append({'animal': str(a.id), 'presence': p.id, 'memberships': list(a.memberships.filter(superseded=False, end__isnull=True).values_list('id', flat=True))})
        p.end, p.departure = event.effective_at, event
        p.save()
        a.memberships.filter(superseded=False, end__isnull=True).update(end=event.effective_at)
        a.status = 'dead' if death else 'exited'
        a.save(update_fields=['status'])
    if restrictions and not data.get('accept_restriction'):
        raise ValidationError('Departure is within a restriction. Explicit acceptance is required: ' + ', '.join(restrictions))
    price = Decimal(0) if death else number(data['price'], nonnegative=True)
    total = price if data.get('price_mode') == 'group' else price * len(animals)
    event.before = {'departures': before}
    allocate(event, animals, total, 'sale')
    return {'count': len(animals), 'revenue': total, 'restriction_acceptance': restrictions}

UNITS = {'kg': ('kg', Decimal(1)), 'g': ('g', Decimal(1)), 'L': ('mL', Decimal(1000)), 'mL': ('mL', Decimal(1)), 'unit': ('unit', Decimal(1))}

def receipt(actor, event, data):
    kind = data['kind']
    if kind not in ['feed', 'chemical'] or not str(data.get('name', '')).strip():
        raise ValidationError('Inventory kind and product name are required.')
    size = number(data['package_size'], positive=True)
    price = number(data['package_price'], nonnegative=True)
    count = number(data['packages'], positive=True)
    unit = data.get('stock_unit', 'kg')
    if unit not in UNITS:
        raise ValidationError('Unsupported stock unit.')
    base_unit, factor = UNITS[unit]
    if unit == 'g' and kind == 'feed':
        base_unit, factor = 'kg', Decimal('0.001')
    if unit == 'kg' and kind == 'chemical':
        base_unit, factor = 'g', Decimal(1000)
    base = size * factor
    date_kind = data.get('date_kind', '')
    if date_kind not in ['', 'expiry', 'DOM']:
        raise ValidationError('Choose expiry or DOM explicitly.')
    if bool(date_kind) != bool(data.get('date_value')):
        raise ValidationError('Date and explicit date type must be supplied together.')
    spec = {'kind': kind, 'name': data['name'].strip(), 'feed_type': data.get('feed_type', ''), 'package_size': str(size), 'package_price': str(price), 'stock_unit': unit, 'dose_unit': data.get('dose_unit', 'mL'), 'batch': data.get('batch', ''), 'date_kind': date_kind, 'date_value': data.get('date_value') or '', 'category': data.get('category', 'veterinary'), 'restriction_days': int(data.get('restriction_days') or 0)}
    if spec['restriction_days'] < 0:
        raise ValidationError('Restriction days cannot be negative.')
    signature = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    values = dict(spec)
    values['date_value'] = date.fromisoformat(spec['date_value']) if spec['date_value'] else None
    item, created = Inventory.objects.get_or_create(property=actor.property, signature=signature, defaults={**values, 'base_unit': base_unit, 'base_per_package': base, 'unit_cost': price / base, 'storage': data.get('storage', '')})
    if item.retired:
        raise ValidationError('This item is retired. Use an explicit inventory correction before selecting it again.')
    post_stock(event, item, count * base)
    return {'item': item.id, 'created': created, 'received': count * base, 'balance': item.balance, 'cost': price * count, 'base_unit': base_unit}

def post_stock(event, item, qty):
    item.balance = rounded(item.balance + qty)
    if item.kind == 'chemical' and item.balance < 0:
        raise ValidationError('Insufficient chemical stock. No quantity, dose or allocation was changed.')
    item.save(update_fields=['balance'])
    StockPosting.objects.create(event=event, item=item, quantity=qty, value=rounded(qty * item.unit_cost))
    # A backdated insertion cannot make a previously accepted later event invalid.
    postings = item.postings.select_related('event').order_by('event__effective_at', 'event__effective_order', 'id')
    balance = Decimal(0)
    for p in postings:
        if p.quantity < 0 and (item.kind == 'chemical' and balance + p.quantity < 0 or item.kind == 'feed' and p.event.kind == 'feed' and balance <= 0):
            raise ValidationError('This backdated stock change conflicts with a later accepted event. Review corrections first.')
        balance += p.quantity


def stocktake(actor, event, data):
    if not data.get('reason'):
        raise ValidationError('A stocktake/correction reason is required.')
    item = scoped(Inventory, actor, data['item'])
    actual = number(data['actual'])
    if item.kind == 'chemical' and actual < 0:
        raise ValidationError('Chemical stock cannot be negative.')
    event.before = {'balance': str(item.balance)}
    post_stock(event, item, actual - item.balance)
    return {'item': item.id, 'balance': item.balance}

def retire(actor, event, data):
    item = scoped(Inventory, actor, data['item'])
    event.before = {'retired': item.retired}
    item.retired = bool(data.get('retired', True))
    item.save(update_fields=['retired'])
    return {'item': item.id, 'retired': item.retired}

def feed(actor, event, data):
    animals = members(actor, data['mob'], event.effective_at)
    item = scoped(Inventory, actor, data['item'])
    if item.kind != 'feed' or item.retired or item.balance <= 0:
        raise ValidationError('Choose an available feed item with positive starting stock.')
    amount = number(data['quantity'], positive=True)
    mode = data.get('mode', 'total_kg')
    if mode == 'bales':
        qty = amount * item.base_per_package
    elif mode == 'kg_per_head':
        qty = amount * len(animals)
    elif mode == 'total_kg':
        if item.base_unit != 'kg':
            raise ValidationError('Selected feed is not measured in kg. Use stock units.')
        qty = amount
    elif mode == 'stock_units':
        qty = amount * UNITS[item.stock_unit][1]
    else:
        raise ValidationError('Unknown feeding unit mode.')
    cost = rounded(qty * item.unit_cost)
    post_stock(event, item, -qty)
    allocate(event, animals, -cost, 'feed')
    return {'count': len(animals), 'consumed': qty, 'cost': cost, 'unit_cost': item.unit_cost, 'balance': item.balance, 'storage': data.get('storage', item.storage), 'responsible_name': data.get('responsible_name') or actor.get_full_name() or actor.username}

def treat(actor, event, data):
    animals = targets(actor, data, event.effective_at)
    performing = data.get('administered_by') or actor.get_full_name() or actor.username
    cost, qty = Decimal(0), Decimal(0)
    days = 0
    product = {}
    if data.get('item'):
        item = scoped(Inventory, actor, data['item'])
        if item.kind != 'chemical' or item.retired:
            raise ValidationError('Choose an active chemical item.')
        dose = number(data.get('dose'), positive=True)
        unit = data.get('dose_unit') or item.dose_unit
        if unit not in UNITS:
            raise ValidationError('Unsupported dose unit.')
        base_unit, factor = UNITS[unit]
        if unit == 'kg':
            base_unit, factor = 'g', Decimal(1000)
        if base_unit != item.base_unit:
            raise ValidationError('Stock and dose units are incompatible.')
        qty = dose * factor * len(animals)
        local_day = __import__('datetime').datetime.fromtimestamp(event.effective_at, ZoneInfo(actor.property.timezone)).date()
        if item.date_kind == 'expiry' and item.date_value < local_day and not data.get('expired_override'):
            raise ValidationError('Expired product requires an explicit logged override.')
        if item.date_kind == 'expiry' and item.date_value < local_day and not data.get('override_reason'):
            raise ValidationError('Expired-use override reason is required.')
        if qty > item.balance:
            raise ValidationError('Insufficient chemical stock. Enter the actual dose or correct stock; the system never adjusts doses.')
        post_stock(event, item, -qty)
        cost = rounded(qty * item.unit_cost)
        days = item.restriction_days
        product = {'product_name': item.name, 'batch': item.batch, 'date_kind': item.date_kind, 'date_value': item.date_value, 'unit_cost': item.unit_cost}
        allocate(event, animals, -cost, 'chemical')
    elif event.kind == 'treat':
        raise ValidationError('Chemical treatment requires a product; use Procedure for a non-chemical activity.')
    fee = number(data.get('fee') or 0, nonnegative=True)
    fee_total = fee if data.get('fee_mode') == 'group' else fee * len(animals)
    if event.kind in ['procedure', 'vet'] or fee_total:
        allocate(event, animals, -fee_total, 'vet' if event.kind == 'vet' else 'procedure')
    participants(event, animals)
    if data.get('procedure') == 'castration':
        for a in animals:
            if a.sex.upper() not in ['M', 'MALE', 'BULL']:
                raise ValidationError('Castration requires a male animal; previous sex remains in history.')
            AttributeChange.objects.create(event=event, animal=a, field='sex', before=a.sex, after='STEER')
            a.sex = 'STEER'
            a.save(update_fields=['sex'])
    if days:
        for a in animals:
            Restriction.objects.create(event=event, animal=a, starts_at=event.effective_at, ends_at=clock.calendar_days(event.effective_at, days, actor.property.timezone), days=days, timezone=actor.property.timezone)
    return {'count': len(animals), 'consumed': qty, 'cost': cost + fee_total, 'combined_restriction_days': days, 'administered_by': performing, **product}

def observation(actor, event, data):
    if not data.get('notes'):
        raise ValidationError('Observation notes are required.')
    animals = targets(actor, data, event.effective_at)
    participants(event, animals)
    return {'count': len(animals), 'cost': '0'}

def reconcile_membership(actor, correction):
    affected = []
    originals = Event.objects.filter(property=actor.property, kind__in=['feed', 'treat', 'procedure', 'vet'], effective_at__gte=correction.effective_at, reversed_by__isnull=True).exclude(pk=correction.pk)
    for original in originals:
        if not original.details.get('mob'):
            continue
        animals = members(actor, original.details['mob'], original.effective_at)
        related = list(Event.objects.filter(property=actor.property, details__original=str(original.id), kind='allocation_correction').order_by('submitted_at', 'effective_order', 'id'))
        old_ids = {__import__('uuid').UUID(x) for x in related[-1].details['after_members']} if related else set(original.participants.values_list('animal_id', flat=True))
        new_ids = {a.id for a in animals}
        if old_ids == new_ids:
            continue
        if original.details.get('procedure') == 'castration':
            raise ValidationError('A historical move changes a castration cohort. Correct the dated procedure/sex history first; no partial movement was saved.')
        adjustment = Event.objects.create(property=actor.property, actor=actor, kind='allocation_correction', effective_at=original.effective_at, effective_order=correction.effective_order, details={'original': str(original.id), 'movement': str(correction.id), 'before_members': [str(x) for x in old_ids], 'after_members': [str(a.id) for a in animals]})
        categories = {}
        sums = Allocation.objects.filter(event__in=[original, *related]).values('animal_id', 'category').annotate(total=Sum('amount'))
        old = {}
        for row in sums:
            old[(row['animal_id'], row['category'])] = row['total']
        count = len(animals)
        if original.kind == 'feed':
            qty = Decimal(original.details['consumed'])
            if original.details.get('mode') == 'kg_per_head':
                qty = number(original.details['quantity'], positive=True) * count
            categories['feed'] = -rounded(qty * Decimal(original.details['unit_cost']))
        else:
            qty = Decimal(original.details.get('consumed', '0')) / int(original.details['count']) * count
            if original.details.get('item'):
                categories['chemical'] = -rounded(qty * Decimal(original.details['unit_cost']))
            fee = Decimal(original.details.get('fee') or '0')
            if original.kind in ['procedure', 'vet'] or fee:
                categories['vet' if original.kind == 'vet' else 'procedure'] = -(fee if original.details.get('fee_mode') == 'group' else fee * count)
        if original.details.get('item'):
            item = scoped(Inventory, actor, original.details['item'])
            used = -sum(StockPosting.objects.filter(event__in=[original, *related], item=item).values_list('quantity', flat=True))
            difference = used - qty
            if difference:
                if item.kind == 'feed' and difference < 0 and item.balance <= 0:
                    raise ValidationError('Correcting historical membership needs additional feed but current stock is nonpositive. Replenish/correct stock first.')
                post_stock(adjustment, item, difference)
        desired = {}
        for category, total in categories.items():
            for animal, amount in split(total, animals):
                desired[(animal.id, category)] = amount
        for identity, category in set(old) | set(desired):
            delta = desired.get((identity, category), Decimal(0)) - old.get((identity, category), Decimal(0))
            if delta:
                Allocation.objects.create(event=adjustment, animal_id=identity, category=category, amount=delta)
        participants(adjustment, list(Animal.objects.filter(id__in=old_ids | new_ids)))
        Restriction.objects.filter(event__in=[original, *related], animal_id__in=old_ids-new_ids, superseded_by__isnull=True).update(superseded_by=adjustment)
        days = int(original.details.get('combined_restriction_days') or 0)
        if days:
            for identity in new_ids-old_ids:
                Restriction.objects.create(event=adjustment, animal_id=identity, starts_at=original.effective_at, ends_at=clock.calendar_days(original.effective_at, days, actor.property.timezone), days=days, timezone=actor.property.timezone)
        adjustment.details.update({'effective_consumed': str(qty), 'totals': clean(categories)})
        adjustment.save(update_fields=['details'])
        audit(actor, 'historical_allocation_correction', adjustment, original=str(original.id), before=[str(x) for x in old_ids], after=[str(a.id) for a in animals], cost_effects=clean(categories))
        affected.append(str(adjustment.id))
    return affected


def reverse(actor, event, data):
    original = scoped(Event, actor, data['original'])
    if original.reversed_by_id:
        raise ValidationError('This event was already reversed.')
    if not data.get('reason'):
        raise ValidationError('A correction reason is required.')
    if original.kind in ['sale', 'death'] or original.actor_id != actor.id or clock.now() >= original.submitted_at + 86400:
        administrator(actor)
    eligible = ['feed', 'treat', 'procedure', 'vet', 'receipt', 'stocktake', 'retire', 'sale', 'death', 'replace_tag', 'edit_animal', 'observation']
    if original.kind not in eligible:
        raise ValidationError('This event requires historical administration rather than a simple reversal.')
    affected_animals = list(Animal.objects.filter(participant__event=original).distinct())
    # Restriction/sex/lifecycle corrections must not invalidate downstream actions.
    if original.kind in ['sale', 'death', 'replace_tag', 'edit_animal', 'procedure', 'treat']:
        later = Participant.objects.filter(animal__in=affected_animals, event__submitted_at__gt=original.submitted_at, event__reversed_by__isnull=True).exclude(event=event)
        if later.exists():
            raise ValidationError('Later animal actions conflict. Review and reverse dependencies first; no partial reversal applied.')
    for posting in original.stock_postings.select_related('item'):
        item = posting.item
        post_stock(event, item, -posting.quantity)
    for allocation in original.allocations.all():
        Allocation.objects.create(event=event, animal=allocation.animal, category=allocation.category, amount=-allocation.amount, unknown=allocation.unknown)
    participants(event, affected_animals)
    for change in AttributeChange.objects.filter(event=original):
        a = change.animal
        setattr(a, change.field, change.before)
        a.save(update_fields=[change.field])
        AttributeChange.objects.create(event=event, animal=a, field=change.field, before=change.after, after=change.before)
    if original.kind in ['sale', 'death']:
        for row in original.before['departures']:
            Presence.objects.filter(pk=row['presence']).update(end=None, departure=None)
            Membership.objects.filter(pk__in=row['memberships']).update(end=None)
            Animal.objects.filter(pk=row['animal']).update(status='active')
    if original.kind == 'replace_tag':
        a = affected_animals[0]
        a.identifiers.filter(current=True).update(current=False, retired_at=event.effective_at)
        for old in original.before['identifiers']:
            attach(event, a, old['kind'], old['value'], 'Reversal: ' + data['reason'])
    if original.kind == 'edit_animal':
        Allocation.objects.filter(resolved_by=original).update(resolved_by=None)
    if original.kind == 'retire':
        Inventory.objects.filter(pk=original.details['item'], property=actor.property).update(retired=original.before['retired'])
    original.reversed_by = event
    original.save(update_fields=['reversed_by'])
    return {'original': str(original.id), 'reversed': True}

def report_template(actor, event, data):
    from .reports import validate_definition
    definition = data.get('definition', {})
    validate_definition(definition)
    if data.get('template'):
        template = scoped(ReportTemplate, actor, data['template'])
        event.before = {'name': template.name, 'definition': template.definition, 'version': template.version}
        if data.get('delete'):
            template.delete()
            return {'deleted': True}
        template.name, template.definition, template.version = data['name'], definition, template.version + 1
        template.save()
    else:
        template = ReportTemplate.objects.create(property=actor.property, name=data['name'], definition=definition)
    return {'template': template.id, 'version': template.version}

def account_change(actor, event, data):
    administrator(actor)
    user = scoped(Account, actor, data['account']) if data.get('account') else Account(property=actor.property)
    if user.pk and user.administrator and (data.get('role') != 'admin' or not data.get('active', True)) and Account.objects.filter(property=actor.property, role='admin', is_active=True).count() <= 1:
        raise ValidationError('The last active administrator cannot be disabled or demoted.')
    if data.get('role', 'standard') not in ['standard', 'admin']:
        raise ValidationError('Invalid account role.')
    user.username, user.role, user.is_active = data['username'], data.get('role', 'standard'), bool(data.get('active', True))
    if data.get('password'):
        validate_password(data['password'], user)
        user.set_password(data['password'])
    elif not user.pk:
        raise ValidationError('A secure initial password is required.')
    user.save()
    # Never retain password material in event payload, result or audit.
    data.pop('password', None)
    event.details = data
    return {'account': user.id, 'username': user.username, 'role': user.role, 'active': user.is_active}

def purge(actor, event, data):
    administrator(actor)
    if not data.get('reason') or not data.get('confirm'):
        raise ValidationError('A deliberate purge reason and confirmation are required.')
    a = find_animal(actor, data['animal'])
    last = a.presence.order_by('-start').first()
    if a.status == 'active' or not last or last.end is None:
        raise ValidationError('Active/on-property animals cannot be purged.')
    local = __import__('datetime').datetime.fromtimestamp(last.end, ZoneInfo(actor.property.timezone))
    try:
        cutoff = local.replace(year=local.year + 10)
    except ValueError:
        cutoff = local.replace(year=local.year + 10, day=28)
    if clock.now() < int(cutoff.timestamp()):
        raise ValidationError('Ten calendar years have not elapsed since the latest exit/death.')
    a.breed, a.sex, a.mother_nlis, a.dob, a.estimated_weeks, a.age_reference = '', '', '', None, None, None
    a.purged = True
    a.save()
    Participant.objects.filter(animal=a).update(snapshot={})
    # Preserve shared event totals and opaque allocation/identity reservations.
    reserved = set(a.identifiers.values_list('value', flat=True)) | {str(a.id)}
    def redact(value):
        if isinstance(value, dict):
            # Delete only this animal's imported row, never a shared cohort's payload.
            if any(str(value.get(k, '')) in reserved for k in ['nlis', 'rfid', 'identity']):
                return {'retention_redacted_identity': str(a.id)}
            return {k: redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact(v) for v in value]
        return '[retained identity reservation]' if isinstance(value, str) and value in reserved else value
    for old in Event.objects.filter(participants__animal=a).distinct():
        old.details, old.before = redact(old.details), redact(old.before)
        old.save(update_fields=['details', 'before'])
        for log in Audit.objects.filter(event=old):
            log.details = redact(log.details)
            log.save(update_fields=['details'])
        for sub in Submission.objects.filter(event=old):
            sub.result = redact(sub.result)
            sub.save(update_fields=['result'])
    ImportPreview.objects.filter(property=actor.property).delete()
    return {'identity': str(a.id), 'purged': True, 'reservations_retained': True}

HANDLERS = {'register': register, 'mob': mob_create, 'move': move, 'replace_tag': replace_tag, 'edit_animal': edit_animal, 'sale': depart, 'death': depart, 'receipt': receipt, 'stocktake': stocktake, 'retire': retire, 'feed': feed, 'treat': treat, 'procedure': treat, 'vet': treat, 'observation': observation, 'reverse': reverse, 'template': report_template, 'account': account_change, 'purge': purge}
