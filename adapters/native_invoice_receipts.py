"""Read-only incumbent invoice contracts. Neither a cash receipt nor vendor proof."""
import hashlib
from decimal import Decimal, localcontext
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from apps.finance.invoices import delivery_payload
from apps.finance.rules import number
from adapters import native_application_archive as n

VERSION='psl.internal-finance-invoice/v1'
VARIANTS=('issue','deliver','adjust','adjust_deliver')

def document(db,job_id,case_id,max_bytes):
    row=db.execute("""SELECT to_jsonb(j),to_jsonb(i),
      encode(sha256(convert_to(to_jsonb(j)::text,'UTF8')),'hex')
      FROM finance_invoicejob j JOIN finance_invoice i ON i.id=j.invoice_id
      WHERE j.id=%s AND i.case_id=%s AND octet_length(j.intent::text)+octet_length(i.payload::text)<=%s""",
      [job_id,case_id,max_bytes]).fetchone()
    if not row:raise ValidationError('Exact bounded incumbent invoice job required')
    j,i,row_sha=row
    if j['kind'] not in VARIANTS or j['operation_key']!=f"invoice:{i['id']}:{j['kind']}:g{j['generation']}" or n.digest(i['payload'])!=i['sha256']:
        raise ValidationError('Exact incumbent invoice operation and document hash required')
    correction=None
    if j['kind'] in ('issue','deliver'):
        payload=i['payload'] if j['kind']=='issue' else delivery_payload(SimpleNamespace(payload=i['payload']))
    else:
        row=db.execute("""SELECT to_jsonb(c)||jsonb_build_object('amount',c.amount::text),s.obligation_key,e.sha256 FROM finance_invoicecorrection c
          JOIN finance_invoiceissue s ON s.id=c.issue_id JOIN core_evidence e ON e.id=c.evidence_id
          WHERE c.id=%s AND c.case_id=%s AND s.invoice_id=%s AND octet_length(c.payload::text)<=%s""",
          [j['intent'].get('correction'),case_id,i['id'],max_bytes]).fetchone()
        if not row:raise ValidationError('Exact bounded legal correction required')
        correction,obligation,source_sha=row
        c=correction
        if c['amount'] is None or c['kind'] not in ('credit','debit','void') or obligation!=i['obligation_key']:
            raise ValidationError('Known exact correction amount and obligation required')
        with localcontext() as ctx:
            ctx.prec=512;amount=Decimal(str(c['amount']));delta=amount if c['kind']=='debit' else -amount
            if j['kind']=='adjust':
                prior=j['intent']['snapshot']['state']['face']
                payload=dict(correction=c['id'],obligation_key=obligation,kind=c['kind'],amount=number(amount),signed_delta=number(delta),
                    prior_face=prior,adjusted_face=number(Decimal(prior)+delta),review=j['intent']['review'],source_hash=source_sha)
            else:
                a=db.execute('SELECT payload,sha256 FROM finance_invoicecorrectionacceptance WHERE correction_id=%s',[c['id']]).fetchone()
                if not a or n.digest(a[0])!=a[1]:raise ValidationError('Exact immutable correction acceptance required before delivery')
                payload=dict(document_type=c['kind']+'_note',reference=c['reference'],version=c['version'],corrects_invoice=i['reference'],
                    kind=c['kind'],amount=a[0]['amount'],currency=i['currency'],amount_basis=i['amount_basis'],adjusted_face=a[0]['adjusted_face'])
    if j['kind'] in ('deliver','adjust_deliver') and j['intent'].get('delivery_hash')!=n.digest(payload):
        raise ValidationError('Exact public delivery projection required')
    return j,i,correction,payload,row_sha

def original(db,effect,max_bytes):
    try:j,i,c,payload,row_sha=document(db,effect['job_id'],effect['case_id'],max_bytes)
    except (KeyError,ValueError,ArithmeticError,TypeError):raise ValidationError('Unsupported incumbent invoice shape') from None
    op=j['operation_key']
    if row_sha!=effect['intent_sha256'] or hashlib.sha256(op.encode()).hexdigest()!=effect['operation_sha256']:
        raise ValidationError('Invoice operation/row differs from complete inventory')
    metadata=dict(contract_version=VERSION,effect_key=effect['effect_key'],source_case_id=i['case_id'],source_invoice_id=i['id'],
        source_correction_id=c['id'] if c else None,variant=j['kind'],operation_sha256=effect['operation_sha256'],source_row_sha256=row_sha,
        source_intent_sha256=n.digest(j['intent']),invoice_sha256=i['sha256'],obligation_key=i['obligation_key'],payload_sha256=n.digest(payload),
        recipient_id=j['intent']['recipient'] if j['kind'] in ('deliver','adjust_deliver') else None)
    return metadata,op,payload

def receipt(db,m,payload,max_bytes=1048576):
    """Exact source identifiers are an explicit v1 contract; no fuzzy ID mapping."""
    variant=m['variant'];correction=m['source_correction_id'];invoice=m['source_invoice_id']
    i=db.execute('SELECT case_id::text,sha256,obligation_key FROM finance_invoice WHERE id=%s',[invoice]).fetchone()
    if i is None:return 'unknown',None,None
    if i!=(m['source_case_id'],m['invoice_sha256'],m['obligation_key']):return 'conflict',None,None
    if correction is not None:
        c=db.execute('SELECT c.case_id::text,s.invoice_id FROM finance_invoicecorrection c JOIN finance_invoiceissue s ON s.id=c.issue_id WHERE c.id=%s',[correction]).fetchone()
        if c is None:return 'unknown',None,None
        if c!=(m['source_case_id'],invoice):return 'conflict',None,None
    # Identifiers below are code-owned, never interpolated from evidence or configuration.
    table,field={
      'issue':('finance_invoiceissue','invoice_id'),'deliver':('finance_invoicedelivery','invoice_id'),
      'adjust':('finance_invoicecorrectionacceptance','correction_id'),'adjust_deliver':('finance_invoicecorrectiondelivery','correction_id')}[variant]
    rows=db.execute(f'SELECT CASE WHEN octet_length(to_jsonb(r)::text)+octet_length(j.intent::text)<=%s THEN to_jsonb(r) END,CASE WHEN octet_length(j.intent::text)<=%s THEN to_jsonb(j) END FROM {table} r JOIN finance_invoicejob j ON j.id=r.job_id WHERE r.{field}=%s LIMIT 2',
        [max_bytes,max_bytes,correction if correction is not None else invoice]).fetchall()
    if not rows:return 'unknown',None,None
    if len(rows)!=1:return 'conflict',None,None
    r,j=rows[0]
    if r is None or j is None:raise ValidationError('Current Finance receipt exceeds configured observation budget')
    exact=(j['invoice_id']==invoice and j['kind']==variant and r['payload']==payload and r['sha256']==n.digest(payload))
    if correction is not None:exact=exact and j['intent'].get('correction')==correction
    if variant=='issue':exact=exact and r['obligation_key']==m['obligation_key'] and r['operation_key']=='obligation:'+m['obligation_key']
    if variant in ('deliver','adjust_deliver'):exact=exact and r['recipient_id']==m['recipient_id'] and j['intent'].get('recipient')==m['recipient_id']
    if not exact:return 'conflict',None,None
    return 'present',str(r['id']),n.digest({'variant':variant,'receipt':r})
