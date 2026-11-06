"""Display aliases for generated examples; no mutation of source records."""
SAMPLE_LABELS=[(('af13',),'Operational readiness'),(('d13',),'Payment review'),(('finance normal',),'Finance document intake'),(('private finance',),'Finance evidence review'),(('f01 missing',),'Transaction verification'),(('f01 duplicate',),'Transaction corrections'),(('f01','ledger'),'Finance transaction review'),(('b14','support','complaint'),'Customer support'),
        (('readiness','provider','adapter'),'Connections and services'),(('operations','recovery','protection','backup'),'Business continuity'),
        (('p14','costing','oracle'),'Project costing'),(('d03','billing'),'Billing review'),(('d11','migration'),'Migration planning'),
        (('p02','approval'),'Department approvals'),(('payroll','staff cost'),'Staff costs'),(('hr','f35'),'HR and Finance'),
        (('forecast',),'Cash forecast'),(('rfp',),'Proposals and opportunities'),(('emergency','glpi'),'Urgent changes'),
        (('partner',),'Partner services'),(('minutes','meeting','report'),'Meetings and reporting'),(('finance','invoice','cash'),'Finance workspace'),
        (('evidence',),'Document review'),(('delivery',),'Project delivery')]

def workspace_name(value):
    if isinstance(value,dict):title=value.get('title',value.get('case_title','Workspace'));sample=value.get('synthetic',False);kind=value.get('kind','')
    else:title=getattr(value,'title',str(value));sample=getattr(value,'synthetic',False);kind=getattr(value,'kind','')
    if not sample or not (title.lower().startswith('synthetic') or title=='Test engagement' or title.lower().startswith(('af13 synthetic ','d13 synthetic '))):return title
    lower=title.lower()
    for terms,label in SAMPLE_LABELS:
        if any(term in lower for term in terms):return label
    return 'Customer support' if kind=='support' else 'Project workspace'

