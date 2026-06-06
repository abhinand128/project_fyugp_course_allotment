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

@register.filter(name='get_paper_display_name')
def get_paper_display_name(paper_no, semester):
    """
    Returns descriptive paper name (e.g., DSC1, DSC4, MDC, VAC)
    """
    try:
        sem = int(semester)
        p_no = int(paper_no)
        
        if sem == 1 or sem == 2:
            if p_no == 4:
                return "MDC"
            dsc_num = 3 * (sem - 1) + p_no
            return f"DSC {dsc_num}"
        elif sem == 3:
            if p_no == 5:
                return "MDC"
            if p_no == 6:
                return "VAC"
            # 1->7, 2->8, 3->9, 4->10
            dsc_num = 2 * (sem - 1) + p_no + 4 # This is getting messy, let's just use explicit mapping
            mapping = {1: "DSC 7", 2: "DSC 8", 3: "DSC 9", 4: "DSC 10"}
            return mapping.get(p_no, f"Paper {p_no}")
        
        return f"Paper {p_no}"
    except (ValueError, TypeError, AttributeError):
        return f"Paper {paper_no}"


