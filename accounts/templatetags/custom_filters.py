# accounts/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter(name='split')
def split(value, key):
    """
    Returns the value turned into a list by splitting on the given key.
    Usage: {{ value|split:"," }}
    """
    if not value:
        return []
    return str(value).split(key)

@register.filter(name='trim')
def trim(value):
    """
    Removes leading and trailing whitespace from a string.
    Usage: {{ value|trim }}
    """
    if not value:
        return ""
    return str(value).strip()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Gets an item from a dictionary.
    Usage: {{ mydict|get_item:key }}
    """
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter(name='multiply')
def multiply(value, arg):
    """
    Multiplies the value by the argument.
    Usage: {{ value|multiply:3 }}
    """
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def mul(value, arg):
    """Multiplies the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
@register.filter
def progress_circumference(value):
    """Calculate progress circumference for SVG circle (radius=25, so circumference=157)"""
    try:
        # For a circle with radius 25, circumference = 2 * π * 25 ≈ 157
        # Calculate the dash length based on percentage
        circumference = 157
        progress = float(value) / 100 * circumference
        return f"{progress:.1f}"
    except (ValueError, TypeError):
        return "0"