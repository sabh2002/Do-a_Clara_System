# Generated manually on 2025-09-05

from django.db import migrations

def create_default_tipo_facturas(apps, schema_editor):
    TipoFactura = apps.get_model('black_invoices', 'TipoFactura')
    
    # Crear tipo de factura de contado si no existe
    contado, created = TipoFactura.objects.get_or_create(
        credito_fac=False,
        contado_fac=True,
        defaults={
            'plazo_credito': None
        }
    )
    
    # Crear tipo de factura a crédito si no existe  
    credito, created = TipoFactura.objects.get_or_create(
        credito_fac=True,
        contado_fac=False,
        defaults={
            'plazo_credito': 30  # 30 días por defecto
        }
    )

def reverse_default_tipo_facturas(apps, schema_editor):
    TipoFactura = apps.get_model('black_invoices', 'TipoFactura')
    TipoFactura.objects.filter(credito_fac=False, contado_fac=True).delete()
    TipoFactura.objects.filter(credito_fac=True, contado_fac=False).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('black_invoices', '0006_merge_20250905_0905'),
    ]

    operations = [
        migrations.RunPython(create_default_tipo_facturas, reverse_default_tipo_facturas),
    ]