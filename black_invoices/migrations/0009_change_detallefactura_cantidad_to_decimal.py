# Generated manually on 2025-09-05

from django.db import migrations, models
import django.core.validators
from decimal import Decimal

class Migration(migrations.Migration):

    dependencies = [
        ('black_invoices', '0008_change_stock_to_decimal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detallefactura',
            name='cantidad',
            field=models.DecimalField(
                decimal_places=3,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal('0.001'))],
                verbose_name='Cantidad'
            ),
        ),
    ]