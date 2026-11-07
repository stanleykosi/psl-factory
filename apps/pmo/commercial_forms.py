from django import forms
from apps.core.models import Evidence
from .commercial import SOURCE_KINDS, ROLES


class ProposalForm(forms.Form):
    context=forms.ModelChoiceField(queryset=Evidence.objects.none())
    reason=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    reuse=forms.BooleanField(required=False,label='Request configured reuse of unchanged-subject decisions')
    def __init__(self,*args,case,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['context'].queryset=case.evidence.filter(kind__in=['requirements','client_feedback','change_request'])
        for kind in SOURCE_KINDS:
            self.fields[kind]=forms.ModelChoiceField(queryset=case.evidence.filter(kind=kind))


class CommercialDecisionForm(forms.Form):
    role=forms.ChoiceField(choices=[(v,v) for v in ROLES])
    verdict=forms.ChoiceField(choices=[(v,v.title()) for v in ['approve','return','reject','withdraw']])
    note=forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    delegated=forms.BooleanField(required=False,label='Use configured delegated authority')


class SignaturePacketForm(forms.Form):
    prd = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Exact current PRD document version')
    predecessor = forms.IntegerField(required=False, widget=forms.HiddenInput)
    operation_key = forms.CharField(max_length=100, label='Unique capture reference')
    note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import CommercialRevision, CommercialCase
        self.fields['commercial_revision'] = forms.ModelChoiceField(queryset=CommercialRevision.objects.filter(dossier__case=case), required=False, label='Exact commercial revision, including the adopted version for reaffirmation')
        self.fields['commercial_revision'].initial = CommercialCase.objects.filter(case=case).values_list('current_id', flat=True).first()
        self.fields['prd'].queryset = case.evidence.filter(kind='prd')
        for kind in ['sow', 'prd']:
            title = kind.upper()
            self.fields[kind + '_signature'] = forms.ModelChoiceField(queryset=case.evidence.filter(kind='signature'), required=False, label=title + ' signature evidence')
            self.fields[kind + '_party'] = forms.CharField(max_length=200, required=False, label=title + ' actual owner-eligible signer reference')
            self.fields[kind + '_method'] = forms.CharField(max_length=200, required=False, label=title + ' evidence method')
            self.fields[kind + '_locator'] = forms.CharField(max_length=500, required=False, label=title + ' signature location within evidence')
            self.fields[kind + '_verified'] = forms.BooleanField(required=False, label='I checked this exact ' + title + ' signature reference as a human; no provider verification is claimed')

    def clean(self):
        data = super().clean()
        signatures = {}
        for kind in ['sow', 'prd']:
            evidence = data.get(kind + '_signature')
            details = [data.get(kind + '_' + field) for field in ['party', 'method', 'locator']]
            if evidence:
                if data.get(kind + '_verified') and not all(details):
                    raise forms.ValidationError('Identify the actual party, method and signature location for each selected document signature')
                signatures[kind] = {'evidence_id': evidence.pk, 'party_ref': details[0] or None, 'method': details[1] or None,
                                    'locator': details[2] or None, 'human_verified': data.get(kind + '_verified', False)}
            elif any(details) or data.get(kind + '_verified'):
                raise forms.ValidationError('Select evidence for the entered signature details')
        data['signatures'] = signatures
        return data


class SignatureContractForm(forms.Form):
    party_ref = forms.CharField(max_length=200, required=False, label='Owner-authorized signer reference, only when signatures are required')
    display_name = forms.CharField(max_length=200, required=False, label='Actual eligible signer name')
    identity_evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), required=False)
    documents = forms.MultipleChoiceField(required=False, choices=[('sow', 'SOW'), ('prd', 'PRD')], widget=forms.CheckboxSelectMultiple)
    methods = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), label='Owner-approved signature evidence methods, one per line')
    applicability = forms.ChoiceField(initial='unresolved', choices=[('unresolved', 'Owner classification unresolved'), ('client_project', 'Client project'), ('internal_project', 'Proven internal-only project')])
    signature_requirement = forms.ChoiceField(initial='unresolved', choices=[('unresolved', 'Owner decision unresolved'), ('required', 'Actual eligible signatures required'), ('not_applicable', 'Owner confirms signatures are not applicable to this proven internal project')])
    scope_evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), required=False, label='Owner-backed project scope evidence, required for internal classification')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Owner decision evidence')
    unchanged_prd_signature_reuse = forms.ChoiceField(required=False, initial='unconfigured', label='Owner rule for reusing an unchanged PRD signature on another baseline', choices=[('unconfigured', 'Owner decision unresolved'), ('same_document_reference_allowed', 'Owner permits exact unchanged-document reference reuse'), ('fresh_document_signature_required', 'Owner requires a fresh signature reference')])
    effective_from = forms.DateTimeField()

    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, **kwargs)
        self.case = case
        self.fields['identity_evidence'].queryset = case.evidence.filter(kind__in=['client_identity', 'internal_signer_identity'])
        self.fields['scope_evidence'].queryset = case.evidence.filter(kind__in=['internal_project_scope', 'client_project_scope'])
        self.fields['evidence'].queryset = case.evidence.filter(kind='policy_decision')

    def clean_methods(self):
        methods = [line.strip() for line in self.cleaned_data['methods'].splitlines() if line.strip()]
        if len(methods) > 20 or any(len(item) > 200 for item in methods) or len(set(methods)) != len(methods):
            raise forms.ValidationError('Provide at most 20 distinct owner-approved methods, each at most 200 characters')
        return methods

    def clean(self):
        data = super().clean()
        party = [data.get(key) for key in ['party_ref', 'display_name', 'identity_evidence', 'documents']]
        if (any(party) or data.get('signature_requirement') == 'required') and not all(party):
            raise forms.ValidationError('Required signatures need the actual eligible signer identity and document scope; unresolved or exempt projects need no invented signer')
        return data

    def contract(self):
        d = self.cleaned_data
        return {'parties': ([{'party_ref': d['party_ref'], 'display_name': d['display_name'],
                            'identity_evidence_id': d['identity_evidence'].pk, 'documents': d['documents']}] if d['identity_evidence'] else []),
                'methods': d['methods'], 'assurance': 'human_verified_reference_only',
                'unchanged_prd_signature_reuse': d['unchanged_prd_signature_reuse'] or 'unconfigured',
                'applicability': d['applicability'], 'signature_requirement': d['signature_requirement'],
                'scope_evidence_id': d['scope_evidence'].pk if d['scope_evidence'] else None, 'allow_synthetic': self.case.synthetic}


class InternalSignatureExemptionForm(forms.Form):
    prd = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='Exact prepared internal PRD version')
    predecessor = forms.IntegerField(required=False, widget=forms.HiddenInput)
    operation_key = forms.CharField(max_length=100, label='Unique internal exemption capture reference')
    note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['prd'].queryset = case.evidence.filter(kind='prd')
