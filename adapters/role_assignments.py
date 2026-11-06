"""Local nomination/eligibility metadata; cannot grant roles, activate or execute."""
class LocalRoleAssignmentsAdapter:
    def read(self,actor,case_id):
        from apps.policy.role_assignments import report
        return report(actor,case_id)
