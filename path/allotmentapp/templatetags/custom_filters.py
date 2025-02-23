from django import template

register = template.Library()

@register.simple_tag
def get_specific_preference(preferences, paper_no, pref_no):
    """
    Tag to get specific paper preference
    Usage: {% get_specific_preference preferences paper_no pref_no %}
    """
    specific_pref = preferences.filter(paper_no=paper_no, preference_number=pref_no).first()
    if specific_pref:
        return specific_pref.batch.course.course_name
    return '-'

@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={'class': css_class})

@register.filter
def get_item(dictionary, key):
    """Returns the value from a dictionary given a key."""
    return dictionary.get(key, "")


@register.filter(name='replace')
def replace(value, arg):
    """Replaces underscores with spaces"""
    return value.replace("_", " ") if isinstance(value, str) else value



