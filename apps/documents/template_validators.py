from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.identity.models import Grant
from .models import TemplateScope


def validate_owners(case, content, *, runtime=False):
    rules = content.get('template_owners', [])
    if not rules:
        raise ValidationError('Storage v3 requires explicit scoped template-owner assignments')
    scopes = [r['scope_id'] for r in rules]
    if len(scopes) != len(set(scopes)) or TemplateScope.objects.filter(case=case, pk__in=scopes).count() != len(scopes):
        raise ValidationError('Each exact same-case applicability scope must have one explicit owner; no guessed owner or duplicate scope')
    # Currentness resolution checks its selected owner's live grants. An unrelated
    # revoked owner must not break ordinary historical selection or publication.
    if not runtime:
        for rule in rules:
            if not get_user_model().objects.filter(pk=rule['user_id'], is_active=True).exists() or Grant.objects.filter(
                user_id=rule['user_id'], case=case, active=True, action__in=['case.read', 'document.read', 'document.template']).count() != 3:
                raise ValidationError('A scoped owner needs an active principal and explicit case/document read and template grants')
