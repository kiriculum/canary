from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def company_cell(value: list, arg: int = 0):
    comp = value[arg-1]
    color = 'text-success' if comp[1] > 0 else 'text-danger'
    return mark_safe(f'<span>{comp[0]}</span><span class="ms-2 {color}">{comp[1]}%</span>')
