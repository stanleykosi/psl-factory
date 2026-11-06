from adapters.role_assignments import LocalRoleAssignmentsAdapter


def investigate(actor,case_id):
    value=LocalRoleAssignmentsAdapter().read(actor,case_id)
    return {'capability':'A04 role eligibility investigation','provider':'deterministic_internal_no_external_model','observation':value,
        'held_bundles':[r for r in value['assignments'] if not r['eligible_role_bundle']],
        'next_work':['Obtain explicit owner evidence for exact nominated roles and eligibility windows','Use reviewed configuration lifecycle; action grants and independent human controls still apply'],
        'effect_tools':[],'owner_values_inferred':False,'business_approval':False}
