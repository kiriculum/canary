from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def company_cell(value: list | None, arg: int = 0):
    try:
        comp = value[arg - 1]
    except IndexError:
        return '-'
    color = 'style=color:rgb(48,84,150)'
    return mark_safe(f'<span {"" if comp[1] > 0 else color}>{comp[0]}</span>'
                     f'<span {"" if comp[1] > 0 else color} class="ms-2">'
                     f'{f"{comp[1]}%" if comp[1] > 0 else f"({abs(comp[1])}%)"}</span>')


@register.filter
def change_cell(value: int | None):
    if value is None:
        return '-'
    return f'{value}%' if value > 0 else f'({abs(value)}%)'
