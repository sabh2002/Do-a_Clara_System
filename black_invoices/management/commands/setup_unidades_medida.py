from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import UnidadMedida, TasaCambio
from decimal import Decimal
from datetime import date

class Command(BaseCommand):
    help = 'Configura las unidades de medida iniciales para el sistema'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write('Creando unidades de medida...')
        
        unidades = [
            {
                'nombre': 'Metros',
                'abreviatura': 'm',
                'descripcion': 'Medida lineal para mangueras y cables',
                'permite_decimales': True
            },
            {
                'nombre': 'Centímetros',
                'abreviatura': 'cm',
                'descripcion': 'Medida lineal pequeña',
                'permite_decimales': True
            },
            {
                'nombre': 'Kilogramos',
                'abreviatura': 'kg',
                'descripcion': 'Medida de peso para electrodos y materiales',
                'permite_decimales': True
            },
            {
                'nombre': 'Gramos',
                'abreviatura': 'g',
                'descripcion': 'Medida de peso pequeña',
                'permite_decimales': True
            },
            {
                'nombre': 'Unidades',
                'abreviatura': 'un',
                'descripcion': 'Para productos que se venden por pieza',
                'permite_decimales': False
            },
            {
                'nombre': 'Pares',
                'abreviatura': 'par',
                'descripcion': 'Para productos que se venden en pares',
                'permite_decimales': False
            },
            {
                'nombre': 'Juegos',
                'abreviatura': 'jgo',
                'descripcion': 'Para productos que se venden en juegos o sets',
                'permite_decimales': False
            },
            {
                'nombre': 'Rollos',
                'abreviatura': 'rllo',
                'descripcion': 'Para mangueras vendidas en rollos',
                'permite_decimales': False
            }
        ]
        
        created_count = 0
        for unidad_data in unidades:
            unidad, created = UnidadMedida.objects.get_or_create(
                abreviatura=unidad_data['abreviatura'],
                defaults=unidad_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creada: {unidad.nombre} ({unidad.abreviatura})')
                )
            else:
                self.stdout.write(f'- Ya existe: {unidad.nombre} ({unidad.abreviatura})')
        
        self.stdout.write(f'\n{created_count} unidades de medida creadas.')
        
        # Crear una tasa de cambio inicial si no existe
        self.stdout.write('\nVerificando tasa de cambio inicial...')
        tasa_hoy = TasaCambio.objects.filter(fecha=date.today()).first()
        
        if not tasa_hoy:
            # Crear tasa inicial (será actualizada por la API)
            TasaCambio.objects.create(
                fecha=date.today(),
                tasa_usd_ves=Decimal('36.50'),  # Tasa temporal
                fuente='Manual - Inicial',
                activo=True
            )
            self.stdout.write(
                self.style.SUCCESS('✓ Tasa de cambio inicial creada (será actualizada automáticamente)')
            )
        else:
            self.stdout.write('- Tasa de cambio ya existe para hoy')
        
        self.stdout.write(
            self.style.SUCCESS('\n🎉 Configuración de unidades de medida completada!')
        )