import uuid
import builtins
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Length, Concat, Cast
from django.db.models.lookups import Exact
from .clock import now

def decimal_field(default=0):
    return models.DecimalField(max_digits=30, decimal_places=12, default=default)

class Property(models.Model):
    name = models.CharField(max_length=160)
    pic = models.CharField(max_length=32, unique=True)
    timezone = models.CharField(max_length=64, default='Australia/Melbourne')
    version = models.PositiveBigIntegerField(default=0)

class Account(AbstractUser):
    property = models.ForeignKey(Property, on_delete=models.PROTECT, null=True)
    role = models.CharField(max_length=16, choices=[('admin', 'Administrator'), ('standard', 'Standard user')], default='standard')
    display_timezone = models.CharField(max_length=64, default='Australia/Melbourne')
    date_format = models.CharField(max_length=32, default='%d/%m/%Y %H:%M')
    @builtins.property
    def administrator(self):
        return self.is_active and self.role == 'admin'

class Scoped(models.Model):
    property = models.ForeignKey(Property, on_delete=models.PROTECT)
    class Meta:
        abstract = True

class Event(Scoped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=24)
    effective_at = models.BigIntegerField(db_index=True)
    effective_order = models.PositiveIntegerField(default=0)
    submitted_at = models.BigIntegerField(default=now)
    actor = models.ForeignKey(Account, on_delete=models.PROTECT)
    details = models.JSONField(default=dict)
    before = models.JSONField(default=dict)
    reversed_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    class Meta:
        ordering = ['effective_at', 'effective_order', 'submitted_at', 'id']

class Submission(Scoped):
    actor = models.ForeignKey(Account, on_delete=models.PROTECT)
    key = models.CharField(max_length=80)
    digest = models.CharField(max_length=64)
    event = models.ForeignKey(Event, null=True, on_delete=models.PROTECT)
    result = models.JSONField(default=dict)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['property', 'actor', 'key'], name='submission_once')]

class Animal(Scoped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    breed = models.CharField(max_length=80, blank=True)
    sex = models.CharField(max_length=24, blank=True)
    dob = models.DateField(null=True, blank=True)
    estimated_weeks = models.PositiveIntegerField(null=True, blank=True)
    age_reference = models.BigIntegerField(null=True)
    mother_nlis = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=16, default='active')
    purged = models.BooleanField(default=False)
    @builtins.property
    def label(self):
        return self.identifiers.filter(current=True, kind='nlis').values_list('value', flat=True).first() or self.identifiers.filter(current=True).values_list('value', flat=True).first() or str(self.id)

class Identifier(models.Model):
    animal = models.ForeignKey(Animal, related_name='identifiers', on_delete=models.PROTECT)
    kind = models.CharField(max_length=8)
    value = models.CharField(max_length=16, db_collation='utf8mb4_bin')
    current = models.BooleanField(default=True)
    current_slot = models.GeneratedField(expression=models.Case(models.When(current=True, then=Concat(Cast('animal_id', output_field=models.CharField()), models.Value(':'), 'kind')), default=None), output_field=models.CharField(max_length=64), db_persist=True, unique=True)
    effective_at = models.BigIntegerField()
    retired_at = models.BigIntegerField(null=True)
    reason = models.TextField(blank=True)
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['kind', 'value'], name='identifier_permanent_nonreuse'),
            models.CheckConstraint(condition=Q(kind='nlis') & Exact(Length('value'), 16) | Q(kind='rfid', value__regex=r'^[0-9]{15}$') & Exact(Length('value'), 15), name='identifier_format'),
        ]

class Presence(models.Model):
    animal = models.ForeignKey(Animal, related_name='presence', on_delete=models.PROTECT)
    start = models.BigIntegerField()
    end = models.BigIntegerField(null=True)
    arrival = models.ForeignKey(Event, related_name='+', on_delete=models.PROTECT)
    departure = models.ForeignKey(Event, related_name='+', null=True, on_delete=models.PROTECT)
    class Meta:
        indexes = [models.Index(fields=['animal', 'start', 'end'])]
        constraints = [models.CheckConstraint(condition=Q(end__isnull=True) | Q(end__gte=models.F('start')), name='presence_interval_order')]

class Mob(Scoped):
    name = models.CharField(max_length=80)
    retired = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['property', 'name'], name='mob_property_name')]

class Membership(models.Model):
    animal = models.ForeignKey(Animal, related_name='memberships', on_delete=models.PROTECT)
    mob = models.ForeignKey(Mob, on_delete=models.PROTECT)
    start = models.BigIntegerField()
    end = models.BigIntegerField(null=True)
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    superseded = models.BooleanField(default=False)
    class Meta:
        indexes = [models.Index(fields=['mob', 'start', 'end']), models.Index(fields=['animal', 'start', 'end'])]
        constraints = [models.CheckConstraint(condition=Q(end__isnull=True) | Q(end__gte=models.F('start')), name='membership_interval_order')]

class Participant(models.Model):
    event = models.ForeignKey(Event, related_name='participants', on_delete=models.PROTECT)
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT)
    snapshot = models.JSONField(default=dict)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'animal'], name='event_participant_once')]

class Allocation(models.Model):
    event = models.ForeignKey(Event, related_name='allocations', on_delete=models.PROTECT)
    animal = models.ForeignKey(Animal, related_name='allocations', on_delete=models.PROTECT)
    category = models.CharField(max_length=20)
    amount = decimal_field()
    unknown = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(Event, related_name='+', null=True, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'animal', 'category'], name='allocation_once')]

class AttributeChange(models.Model):
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT)
    field = models.CharField(max_length=32)
    before = models.TextField(blank=True)
    after = models.TextField(blank=True)

class Inventory(Scoped):
    kind = models.CharField(max_length=12, choices=[('feed', 'Feed'), ('chemical', 'Chemical')])
    name = models.CharField(max_length=120)
    feed_type = models.CharField(max_length=24, blank=True)
    category = models.CharField(max_length=24, default='veterinary')
    package_size = decimal_field(1)
    package_price = decimal_field()
    stock_unit = models.CharField(max_length=12, default='kg')
    base_unit = models.CharField(max_length=12, default='kg')
    dose_unit = models.CharField(max_length=12, default='mL')
    base_per_package = decimal_field(1)
    unit_cost = models.DecimalField(max_digits=38, decimal_places=18)
    balance = decimal_field()
    batch = models.CharField(max_length=80, blank=True)
    date_kind = models.CharField(max_length=12, blank=True)
    date_value = models.DateField(null=True, blank=True)
    restriction_days = models.PositiveIntegerField(default=0)
    storage = models.CharField(max_length=120, blank=True)
    signature = models.CharField(max_length=64)
    retired = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['property', 'signature'], name='inventory_matching_spec'), models.CheckConstraint(condition=Q(kind='feed') | Q(balance__gte=0), name='chemicals_never_negative'), models.CheckConstraint(condition=Q(package_size__gt=0, base_per_package__gt=0, package_price__gte=0), name='inventory_positive_spec')]

class StockPosting(models.Model):
    event = models.ForeignKey(Event, related_name='stock_postings', on_delete=models.PROTECT)
    item = models.ForeignKey(Inventory, related_name='postings', on_delete=models.PROTECT)
    quantity = decimal_field()
    value = decimal_field()

class Restriction(models.Model):
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    animal = models.ForeignKey(Animal, related_name='restrictions', on_delete=models.PROTECT)
    starts_at = models.BigIntegerField()
    ends_at = models.BigIntegerField()
    days = models.PositiveIntegerField()
    timezone = models.CharField(max_length=64)
    superseded_by = models.ForeignKey(Event, related_name='+', null=True, on_delete=models.PROTECT)

class Audit(Scoped):
    recorded_at = models.BigIntegerField(default=now)
    actor = models.ForeignKey(Account, on_delete=models.PROTECT)
    event = models.ForeignKey(Event, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    details = models.JSONField(default=dict)

class ReportTemplate(Scoped):
    name = models.CharField(max_length=120)
    definition = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)

class ImportPreview(Scoped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    actor = models.ForeignKey(Account, on_delete=models.PROTECT)
    created_at = models.BigIntegerField(default=now)
    rows = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    confirmed = models.BooleanField(default=False)

class LoginAttempt(models.Model):
    identity_hash = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    blocked_until = models.BigIntegerField(default=0)
