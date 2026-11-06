from apps.core.models import Evidence
from apps.finance.models import SignedBaselineIntake


class InternalSignedBaselineAdapter:
    """Same-database atomic delivery; future remote writes need a reserved-effect worker."""
    def deliver(self, adoption):
        case = adoption.revision.dossier.case
        sources = {name: Evidence.objects.get(case=case, pk=adoption.after[name+'_id'])
            for name in ['plan', 'sow', 'signed']}
        payload = {'adoption_id': adoption.pk, 'commercial_revision_id': adoption.revision_id,
            'sources': {name: {'id': source.pk, 'sha256': source.sha256} for name, source in sources.items()},
            'agreed_billing_schedule': None, 'invoice_created': False}
        receipt, _ = SignedBaselineIntake.objects.get_or_create(adoption=adoption,
            defaults={'case': case, 'operation_key': f'baseline-adoption:{adoption.pk}:finance:v1', 'payload': payload})
        if receipt.payload != payload:
            raise ValueError('Signed-baseline delivery payload mismatch; reconcile before retry')
        return receipt
