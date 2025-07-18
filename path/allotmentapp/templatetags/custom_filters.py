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


@register.filter
def multiply(value, arg):
    """Multiplies the given value by the provided argument."""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return ''


@register.filter(name='calculate_total_quota')
def calculate_total_quota(setting):
    return max(1, round(setting.strength * setting.department_quota_percentage / 100))

@register.filter(name='calculate_general_quota')
def calculate_general_quota(setting):
    total = calculate_total_quota(setting)
    return max(1, round(total * setting.general_quota_percentage / 100))

@register.filter(name='calculate_sc_st_quota')
def calculate_sc_st_quota(setting):
    total = calculate_total_quota(setting)
    return max(1, round(total * setting.sc_st_quota_percentage / 100))

@register.filter(name='calculate_other_quota')
def calculate_other_quota(setting):
    total = calculate_total_quota(setting)
    return max(1, round(total * setting.other_quota_percentage / 100))


