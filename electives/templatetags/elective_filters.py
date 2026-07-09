from django import template

register = template.Library()

@register.filter(name='filter_by_category')
def filter_by_category(queryset, category):
    """Filter preferences by course category"""
    return queryset.filter(course__category=category)
