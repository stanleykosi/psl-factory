"""Ordinary client test-response contracts; never go-live or payment authority."""
import re
import unicodedata
from adapters.forecast import obj
from apps.documents.contracts import validate

TARGET='uat_client_target'
RESPONSE='uat_client_response'
KINDS={TARGET,RESPONSE}
LEGACY_INSPECTION='client-uat-evidence-check/v1'
INSPECTION='client-uat-evidence-check/v2'
REVIEW='human-client-uat-proof/v1'
GATE='human-attested-client-uat/v1'
WITHDRAWAL='client-uat-recording-withdrawal/v1'
ID={'type':'integer','minimum':1}
NULL_ID={'anyOf':[ID,{'type':'null'}]}
HASH={'type':'string','pattern':'^[a-f0-9]{64}$'}
OP={'type':'string','pattern':r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'}
TEXT={'type':'string','minLength':1,'maxLength':2000}
AUTH={'type':'object','properties':{'D05.role_principal_assignments':ID},
      'required':['D05.role_principal_assignments'],'additionalProperties':False}
OUTCOMES={'approved':'Approved','changes_requested':'Asked for changes','rejected':'Rejected',
          'approved_with_workaround':'Approved the stated workaround'}
PROOF=obj({'id':ID,'sha256':HASH,'size':{'type':'integer','minimum':1,'maximum':5*1024*1024},'actor_id':ID})
CONTACT=obj({'id':ID,'number':ID,'evidence_id':ID,'evidence_sha256':HASH})
CANDIDATE=obj({'id':ID,'reference':{'type':'string','minLength':1,'maxLength':160},
               'requirements_id':ID,'requirements_sha256':HASH})
SCHEMAS={
 TARGET:obj({'format':{'const':'psl.client-uat-target/v1'},'number':ID,'predecessor_id':NULL_ID,'operation_key':OP,'command_sha256':HASH,
     'candidate':CANDIDATE,'contact':CONTACT,'sent_at':{'type':'string'},
     'baseline':{'type':'object','additionalProperties':ID},'replaces_gate_id':NULL_ID,
     'recording_authority':AUTH}),
 RESPONSE:obj({'format':{'const':'psl.client-uat-response/v1'},'number':ID,'predecessor_id':NULL_ID,'operation_key':OP,'command_sha256':HASH,
     'target_id':ID,'target_sha256':HASH,'responded_at':{'type':'string'},
     'outcome':{'enum':list(OUTCOMES)},'genuine':{'const':True},
     'note':{'type':'string','maxLength':2000},'workaround':{'anyOf':[TEXT,{'type':'null'}]},
     'source_reference':{'anyOf':[{'type':'string','minLength':1,'maxLength':240},{'type':'null'}]},
     'proofs':{'type':'array','minItems':1,'maxItems':4,'items':PROOF},'recording_authority':AUTH}),
}
TARGET_COMMAND=obj({'dossier':ID,'contact':ID,'sent_at':{'type':'string','maxLength':64},
                    'previous':NULL_ID,'gate':NULL_ID,'replace':{'type':'boolean'}})
RESPONSE_COMMAND=obj({'target':ID,'responded_at':{'type':'string','maxLength':64},'outcome':{'enum':list(OUTCOMES)},
    'genuine':{'const':True},'note':{'type':'string','maxLength':2000},
    'workaround':{'anyOf':[TEXT,{'type':'null'}]},
    'source_reference':{'anyOf':[{'type':'string','minLength':1,'maxLength':240},{'type':'null'}]},
    'proof_ids':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,'items':ID},'previous':NULL_ID})


def validate_payload(kind,payload):
    validate(SCHEMAS[kind],payload)
    if kind==RESPONSE:
        if len({row['id'] for row in payload['proofs']})!=len(payload['proofs']):
            from django.core.exceptions import ValidationError
            raise ValidationError('Choose each proof file once')
        if (payload['outcome']=='approved_with_workaround')!=(payload['workaround'] is not None):
            from django.core.exceptions import ValidationError
            raise ValidationError('State a workaround only when the client explicitly approved it')
        if payload['workaround'] is not None and not payload['workaround'].strip():
            from django.core.exceptions import ValidationError
            raise ValidationError('State the actual workaround the client approved')


def normalized(value,*,fold=True):
    text=unicodedata.normalize('NFKC',value)
    return ' '.join((text.casefold() if fold else text).split())


def mentions(text,value,*,identifier=False):
    expected=normalized(value,fold=not identifier)
    if not expected:return False
    # A build reference keeps its case and punctuation. A different slug or
    # version suffix must not satisfy a literal match; sentence punctuation may.
    boundary=r'(?<![\w/:@.\-])' if identifier else r'(?<!\w)'
    ending=r'(?![\w/:@\-]|\.[\w])' if identifier else r'(?!\w)'
    return re.search(boundary+re.escape(expected)+ending,normalized(text,fold=not identifier)) is not None
