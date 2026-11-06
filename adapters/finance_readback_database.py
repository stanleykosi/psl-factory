"""Ephemeral, thread/context-isolated ORM reads against an already validated provider.

Routing never activates a recovered app. Only the installed Finance authority evaluator
uses this compartment. SQL read-only transactions and a rejecting write router agree.
"""
import copy
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4
from django.db import connections,transaction
from django.core.exceptions import PermissionDenied,ValidationError

ACTIVE=ContextVar('finance_readback_database',default=None)
SUCCESSORS=ContextVar('finance_readback_successors',default=False)
ALLOWED={'core.case','core.evidence','auth.user','identity.grant','policy.configuration','policy.policystate','policy.registeredreference',
 'finance.financereceiptfollowup','finance.financereceiptfollowupdecision','finance.invoicejob'}
LINEAGE={'finance.financefollowupsuccessor','finance.financefollowupsuccessorreview','finance.invoice','finance.invoicecorrection',
 'finance.invoiceissue','finance.invoicedelivery','finance.invoicecorrectionacceptance','finance.invoicecorrectiondelivery'}
class Router:
    def db_for_read(self,model,**hints):
        alias=ACTIVE.get()
        if alias and model._meta.label_lower not in ALLOWED | (LINEAGE if SUCCESSORS.get() else set()):raise PermissionDenied('Model outside installed Finance readback contract')
        return alias
    def db_for_write(self,model,**hints):
        if ACTIVE.get():raise PermissionDenied('Finance readback cannot write source records')
    def allow_relation(self,obj1,obj2,**hints):
        if ACTIVE.get():return obj1._state.db==obj2._state.db==ACTIVE.get()

@contextmanager
def provider(args,rules,successors=False):
    alias='finance_readback_'+uuid4().hex
    config=copy.deepcopy(connections['default'].settings_dict)
    config.update(NAME=args['dbname'],HOST=args['host'],PORT=str(args['port']),USER=args['user'],PASSWORD=args['password'],CONN_MAX_AGE=0,ATOMIC_REQUESTS=False,
        OPTIONS={'sslmode':args['sslmode'],'connect_timeout':5,'options':'-c default_transaction_read_only=on'})
    connections.databases[alias]=config
    token=None;lineage_token=SUCCESSORS.set(successors);db=connections[alias];queries=0
    def bounded(execute,sql,params,many,context):
        nonlocal queries
        queries+=1
        if queries>rules['max_queries'] or not sql.lstrip().upper().startswith('SELECT'):
            raise ValidationError('Installed read-only Finance query budget exceeded')
        return execute(sql,params,many,context)
    try:
        with transaction.atomic(using=alias):
            with db.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                cursor.execute("SELECT set_config('statement_timeout',%s,true)",[str(rules['max_seconds']*1000)])
            token=ACTIVE.set(alias)
            with db.execute_wrapper(bounded):yield db
    finally:
        if token is not None:ACTIVE.reset(token)
        SUCCESSORS.reset(lineage_token)
        db.close();del connections[alias];connections.databases.pop(alias,None)
