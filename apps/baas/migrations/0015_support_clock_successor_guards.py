from django.db import migrations

class Migration(migrations.Migration):
 dependencies=[('baas','0014_supportclockcorrection_supportclockcorrectionreview_and_more')]
 operations=[migrations.RunSQL(f'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON baas_{name} FOR EACH ROW EXECUTE FUNCTION psl_append_only()',f'DROP TRIGGER psl_immutable ON baas_{name}') for name in ['supportclockcorrection','supportclockcorrectionreview']]+[migrations.RunSQL("""
 CREATE UNIQUE INDEX support_channel_source_version ON baas_supportchannelclaim(tenant,channel,account,external_ref,(payload->>'receipt_version'));
 CREATE FUNCTION psl_support_channel_successor_guard() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE p baas_supportchannelclaim%ROWTYPE;
 BEGIN
 IF NEW.predecessor_id IS NOT NULL THEN
 SELECT * INTO p FROM baas_supportchannelclaim WHERE id=NEW.predecessor_id;
 IF p.id IS NULL OR (NEW.case_id,NEW.packet_id,NEW.tenant,NEW.channel,NEW.account,NEW.external_ref,NEW.payload-'receipt_version') IS DISTINCT FROM (p.case_id,p.packet_id,p.tenant,p.channel,p.account,p.external_ref,p.payload-'receipt_version') OR NEW.evidence_id IS NULL THEN RAISE EXCEPTION 'Exact immutable source successor lineage required'; END IF;
 END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_source_lineage BEFORE INSERT ON baas_supportchannelclaim FOR EACH ROW EXECUTE FUNCTION psl_support_channel_successor_guard();
 CREATE FUNCTION psl_support_clock_correction_guard() RETURNS trigger LANGUAGE plpgsql AS $$
 DECLARE p baas_supportclockcorrection%ROWTYPE;
 BEGIN
 IF NEW.predecessor_id IS NULL THEN
 IF NEW.version<>1 THEN RAISE EXCEPTION 'First correction version required'; END IF;
 ELSE
 SELECT * INTO p FROM baas_supportclockcorrection WHERE id=NEW.predecessor_id;
 IF p.id IS NULL OR p.case_id<>NEW.case_id OR NEW.version<>p.version+1 THEN RAISE EXCEPTION 'Exact correction predecessor required'; END IF;
 END IF;
 IF NEW.mode NOT IN ('withdraw','replace','revalidate','late') OR ((NEW.mode='withdraw')<>(NEW.receipt_id IS NULL)) THEN RAISE EXCEPTION 'Typed correction receipt disposition required'; END IF;
 IF NEW.receipt_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM baas_supportchannelreceipt r JOIN baas_supportchannelcheck j ON j.id=r.job_id JOIN baas_supportchannelclaim c ON c.id=j.claim_id WHERE r.id=NEW.receipt_id AND c.case_id=NEW.case_id) THEN RAISE EXCEPTION 'Exact case correction receipt required'; END IF;
 RETURN NEW; END $$;
 CREATE TRIGGER psl_clock_lineage BEFORE INSERT ON baas_supportclockcorrection FOR EACH ROW EXECUTE FUNCTION psl_support_clock_correction_guard();
 ""","""
 DROP TRIGGER psl_clock_lineage ON baas_supportclockcorrection;
 DROP FUNCTION psl_support_clock_correction_guard();
 DROP TRIGGER psl_source_lineage ON baas_supportchannelclaim;
 DROP FUNCTION psl_support_channel_successor_guard();
 DROP INDEX support_channel_source_version;
 """)]
