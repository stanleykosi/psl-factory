"""Explicit owner selection for ambiguous submitted RFP versions; no result precedence."""
from adapters.forecast import obj
from .document_validators import typed

COMPONENT='OPS.rfp_outcome_reconciliation'
SCHEMA='schema:psl/rfp-outcome-reconciliation/v1'
METHOD='explicit_current_owner_selection_v1'
VALUE=obj({'method':{'enum':[None,METHOD]}})


def validate_reference(component,target,case,runtime=False):
    # The native RFP service rechecks existing relationship-owner authority and
    # exact submission/outcome evidence. This method never appoints an owner.
    return typed(target,SCHEMA,VALUE)
