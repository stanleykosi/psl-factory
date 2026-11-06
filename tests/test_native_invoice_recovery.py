from .test_native_finance import NativeFinanceTests as Base

class NativeInvoiceRecoveryTests(Base):
    test_10_exact_native_receipts_unknown_conflict_mapping_and_ui=None
    test_11_native_scope_guards_rotation_expiry_and_revocation=None
    test_12_reviewed_publication_crash_and_fresh_reconciliation=None

    @classmethod
    def child(cls,stage,v,cold=True):
        v['with_invoice_variants']=True
        return super().child(stage,v,cold)

    def test_archived_four_variants_published_handoff_and_current_source_owner(self):
        v,r=self.scenario('invoice_variants');self.assertEqual(r['outcomes'],['present']*8)
        v.update(r);current=self.child('source_accept',v)
        self.assertTrue(current['decision_current']);self.assertFalse(current['execution_authorized']);self.assertFalse(current['financial_effect_verified'])
