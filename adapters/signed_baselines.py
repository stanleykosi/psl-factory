from apps.core.models import Evidence
from apps.finance.models import SignedBaselineIntake


class InternalSignedBaselineAdapter:
    """Same-database atomic delivery; future remote writes need a reserved-effect worker."""
    def deliver(self, adoption):
        from apps.pmo.models import CommercialSignatureUse
        case = adoption.revision.dossier.case
        sources = {name: Evidence.objects.get(case=case, pk=adoption.after[name+'_id'])
            for name in ['plan', 'sow', 'signed']}
        payload = {'adoption_id': adoption.pk, 'commercial_revision_id': adoption.revision_id,
            'sources': {name: {'id': source.pk, 'sha256': source.sha256} for name, source in sources.items()},
            'agreed_billing_schedule': None, 'invoice_created': False}
        use = CommercialSignatureUse.objects.filter(adoption=adoption).select_related('packet').first()
        if use:
            payload['signature_packet'] = {'id': use.packet_id, 'sources': use.packet.sources,
                'signatures': use.packet.signatures, 'contract_id': use.packet.policy_id,
                'assurance': 'human_verified_reference_only'}
        # Lookup before creation preserves exact historical receipts. A legacy
        # generic-signature adoption is history, not newly verified dual proof.
        receipt = SignedBaselineIntake.objects.filter(adoption=adoption).first()
        if receipt:
            if receipt.payload != payload:
                raise ValueError('Signed-baseline delivery payload mismatch; reconcile before retry')
            return receipt
        if not use:
            raise ValueError('Historical baseline has no two-document proof or receipt; reconcile without inventing signatures')
        receipt, _ = SignedBaselineIntake.objects.get_or_create(adoption=adoption,
            defaults={'case': case, 'operation_key': f'baseline-adoption:{adoption.pk}:finance:v1', 'payload': payload})
        if receipt.payload != payload:
            raise ValueError('Signed-baseline delivery payload mismatch; reconcile before retry')
        return receipt
