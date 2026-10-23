import io
import pytest
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from herd import clock,services as s,reports
from herd.models import Animal,Event,ImportPreview
from herd.imports import read_upload,mapped_preview
from .test_foundations import arrival,run
from .test_business_rules import setup_mob,stock,T

@pytest.mark.django_db
def test_auth_csrf_roles_and_all_workflow_pages(farm):
    _,admin,b,c=farm
    unauth=Client()
    assert unauth.get('/animals/').status_code==302
    assert unauth.post('/action/register/',{}).status_code==302
    client=Client(enforce_csrf_checks=True);client.force_login(b)
    assert client.post('/action/mob/',{'name':'No CSRF'}).status_code==403
    for url in ['/','/animals/','/inventory/','/events/','/reports/','/settings/','/import/']:
        response=client.get(url);assert response.status_code==200,(url,response.status_code)
        assert response['Cache-Control']=='no-store'
    for operation in ['register','mob','move','replace_tag','edit_animal','sale','death','receipt','feed','treat','procedure','vet','stocktake','retire','observation','reverse','template']:
        assert client.get('/action/'+operation+'/').status_code==200
    assert client.get('/accounts/').status_code==403 and client.get('/action/purge/').status_code==403
    client.force_login(admin)
    assert client.get('/accounts/').status_code==200

@pytest.mark.django_db
def test_import_mapping_preview_atomic_selection_and_rejection(farm):
    _,a,b,c=farm
    raw=b'Visual,RFID,Arrival,PIC,NVD,Price\nZZZZZZZZZZZZZZZZ,000000000000001,2020-09-13T12:00:00,SRC00001,00001,\nZZZZZZZZZZZZZZZZ,000000000000002,2020-09-13T12:00:00,SRC00001,00001,100\n'
    upload=SimpleUploadedFile('synthetic.csv',raw)
    headers,rows=read_upload(upload)
    with clock.at(T+86400):
        result,errors=mapped_preview(b,headers,rows,dict(zip(['nlis','rfid','effective_at','source_pic','nvd','purchase_cost'],map(str,range(6)))),{})
        assert not errors[0] and errors[1] and 'purchase_cost' in result[0]['missing']
        assert not Animal.objects.exists()
        run(b,'register',{'rows':[result[0]['data']]})
        assert Animal.objects.count()==1 and not reports.build(b,{})['rows'][0]['financial_complete']
    from openpyxl import Workbook
    wb=Workbook();wb.active.append(['nlis']);wb.active.append(['=HYPERLINK("bad")']);stream=io.BytesIO();wb.save(stream)
    with pytest.raises(__import__('django').core.exceptions.ValidationError):read_upload(SimpleUploadedFile('formula.xlsx',stream.getvalue()))

@pytest.mark.django_db
def test_lpa_all_sections_have_explicit_fields_and_exports(farm):
    _,a,b,c=farm
    with clock.at(T):
        mob=setup_mob(b,1)
        feed=stock(b)
        run(b,'feed',{'mob':mob,'item':feed,'quantity':1,'mode':'bales','responsible_name':'Synthetic feeder'})
        chemical=stock(b,kind='chemical',restriction_days=28,date_kind='expiry',date_value='2022-01-01')
        run(b,'treat',{'mob':mob,'item':chemical,'dose':1,'adverse_reactions':'None observed','broken_needle_status':'no','equipment_cleaned_calibrated':'yes','equipment_checked_on':'2020-09-13','equipment_checked_by_name':'Synthetic calibrator','equipment_checked_by_contact':'TEST CONTACT','administered_by':'Synthetic vet','administered_by_contact':'TEST VET','livestock_description':'Angus calf','location_text':'Synthetic yard','rate_description':'Actual 1 mL/head'})
    with clock.at(T+1):run(b,'sale',{'mob':mob,'destination_pic':'DST00001','nvd':'TEST OUT','price':200,'accept_restriction':True})
    for ds in reports.LPA_FIELDS:
        r=reports.build(b,{'dataset':ds})
        assert r['rows'] and set(reports.LPA_FIELDS[ds])<=set(r['rows'][0])
        assert reports.pdf(r).startswith(b'%PDF')
        assert reports.xlsx(r).startswith(b'PK')
    treatment=reports.build(b,{'dataset':'lpa2'})['rows'][0]
    assert treatment['adverse_reactions']=='None observed' and treatment['equipment_checked_by_contact']=='TEST CONTACT' and treatment['approximate_live_weight'].startswith('Not collected')
