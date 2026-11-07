import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


FORWARD_SQL = r"""
CREATE FUNCTION psl_draft_generation_business(pid bigint) RETURNS text LANGUAGE sql STABLE AS $$
 SELECT CASE WHEN u.collective_acceptance_id IS NOT NULL THEN psl_usage_obligation(u.id)
 WHEN p.kind='fixed_contract' THEN psl_fixed_obligation(p.fixed_charge_id)
 ELSE psl_usage_hash(jsonb_build_object('case',p.case_id::text,'customer',c.customer,'contract',c.contract,
 'kind',p.kind,'usage',CASE WHEN p.kind='usage' THEN p.usage_id ELSE NULL END)) END
 FROM finance_billingpreparation p JOIN finance_billingcoverage c ON c.id=p.coverage_id
 LEFT JOIN finance_billingusage u ON u.id=p.usage_id WHERE p.id=pid;
$$;
CREATE FUNCTION psl_draft_generation_source(sid bigint,rid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM finance_billingevidencesource s JOIN finance_billingevidencereview r ON r.source_id=s.id
 WHERE s.id=sid AND r.id=rid AND r.id=(SELECT max(id) FROM finance_billingevidencereview WHERE source_id=s.id)
 AND r.verdict='confirm' AND r.meaning<>'unresolved' AND s.sha256=psl_usage_hash(s.payload)
 AND NOT EXISTS(SELECT 1 FROM finance_billingevidencesource n WHERE n.case_id=s.case_id AND n.reference=s.reference AND n.version>s.version)
 AND psl_schedules_grants(s.case_id,r.actor_id,ARRAY['case.read','finance.read','d03.read','d03.source.read','d03.review'])
 AND psl_schedules_policy_current(s.case_id,(r.authority->>'D05.role_principal_assignments')::bigint));
$$;
CREATE FUNCTION psl_draft_generation_current(g finance_draftgeneration) RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE p finance_billingpreparation; s finance_billingevidencesource; b finance_billingcoverage; c core_case;
 cap jsonb; auth jsonb; item jsonb; stmt jsonb;
BEGIN
 SELECT * INTO p FROM finance_billingpreparation WHERE id=g.preparation_id;
 SELECT * INTO s FROM finance_billingevidencesource WHERE id=g.source_id;
 SELECT * INTO b FROM finance_billingcoverage WHERE id=p.coverage_id;
 SELECT * INTO c FROM core_case WHERE id=g.case_id;
 cap:=(s.payload->>'quote')::jsonb; stmt:=g.payload->'statement_reference';
 SELECT jsonb_agg(jsonb_build_array(action,id) ORDER BY action) INTO auth FROM identity_grant
 WHERE case_id=g.case_id AND user_id=g.actor_id AND active AND action IN ('case.read','finance.read','d03.read','d03.source.read','finance.draft_generation.dispatch');
 IF c.synthetic IS DISTINCT FROM true OR p.case_id IS DISTINCT FROM c.id OR s.case_id IS DISTINCT FROM c.id OR g.tenant IS DISTINCT FROM c.tenant
 OR g.sha256 IS DISTINCT FROM psl_usage_hash(g.payload) OR g.business_key IS DISTINCT FROM psl_draft_generation_business(p.id)
 OR g.payload->>'schema' IS DISTINCT FROM 'draft-generation-intent/v1' OR g.payload->>'action' IS DISTINCT FROM 'draft_generation'
 OR g.payload->>'implementation' IS DISTINCT FROM 'mock_draft_generation_v1' OR g.payload->'draft_only' IS DISTINCT FROM 'true'::jsonb
 OR g.payload->>'tenant' IS DISTINCT FROM g.tenant OR g.payload->>'case' IS DISTINCT FROM c.id::text
 OR g.payload->>'operation_key' IS DISTINCT FROM g.operation_key OR g.payload->>'actor' IS DISTINCT FROM g.actor_id::text
 OR g.payload->'authority' IS DISTINCT FROM auth
 OR NOT psl_schedules_grants(c.id,g.actor_id,ARRAY['case.read','finance.read','d03.read','d03.source.read','finance.draft_generation.dispatch'])
 OR g.payload->>'preparation' IS DISTINCT FROM p.id::text OR g.payload->>'preparation_key' IS DISTINCT FROM p.operation_key
 OR g.payload->>'batch_sha256' IS DISTINCT FROM psl_usage_hash(jsonb_build_object('snapshot',p.snapshot,'result',p.result))
 OR g.payload->>'source' IS DISTINCT FROM s.id::text OR g.payload->>'source_sha256' IS DISTINCT FROM s.sha256
 OR s.kind IS DISTINCT FROM 'flow_contract' OR s.payload->>'implementation' IS DISTINCT FROM 'incumbent_reference_only'
 OR NOT psl_draft_generation_source(s.id,(g.payload->>'source_review')::bigint)
 OR cap->>'schema' IS DISTINCT FROM 'draft-generation-contract/v1' OR cap->>'action' IS DISTINCT FROM 'draft_generation'
 OR cap->>'implementation' IS DISTINCT FROM 'mock_draft_generation_v1' OR cap->'draft_only' IS DISTINCT FROM 'true'::jsonb
 OR cap->'output_contract' IS DISTINCT FROM g.payload->'output_contract'
 OR cap->'output_contract'->>'schema' IS DISTINCT FROM 'draft-document/v1'
 OR cap->'output_contract'->'posted' IS DISTINCT FROM 'false'::jsonb OR cap->'output_contract'->'sent' IS DISTINCT FROM 'false'::jsonb
 OR cap->'output_contract'->>'document_ref' IS NULL
 OR p.result->>'status' IS DISTINCT FROM 'prepared'
 OR NOT psl_schedules_grants(c.id,p.actor_id,ARRAY['case.read','finance.read','finance.billing.prepare'])
 OR EXISTS(SELECT 1 FROM finance_billingcoverage WHERE case_id=c.id AND reference=b.reference AND version>b.version)
 OR NOT psl_schedules_policy_current(c.id,(g.payload->>'statement_policy')::bigint)
 OR NOT psl_draft_generation_source((stmt->>'source_id')::bigint,(stmt->>'review_id')::bigint)
 OR NOT EXISTS(SELECT 1 FROM finance_billingevidencesource WHERE id=(stmt->>'source_id')::bigint AND case_id=c.id AND kind='statement' AND sha256=stmt->>'source_sha256')
 OR EXISTS(SELECT 1 FROM finance_draftgenerationcancellation WHERE generation_id=g.id)
 OR EXISTS(SELECT 1 FROM finance_draftgenerationobservation o JOIN finance_draftgenerationattempt a ON a.id=o.attempt_id WHERE a.generation_id=g.id AND NOT o.accepted)
 THEN RETURN false; END IF;
 FOR item IN SELECT to_jsonb(x) FROM unnest(ARRAY['flow_ref','flow_version','environment_ref']) x LOOP
  IF g.payload->(item#>>'{}') IS DISTINCT FROM cap->(item#>>'{}') OR g.payload->(item#>>'{}') IS DISTINCT FROM s.payload->(item#>>'{}') THEN RETURN false; END IF;
 END LOOP;
 IF p.kind='fixed_contract' THEN RETURN psl_fixed_preparation_current(p.id); END IF;
 FOR item IN SELECT value FROM jsonb_each(p.snapshot->'policies') LOOP
  IF item->>'status'='ACTIVE' AND NOT psl_schedules_policy_current(c.id,(item->>'id')::bigint) THEN RETURN false; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM finance_billingusage WHERE id=p.usage_id AND collective_acceptance_id IS NOT NULL)
 AND NOT psl_usage_current(p.usage_id) THEN RETURN false; END IF;
 RETURN true;
EXCEPTION WHEN others THEN RETURN false;
END $$;
CREATE FUNCTION psl_draft_generation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g finance_draftgeneration; a finance_draftgenerationattempt; old jsonb; facts text[];
BEGIN
 IF TG_TABLE_NAME='finance_draftgeneration' THEN
  PERFORM 1 FROM core_case WHERE id=NEW.case_id FOR UPDATE;
  IF psl_draft_generation_current(NEW) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Current exact draft generation intent required'; END IF;
 ELSIF TG_TABLE_NAME='finance_draftgenerationattempt' THEN
  SELECT * INTO g FROM finance_draftgeneration WHERE id=NEW.generation_id;
  PERFORM 1 FROM core_case WHERE id=g.case_id FOR UPDATE;
  IF NEW.intent_sha256 IS DISTINCT FROM g.sha256 OR NEW.sequence IS DISTINCT FROM (SELECT coalesce(max(sequence),0)+1 FROM finance_draftgenerationattempt WHERE generation_id=g.id)
  OR NOT psl_schedules_grants(g.case_id,NEW.actor_id,ARRAY['case.read','finance.read','d03.read','finance.draft_generation.lookup'])
  OR NEW.action NOT IN ('generate','lookup') THEN RAISE EXCEPTION 'Exact fenced generation attempt required'; END IF;
  IF NEW.action='generate' AND (NEW.actor_id<>g.actor_id OR psl_draft_generation_current(g) IS DISTINCT FROM true) THEN RAISE EXCEPTION 'Generation authority/source changed'; END IF;
  IF NEW.action='lookup' AND NOT EXISTS(SELECT 1 FROM finance_draftgenerationattempt WHERE generation_id=g.id AND action='generate') THEN RAISE EXCEPTION 'Lookup requires original generate claim'; END IF;
 ELSIF TG_TABLE_NAME='finance_draftgenerationcancellation' THEN
  SELECT * INTO g FROM finance_draftgeneration WHERE id=NEW.generation_id;
  PERFORM 1 FROM core_case WHERE id=g.case_id FOR UPDATE;
  IF NOT psl_schedules_grants(g.case_id,NEW.actor_id,ARRAY['case.read','finance.read','d03.read','finance.draft_generation.cancel'])
  OR length(trim(NEW.reason)) NOT BETWEEN 1 AND 500 THEN RAISE EXCEPTION 'Scoped cancellation required'; END IF;
 ELSE
  SELECT * INTO a FROM finance_draftgenerationattempt WHERE id=NEW.attempt_id;
  SELECT * INTO g FROM finance_draftgeneration WHERE id=a.generation_id;
  PERFORM 1 FROM core_case WHERE id=g.case_id FOR UPDATE;
  IF NEW.fence IS DISTINCT FROM a.fence OR NOT psl_schedules_grants(g.case_id,NEW.actor_id,ARRAY['case.read','finance.read','d03.read','finance.draft_generation.lookup']) THEN RAISE EXCEPTION 'Original fence and current lookup grant required'; END IF;
  IF NEW.sha256 IS DISTINCT FROM psl_usage_hash(NEW.payload) THEN RAISE EXCEPTION 'Observation hash mismatch'; END IF;
  IF NEW.accepted THEN
   IF NOT psl_usage_keys(NEW.payload,ARRAY['schema','tenant','case','operation_key','intent_sha256','observed_at','outcome','run_id','document_ref','document_version','document_sha256','generated','posted','sent'])
   OR NEW.payload->>'observed_at' IS NULL OR NEW.payload->>'outcome' IS NULL
   OR NEW.finding<>'' OR NEW.payload->>'schema' IS DISTINCT FROM 'draft-generation-observation/v1'
   OR NEW.payload->>'tenant' IS DISTINCT FROM g.tenant OR NEW.payload->>'case' IS DISTINCT FROM g.case_id::text
   OR NEW.payload->>'operation_key' IS DISTINCT FROM g.operation_key OR NEW.payload->>'intent_sha256' IS DISTINCT FROM g.sha256
   OR (NEW.payload->>'observed_at')::timestamptz NOT BETWEEN a.created_at AND clock_timestamp()
   OR NEW.payload->>'outcome' NOT IN ('found','unknown','not_found') THEN RAISE EXCEPTION 'Original operation observation mismatch'; END IF;
   facts:=ARRAY['run_id','document_ref','document_version','document_sha256','generated','posted','sent'];
   IF NEW.payload->>'outcome'='found' THEN
    PERFORM pg_advisory_xact_lock(('x'||substr(psl_usage_hash(jsonb_build_object('draft_output',jsonb_build_object(
     'tenant',g.tenant,'system',(SELECT system FROM finance_billingevidencesource WHERE id=g.source_id),
     'environment',g.payload->>'environment_ref','document_ref',NEW.payload->>'document_ref','document_version',NEW.payload->>'document_version'))),1,15))::bit(60)::bigint);
    IF EXISTS(SELECT 1 FROM finance_draftgenerationobservation o JOIN finance_draftgenerationattempt t ON t.id=o.attempt_id
     JOIN finance_draftgeneration otherg ON otherg.id=t.generation_id JOIN finance_billingevidencesource others ON others.id=otherg.source_id
     WHERE o.accepted AND o.payload->>'outcome'='found' AND otherg.id<>g.id AND otherg.tenant=g.tenant
     AND others.system=(SELECT system FROM finance_billingevidencesource WHERE id=g.source_id)
     AND otherg.payload->>'environment_ref'=g.payload->>'environment_ref'
     AND o.payload->>'document_ref'=NEW.payload->>'document_ref' AND o.payload->>'document_version'=NEW.payload->>'document_version')
    THEN RAISE EXCEPTION 'Generated document belongs to another original operation'; END IF;
    IF NEW.payload->'generated' IS DISTINCT FROM 'true'::jsonb OR NEW.payload->'posted' IS DISTINCT FROM 'false'::jsonb OR NEW.payload->'sent' IS DISTINCT FROM 'false'::jsonb
    OR NEW.payload->>'document_ref' IS DISTINCT FROM g.payload->'output_contract'->>'document_ref'
    OR NEW.payload->>'run_id' IS NULL OR length(NEW.payload->>'run_id') NOT BETWEEN 1 AND 100
    OR NEW.payload->>'document_version' IS NULL OR length(NEW.payload->>'document_version') NOT BETWEEN 1 AND 100
    OR NEW.payload->>'document_sha256' IS NULL OR NEW.payload->>'document_sha256' !~ '^[a-f0-9]{64}$'
    THEN RAISE EXCEPTION 'Exact draft-only generated document required'; END IF;
    SELECT o.payload INTO old FROM finance_draftgenerationobservation o JOIN finance_draftgenerationattempt t ON t.id=o.attempt_id
    WHERE t.generation_id=g.id AND o.accepted AND o.payload->>'outcome'='found' ORDER BY o.id LIMIT 1;
    IF old IS NOT NULL AND EXISTS(SELECT 1 FROM unnest(facts) k WHERE NEW.payload->k IS DISTINCT FROM old->k) THEN RAISE EXCEPTION 'Conflicting generation receipt'; END IF;
   ELSIF EXISTS(SELECT 1 FROM unnest(facts) k WHERE NEW.payload->k IS DISTINCT FROM 'null'::jsonb) THEN RAISE EXCEPTION 'Unknown result cannot invent facts'; END IF;
  ELSIF NEW.finding='' THEN RAISE EXCEPTION 'Conflict observation requires finding'; END IF;
 END IF;
 RETURN NEW;
END $$;
"""

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_append_only_history'),
        ('finance', '0070_forecast_continuation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DraftGeneration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant', models.CharField(max_length=100)),
                ('operation_key', models.CharField(max_length=100)),
                ('business_key', models.CharField(max_length=64)),
                ('payload', models.JSONField()),
                ('sha256', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
                ('preparation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.billingpreparation')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='finance.billingevidencesource')),
            ],
        ),
        migrations.CreateModel(
            name='DraftGenerationAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=20)),
                ('sequence', models.PositiveIntegerField()),
                ('fence', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('intent_sha256', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('generation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attempts', to='finance.draftgeneration')),
            ],
        ),
        migrations.CreateModel(
            name='DraftGenerationCancellation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('generation', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='cancellation', to='finance.draftgeneration')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='DraftGenerationObservation',
            fields=[
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('fence', models.UUIDField()),
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload', models.JSONField()),
                ('sha256', models.CharField(max_length=64)),
                ('accepted', models.BooleanField()),
                ('finding', models.CharField(max_length=240)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='observations', to='finance.draftgenerationattempt')),
            ],
        ),
        migrations.AddConstraint(
            model_name='draftgeneration',
            constraint=models.UniqueConstraint(fields=('tenant', 'operation_key'), name='draft_generation_operation'),
        ),
        migrations.AddConstraint(
            model_name='draftgeneration',
            constraint=models.UniqueConstraint(fields=('tenant', 'business_key'), name='draft_generation_business'),
        ),
        migrations.AddConstraint(
            model_name='draftgenerationattempt',
            constraint=models.UniqueConstraint(fields=('generation', 'sequence'), name='draft_generation_attempt_sequence'),
        ),
        migrations.AddConstraint(
            model_name='draftgenerationattempt',
            constraint=models.UniqueConstraint(condition=models.Q(('action', 'generate')), fields=('generation',), name='draft_generation_once'),
        ),
        migrations.AddConstraint(
            model_name='draftgenerationobservation',
            constraint=models.UniqueConstraint(fields=('attempt', 'sha256'), name='draft_generation_observation_retry'),
        ),
    ]

    operations += [migrations.RunSQL(FORWARD_SQL, "DROP FUNCTION psl_draft_generation_guard(); DROP FUNCTION psl_draft_generation_current(finance_draftgeneration); DROP FUNCTION psl_draft_generation_source(bigint,bigint); DROP FUNCTION psl_draft_generation_business(bigint);")]
    for table in ['draftgeneration', 'draftgenerationattempt', 'draftgenerationobservation', 'draftgenerationcancellation']:
        operations += [migrations.RunSQL(
            f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_{table} FOR EACH ROW EXECUTE FUNCTION psl_append_only(); CREATE TRIGGER psl_draft_generation_guard BEFORE INSERT ON finance_{table} FOR EACH ROW EXECUTE FUNCTION psl_draft_generation_guard();',
            f'DROP TRIGGER psl_draft_generation_guard ON finance_{table}; DROP TRIGGER psl_immutable ON finance_{table};')]
