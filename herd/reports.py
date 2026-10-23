"""Allowlisted selections; financial dates select identities, never clip lifetime."""
import io
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from . import clock
from .models import Animal, Event, Inventory, Membership, Allocation, Audit
DATASETS = ['animals', 'inventory', 'feed', 'treatments', 'restrictions', 'arrivals', 'exits', 'audit', 'lpa2', 'lpa3C', 'lpa3D', 'lpa5A', 'lpa5B', 'lpa6']
FIELDS = ['animal','identity','status','breed','sex','age_weeks','estimated_age','mob','purchase','sale','feed','chemical','procedure','vet','cost','revenue','profit','financial_complete','tags','restriction_end','effective_at','submitted_at','event','kind','name','balance','unit','value','details','actor','action','count']
FILTERS = {'breed','sex','status','animal','mob','min_age','max_age','present_from','present_to','activity_from','activity_to','as_of'}

def validate_definition(definition):
    if not isinstance(definition, dict) or set(definition) - {'dataset','columns','filters','sort','group','attribute_time','filter_mode'}:
        raise ValidationError('Unsupported report settings. Executable expressions and SQL are not accepted.')
    if definition.get('dataset','animals') not in DATASETS:
        raise ValidationError('Unsupported report dataset.')
    if set(definition.get('columns',[])) - set(FIELDS) or definition.get('sort','animal').lstrip('-') not in FIELDS or definition.get('group','') not in ['', 'mob','breed','sex','status','kind','name']:
        raise ValidationError('Choose allowed report columns, grouping and sort fields.')
    filters = definition.get('filters',{})
    if not isinstance(filters,dict) or set(filters)-FILTERS:
        raise ValidationError('Unsupported report filter.')
    for key in FILTERS - {'breed','sex','status','animal','mob'}:
        if filters.get(key) not in [None,'']:
            try:int(filters[key])
            except (TypeError,ValueError):raise ValidationError('Report ages/timestamps must be integers.')
    if definition.get('attribute_time','current') not in ['current','as_of'] or definition.get('filter_mode','all') not in ['all','any']:
        raise ValidationError('Invalid attribute time or filter combination.')
    if definition.get('attribute_time') == 'as_of' and not filters.get('as_of'):
        raise ValidationError('An as-of timestamp is required for historical attributes.')
    return definition

def animal_rows(actor, definition):
    from .models import AttributeChange
    f = definition.get('filters',{})
    at = int(f.get('as_of') or clock.now())
    rows=[]
    for a in Animal.objects.filter(property=actor.property,purged=False).prefetch_related('identifiers','allocations','memberships__mob','restrictions'):
        breed,sex,status=a.breed,a.sex,a.status
        if definition.get('attribute_time')=='as_of':
            for field in ['breed','sex']:
                later = AttributeChange.objects.filter(animal=a,field=field,event__effective_at__gt=at,event__reversed_by__isnull=True).order_by('event__effective_at','event__effective_order').first()
                if later:
                    if field=='breed':breed=later.before
                    else:sex=later.before
            p=a.presence.filter(start__lte=at).order_by('-start').first()
            status='active' if p and (p.end is None or p.end>at) else 'absent'
        age=None
        if a.dob:
            age=(datetime.fromtimestamp(at,ZoneInfo(actor.property.timezone)).date()-a.dob).days//7
        elif a.estimated_weeks is not None and a.age_reference is not None:
            age=a.estimated_weeks+(at-a.age_reference)//(7*86400)
        mob=a.memberships.filter(superseded=False,start__lte=at).filter(Q(end__isnull=True)|Q(end__gt=at)).select_related('mob').first()
        checks=[]
        if f.get('breed'):checks.append(breed.casefold()==str(f['breed']).casefold())
        if f.get('sex'):checks.append(sex.casefold()==str(f['sex']).casefold())
        if f.get('status'):checks.append(status==f['status'])
        if f.get('animal'):checks.append(str(a.id)==str(f['animal']) or a.identifiers.filter(value=str(f['animal']).upper()).exists())
        if f.get('mob'):checks.append(a.memberships.filter(mob_id=f['mob'],superseded=False).exists())
        if f.get('min_age'):checks.append(age is not None and age>=int(f['min_age']))
        if f.get('max_age'):checks.append(age is not None and age<=int(f['max_age']))
        if f.get('present_from') or f.get('present_to'):
            lo=int(f.get('present_from') or 0); hi=int(f.get('present_to') or clock.now())
            checks.append(a.presence.filter(start__lte=hi).filter(Q(end__isnull=True)|Q(end__gte=lo)).exists())
        if f.get('activity_from') or f.get('activity_to'):
            q=a.participant_set.filter(event__effective_at__gte=int(f.get('activity_from') or 0),event__effective_at__lte=int(f.get('activity_to') or clock.now()))
            checks.append(q.exists())
        if checks and not (any(checks) if definition.get('filter_mode')=='any' else all(checks)):continue
        sums={r['category']:r['total'] for r in a.allocations.values('category').annotate(total=Sum('amount'))}
        revenue=sums.get('sale',Decimal(0))
        cost=-sum(v for k,v in sums.items() if k!='sale')
        complete=not a.allocations.filter(unknown=True,event__reversed_by__isnull=True).exists()
        restrictions=a.restrictions.filter(event__reversed_by__isnull=True).order_by('-ends_at').first()
        row={'animal':a.label,'identity':str(a.id),'status':status,'breed':breed or 'Unknown','sex':sex or 'Unknown','age_weeks':age,'estimated_age':not bool(a.dob),'mob':mob.mob.name if mob else 'Unassigned / exited','cost':cost,'revenue':revenue,'profit':revenue-cost if complete else None,'financial_complete':complete,'tags':'; '.join(f'{t.kind}:{t.value} ({"current" if t.current else "retired"})' for t in a.identifiers.all()),'restriction_end':restrictions.ends_at if restrictions else None}
        for cat in ['purchase','sale','feed','chemical','procedure','vet']:row[cat]=sums.get(cat,Decimal(0)) if cat=='sale' else -sums.get(cat,Decimal(0))
        rows.append(row)
    return rows

def build(actor, definition):
    validate_definition(definition)
    ds=definition.get('dataset','animals')
    if ds=='animals':rows=animal_rows(actor,definition)
    elif ds=='inventory':
        rows=[{'name':i.name,'kind':i.kind,'balance':i.balance,'unit':i.base_unit,'value':i.balance*i.unit_cost,'details':{'retired':i.retired,'batch':i.batch,'date_kind':i.date_kind,'date_value':str(i.date_value or ''),'package_size':str(i.package_size),'package_price':str(i.package_price)}} for i in Inventory.objects.filter(property=actor.property)]
    elif ds=='restrictions':
        from .models import Restriction
        rows=[{'animal':r.animal.label,'effective_at':r.starts_at,'restriction_end':r.ends_at,'details':{'combined_days':r.days,'timezone':r.timezone},'event':str(r.event_id)} for r in Restriction.objects.filter(animal__property=actor.property,event__reversed_by__isnull=True)]
    elif ds=='audit':
        rows=[{'actor':r.actor.username,'action':r.action,'submitted_at':r.recorded_at,'event':str(r.event_id or ''),'details':r.details} for r in Audit.objects.filter(property=actor.property).select_related('actor')]
    else:
        kinds={'feed':['feed'],'lpa3C':['feed'],'lpa3D':['receipt'],'lpa6':['receipt'],'treatments':['treat','procedure','vet','observation'],'lpa2':['treat'],'arrivals':['register'],'lpa5A':['register'],'exits':['sale','death'],'lpa5B':['sale']}
        rows=[]
        for e in Event.objects.filter(property=actor.property,kind__in=kinds[ds]).select_related('actor'):
            if ds=='lpa3D' and e.details.get('kind')!='feed' or ds=='lpa6' and e.details.get('kind')!='chemical':continue
            rows.append({'event':str(e.id),'kind':e.kind,'effective_at':e.effective_at,'submitted_at':e.submitted_at,'actor':e.actor.username,'count':e.participants.count(),'details':{**e.details,'reversed_by':str(e.reversed_by_id or '')}})
        f=definition.get('filters',{})
        if f.get('activity_from'):rows=[r for r in rows if r['effective_at']>=int(f['activity_from'])]
        if f.get('activity_to'):rows=[r for r in rows if r['effective_at']<=int(f['activity_to'])]
    sort=definition.get('sort','animal'); group=definition.get('group')
    rows.sort(key=lambda r:(str(r.get(group,'')) if group else '',str(r.get(sort.lstrip('-'),''))),reverse=sort.startswith('-'))
    totals={k:sum((r[k] for r in rows if isinstance(r.get(k),Decimal)),Decimal(0)) for k in ['cost','revenue','profit']}
    return {'rows':rows,'totals':totals,'definition':definition,'generated_at':clock.now(),'note':'AUD. Animal selection filters never clip lifetime financials. Unknown purchase cost makes P/L incomplete. Active animals show costs/revenue to date, not final realised sale. Timestamps are Unix seconds; property timezone '+actor.property.timezone+'. Stored allocations retain 12 decimal places.'}

def text(value):
    import json
    return json.dumps(value,default=str,ensure_ascii=False) if isinstance(value,(dict,list)) else '' if value is None else str(value)

def xlsx(report):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb=Workbook();ws=wb.active;ws.title='StockLOG'
    ws.append(['StockLOG report']);ws.append([report['note']]);ws.append(['Selection',text(report['definition'])])
    columns=report['definition'].get('columns') or (list(report['rows'][0]) if report['rows'] else ['animal','cost','revenue','profit'])
    ws.append(columns)
    for cell in ws[4]:cell.font=Font(bold=True)
    for row in report['rows']:
        ws.append([text(row.get(c)) for c in columns])
        for cell in ws[ws.max_row]:
            # Explicit string cell type, not a formula, including leading =,+,-,@ text.
            cell.data_type='s'
    ws.append(['Totals (full precision)',text(report['totals'])])
    ws.freeze_panes='A5';ws.auto_filter.ref=f'A4:{__import__("openpyxl").utils.get_column_letter(len(columns))}{ws.max_row-1}'
    for column in ws.columns:ws.column_dimensions[column[0].column_letter].width=min(60,max(16,len(str(column[3].value or ''))+2))
    ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0
    ws.print_title_rows='1:4'
    out=io.BytesIO();wb.save(out);return out.getvalue()

def pdf(report):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import landscape,A4
    from xml.sax.saxutils import escape
    styles=getSampleStyleSheet();out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24)
    story=[Paragraph('StockLOG — '+report['definition'].get('dataset','animals'),styles['Title']),Paragraph(escape(report['note']),styles['Normal']),Spacer(1,8),Paragraph('Selection: '+escape(text(report['definition'])),styles['Normal']),Spacer(1,12)]
    default=['animal','status','cost','revenue','profit','financial_complete'] if report['definition'].get('dataset','animals')=='animals' else ['event','kind','effective_at','actor','details']
    columns=report['definition'].get('columns') or default
    for offset in range(0,len(columns),7):
        subset=columns[offset:offset+7]
        if offset:story.append(PageBreak())
        table=[[Paragraph(escape(c.replace('_',' ').title()),styles['BodyText']) for c in subset]]
        for row in report['rows']:
            table.append([Paragraph(escape(text(row.get(c))).replace('\n','<br/>'),styles['BodyText']) for c in subset])
        t=Table(table,colWidths=[(landscape(A4)[0]-48)/len(subset)]*len(subset),repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#d7e7dc')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.grey),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        story.append(t)
    story += [Spacer(1,12),Paragraph('Totals (AUD, full precision): '+escape(text(report['totals'])),styles['Normal'])]
    doc.build(story);return out.getvalue()
