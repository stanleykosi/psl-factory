from django import template
register=template.Library()
@register.filter
def section_label(value):
    return str(value).replace('_',' ').capitalize()
