class LocalIssueEscalationAdapter:
    """Exact local issue snapshot only; transport remains the controlled publication adapter."""
    def fields(self,request,template,audience):
        profile=request.profile;state=profile.state
        values={'executive_summary':state.title+': '+request.direction.replace('_',' ')+' requested.',
            'status':state.status,'issue_status':state.status+'; severity '+(state.severity or 'unknown'),
            'issue_impact':'Timeline impact '+('unknown' if profile.timeline_impact is None else 'yes' if profile.timeline_impact else 'no')+'. '+profile.classification,
            'issue_resolution':'Fix reference #'+str(state.fix_id) if state.fix_id else 'Resolution not recorded',
            'next_steps':request.note,'actions':state.next_action}
        citations=sorted({state.evidence_id,profile.evidence_id,request.evidence_id})
        allowed=template.definition['audience_fields'].get(audience,[])
        return {key:{'text':value,'evidence_ids':citations} for key,value in values.items() if key in allowed}
