from django import template

register = template.Library()

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
