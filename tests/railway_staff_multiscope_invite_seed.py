"""Two isolated sample workspaces for the ordinary staff invitation form."""

import json
import os
from copy import deepcopy
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.identity import intake, staff
from apps.identity.intake_models import CaseIntake, TenantAuthority
from apps.identity.models import Grant
from apps.identity.staff_models import StaffAdmission, StaffInvitation
from tests.test_staff_profiles import PROFILES


PROJECT = 'f957481b-c6f7-43af-bc66-449a330a9d53'
TENANT = 'design-staff-multiscope-invitation'
BOOTSTRAP = 'sample-staff-multiscope-invitation-bootstrap'
WORKSPACES = {'sample-invitation-first': 'SAMPLE invitation workspace one',
              'sample-invitation-second': 'SAMPLE invitation workspace two'}
RECIPIENT = {'name': 'SAMPLE multi-workspace colleague', 'username': 'sample-multiscope-invite-colleague',
             'email': 'multiscope-invitation@example.invalid'}


def authority_value(create_cases):
    return {'format': 'psl.tenant-access/v3', 'manage_access': True, 'create_cases': create_cases,
            'classification': 'synthetic', 'kinds': ['project'], 'initial_actions': ['case.read'],
            'allowed_actions': sorted({action for profile in PROFILES for action in profile['actions']}),
            'staff_lifecycle': {'invite_minutes': 30, 'allow_invite': True, 'allow_deactivation': False,
                                'allow_roster':True,'allow_profile_edit':True,
                                'profiles': deepcopy(PROFILES)}}


def preserved_admission():
    """Read only the known completed preview admission and its active workspace grants."""
    original = StaffAdmission.objects.filter(invitation_id=6, user_id=123).values_list('pk', 'created_at').first()
    if original is None:
        return None
    invitation = StaffInvitation.objects.filter(pk=6).values_list('case_id', 'number', 'profile_key', 'workspace_profiles').get()
    current = get_user_model().objects.filter(pk=123).values_list('is_active', flat=True).get()
    grants = tuple(Grant.objects.filter(user_id=123).order_by('pk').values_list('case_id', 'action', 'active'))
    return original, invitation, current, grants


@transaction.atomic
def prepare(manager):
    intake.lock_users([manager.pk])
    before = preserved_admission()
    current = TenantAuthority.objects.filter(tenant=TENANT).order_by('-pk').first()
    if current is None:
        if Case.objects.filter(tenant=TENANT).exists():
            raise RuntimeError('The isolated sample tenant unexpectedly has existing workspaces.')
        bootstrap = get_user_model().objects.create_superuser(BOOTSTRAP)
        expires_at = timezone.now() + timedelta(days=1)
        intake.provision(bootstrap, manager, TENANT, authority_value(True), expires_at, True,
                         'SAMPLE scoped bootstrap for two invitation workspaces')
        for reference, title in WORKSPACES.items():
            intake.create_case(manager, TENANT, reference, title, 'project')
        current = intake.provision(bootstrap, manager, TENANT, authority_value(False), expires_at, True,
                                   'SAMPLE named invitation profiles on the two prepared workspaces')
        bootstrap.is_active = bootstrap.is_staff = bootstrap.is_superuser = False
        bootstrap.save(update_fields=['is_active', 'is_staff', 'is_superuser'])
    elif current.user_id != manager.pk or current.value != authority_value(False):
        raise RuntimeError('Preserve the existing scoped authority and use the original sample manager.')

    records = {row.reference: row.case for row in CaseIntake.objects.select_related('case').filter(tenant=TENANT, actor=manager)}
    if (set(records) != set(WORKSPACES) or Case.objects.filter(tenant=TENANT).count() != len(WORKSPACES)
            or any(not case.synthetic or case.kind != 'project' or case.title != WORKSPACES[key]
                   for key, case in records.items())):
        raise RuntimeError('The two exact isolated invitation workspaces are required.')
    cases = [records[key] for key in WORKSPACES]
    for case in cases:
        cfg, _ = staff.authority(manager, case, 'allow_invite')
        if cfg.pk != current.pk or set(Grant.objects.filter(case=case, user=manager, active=True)
                .values_list('action', flat=True)) != {'case.read'}:
            raise RuntimeError('The sample manager needs only the original scoped invitation access.')
    if before != preserved_admission():
        raise RuntimeError('The original completed preview admission changed.')

    first, second = cases
    invites = StaffInvitation.objects.filter(case__in=cases).count()
    return {'authority': current.pk, 'manager': manager.pk, 'first': str(first.pk), 'second': str(second.pk),
            'form': reverse('staff_invites', args=[first.pk]), 'additional_field': f'profile_{second.pk.hex}',
            'profiles': [profile['key'] for profile in PROFILES], 'recipient': RECIPIENT, 'existing_invitations': invites,
            'preserved_original_admission': before is not None}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'),
            os.getenv('PSL_STAFF_MULTISCOPE_INVITE_FIXTURE')) != ('design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit staff invitation fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    manager = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print('PSL_STAFF_MULTISCOPE_INVITE_FIXTURE=' + json.dumps(prepare(manager)), flush=True)
