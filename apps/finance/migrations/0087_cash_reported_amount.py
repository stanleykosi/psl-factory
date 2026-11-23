from django.conf import settings
from django.db import migrations, models
from django.db.models.deletion import PROTECT


SQL = r"""
CREATE FUNCTION psl_cash_amount_evidence_matches(eid bigint, cid uuid, supplied_kind text, candidate jsonb)
RETURNS boolean LANGUAGE plpgsql STABLE AS $$
DECLARE e core_evidence; body jsonb; amount text;
BEGIN
 SELECT * INTO e FROM core_evidence WHERE id=eid AND case_id=cid AND kind=supplied_kind;
 IF NOT FOUND OR length(e.body)>10000 OR encode(sha256(convert_to(e.body,'UTF8')),'hex')<>e.sha256 THEN RETURN false; END IF;
 body:=e.body::jsonb;
 amount:=body->>'amount';
 IF jsonb_typeof(body->'amount') IS DISTINCT FROM 'string'
    OR amount !~ '^(0|[1-9][0-9]{0,23})([.][0-9]{1,8})?$' THEN RETURN false; END IF;
 RETURN (body-'amount')=(candidate-'amount') AND amount::numeric>0
  AND trim_scale(amount::numeric)::text=candidate->>'amount';
END $$;

CREATE FUNCTION psl_cash_reported_amount_insert_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE base finance_cashreceipt; proof_author bigint;
BEGIN
 SELECT * INTO base FROM finance_cashreceipt WHERE id=NEW.receipt_id;
 PERFORM id FROM core_case WHERE id=base.case_id FOR NO KEY UPDATE;
 SELECT created_by_id INTO proof_author FROM core_evidence WHERE id=NEW.evidence_id;
 IF base.id IS NULL OR base.payload->'amount' IS DISTINCT FROM 'null'::jsonb
    OR NEW.actor_id IS DISTINCT FROM base.actor_id OR proof_author IS DISTINCT FROM base.actor_id
    OR NOT psl_schedules_grants(base.case_id,base.actor_id,ARRAY['case.read','finance.read','evidence.add','finance.cash.record'])
    OR NEW.evidence_id=base.evidence_id OR NEW.reason !~ '[^[:space:]]'
    OR (NEW.payload-'amount') IS DISTINCT FROM (base.payload-'amount')
    OR NOT psl_cash_amount_evidence_matches(NEW.evidence_id,base.case_id,'cash_report',NEW.payload)
    OR EXISTS(SELECT 1 FROM finance_cashverification lot WHERE lot.receipt_id=base.id)
 THEN RAISE EXCEPTION 'Exact original Unknown receipt and current source are required before its first verification'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION psl_cash_first_reported_amount_lot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE base finance_cashreceipt; amount_report finance_cashreportedamount; report_evidence core_evidence;
 proof core_evidence; role text; rec_id bigint; src_id bigint; recorder jsonb; bank jsonb;
BEGIN
 SELECT * INTO base FROM finance_cashreceipt WHERE id=NEW.receipt_id;
 IF NEW.successor_id IS NOT NULL THEN
  IF base.payload->'amount'='null'::jsonb AND NOT EXISTS(
    SELECT 1 FROM finance_cashsuccessor successor JOIN finance_cashverification parent ON parent.id=successor.parent_id
    WHERE successor.id=NEW.successor_id AND parent.receipt_id=base.id)
  THEN RAISE EXCEPTION 'Cash successor must extend a verified lot on the exact receipt'; END IF;
  RETURN NEW;
 END IF;
 IF base.payload->'amount' IS DISTINCT FROM 'null'::jsonb AND NEW.reported_amount_id IS NULL THEN RETURN NEW; END IF;
 PERFORM id FROM core_case WHERE id=base.case_id FOR NO KEY UPDATE;
 SELECT * INTO amount_report FROM finance_cashreportedamount WHERE receipt_id=base.id;
 SELECT * INTO report_evidence FROM core_evidence WHERE id=amount_report.evidence_id;
 SELECT * INTO proof FROM core_evidence WHERE id=NEW.evidence_id;
 role:=NEW.authority->'reported_amount'->>'role';
 rec_id:=(NEW.authority->>'D14.recorder_authority_ref')::bigint;
 src_id:=(NEW.authority->>'D14.receipt_verification_source_ref')::bigint;
 recorder:=psl_schedules_values(rec_id)->0;
 bank:=psl_schedules_values(src_id)->0;
 IF base.payload->'amount' IS DISTINCT FROM 'null'::jsonb OR amount_report.id IS NULL
    OR NEW.reported_amount_id IS DISTINCT FROM amount_report.id OR role IS NULL
    OR NEW.authority->'reported_amount' IS DISTINCT FROM jsonb_build_object(
        'id',amount_report.id,'evidence',report_evidence.id,'sha256',report_evidence.sha256,'role',role)
    OR NEW.amount IS DISTINCT FROM (amount_report.payload->>'amount')::numeric
    OR NOT psl_schedules_grants(base.case_id,base.actor_id,ARRAY['case.read','finance.read','evidence.add','finance.cash.record'])
    OR NOT psl_schedules_grants(base.case_id,NEW.actor_id,ARRAY['case.read','finance.read','finance.cash.verify'])
    OR NOT psl_schedules_grants(base.case_id,proof.created_by_id,ARRAY['case.read','finance.read','evidence.add'])
    OR NOT psl_schedules_role_current(base.case_id,NEW.actor_id,NEW.authority,role)
    OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id=rec_id AND component='D14.recorder_authority_ref'
                  AND psl_schedules_policy_current(base.case_id,id))
    OR NOT EXISTS(SELECT 1 FROM policy_configuration WHERE id=src_id AND component='D14.receipt_verification_source_ref'
                  AND psl_schedules_policy_current(base.case_id,id))
    OR NEW.authority->'rule' IS DISTINCT FROM recorder
    OR NOT COALESCE((recorder->'roles') ? role,false)
    OR (NEW.actor_id=base.actor_id AND COALESCE(recorder->>'allow_reporter_verify','false')<>'true')
    OR (bank->>'require_independent_evidence'='true' AND proof.source IS NOT DISTINCT FROM report_evidence.source)
    OR (bank->>'source',bank->>'currency',bank->>'amount_basis') IS DISTINCT FROM
       (amount_report.payload->>'source',amount_report.payload->>'currency',amount_report.payload->>'amount_basis')
    OR round(NEW.amount,(bank->>'decimal_places')::int) IS DISTINCT FROM NEW.amount
    OR NOT psl_cash_amount_evidence_matches(NEW.evidence_id,base.case_id,'cash_verification',amount_report.payload)
 THEN RAISE EXCEPTION 'First verification requires the exact current reported amount and native Finance authority'; END IF;
 RETURN NEW;
END $$;

CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_cashreportedamount
 FOR EACH ROW EXECUTE FUNCTION psl_append_only();
CREATE TRIGGER psl_cash_reported_amount_insert BEFORE INSERT ON finance_cashreportedamount
 FOR EACH ROW EXECUTE FUNCTION psl_cash_reported_amount_insert_guard();
CREATE TRIGGER psl_cash_first_reported_amount_lot BEFORE INSERT ON finance_cashverification
 FOR EACH ROW EXECUTE FUNCTION psl_cash_first_reported_amount_lot_guard();
"""

REVERSE_SQL = """
DROP TRIGGER psl_cash_first_reported_amount_lot ON finance_cashverification;
DROP TRIGGER psl_cash_reported_amount_insert ON finance_cashreportedamount;
DROP TRIGGER psl_immutable ON finance_cashreportedamount;
DROP FUNCTION psl_cash_first_reported_amount_lot_guard();
DROP FUNCTION psl_cash_reported_amount_insert_guard();
DROP FUNCTION psl_cash_amount_evidence_matches(bigint,uuid,text,jsonb);
"""


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0086_payroll_review_note'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='CashReportedAmount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload', models.JSONField()),
                ('reason', models.CharField(max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=PROTECT, to=settings.AUTH_USER_MODEL)),
                ('evidence', models.ForeignKey(on_delete=PROTECT, to='core.evidence')),
                ('receipt', models.OneToOneField(on_delete=PROTECT, related_name='reported_amount_supplement', to='finance.cashreceipt')),
            ],
        ),
        migrations.AddField(
            model_name='cashverification',
            name='reported_amount',
            field=models.OneToOneField(null=True, on_delete=PROTECT, to='finance.cashreportedamount'),
        ),
        migrations.AddConstraint(
            model_name='cashverification',
            constraint=models.CheckConstraint(condition=models.Q(reported_amount__isnull=True)|models.Q(successor__isnull=True),
                                              name='cash_supplement_first_lot_only'),
        ),
        migrations.RunSQL(SQL, REVERSE_SQL),
    ]
