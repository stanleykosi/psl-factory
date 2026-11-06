"""Local control boundary, not an Engineering/GLPI deployment adapter."""
class LocalPaymentReleaseControls:
    def check_for_use(self,actor,case_id,reservation_id):
        from apps.finance.payments import revalidate
        r=revalidate(actor,case_id,reservation_id)
        return {'reservation':r.pk,'sha256':r.sha256,'controls_current':True,'deployment_dispatched':False,'debt_waived':False}
