# Generated manually on 2025-09-05

from django.db import migrations, models
import django.core.validators
from decimal import Decimal

class Migration(migrations.Migration):

    dependencies = [
        ('black_invoices', '0007_add_default_tipo_facturas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='stock',
            field=models.DecimalField(
                decimal_places=3,
                default=0,
                help_text='Cantidad disponible (Máximo: 999,999 unidades). Permite hasta 3 decimales.',
                max_digits=10,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0'), message='El stock no puede ser negativo'),
                    django.core.validators.MaxValueValidator(999999, message='El stock no puede ser mayor a 999,999 unidades')
                ],
                verbose_name='Stock disponible'
            ),
        ),
    ]