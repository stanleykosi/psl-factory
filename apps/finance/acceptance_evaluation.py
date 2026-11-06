"""One evaluation per locked command/report, never a cross-request authority cache."""
from contextvars import ContextVar
from functools import wraps
from django.db import connection

_scope=ContextVar('finance_acceptance_evaluation',default=None)

def evaluated(function):
 @wraps(function)
 def call(*args,**kwargs):
  if _scope.get() is not None:return function(*args,**kwargs)
  token=_scope.set({'locked':set(),'current':set(),'confirmed':{}})
  try:return function(*args,**kwargs)
  finally:_scope.reset(token)
 return call

def locked(case_id):
 value=_scope.get()
 if value is not None and connection.in_atomic_block:value['locked'].add(str(case_id))

def checks(case_id):
 value=_scope.get()
 return value['current'] if value is not None and connection.in_atomic_block and str(case_id) in value['locked'] else None

def confirmed(case_id,key,read):
 value=_scope.get()
 if checks(case_id) is None:return read()
 if key not in value['confirmed']:value['confirmed'][key]=read()
 return value['confirmed'][key]

def changed():
 value=_scope.get()
 if value is not None:
  value['current'].clear();value['confirmed'].clear()
