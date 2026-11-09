"""Native identity boundaries. Requires the separately authorised PostgreSQL run."""
import json
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, DatabaseError
from apps.finance import invoices, invoice_delivery, obligations
from apps.finance.models import ObligationClaim, ObligationBinding, ObligationEffect, InvoiceIssue
from apps.policy import scopes
from .settlement_helpers import fixture, draft, approve
from .helpers import rev
from .obligation_helpers import configure, bind


class ObligationIdentityTests(TransactionTestCase):
    def setUp(self):
        self.a,self.c,self.cov,self.p,self.e=fixture()
        self.i=draft(self.a,self.c,self.p)

    def test_unconfigured_draft_and_review_remain_possible_but_issue_holds(self):
        approve(self.a,self.c,self.i,self.e)
        with self.assertRaises(ValidationError):
            invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        self.assertFalse(InvoiceIssue.objects.exists())
        self.assertEqual(obligations.projection(self.i)['status'],'binding_required')

    def ready(self):
        source,config=configure(self.a,self.c)
        binding=bind(self.a,self.c,self.i)
        approve(self.a,self.c,self.i,self.e)
        return source,config,binding

    def test_explicit_binding_issues_and_preserves_original_key(self):
        key=self.i.obligation_key
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(job_id=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status,'confirmed',job.error)
        issue=InvoiceIssue.objects.get(invoice=self.i)
        self.assertEqual(issue.obligation_key,key)
        self.assertEqual(ObligationEffect.objects.get().claim_id,binding.local_key.claim_id)
        self.assertEqual(issue.operation_key,'obligation:'+key)

    def test_revoked_namespace_holds_new_dispatch(self):
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        scopes.transition(self.a,source.pk,'revoked')
        invoice_delivery.run_once(job_id=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status,'held')
        self.assertFalse(InvoiceIssue.objects.exists())

    def test_claim_is_not_reassigned_after_policy_reaffirmation(self):
        source,config,binding=self.ready()
        with self.assertRaises(ValidationError):
            bind(self.a,self.c,self.i,key='different-key')
        self.assertEqual(ObligationClaim.objects.count(),1)
        self.assertEqual(ObligationBinding.objects.count(),1)

    def test_raw_sql_identity_history_is_immutable(self):
        self.ready()
        with self.assertRaises(DatabaseError),transaction.atomic():
            ObligationClaim.objects.update(key='forged')
        self.assertNotEqual(ObligationClaim.objects.get().key,'forged')

    def second_case(self, source):
        from .helpers import setup_case
        from .billing_helpers import coverage,prices,usage,prepare,evidence
        from .settlement_helpers import configured
        from apps.identity.models import Grant
        a,c=setup_case(username='other-human')
        cov=coverage(a,c);prices(a,c,cov);u=usage(a,c,cov);p=prepare(a,c,cov,u=u);configured(a,c)
        e={'invoice_review':evidence(a,c,'invoice_review','Synthetic exact review')}
        Grant.objects.create(user=a,case=self.c,action='case.read')
        Grant.objects.create(user=a,case=self.c,action='policy.read')
        configure(a,c,source=source)
        i=draft(a,c,p,reference='OTHER-INV')
        return a,c,i,e

    def test_same_namespace_cross_case_claim_is_private_conflict(self):
        source,config=configure(self.a,self.c)
        a,c,i,e=self.second_case(source)
        bind(self.a,self.c,self.i,key='explicit-obligation-1')
        with self.assertRaises(ValidationError) as raised:
            bind(a,c,i,key='explicit-obligation-1')
        message=str(raised.exception)
        self.assertIn('Identity already claimed',message)
        for secret in [str(self.c.pk),self.i.reference,self.c.title]:
            self.assertNotIn(secret,message)
        self.assertEqual(ObligationClaim.objects.count(),1)

    def test_parallel_cross_case_claim_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        source,config=configure(self.a,self.c)
        a,c,i,e=self.second_case(source)
        barrier=Barrier(2)
        def attempt(actor,case,invoice):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                bind(actor,case,invoice,key='one-racing-key')
                return 'claimed'
            except ValidationError:
                return 'conflict'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda args:attempt(*args),[(self.a,self.c,self.i),(a,c,i)]))
        self.assertCountEqual(results,['claimed','conflict'])
        self.assertEqual(ObligationClaim.objects.count(),1)

    def test_timeout_after_accept_recovers_after_namespace_revocation(self):
        from adapters.invoices import TimeoutAfterInvoiceAccept
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(adapter=TimeoutAfterInvoiceAccept(),job_id=job.pk)
        job.refresh_from_db();self.assertEqual(job.status,'unknown')
        scopes.transition(self.a,source.pk,'revoked')
        invoice_delivery.run_once(job_id=job.pk,lookup_only=True)
        job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assertEqual(InvoiceIssue.objects.count(),1)
        self.assertEqual(ObligationEffect.objects.count(),1)

    def test_alias_is_evidenced_and_cannot_merge_independent_claim(self):
        from .billing_helpers import evidence
        source,config,binding=self.ready()
        claim=binding.local_key.claim
        body={'namespace':claim.namespace.name,'key':'spelling-alias','canonical_claim_id':claim.pk,
            'canonical_key':claim.key,'canonical_case_id':str(self.c.pk)}
        ev=evidence(self.a,self.c,'invoice_identity_alias',json.dumps(body))
        alias=obligations.resolve_alias(self.a,self.c.pk,claim.pk,'spelling-alias',ev.pk,rev(self.c))
        self.assertEqual(alias.claim_id,claim.pk)
        bind(self.a,self.c,self.i,key='spelling-alias')
        self.assertEqual(ObligationClaim.objects.count(),1)
        with self.assertRaises(ValidationError):
            obligations.resolve_alias(self.a,self.c.pk,claim.pk,claim.key,ev.pk,rev(self.c))

    def test_direct_sql_frozen_marker_cannot_be_forged(self):
        from apps.finance.models import ObligationLegacyAttempt
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():
            ObligationLegacyAttempt.objects.create(job=job,snapshot={'forged':True})
        self.assertFalse(ObligationLegacyAttempt.objects.exists())

    def test_direct_sql_job_cannot_impersonate_reserved_binding(self):
        from apps.finance.models import InvoiceJob
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        forged=dict(job.intent,obligation_identity=dict(job.intent['obligation_identity'],claim=987654321))
        with self.assertRaises(DatabaseError),transaction.atomic():
            InvoiceJob.objects.create(invoice=self.i,kind='issue',generation=2,intent=forged,
                operation_key='forged-new-request',actor=self.a)
        with self.assertRaises(DatabaseError),transaction.atomic():
            InvoiceJob.objects.filter(pk=job.pk).update(intent=forged)
        job.refresh_from_db();self.assertEqual(job.intent['obligation_identity']['claim'],binding.local_key.claim_id)

    def test_namespace_conflicting_source_does_not_silently_win(self):
        source,config,binding=self.ready()
        a,c,i,e=self.second_case(source)
        configure(a,c,namespace=binding.local_key.claim.namespace.name)
        with self.assertRaisesMessage(ValidationError,'authoritative source changed'):
            bind(a,c,i,key='new-opaque-key')
        self.assertEqual(ObligationClaim.objects.count(),1)

    def test_exact_namespace_contract_change_cannot_release_claim(self):
        source,config,binding=self.ready()
        old=binding.local_key.claim
        # A replacement source with a different name cannot re-key the already-bound local identity.
        configure(self.a,self.c,namespace='replacement-namespace')
        with self.assertRaisesMessage(ValidationError,'cannot be reassigned'):
            bind(self.a,self.c,self.i,key='replacement-key')
        self.assertEqual(ObligationClaim.objects.count(),1)
        self.assertEqual(ObligationBinding.objects.get().local_key.claim_id,old.pk)

    def test_alias_reaffirmation_keeps_same_target_and_tombstone(self):
        from .billing_helpers import evidence
        from apps.finance.models import ObligationAlias
        source,config,binding=self.ready()
        claim=binding.local_key.claim
        body={'namespace':claim.namespace.name,'key':'repeat-alias','canonical_claim_id':claim.pk,
              'canonical_key':claim.key,'canonical_case_id':str(self.c.pk)}
        e=evidence(self.a,self.c,'invoice_identity_alias',json.dumps(body))
        first=obligations.resolve_alias(self.a,self.c.pk,claim.pk,'repeat-alias',e.pk,rev(self.c))
        second=obligations.resolve_alias(self.a,self.c.pk,claim.pk,'repeat-alias',e.pk,rev(self.c))
        self.assertEqual((first.version,second.version),(1,2))
        self.assertEqual(ObligationAlias.objects.count(),2)
        with self.assertRaises(ValidationError):obligations.alias_current(first)
        obligations.alias_current(second)

    def test_same_explicit_key_in_distinct_namespaces_is_not_inferred_equal(self):
        source,config=configure(self.a,self.c,namespace='explicit-scope-one')
        a,c,i,e=self.second_case(source)
        configure(a,c,namespace='explicit-scope-two')
        first=bind(self.a,self.c,self.i,key='same-source-spelling')
        second=bind(a,c,i,key='same-source-spelling')
        self.assertNotEqual(first.local_key.claim_id,second.local_key.claim_id)
        self.assertEqual(ObligationClaim.objects.count(),2)

    def test_sql_unbound_new_reservation_is_rejected(self):
        from apps.finance.models import InvoiceJob
        approve(self.a,self.c,self.i,self.e)
        with self.assertRaises(DatabaseError),transaction.atomic():
            InvoiceJob.objects.create(invoice=self.i,kind='issue',intent={'identity':{'lease_seconds':30}},
                operation_key='unbound-new-request',actor=self.a)
        self.assertFalse(InvoiceJob.objects.exists())

    def test_attempted_effect_cannot_get_new_operation_key_on_same_invoice(self):
        from apps.finance.models import InvoiceJob
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        pk,fence=invoice_delivery.claim(job_id=job.pk)
        invoice_delivery.dispatch_context(pk,fence)  # Reserved exact attempt; no provider receipt yet.
        invoice_delivery.finish(pk,fence,'held','Synthetic lookup cannot establish acceptance')
        with self.assertRaisesMessage(ValidationError,'Original attempted effect'):
            invoice_delivery.operate(self.a,self.c.pk,job.pk,'replace_intent','Synthetic same-invoice replacement',rev(self.c))
        job.refresh_from_db()
        with self.assertRaises(DatabaseError),transaction.atomic():
            InvoiceJob.objects.create(invoice=self.i,kind='issue',generation=2,intent=job.intent,
                operation_key='different-external-operation',actor=self.a)
        self.assertEqual(InvoiceJob.objects.filter(invoice=self.i,kind='issue').count(),1)
        self.assertFalse(InvoiceIssue.objects.exists())

    def test_repeatable_read_identity_write_is_rejected(self):
        from django.db import connection
        source,config=configure(self.a,self.c)
        with self.assertRaisesMessage(ValidationError,'READ COMMITTED'),transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            bind(self.a,self.c,self.i,key='rr-key')
        self.assertFalse(ObligationClaim.objects.exists())

    def test_sql_repeatable_read_reservation_is_rejected(self):
        from django.db import connection
        from apps.finance.models import InvoiceJob
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            InvoiceJob.objects.create(invoice=self.i,kind='issue',generation=2,intent=job.intent,
                operation_key='rr-operation',actor=self.a)
        self.assertEqual(InvoiceJob.objects.count(),1)

    def test_namespace_revocation_does_not_gate_delivery_of_proven_original(self):
        from apps.finance.models import InvoiceDelivery
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(job_id=job.pk)
        before=invoices.review_packet(self.i)
        scopes.transition(self.a,source.pk,'revoked')
        self.assertEqual(invoices.review_packet(self.i),before)
        delivery=invoices.reserve(self.a,self.c.pk,self.i.pk,'deliver','Finance',rev(self.c))
        invoice_delivery.run_once(job_id=delivery.pk)
        delivery.refresh_from_db();self.assertEqual(delivery.status,'confirmed',delivery.error)
        self.assertEqual(InvoiceDelivery.objects.filter(invoice=self.i).count(),1)
        self.assertEqual(InvoiceIssue.objects.count(),1)

    def test_delivery_still_requires_its_existing_grant(self):
        from apps.identity.models import Grant
        from django.core.exceptions import PermissionDenied
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(job_id=job.pk)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.invoice.deliver').update(active=False)
        with self.assertRaises(PermissionDenied):
            invoices.reserve(self.a,self.c.pk,self.i.pk,'deliver','Finance',rev(self.c))

    def test_namespace_revocation_does_not_gate_original_issue_correction(self):
        from .correction_helpers import configure as correction_configure,note,apply
        from .billing_helpers import evidence
        from apps.finance.models import InvoiceCorrectionAcceptance
        correction_configure(self.a,self.c)
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(job_id=job.pk)
        original=InvoiceIssue.objects.get(invoice=self.i)
        scopes.transition(self.a,source.pk,'revoked')
        self.e['review']=evidence(self.a,self.c,'financial_correction_review','Synthetic exact correction approval')
        correction=note(self.a,self.c,original,self.e)
        adjusted=apply(self.a,self.c,correction,self.e)
        adjusted.refresh_from_db();self.assertEqual(adjusted.status,'confirmed',adjusted.error)
        self.assertEqual(InvoiceCorrectionAcceptance.objects.count(),1)
        self.assertEqual(InvoiceIssue.objects.count(),1)
        self.assertEqual(ObligationEffect.objects.get().job_id,job.pk)

    def test_revoked_source_cannot_anchor_namespace_via_raw_sql(self):
        from apps.finance.models import ObligationNamespace
        from apps.policy.services import reference_values
        source,config=configure(self.a,self.c)
        value=reference_values(config)[0]
        scopes.transition(self.a,source.pk,'revoked')
        with self.assertRaises(DatabaseError),transaction.atomic():
            ObligationNamespace.objects.create(tenant=self.c.tenant,synthetic=self.c.synthetic,
                name=value['namespace'],key_contract=value['key_contract'],source=source)
        self.assertFalse(ObligationNamespace.objects.exists())

    def test_parallel_alias_and_claim_cannot_own_same_namespace_key(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        from .billing_helpers import evidence
        from apps.finance.models import ObligationAlias
        source,config,binding=self.ready()
        a,c,i,e=self.second_case(source)
        canonical=binding.local_key.claim
        body={'namespace':canonical.namespace.name,'key':'alias-or-claim','canonical_claim_id':canonical.pk,
              'canonical_key':canonical.key,'canonical_case_id':str(self.c.pk)}
        proof=evidence(self.a,self.c,'invoice_identity_alias',json.dumps(body))
        barrier=Barrier(2)
        def attempt(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if kind=='alias':
                    obligations.resolve_alias(self.a,self.c.pk,canonical.pk,'alias-or-claim',proof.pk,rev(self.c))
                else:
                    bind(a,c,i,key='alias-or-claim')
                return 'owned'
            except ValidationError:
                return 'conflict'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(attempt,['alias','claim']))
        self.assertCountEqual(results,['owned','conflict'])
        self.assertEqual(ObligationAlias.objects.filter(key='alias-or-claim').count()+ObligationClaim.objects.filter(key='alias-or-claim').count(),1)

    def test_existing_namespace_sql_requires_current_source_activation_grant(self):
        from apps.identity.models import Grant
        from django.db import connection
        source,config,binding=self.ready()
        namespace=binding.local_key.claim.namespace_id
        Grant.objects.filter(case=self.c,user=self.a,action='policy.activate').update(active=False)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_obligation_namespace_policy(%s,%s,%s)',[namespace,config.pk,self.c.pk])
            self.assertIs(cursor.fetchone()[0],False)
        with self.assertRaises(ValidationError):obligations.current(self.i)

    def test_delivery_has_no_new_repeatable_read_namespace_gate(self):
        from django.db import connection
        source,config,binding=self.ready()
        issue=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(job_id=issue.pk)
        expected=rev(self.c)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            delivery=invoices.reserve(self.a,self.c.pk,self.i.pk,'deliver','Finance',expected)
        self.assertEqual(delivery.kind,'deliver')

    def test_correction_reservation_has_no_new_repeatable_read_namespace_gate(self):
        from .correction_helpers import configure as correction_configure,note,review
        from .billing_helpers import evidence
        from apps.finance import corrections
        from django.db import connection
        correction_configure(self.a,self.c)
        source,config,binding=self.ready()
        job=invoices.reserve(self.a,self.c.pk,self.i.pk,'issue','Finance',rev(self.c))
        invoice_delivery.run_once(job_id=job.pk)
        original=InvoiceIssue.objects.get(invoice=self.i)
        self.e['review']=evidence(self.a,self.c,'financial_correction_review','Synthetic exact correction approval')
        correction=note(self.a,self.c,original,self.e)
        review(self.a,self.c,correction,self.e)
        expected=rev(self.c)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            adjusted=corrections.reserve(self.a,self.c.pk,correction.pk,'adjust','Finance',expected)
        self.assertEqual(adjusted.kind,'adjust')
