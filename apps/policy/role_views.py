from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.core.views import accessible_case
from apps.agents.role_assignments import investigate


@login_required
def guidance(request,case_id):
    case=accessible_case(request.user,case_id)
    response=render(request,'role_eligibility_guidance.html',{'case':case,'report':investigate(request.user,case_id)})
    response['Cache-Control']='no-store';return response
