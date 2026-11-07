import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


SQL = r"""CREATE FUNCTION psl_template_owner(sid bigint, uid bigint, pid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM documents_templatescope s JOIN policy_configuration p ON p.case_id=s.case_id
 JOIN policy_registeredreference r ON r.case_id=p.case_id AND r.ref=p.envelope->'value'->>'artifact_ref'
 AND r.version=(p.envelope->'value'->>'artifact_version')::integer AND r.sha256=p.envelope->'value'->>'sha256'
 WHERE s.id=sid AND p.id=pid AND p.component='D11.template_storage_retention_rules'
 AND r.schema_ref='schema:psl/document-storage/v3' AND p.envelope->'value'->>'schema_ref'=r.schema_ref
 AND psl_ppe_policy_current(s.case_id,p.id) AND psl_ppe_grants(s.case_id,uid,ARRAY['case.read','document.read','document.template'])
 AND (s.document_type NOT IN ('finance_report','finance_group_report') OR psl_ppe_grants(s.case_id,uid,ARRAY['finance.read']))
 AND NOT EXISTS(SELECT 1 FROM policy_configuration later WHERE later.case_id=p.case_id AND later.component=p.component AND later.revision>p.revision
 AND (SELECT state FROM policy_policystate WHERE configuration_id=later.id ORDER BY id DESC LIMIT 1) IN ('active','superseded','revoked'))
 AND (SELECT count(*) FROM jsonb_array_elements(r.content->'template_owners') o WHERE o->>'scope_id'=sid::text)=1
 AND r.content->'template_owners' @> jsonb_build_array(jsonb_build_object('scope_id',sid,'user_id',uid)));
$$;
CREATE FUNCTION psl_template_enabled(pid bigint, tid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM policy_configuration p JOIN policy_registeredreference r ON r.case_id=p.case_id
 AND r.ref=p.envelope->'value'->>'artifact_ref' AND r.version=(p.envelope->'value'->>'artifact_version')::integer
 AND r.sha256=p.envelope->'value'->>'sha256' WHERE p.id=pid AND r.content->'template_ids' @> jsonb_build_array(tid));
$$;
CREATE FUNCTION psl_template_claim_ids(sid bigint) RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT coalesce(jsonb_agg(c.id ORDER BY c.id),'[]'::jsonb) FROM documents_templateclaim c
 WHERE c.scope_id=sid AND NOT EXISTS(SELECT 1 FROM documents_templateclaimretraction w WHERE w.claim_id=c.id);
$$;
CREATE FUNCTION psl_template_current(sid bigint) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
 DECLARE ids jsonb; r documents_templateresolution; c documents_templateclaim;
 BEGIN
 ids:=psl_template_claim_ids(sid);
 IF ids='[]'::jsonb THEN RETURN NULL; END IF;
 SELECT * INTO r FROM documents_templateresolution WHERE scope_id=sid ORDER BY id DESC LIMIT 1;
 IF r.id IS NOT NULL AND r.claim_ids=ids AND psl_template_owner(sid,r.actor_id,r.owner_policy_id) THEN
  SELECT * INTO c FROM documents_templateclaim WHERE id=r.selected_claim_id AND scope_id=sid AND ids @> jsonb_build_array(id);
  IF c.id IS NOT NULL AND psl_template_enabled(r.owner_policy_id,c.template_id) THEN
   RETURN jsonb_build_object('scope_id',sid,'template_id',c.template_id,'claim_ids',ids,'configuration_id',r.owner_policy_id,'resolution_id',r.id,'owner_claim_id',NULL);
  END IF;
 END IF;
 IF (SELECT count(DISTINCT template_id) FROM documents_templateclaim WHERE scope_id=sid AND ids @> jsonb_build_array(id))<>1 THEN RETURN NULL; END IF;
 SELECT * INTO c FROM documents_templateclaim WHERE scope_id=sid AND ids @> jsonb_build_array(id)
 AND owner_policy_id IS NOT NULL AND psl_template_owner(sid,actor_id,owner_policy_id) ORDER BY id LIMIT 1;
 IF c.id IS NULL OR NOT psl_template_enabled(c.owner_policy_id,c.template_id) THEN RETURN NULL; END IF;
 RETURN jsonb_build_object('scope_id',sid,'template_id',c.template_id,'claim_ids',ids,'configuration_id',c.owner_policy_id,'resolution_id',NULL,'owner_claim_id',c.id);
 END;
$$;
CREATE FUNCTION psl_template_source(cid uuid, eid bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM core_evidence WHERE id=eid AND case_id=cid AND kind IN ('policy_decision','template_current_source'));
$$;
CREATE FUNCTION psl_template_record_guard() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE s documents_templatescope; c documents_templateclaim; cid uuid;
 BEGIN
 IF TG_TABLE_NAME='documents_templatescope' THEN
  cid:=NEW.case_id;
 ELSE
  IF TG_TABLE_NAME='documents_templateclaimretraction' THEN
   SELECT * INTO c FROM documents_templateclaim WHERE id=NEW.claim_id;
   SELECT * INTO s FROM documents_templatescope WHERE id=c.scope_id;
  ELSE
   SELECT * INTO s FROM documents_templatescope WHERE id=NEW.scope_id;
  END IF;
  cid:=s.case_id;
 END IF;
 PERFORM 1 FROM core_case WHERE id=cid FOR UPDATE;
 IF cid IS NULL OR NOT psl_template_source(cid,NEW.evidence_id)
 OR NOT psl_ppe_grants(cid,NEW.actor_id,ARRAY['document.read','document.template'])
 THEN RAISE EXCEPTION 'Exact same-case source and active template/document grants required'; END IF;
 IF TG_TABLE_NAME='documents_templatescope' THEN
  IF NEW.document_type IN ('finance_report','finance_group_report') AND NOT psl_ppe_grants(cid,NEW.actor_id,ARRAY['finance.read'])
  THEN RAISE EXCEPTION 'Finance template scope requires owning-domain access'; END IF;
  IF NEW.document_type NOT IN ('sow','status_report','minutes','project_artifact','rfp_response','finance_report','finance_group_report')
   OR NEW.audience NOT IN ('internal','client','management','group') OR btrim(NEW.purpose)='' OR btrim(NEW.context)='' OR btrim(NEW.source_owner)=''
   OR NEW.purpose<>btrim(NEW.purpose) OR NEW.context<>btrim(NEW.context) OR NEW.source_owner<>btrim(NEW.source_owner)
  THEN RAISE EXCEPTION 'Exact nonempty applicability scope required'; END IF;
 ELSE
  IF s.document_type IN ('finance_report','finance_group_report') AND NOT psl_ppe_grants(cid,NEW.actor_id,ARRAY['finance.read'])
  THEN RAISE EXCEPTION 'Finance template claims require owning-domain access'; END IF;
  IF btrim(NEW.note)='' THEN RAISE EXCEPTION 'Source-backed rationale required'; END IF;
  IF TG_TABLE_NAME='documents_templateclaim' THEN
   IF NOT EXISTS(SELECT 1 FROM documents_template t WHERE t.id=NEW.template_id AND t.case_id=cid
    AND t.definition->>'document_type'=s.document_type AND t.definition->'audience_fields' ? s.audience)
    OR (NEW.owner_policy_id IS NOT NULL AND (NOT psl_template_owner(s.id,NEW.actor_id,NEW.owner_policy_id) OR NOT psl_template_enabled(NEW.owner_policy_id,NEW.template_id)))
   THEN RAISE EXCEPTION 'Exact template applicability and current owner authority required'; END IF;
  ELSIF TG_TABLE_NAME='documents_templateclaimretraction' THEN
   IF (NEW.actor_id<>c.actor_id AND (NEW.owner_policy_id IS NULL OR NOT psl_template_owner(s.id,NEW.actor_id,NEW.owner_policy_id)))
    OR (NEW.owner_policy_id IS NOT NULL AND NOT psl_template_owner(s.id,NEW.actor_id,NEW.owner_policy_id))
   THEN RAISE EXCEPTION 'Only the recorder or current scoped owner may retract a claim'; END IF;
  ELSE
   IF NOT psl_template_owner(s.id,NEW.actor_id,NEW.owner_policy_id) OR NEW.claim_ids IS DISTINCT FROM psl_template_claim_ids(s.id)
    OR NEW.claim_ids='[]'::jsonb OR NOT EXISTS(SELECT 1 FROM documents_templateclaim chosen
     WHERE chosen.id=NEW.selected_claim_id AND chosen.scope_id=s.id AND NEW.claim_ids @> jsonb_build_array(chosen.id)
     AND psl_template_enabled(NEW.owner_policy_id,chosen.template_id))
   THEN RAISE EXCEPTION 'Current scoped owner must resolve the exact complete active claim set'; END IF;
  END IF;
 END IF;
 RETURN NEW;
 END;
$$;
CREATE FUNCTION psl_template_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE cid uuid; s documents_templatescope; actual jsonb;
 BEGIN
 IF NEW.template_current_manifest='{}'::jsonb THEN RETURN NEW; END IF;
 SELECT case_id INTO cid FROM documents_document WHERE id=NEW.document_id;
 PERFORM 1 FROM core_case WHERE id=cid FOR UPDATE;
 SELECT * INTO s FROM documents_templatescope WHERE id=(NEW.template_current_manifest->>'scope_id')::bigint;
 actual:=psl_template_current(s.id);
 IF s.id IS NULL OR s.case_id<>cid OR s.audience<>NEW.audience OR actual IS NULL OR actual<>NEW.template_current_manifest
 OR actual->>'template_id'<>NEW.template_id::text OR NOT EXISTS(SELECT 1 FROM documents_template WHERE id=NEW.template_id AND case_id=cid AND definition->>'document_type'=s.document_type)
 THEN RAISE EXCEPTION 'Current template assertion needs exact scoped owner confirmation and complete claim set'; END IF;
 RETURN NEW;
 END;
$$;
CREATE FUNCTION psl_template_effect_guard() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE v documents_version; cid uuid; actual jsonb;
 BEGIN
 IF TG_TABLE_NAME='documents_publication' THEN SELECT * INTO v FROM documents_version WHERE id=NEW.version_id;
 ELSE SELECT ver.* INTO v FROM documents_version ver JOIN documents_publication p ON p.version_id=ver.id WHERE p.id=NEW.publication_id; END IF;
 IF v.template_current_manifest='{}'::jsonb THEN RETURN NEW; END IF;
 SELECT case_id INTO cid FROM documents_document WHERE id=v.document_id;
 PERFORM 1 FROM core_case WHERE id=cid FOR UPDATE;
 actual:=psl_template_current((v.template_current_manifest->>'scope_id')::bigint);
 IF actual IS NULL OR actual<>v.template_current_manifest THEN RAISE EXCEPTION 'Current template claim changed before new publication effect'; END IF;
 RETURN NEW;
 END;
$$;

CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON documents_templatescope FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE TRIGGER psl_template_guard BEFORE INSERT ON documents_templatescope FOR EACH ROW EXECUTE FUNCTION psl_template_record_guard();

CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON documents_templateclaim FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE TRIGGER psl_template_guard BEFORE INSERT ON documents_templateclaim FOR EACH ROW EXECUTE FUNCTION psl_template_record_guard();

CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON documents_templateclaimretraction FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE TRIGGER psl_template_guard BEFORE INSERT ON documents_templateclaimretraction FOR EACH ROW EXECUTE FUNCTION psl_template_record_guard();

CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON documents_templateresolution FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE TRIGGER psl_template_guard BEFORE INSERT ON documents_templateresolution FOR EACH ROW EXECUTE FUNCTION psl_template_record_guard();

CREATE TRIGGER psl_template_current_guard BEFORE INSERT ON documents_version FOR EACH ROW EXECUTE FUNCTION psl_template_version_guard();

CREATE TRIGGER psl_template_current_guard BEFORE INSERT ON documents_publication FOR EACH ROW EXECUTE FUNCTION psl_template_effect_guard();

CREATE TRIGGER psl_template_current_guard BEFORE INSERT ON documents_publicationreceipt FOR EACH ROW EXECUTE FUNCTION psl_template_effect_guard();
"""
REVERSE = r"""DROP TRIGGER psl_immutable ON documents_templatescope;
DROP TRIGGER psl_template_guard ON documents_templatescope;
DROP TRIGGER psl_immutable ON documents_templateclaim;
DROP TRIGGER psl_template_guard ON documents_templateclaim;
DROP TRIGGER psl_immutable ON documents_templateclaimretraction;
DROP TRIGGER psl_template_guard ON documents_templateclaimretraction;
DROP TRIGGER psl_immutable ON documents_templateresolution;
DROP TRIGGER psl_template_guard ON documents_templateresolution;
DROP TRIGGER psl_template_current_guard ON documents_version;
DROP TRIGGER psl_template_current_guard ON documents_publication;
DROP TRIGGER psl_template_current_guard ON documents_publicationreceipt;
DROP FUNCTION psl_template_effect_guard();
DROP FUNCTION psl_template_version_guard();
DROP FUNCTION psl_template_record_guard();
DROP FUNCTION psl_template_source(uuid,bigint);
DROP FUNCTION psl_template_current(bigint);
DROP FUNCTION psl_template_claim_ids(bigint);
DROP FUNCTION psl_template_enabled(bigint,bigint);
DROP FUNCTION psl_template_owner(bigint,bigint,bigint);"""

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_append_only_history'),
        ('documents', '0030_statement_ppe_scope'),
        ('policy', '0016_cash_operation_identity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='version',
            name='template_current_manifest',
            field=models.JSONField(default=dict),
        ),
        migrations.CreateModel(
            name='TemplateClaim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.CharField(max_length=4000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('owner_policy', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='policy.configuration')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='documents.template')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TemplateClaimRetraction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.CharField(max_length=4000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('claim', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='retraction', to='documents.templateclaim')),
                ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('owner_policy', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='policy.configuration')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TemplateScope',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(max_length=40)),
                ('audience', models.CharField(max_length=20)),
                ('purpose', models.CharField(max_length=160)),
                ('context', models.CharField(max_length=160)),
                ('source_owner', models.CharField(max_length=160)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
                ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
            ],
        ),
        migrations.CreateModel(
            name='TemplateResolution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('claim_ids', models.JSONField()),
                ('note', models.CharField(max_length=4000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('evidence', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.evidence')),
                ('owner_policy', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='policy.configuration')),
                ('selected_claim', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='documents.templateclaim')),
                ('scope', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='resolutions', to='documents.templatescope')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='templateclaim',
            name='scope',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='claims', to='documents.templatescope'),
        ),
        migrations.AddConstraint(
            model_name='templatescope',
            constraint=models.UniqueConstraint(fields=('case', 'document_type', 'audience', 'purpose', 'context', 'source_owner'), name='template_exact_applicability'),
        ),
        migrations.RunSQL(SQL, REVERSE),
    ]
