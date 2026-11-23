import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pmo', '0055_rfpfollowupcursor'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='PlanningDepartmentInput', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('department', models.CharField(max_length=30)),
            ('version', models.PositiveIntegerField()),
            ('source_party', models.CharField(max_length=160)),
            ('received_at', models.DateTimeField()),
            ('summary', models.TextField()),
            ('effort_state', models.CharField(max_length=20)),
            ('person_days', models.DecimalField(max_digits=12, decimal_places=3, null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.case')),
            ('packet', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.evidence')),
            ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.evidence')),
            ('previous', models.OneToOneField(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='successor', to='pmo.planningdepartmentinput')),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [
            models.UniqueConstraint(fields=['packet', 'department', 'version'], name='planning_department_version'),
            models.CheckConstraint(condition=models.Q(department__in=['Engineering', 'QA', 'Security', 'Product', 'Infrastructure']), name='planning_department_name'),
            models.CheckConstraint(condition=(models.Q(effort_state='known', person_days__gte=0, person_days__isnull=False) |
                models.Q(effort_state__in=['unknown', 'not_applicable'], person_days__isnull=True)), name='planning_department_effort'),
        ]}),
        migrations.RunSQL('''
CREATE FUNCTION psl_planning_department_subject() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old pmo_planningdepartmentinput;
BEGIN
 IF NEW.person_days='NaN'::numeric THEN RAISE EXCEPTION 'Finite department effort required'; END IF;
 IF NOT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=NEW.packet_id AND e.case_id=NEW.case_id AND e.kind='planning_packet')
 OR NOT EXISTS(SELECT 1 FROM core_evidence e WHERE e.id=NEW.source_id AND e.case_id=NEW.case_id)
 THEN RAISE EXCEPTION 'Exact same-case planning packet and input source required'; END IF;
 SELECT * INTO old FROM pmo_planningdepartmentinput WHERE packet_id=NEW.packet_id AND department=NEW.department ORDER BY version DESC LIMIT 1;
 IF NEW.version <> COALESCE(old.version,0)+1 OR NEW.previous_id IS DISTINCT FROM old.id
 THEN RAISE EXCEPTION 'Exact planning department input predecessor required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER psl_subject BEFORE INSERT ON pmo_planningdepartmentinput FOR EACH ROW EXECUTE FUNCTION psl_planning_department_subject();
CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON pmo_planningdepartmentinput FOR EACH ROW EXECUTE FUNCTION psl_append_only();
''', '''DROP TRIGGER psl_immutable ON pmo_planningdepartmentinput;
DROP TRIGGER psl_subject ON pmo_planningdepartmentinput;
DROP FUNCTION psl_planning_department_subject();'''),
    ]
