from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.agents.models import CaseUpload
from apps.core.evidence_access import public_timeline
from apps.core.models import Audit, Case
from apps.finance.models import LedgerCheck, LedgerDecision
from apps.identity.models import Grant
from apps.workflows.factory_ledger_observation_proof import ATTACHED
from apps.workflows.models import FactoryWork
from tests import railway_ledger_observation_proof_seed as sample
from tests.helpers import rev


class LedgerObservationProofTests(TestCase):
    def test_optional_empty_multipart_file_is_treated_as_no_attachment(self):
        trial = get_user_model().objects.create_user(sample.TRIAL)
        with patch.dict('os.environ', {sample.GUARD: '1'}):
            data = sample.prepare()
        work = FactoryWork.objects.select_related('case').get(pk=data['work'])
        self.client.force_login(trial)
        payload = {'action': 'observe', 'revision': work.revision, 'case_revision': rev(work.case),
            'target': data['lineage'], 'outcome': 'multiple', 'evidence': data['observations']['multiple']}
        self.assertContains(self.client.post(data['observation_path'], payload | {'file': 'false.pdf'}),
                            'Choose an exact typed incumbent command')
        self.assertFalse(LedgerCheck.objects.filter(lineage_id=data['lineage']).exists())
        self.assertRedirects(self.client.post(data['observation_path'], payload | {'file': ''}), data['observation_path'])
        check = LedgerCheck.objects.get(lineage_id=data['lineage'])
        self.assertEqual((check.status, check.payload['state']), ('held', 'multiple'))
        self.assertFalse(Audit.objects.filter(case=work.case, action=ATTACHED).exists())

    def test_unknown_and_multiple_hold_with_exact_private_attachment_and_original_proof(self):
        trial=get_user_model().objects.create_user(sample.TRIAL)
        with patch.dict('os.environ',{sample.GUARD:'1'}):
            data=sample.prepare()
            self.assertEqual(sample.prepare(),{**data,'preserved':True})
        case=Case.objects.get(pk=data['case'])
        work=FactoryWork.objects.get(pk=data['work'])
        self.client.force_login(trial)
        self.assertContains(self.client.get(data['observation_path']),'Private observation proof')

        def observe(choice,proof,body=sample.PNG_BYTES):
            return self.client.post(data['observation_path'],{
                'action':'observe','revision':work.revision,'case_revision':rev(case),'target':data['lineage'],
                'outcome':choice,'evidence':data['observations'][proof],
                'file':SimpleUploadedFile(sample.PNG_NAME,body,content_type='image/png'),
            })

        with patch('adapters.case_uploads.put') as store, patch('adapters.case_uploads.discard_unbound') as discard:
            self.assertContains(observe('found','unknown'),'selected outcome must match')
            self.assertContains(observe('unknown','unknown',b'invalid PNG'),'valid PNG screenshot')
            store.assert_not_called()
            store.side_effect=OSError('simulated storage failure')
            self.assertContains(observe('unknown','unknown'),'Private proof storage is unavailable')
            discard.assert_called_once_with(store.call_args.args[0])
        self.assertFalse(LedgerCheck.objects.filter(lineage_id=data['lineage']).exists())
        self.assertFalse(Audit.objects.filter(case=case,action=ATTACHED).exists())

        retained={}
        with patch('adapters.case_uploads.put',side_effect=retained.__setitem__):
            self.assertRedirects(observe('unknown','unknown'),data['observation_path'])
            first=LedgerCheck.objects.get(lineage_id=data['lineage'])
            self.assertEqual(first.status,'held')
            self.assertContains(self.client.get(data['observation_path']),'Needs further evidence before Finance can verify the reference')
            self.assertRedirects(observe('multiple','multiple'),data['observation_path'])
        checks=list(LedgerCheck.objects.filter(lineage_id=data['lineage']).order_by('pk'))
        self.assertEqual([(x.pk,x.status,x.payload['state']) for x in checks],
                         [(first.pk,'held','unknown'),(checks[1].pk,'held','multiple')])
        self.assertFalse(CaseUpload.objects.filter(case=case).exists())
        self.assertFalse(public_timeline(case).filter(action=ATTACHED).exists())

        independent=get_user_model().objects.get(pk=data['independent'])
        self.client.force_login(independent)
        decision=self.client.get(data['decision_path'])
        self.assertContains(decision,'Open private observation proof')
        self.assertNotContains(decision,'Approve supplied reference')
        files=[reverse('factory_ledger_observation_proof',args=[work.pk,c.pk]) for c in checks]
        with patch('adapters.case_uploads.read',side_effect=lambda proof:retained[proof.key]) as storage:
            for path in files:
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                self.assertIn('no-store',response['Cache-Control'])
                self.assertEqual(b''.join(response.streaming_content),sample.PNG_BYTES)
            self.assertEqual(storage.call_count,2)
            Grant.objects.filter(case=case,user=trial,action='ledger.verify').update(active=False)
            self.assertNotContains(self.client.get(data['decision_path']),'Open private observation proof')
            self.assertEqual(self.client.get(files[1]).status_code,403)
            self.assertEqual(storage.call_count,2)
        self.assertFalse(LedgerDecision.objects.filter(verification__lineage_id=data['lineage'],verdict='approve').exists())
