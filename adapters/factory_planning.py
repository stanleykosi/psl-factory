"""Domain-authorised internal commands, not an external approval simulator."""
from django.core.exceptions import ValidationError
from apps.pmo import planning,delivery
from apps.pmo.models import DeliveryDossier

class NativePlanningAdapter:
    def investigate(self,work):
        from apps.agents.planning import investigate
        return investigate(work.execution_actor,work.case_id)

    def route(self,work):
        return planning.open_requests(work.execution_actor,work.case_id,work.source_head_id)

    def prepare(self,work):
        return planning.prepare(work.execution_actor,work.case_id,work.source_head_id)

    def handoff(self,work,ready):
        value=planning.current_readiness(work.case,ready.pk)
        dossier=DeliveryDossier.objects.filter(case=work.case,candidate_id=value['inputs']['candidate_id']).first()
        if dossier is None:
            work.case.refresh_from_db()
            dossier=delivery.open_dossier(work.execution_actor,work.case_id,value['inputs']['candidate_id'],ready.pk,
                'Source-referenced planning readiness; delivery verification remains separate.',work.case.revision)
        return planning.bridge(work.execution_actor,work.case_id,ready.pk,dossier.pk)

    def verify(self,work,ready,source):
        value=planning.current_readiness(work.case,ready.pk)
        if value['packet_id']!=work.source_head_id or source.dossier.case_id!=work.case_id or source.dossier.candidate_id!=value['inputs']['candidate_id'] or source.kind!='scope_baseline' or source.evidence_id!=ready.pk or source.external_ref!='psl:planning-readiness:'+str(ready.pk):
            raise ValidationError('Exact current planning readiness and delivery handoff required')
        if source.dossier.sources.filter(kind='scope_baseline').order_by('-pk').first().pk!=source.pk:raise ValidationError('The delivery scope source was superseded; source-owned review is required')
        # Receipt of an internal source is not native source verification or Planning exit.
        return {'verified':True,'verification_scope':'current_planning_artifact_and_internal_handoff',
            'packet':work.source_head_id,'readiness':ready.pk,'delivery_source':source.pk,'dossier':source.dossier_id,
            'owner_observations':value['inputs']['observations'],'native_verified':False,'environment':'synthetic_reference_only'}
