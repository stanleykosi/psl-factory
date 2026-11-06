"""Reviewed JSON gateway extension, not a claim about any model vendor API."""
from django.core.exceptions import ValidationError
from adapters.readiness import http,RECEIPT
from apps.documents.contracts import validate
import json

class FactoryPlannerAdapter:
    def lookup(self,intent,private):
        try:
            value=http(private,'/factory/plans/'+intent['operation_key'])
            json.dumps(value,allow_nan=False);validate(RECEIPT,value)
        except (ValidationError,ValueError,TypeError,RecursionError):raise ConnectionError('Planning receipt transport unavailable') from None
        if value['operation_key']!=intent['operation_key']:raise ConnectionError('Planning receipt identity mismatch')
        if value['status']=='not_found':
            if value['result'] is not None:raise ConnectionError('Ambiguous planning receipt')
            return None
        if value['status']=='failed':return {'provider_failed':True}
        if value['result'] is None:raise ConnectionError('Planning receipt has no result')
        return value['result']

    def plan(self,intent,private):
        try:
            value=http(private,'/factory/plans',method='POST',key=intent['operation_key'],body=intent['payload'])
            json.dumps(value,allow_nan=False);return value
        except (ValidationError,ValueError,TypeError,RecursionError):raise ConnectionError('Planning response unavailable; reconcile original receipt') from None
