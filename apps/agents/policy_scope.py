from apps.policy.scopes import report


def investigate(actor, case_id):
    value = report(actor, case_id)
    return {'capability':'A04 explicit policy origin and impact investigation', 'provider':'deterministic_internal_no_external_model',
        'evidence':value, 'held_applications':[x for x in value['applications'] if x['status'] != 'ACTIVE'],
        'suggested_work':['Review affected local versions and explicitly select an authorized successor; preserve pinned historical decisions.'],
        'effect_tools':[], 'owner_values_inferred':False}
