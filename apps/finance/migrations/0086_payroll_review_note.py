from django.db import migrations, models
from django.db.models import Q
from django.db.models.deletion import PROTECT


class Migration(migrations.Migration):
    dependencies = [('finance', '0085_invoice_draft_stop_guard')]
    operations = [
        migrations.CreateModel(
            name='PayrollReviewNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.CharField(max_length=2000)),
                ('review', models.OneToOneField(on_delete=PROTECT, to='finance.payrollreview')),
            ],
            options={'constraints': [
                models.CheckConstraint(condition=Q(note__regex=r'[^[:space:]]'), name='payroll_review_note_nonblank'),
            ]},
        ),
        migrations.RunSQL(
            'CREATE TRIGGER psl_immutable BEFORE UPDATE OR DELETE ON finance_payrollreviewnote '
            'FOR EACH ROW EXECUTE FUNCTION psl_append_only();',
            'DROP TRIGGER psl_immutable ON finance_payrollreviewnote;',
        ),
    ]
