"""Finite recorded metadata, no evidence bodies, financial payloads or people names."""
from django.core.exceptions import ValidationError
from apps.policy.project_view_validators import GROUPS

class ProjectMetadataAdapter:
    name='recorded-project-metadata-v1'
    def read(self,case,groups,budget):
        from apps.pmo.engagement_models import ProjectIdentifier
        from apps.pmo.models import Milestone,ActionItem,DeliveryRecord
        if case.kind!='project' or any(g not in GROUPS for g in groups) or type(budget) is not int or not 1<=budget<=100:raise ValidationError('Bounded project metadata request required')
        result={}
        for group in groups:
            if group=='identifiers':
                source=ProjectIdentifier.objects.filter(case=case).select_related('record').order_by('-pk')
                convert=lambda x:{'id':x.pk,'namespace':x.namespace,'value':x.value,'source_at':x.record.created_at.isoformat()}
            elif group=='milestones':
                source=Milestone.objects.filter(case=case).order_by('-pk')
                convert=lambda x:{'id':x.pk,'name':x.name,'completed_at':x.completed_at.isoformat(),'source_at':x.completed_at.isoformat()}
            elif group=='actions':
                source=ActionItem.objects.filter(case=case,current__isnull=False).select_related('current').order_by('-pk')
                convert=lambda x:{'id':x.pk,'reference':x.reference,'status':x.current.status,'owner_assigned':x.current.owner_id is not None,'due_at':x.current.due_at.isoformat() if x.current.due_at else None,'deadline_basis':x.current.due_basis,'source_at':x.current.created_at.isoformat()}
            else:
                source=DeliveryRecord.objects.filter(dossier__case=case).exclude(kind='finance_confirmation').order_by('-pk')
                convert=lambda x:{'id':x.pk,'dossier_id':x.dossier_id,'kind':x.kind,'source_at':x.created_at.isoformat()}
            items=list(source[:budget+1])
            result[group]={'items':[convert(x) for x in items[:budget]],'truncated':len(items)>budget}
        return result
