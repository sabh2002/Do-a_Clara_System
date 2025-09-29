# black_invoices/templatetags/custom_filters.py
from django import template
from decimal import Decimal
from ..models import TasaCambio

register = template.Library()

@register.filter
def precio_bolivares(valor_usd):
    """
    Convierte un precio en USD a bolívares usando la tasa actual
    """
    try:
        if not valor_usd:
            return Decimal('0.00')
        
        # Convertir a Decimal si no lo es
        if not isinstance(valor_usd, Decimal):
            valor_usd = Decimal(str(valor_usd))
        
        # Obtener tasa actual
        tasa_actual = TasaCambio.get_tasa_actual()
        if tasa_actual:
            return valor_usd * tasa_actual.tasa_usd_ves
        
        return Decimal('0.00')
    except (ValueError, TypeError, AttributeError):
        return Decimal('0.00')

@register.filter
def tasa_cambio_actual(dummy=None):
    """
    Obtiene la tasa de cambio actual para usar en templates
    """
    try:
        tasa_actual = TasaCambio.get_tasa_actual()
        return tasa_actual.tasa_usd_ves if tasa_actual else 1
    except:
        return 1

# ✅ NUEVO: Filtro multiplicar que faltaba
@register.filter(name='multiplicar')
def multiplicar(value, arg):
    """
    Multiplica el valor por el argumento
    Uso en template: {{ precio|multiplicar:tasa_cambio }}
    """
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

# ✅ FILTROS ADICIONALES ÚTILES
@register.filter(name='formato_moneda_usd')
def formato_moneda_usd(value):
    """
    Formatea un número como moneda en dólares
    Uso: {{ monto|formato_moneda_usd }}
    """
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"

@register.filter(name='formato_moneda_ves')
def formato_moneda_ves(value):
    """
    Formatea un número como moneda en bolívares
    Uso: {{ monto|formato_moneda_ves }}
    """
    try:
        return f"{float(value):,.2f} Bs"
    except (ValueError, TypeError):
        return "0.00 Bs"

@register.filter(name='stock_badge_class')
def stock_badge_class(stock):
    """
    Retorna la clase CSS apropiada para el badge de stock
    Uso: {{ producto.stock|stock_badge_class }}
    """
    try:
        stock_val = int(stock)
        if stock_val <= 0:
            return 'badge-danger'
        elif stock_val <= 5:
            return 'badge-warning'
        elif stock_val <= 20:
            return 'badge-info'
        else:
            return 'badge-success'
    except (ValueError, TypeError):
        return 'badge-secondary'