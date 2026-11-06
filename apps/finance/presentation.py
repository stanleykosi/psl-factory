"""Render only the immutable recipient payload; never fetch internal Finance inputs."""
import json
from decimal import Decimal,InvalidOperation

LABELS={'actual':'Actual','budget':'Budget','variance':'Variance','prior':'Prior','prior_variance':'Prior variance','ratio':'Configured ratio'}


def present(payload):
    if payload.get('type')!='finance_report':return None
    try:
        sections={row['heading']:row['text'] for row in payload['sections']}
        data=json.loads(sections['financial_metrics'])
        if isinstance(data,dict) and data.get('scope')=='captured_case_and_explicit_account_inventory_only':return forecast_projection(data,sections['executive_summary'])
        bus=json.loads(sections['bu_totals'])
        if not isinstance(data,dict) or 'figures' not in data:return None  # Preserve legacy plain-text projections.
        columns=data['columns'];figures=data['figures']
        if not isinstance(columns,list) or not columns or any(c not in LABELS for c in columns) or len(set(columns))!=len(columns):return None
        if not isinstance(figures,dict) or not isinstance(bus,dict) or len(bus)>100:return None
        rows=[];lookup={}
        def exact_number(value):
            if value is None:return None
            if not isinstance(value,str) or len(value)>512:raise ValueError
            result=Decimal(value)
            if not result.is_finite() or result.adjusted()>100 or result.as_tuple().exponent < -512:raise ValueError
            return result
        for bu,scope,values in [(None,'Company',figures)]+[(k,k,v) for k,v in bus.items()]:
            if not isinstance(values,dict) or len(values)>100:raise ValueError
            for key,value in values.items():
                cells=[]
                for column in columns:
                    raw=value.get('value' if column=='actual' else column);exact_number(raw);cells.append(raw)
                rows.append({'scope':scope,'metric':key,'cells':cells,'unit':value['unit']});lookup[(bu,key)]=value
        charts=[];spec=data.get('chart_spec')
        if spec:
            if spec.get('implementation')!='signed_grouped_bars_v1' or len(spec['data'])>1000:raise ValueError
            for item in spec['data']:
                values=lookup[(item['bu'],item['metric'])];selected=[c for c in ['actual','budget','prior'] if c in columns]
                if item['unit']!=values['unit']:raise ValueError
                for col in selected:
                    if item.get(col)!=values.get('value' if col=='actual' else col):raise ValueError
                numeric=[exact_number(item.get(c)) for c in selected];maximum=max([abs(n) for n in numeric if n is not None],default=Decimal(0));bars=[]
                for col,n in zip(selected,numeric):
                    width=Decimal(0) if n is None or maximum==0 else abs(n)/maximum*45
                    bars.append({'column':LABELS[col],'value':item.get(col),'width':format(width,'.2f'),'left':format(50-width if n is not None and n<0 else Decimal(50),'.2f')})
                charts.append({'label':(item['bu'] or 'Company')+' / '+item['label'],'unit':item['unit'],'bars':bars})
        return {'summary':sections['executive_summary'],'columns':[LABELS[c] for c in columns],'rows':rows,'charts':charts,
                'accounting_basis':data.get('accounting_basis'),'periods':data.get('periods',[]),'ratio':data.get('ratio_definition'),'multiplier':data.get('ratio_multiplier')}
    except (ValueError,TypeError,KeyError,InvalidOperation):return None


def forecast_projection(data,summary):
    labels={'opening':'Opening','inflow':'Inflow','outflow':'Outflow','closing':'Closing'}
    periods=data.get('periods')
    if not isinstance(periods,list) or not 1<=len(periods)<=24:return None
    columns=[k for k in labels if k in periods[0]]
    if not columns or data.get('full_business_cash_forecast') is not False or data.get('execution_authorized') is not False:return None
    rows=[]
    for row in periods:
        if set(row)!=set(columns)|{'month'}:return None
        cells=[]
        for key in columns:
            value=row[key]
            if value is not None:
                if not isinstance(value,str) or len(value)>64:return None
                n=Decimal(value)
                if not n.is_finite() or abs(n)>=Decimal('1e24'):return None
            cells.append(value)
        rows.append({'month':row['month'],'cells':cells})
    return {'forecast':True,'summary':summary,'status':data['status'],'currency':data['currency'],'as_of':data['as_of'],'coverage':data['coverage'],'headers':[labels[k] for k in columns],'rows':rows}
