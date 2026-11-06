from typing import Protocol
from apps.documents.contracts import digest
from apps.core.read_observation import read_observation


class DeliverySourceAdapter(Protocol):
    name:str
    def read(self,source)->dict: ...


class SyntheticDeliverySourceAdapter:
    name='synthetic-delivery-source-v1'
    def read(self,source):
        from apps.pmo.delivery import SOURCE_OWNERS
        return {'source_id':source.pk,'candidate_ref':source.dossier.candidate.reference,'external_ref':source.external_ref,
            'owner':SOURCE_OWNERS[source.kind],'evidence_sha256':source.evidence.sha256,'payload_sha256':digest(source.payload),
            'decision':'accepted','source_receipt':'synthetic:delivery:'+str(source.pk)}


class LocalDeliveryAdapter:
    @read_observation
    def read_go_live(self,dossier,data=None,template_id=None):
        from apps.pmo.delivery_closure import go_live_requirements
        return go_live_requirements(dossier,data,template_id)

    @read_observation
    def read_closure(self,dossier,data=None):
        """Native metadata prerequisites; no Finance amounts, document bodies or effects."""
        from apps.pmo.delivery_closure import closure_requirements
        return closure_requirements(dossier,data)

    def read(self,dossier):
        return self._read(dossier,current=False)

    def read_current(self,dossier):
        """Bounded latest facts and consumed document lineage, never a full-history claim."""
        return self._read(dossier,current=True)

    def _read(self,dossier,*,current):
        from django.core.exceptions import ValidationError
        source_query=dossier.sources.order_by('kind','-pk').distinct('kind') if current else dossier.sources.order_by('pk')
        record_query=dossier.records.order_by('kind','-pk').distinct('kind') if current else dossier.records.order_by('pk')
        sources=list(source_query[:101]);records=list(record_query[:201])
        if len(sources)>100 or len(records)>200:raise ValidationError('Delivery investigation exceeds bounded source/record budget')
        from apps.pmo.delivery import SOURCE_OWNERS
        from apps.pmo.models import DeliveryDocumentBinding,MeetingVersion
        binding_query=DeliveryDocumentBinding.objects.filter(dossier=dossier)
        if current:
            # A newer unsent draft must not hide the exact report already consumed
            # by a native acceptance/acknowledgement/decision.
            heads=list(binding_query.order_by('purpose','-pk').distinct('purpose').values_list('pk',flat=True)[:101])
            if len(heads)>100:raise ValidationError('Delivery investigation exceeds the current document-kind budget')
            from apps.documents.models import PublicationReceipt
            receipt_ids=[r.data['receipt_id'] for r in records if r.kind in ['go_live','go_live_reaffirmation','handover']]
            versions=[r.data['version_id'] for r in records if 'version_id' in r.data]
            versions+=list(PublicationReceipt.objects.filter(pk__in=receipt_ids).values_list('publication__version_id',flat=True))
            from django.db.models import Q
            binding_query=binding_query.filter(Q(pk__in=heads)|Q(version_id__in=versions))
        bindings=list(binding_query.select_related('version').order_by('pk')[:101])
        if len(bindings)>100:raise ValidationError('Delivery investigation exceeds the document budget')
        ids={dossier.evidence_id,dossier.candidate.requirements_id,*dossier.baseline.values(),*[s.evidence_id for s in sources],*[r.evidence_id for r in records]}
        for b in bindings:
            ids.update(x['id'] for x in b.version.source_manifest)
            if b.purpose=='closure':
                ids.add(b.data['report_evidence_id'])
                ids.add(MeetingVersion.objects.get(pk=b.data['retrospective_id']).evidence_id)
        for r in records:
            if r.kind in ['go_live','go_live_reaffirmation']:ids.update([r.data['pm_signature_id'],r.data['client_signature_id']])
            if r.kind=='archive':ids.update(r.data['inventory'].values())
        from apps.policy.services import resolve
        for component in ['D11.hypercare_criteria_ref','D11.template_storage_retention_rules','D05.role_principal_assignments']:
            policy=resolve(component,dossier.case)
            if policy.configuration:ids.update(int(x.split(':')[-1]) for x in policy.configuration.envelope['evidence_refs'])
        from apps.core.models import Evidence
        if Evidence.objects.filter(case=dossier.case,pk__in=ids).count()!=len(ids):raise ValidationError('Delivery citation belongs to another case or is missing')
        evidence=sorted(ids)
        signal_query=dossier.signals.order_by('kind','-pk').distinct('kind') if current else dossier.signals.order_by('pk')
        signals=list(signal_query.values('id','kind','source_key','snapshot')[:101 if current else 100])
        if current and len(signals)>100:raise ValidationError('Delivery investigation exceeds the current signal-kind budget')
        def verification_ids(source):
            query=source.verifications.order_by('-pk' if current else 'pk').values_list('pk',flat=True)
            return list(query[:1] if current else query)
        result={'dossier_id':dossier.pk,'candidate':dossier.candidate.reference,'baseline':dossier.baseline,
            'source_evidence_ids':evidence,'sources':[{'id':s.pk,'kind':s.kind,'owner':SOURCE_OWNERS[s.kind],
                'evidence_id':s.evidence_id,'verification_ids':verification_ids(s)} for s in sources],
            'records':[{'id':r.pk,'kind':r.kind,'parent_id':r.parent_id,'data':r.data,'snapshot':r.snapshot} for r in records],
            'signals':signals}
        if current:
            result['coverage']={'scope':'latest_per_kind_and_consumed_documents','complete_history':False,
                'selected':{'sources':len(sources),'records':len(records),'document_bindings':len(bindings),'signals':len(signals)},
                'retained_history':{'sources':dossier.sources.count(),'records':dossier.records.count(),
                    'document_bindings':DeliveryDocumentBinding.objects.filter(dossier=dossier).count(),'signals':dossier.signals.count()}}
        return result


def reporting_manifest(case):
    from django.core.exceptions import ValidationError
    from apps.pmo.models import DeliveryDossier,DeliverySource,DeliverySourceVerification,DeliveryRecord,DeliverySignal
    from apps.policy.services import resolve
    from apps.identity.models import Grant
    result={}
    for key,model,lookup in [('dossiers',DeliveryDossier,'case'),('sources',DeliverySource,'dossier__case'),
        ('verifications',DeliverySourceVerification,'source__dossier__case'),('records',DeliveryRecord,'dossier__case'),('signals',DeliverySignal,'dossier__case')]:
        result[key]=list(model.objects.filter(**{lookup:case}).order_by('pk').values_list('pk',flat=True)[:1001])
        if len(result[key])>1000:raise ValidationError('Delivery report exceeds bounded history budget')
    if result['dossiers']:
        result['policies']={}
        for component in ['D11.hypercare_criteria_ref','D11.template_storage_retention_rules','D05.role_principal_assignments']:
            r=resolve(component,case);result['policies'][component]=[r.status,r.configuration.pk if r.configuration else None]
        result['grants']=list(Grant.objects.filter(case=case,action__startswith='delivery.').order_by('pk').values_list('user_id','action','active','user__is_active')[:1001])
        if len(result['grants'])>1000:raise ValidationError('Delivery report grant budget exceeded')
        result['grants']=[list(x) for x in result['grants']]
    return result
