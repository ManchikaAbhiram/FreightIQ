from decimal import Decimal
from django import template
register=template.Library()
@register.filter
def subtract(value,arg):
    try: return Decimal(str(value or 0))-Decimal(str(arg or 0))
    except Exception: return Decimal('0')
