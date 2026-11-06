from django.urls import path, include
from apps.workflows import cold_recovery_views as v
from apps.workflows import reconstitution_views as r
from apps.workflows import domain_contract_views as dc
from apps.workflows import native_finance_views as nf

urlpatterns = [path('',v.home,name='home'), path('accounts/',include('django.contrib.auth.urls')),
    path('cases/<uuid:case_id>/native-finance/',nf.workbench,name='native_finance'),
    path('cases/<uuid:case_id>/native-finance/<int:mapping_id>/',nf.report,name='native_finance_report'),
    path('cases/<uuid:case_id>/domain-contracts/',dc.workbench,name='domain_contracts'),
    path('cases/<uuid:case_id>/domain-contracts/<int:contract_id>/',dc.report,name='domain_contract_report'),
    path('cases/<uuid:case_id>/reconstitution/',r.workbench,name='reconstitution'),
    path('cases/<uuid:case_id>/reconstitution/<int:plan_id>/',r.report,name='reconstitution_report'),
    path('cases/<uuid:case_id>/cold-recovery/',v.workbench,name='cold_recovery'),
    path('cases/<uuid:case_id>/cold-recovery/<int:plan_id>/',v.report,name='cold_recovery_report'),
    path('cases/<uuid:case_id>/policy/',v.policy,name='policy')]
