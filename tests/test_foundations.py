import uuid
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,IntegrityError
from herd import services as s,clock
from herd.models import Identifier,Animal,Event,Allocation,Submission,Account

def run(user,kind,data,key=None):return s.execute(user,key or uuid.uuid4().hex,kind,data)
def arrival(user,tag='A'*16,**extra):return run(user,'register',{'nlis':tag,'source_pic':'SRC00001','nvd':'00001','purchase_cost':'100','sex':'M',**extra})

@pytest.mark.django_db
def test_real_engine_constraints_and_identity(farm):
    p,a,b,c=farm
    assert connection.vendor=='mysql'
    with clock.at(1600000000):
        result=arrival(b,rfid='000000000000001')
        animal=Animal.objects.get(pk=result['animals'][0])
        assert s.find_animal(c,'000000000000001')==animal
        with pytest.raises(ValidationError):arrival(b)
        with pytest.raises(IntegrityError),transaction.atomic():
            Identifier.objects.create(animal=animal,kind='rfid',value='１２３４５６７８９０１２３４５',event=Event.objects.first(),effective_at=1600000000)
        with pytest.raises(IntegrityError),transaction.atomic():
            Identifier.objects.create(animal=animal,kind='nlis',value='short',event=Event.objects.first(),effective_at=1600000000)

@pytest.mark.django_db
def test_idempotency_and_atomicity(farm):
    _,a,b,c=farm
    with clock.at(1600000000):
        data={'nlis':'A'*16,'source_pic':'SRC','nvd':'NVD','purchase_cost':'100'}
        first=run(b,'register',data,'stable')
        assert run(b,'register',data,'stable')==first
        assert Animal.objects.count()==1
        with pytest.raises(ValidationError):run(b,'register',{**data,'purchase_cost':'101'},'stable')
        before=Event.objects.count()
        with pytest.raises(ValidationError):run(b,'register',{'rows':[{'nlis':'B'*16,'source_pic':'SRC','nvd':'NVD'},{'nlis':'A'*16,'source_pic':'SRC','nvd':'NVD'}]})
        assert Event.objects.count()==before and Animal.objects.count()==1

@pytest.mark.django_db
def test_preview_rolls_back_and_stale_confirmation(farm):
    p,a,b,c=farm
    data={'nlis':'A'*16,'source_pic':'SRC','nvd':'NVD'}
    preview=s.preview(b,'register',data)
    assert not Animal.objects.exists()
    run(c,'mob',{'name':'Changed'})
    with pytest.raises(ValidationError):s.execute(b,'stale','register',data,preview['version'])
    assert not Animal.objects.exists()

@pytest.mark.django_db
def test_account_security_and_last_admin(farm):
    p,a,b,c=farm
    with pytest.raises(PermissionDenied):run(b,'account',{'username':'E','password':'Another-Synthetic-Password'})
    with pytest.raises(ValidationError):run(a,'account',{'account':a.id,'username':'A','role':'standard','active':True})
    run(a,'account',{'username':'NewUser','role':'standard','active':True,'password':'Another-Synthetic-Password'})
    assert Account.objects.get(username='NewUser').check_password('Another-Synthetic-Password')
    assert 'Another-Synthetic-Password' not in str(list(Event.objects.values('details')))

def test_exact_allocation_and_dst():
    from types import SimpleNamespace
    animals=[SimpleNamespace(id=str(i)) for i in range(3)]
    allocation=s.split(Decimal('0.0125'),animals)
    assert sum(v for a,v in allocation)==Decimal('0.0125')
    assert max(v for a,v in allocation)-min(v for a,v in allocation)<=Decimal('0.000000000001')
    start=clock.local_timestamp('2020-10-03T12:00:00','Australia/Melbourne')
    assert clock.calendar_days(start,1,'Australia/Melbourne')-start==23*3600
    with pytest.raises(ValueError):clock.local_timestamp('2020-10-04T02:30:00','Australia/Melbourne')
    with pytest.raises(ValueError):clock.local_timestamp('2020-04-05T02:30:00','Australia/Melbourne')
