from django import forms
from django.forms import formset_factory


SCALES = [('units', 'Full currency amounts'), ('thousands', 'Thousands'), ('millions', 'Millions')]


class ReviewForm(forms.Form):
    entity = forms.CharField(label='Company or business', max_length=180)
    period = forms.RegexField(label='Reporting month (YYYY-MM)', regex=r'^\d{4}-(0[1-9]|1[0-2])$')
    currency = forms.RegexField(label='Currency code (such as NGN)', regex=r'^[A-Z]{3}$')
    unit = forms.ChoiceField(label='Units used in the file', choices=[('', 'Choose the units'), ('unknown', 'Unclear · check the source'), *SCALES,
                                ('mixed', 'Each row has its own units')])
    unit_evidence = forms.CharField(label='Where the document explains the units', max_length=500)
    control_total = forms.CharField(label='Printed check total, if the file gives one', max_length=64, required=False)
    no_total = forms.BooleanField(label='I checked the original and it has no total for these rows.', required=False)
    control_unit = forms.ChoiceField(label='Units for the printed check total', choices=[('file', 'Use file units'), *SCALES], initial='file')
    note = forms.CharField(label='Review note or corrections', max_length=1000, required=False)
    checked = forms.BooleanField(label='I checked the figures, units and any questions against the original file.')

    def clean(self):
        values = super().clean()
        if not values.get('control_total') and not values.get('no_total'):
            self.add_error('control_total', 'Check the original. Enter its printed total or confirm that it has none for these rows.')
        if values.get('control_total'):
            values['no_total'] = False
        return values


class FigureForm(forms.Form):
    account = forms.CharField(label='Account or item', max_length=180)
    amount = forms.CharField(label='Amount as printed', max_length=64)
    unit = forms.ChoiceField(label='Units', choices=[('file', 'Use file units'), ('unknown', 'Unclear · check the source'), *SCALES])
    citation = forms.CharField(label='Where it appears in the original', max_length=500)


Figures = formset_factory(FigureForm, extra=0, max_num=100, absolute_max=101, validate_max=True, can_delete=True)


class AccountsForm(forms.Form):
    entity = forms.RegexField(label='Company code used in management accounts', regex=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$')
    basis = forms.CharField(label='Accounting basis', max_length=100)
    completeness = forms.ChoiceField(label='Coverage of the accounts', choices=[
        ('', 'Choose coverage'), ('complete', 'Complete'), ('partial', 'Partial'), ('unknown', 'Unknown')])
