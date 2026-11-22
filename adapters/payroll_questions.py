"""Closed internal HR question tools. No free text, private rows or external effects."""
from adapters.forecast import obj
from apps.documents.contracts import validate

TOPICS={
    'report_coverage':'Which staff information does this report cover?',
    'business_unit_basis':'How was staff membership assigned to business units?',
    'staff_source_review':'Please check the staff information behind this report.',
}
REPLIES={
    'staff_basis_confirmed':'HR confirmed the staff information used for this report. Finance totals still follow their own review.',
    'source_review_needed':'HR is reviewing the staff information. Any corrected source must follow the usual review process.',
    'more_detail_needed':'HR needs more detail. Use the approved internal channel to discuss the question with the assigned owner.',
}
PACKET=obj({'format':{'const':'psl.payroll-report-question/v1'},
    'publication_id':{'type':'integer','minimum':1},'report_version':{'type':'integer','minimum':1},
    'source_run_id':{'type':'integer','minimum':1},'source_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
    'period':{'type':'string','pattern':r'^\d{4}-(0[1-9]|1[0-2])$'},
    'topic':{'enum':list(TOPICS)},'private_payloads_read':{'const':False}})


def command(kind,value):
    schemas={'record':obj({'topic':{'enum':list(TOPICS)}}),
             'answer':obj({'reply':{'enum':list(REPLIES)}})}
    validate(schemas[kind],value)
    return value
