"""Versioned planning-provider selection; v1 remains synthetic-only."""
from copy import deepcopy
from django.core.exceptions import ValidationError

GOVERNED='governed_factory_v1'
SYNTHETIC='synthetic_factory_v1'

def shape_for(target,schema,shape):
    if target.schema_ref==schema.rsplit('/',1)[0]+'/v2':
        value=deepcopy(shape);value['properties']['provider']={'enum':[None,SYNTHETIC,GOVERNED]}
        return target.schema_ref,value
    return schema,shape

def scope(case,value):
    if value['provider']==SYNTHETIC and not case.synthetic:
        raise ValidationError('Synthetic factory provider cannot activate for operational data')
