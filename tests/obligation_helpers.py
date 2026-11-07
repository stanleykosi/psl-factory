"""Explicit synthetic identity fixtures, never production fallback policy."""
import json
from django.utils import timezone
from apps.finance.billing import digest
from apps.finance import obligations
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy import scopes
from apps.policy.services import transition
from .billing_helpers import evidence
from .helpers import rev


def configure(actor, case, *, namespace=None, source=None, resolver_ids=None):
    if not case.synthetic:
        raise ValueError('This helper declares synthetic test identities only')
    decision = evidence(actor, case, 'policy_decision', 'Synthetic exact obligation namespace fixture; not owner policy')
    if source is None:
        value = {'implementation':'explicit_obligation_identity_v1',
            'namespace':namespace or 'synthetic-'+str(case.pk),
            'key_contract':{'reference':'fixture-explicit-key', 'version':1, 'sha256':digest({'fixture':'supplied-opaque-key/v1'})},
            'history_scope':{'reference':'fixture-history-scope','version':1,'sha256':digest({'fixture':'explicit-test-invoice-inventory'}),'coverage':'supplied_subset'},
            'resolver_role':'Finance', 'resolver_ids':resolver_ids or [actor.pk],
            'legacy_mode':'explicit_reconciliation_only'}
        config = draft_finance_policy(actor, case.pk, obligations.COMPONENT, value, decision.pk, timezone.now())
        transition(actor, config.pk, 'validated')
        source = scopes.create(actor, config.pk, 'organization', case.tenant, [])
        scopes.transition(actor, source.pk, 'validated'); scopes.transition(actor, source.pk, 'active')
    config = scopes.apply(actor, source.pk, case.pk, decision.pk, [])
    transition(actor, config.pk, 'validated'); transition(actor, config.pk, 'active')
    return source, config


def bind(actor, case, invoice, *, key=None, predecessor=None):
    config, source, value = obligations.contract(case)
    key = key or 'fixture:'+invoice.obligation_key
    body = obligations.declaration(invoice, value['namespace'], key, predecessor.pk if predecessor else None)
    e = evidence(actor, case, 'invoice_identity', json.dumps(body))
    return obligations.bind(actor, case.pk, invoice.pk, key, e.pk, rev(case), predecessor_id=predecessor.pk if predecessor else None)
