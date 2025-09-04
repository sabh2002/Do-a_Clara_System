from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import Producto, UnidadMedida
from decimal import Decimal

class Command(BaseCommand):
    help = 'Carga los productos específicos de Corporación Agrícola Doña Clara'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sobrescribir',
            action='store_true',
            help='Sobrescribir productos existentes con el mismo nombre',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('🚛 Cargando productos de Corporación Agrícola Doña Clara...\n')
        
        # Obtener unidades de medida
        try:
            metros = UnidadMedida.objects.get(abreviatura='m')
            kg = UnidadMedida.objects.get(abreviatura='kg')
            unidades = UnidadMedida.objects.get(abreviatura='un')
        except UnidadMedida.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('❌ Error: Ejecuta primero "python manage.py setup_unidades_medida"')
            )
            return
        
        # Definir productos
        productos_data = [
            # MANGUERAS
            # Mang 100R1
            {'nombre': 'Mang 100R1 1/4', 'descripcion': 'Manguera hidráulica 100R1 de 1/4 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R1 3/8', 'descripcion': 'Manguera hidráulica 100R1 de 3/8 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R1 1/2', 'descripcion': 'Manguera hidráulica 100R1 de 1/2 pulgada', 'unidad': metros},
            
            # Mang 100R2
            {'nombre': 'Mang 100R2 1/4', 'descripcion': 'Manguera hidráulica 100R2 de 1/4 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R2 3/8', 'descripcion': 'Manguera hidráulica 100R2 de 3/8 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R2 1/2', 'descripcion': 'Manguera hidráulica 100R2 de 1/2 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R2 5/8', 'descripcion': 'Manguera hidráulica 100R2 de 5/8 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R2 3/4', 'descripcion': 'Manguera hidráulica 100R2 de 3/4 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R2 1"', 'descripcion': 'Manguera hidráulica 100R2 de 1 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R2 1¼', 'descripcion': 'Manguera hidráulica 100R2 de 1¼ pulgada', 'unidad': metros},
            
            # Mang R12
            {'nombre': 'Mang R12 1/2', 'descripcion': 'Manguera hidráulica R12 de 1/2 pulgada', 'unidad': metros},
            {'nombre': 'Mang R12 5/8', 'descripcion': 'Manguera hidráulica R12 de 5/8 pulgada', 'unidad': metros},
            {'nombre': 'Mang R12 3/4', 'descripcion': 'Manguera hidráulica R12 de 3/4 pulgada', 'unidad': metros},
            {'nombre': 'Mang R12 1¼', 'descripcion': 'Manguera hidráulica R12 de 1¼ pulgada', 'unidad': metros},
            
            # Mang 100R15
            {'nombre': 'Mang 100R15 3/4', 'descripcion': 'Manguera hidráulica 100R15 de 3/4 pulgada', 'unidad': metros},
            {'nombre': 'Mang 100R15 1"', 'descripcion': 'Manguera hidráulica 100R15 de 1 pulgada', 'unidad': metros},
            
            # FERRULES
            # Ferrul R1
            {'nombre': 'Ferrul R1 1/4', 'descripcion': 'Férula R1 para manguera de 1/4 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R1 3/8', 'descripcion': 'Férula R1 para manguera de 3/8 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R1 1/2', 'descripcion': 'Férula R1 para manguera de 1/2 pulgada', 'unidad': unidades},
            
            # Ferrul R2
            {'nombre': 'Ferrul R2 1/4', 'descripcion': 'Férula R2 para manguera de 1/4 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R2 3/8', 'descripcion': 'Férula R2 para manguera de 3/8 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R2 1/2', 'descripcion': 'Férula R2 para manguera de 1/2 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R2 5/8', 'descripcion': 'Férula R2 para manguera de 5/8 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R2 3/4', 'descripcion': 'Férula R2 para manguera de 3/4 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R2 1"', 'descripcion': 'Férula R2 para manguera de 1 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R2 1¼', 'descripcion': 'Férula R2 para manguera de 1¼ pulgada', 'unidad': unidades},
            
            # Ferrul R12
            {'nombre': 'Ferrul R12 1/2', 'descripcion': 'Férula R12 para manguera de 1/2 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R12 5/8', 'descripcion': 'Férula R12 para manguera de 5/8 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R12 3/4', 'descripcion': 'Férula R12 para manguera de 3/4 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R12 1"', 'descripcion': 'Férula R12 para manguera de 1 pulgada', 'unidad': unidades},
            {'nombre': 'Ferrul R12 1¼', 'descripcion': 'Férula R12 para manguera de 1¼ pulgada', 'unidad': unidades},
            
            # Ferrul R13
            {'nombre': 'Ferrul R13 1"', 'descripcion': 'Férula R13 para manguera de 1 pulgada', 'unidad': unidades},
            
            # CONEXIONES NJ
            {'nombre': 'Conexion NJ 04x04', 'descripcion': 'Conexión hidráulica NJ 04x04', 'unidad': unidades},
            {'nombre': 'Conexion NJ 04x05', 'descripcion': 'Conexión hidráulica NJ 04x05', 'unidad': unidades},
            {'nombre': 'Conexion NJ 04x06', 'descripcion': 'Conexión hidráulica NJ 04x06', 'unidad': unidades},
            {'nombre': 'Conexion NJ 06x06', 'descripcion': 'Conexión hidráulica NJ 06x06', 'unidad': unidades},
            {'nombre': 'Conexion NJ 06x08', 'descripcion': 'Conexión hidráulica NJ 06x08', 'unidad': unidades},
            {'nombre': 'Conexion NJ 08x08', 'descripcion': 'Conexión hidráulica NJ 08x08', 'unidad': unidades},
            {'nombre': 'Conexion NJ 08x10', 'descripcion': 'Conexión hidráulica NJ 08x10', 'unidad': unidades},
            {'nombre': 'Conexion NJ 10x10', 'descripcion': 'Conexión hidráulica NJ 10x10', 'unidad': unidades},
            {'nombre': 'Conexion NJ 10x12', 'descripcion': 'Conexión hidráulica NJ 10x12', 'unidad': unidades},
            {'nombre': 'Conexion NJ 12x12', 'descripcion': 'Conexión hidráulica NJ 12x12', 'unidad': unidades},
            {'nombre': 'Conexion NJ 16x16', 'descripcion': 'Conexión hidráulica NJ 16x16', 'unidad': unidades},
            {'nombre': 'Conexion NJ 20x20', 'descripcion': 'Conexión hidráulica NJ 20x20', 'unidad': unidades},
            
            # CONEXIONES NJ45° y NJ90°
            {'nombre': 'Conexion NJ45° 04x04', 'descripcion': 'Conexión hidráulica NJ 45° 04x04', 'unidad': unidades},
            {'nombre': 'Conexion NJ45° 04x05', 'descripcion': 'Conexión hidráulica NJ 45° 04x05', 'unidad': unidades},
            {'nombre': 'Conexion NJ45° 04x06', 'descripcion': 'Conexión hidráulica NJ 45° 04x06', 'unidad': unidades},
            {'nombre': 'Conexion NJ45° 06x06', 'descripcion': 'Conexión hidráulica NJ 45° 06x06', 'unidad': unidades},
            {'nombre': 'Conexion NJ45° 06x08', 'descripcion': 'Conexión hidráulica NJ 45° 06x08', 'unidad': unidades},
            {'nombre': 'Conexion NJ45° 08x08', 'descripcion': 'Conexión hidráulica NJ 45° 08x08', 'unidad': unidades},
            
            {'nombre': 'Conexion NJ90° 04x04', 'descripcion': 'Conexión hidráulica NJ 90° 04x04', 'unidad': unidades},
            {'nombre': 'Conexion NJ90° 06x06', 'descripcion': 'Conexión hidráulica NJ 90° 06x06', 'unidad': unidades},
            {'nombre': 'Conexion NJ90° 08x08', 'descripcion': 'Conexión hidráulica NJ 90° 08x08', 'unidad': unidades},
            
            # CONEXIONES OFT
            {'nombre': 'Conexion OFT 04x04', 'descripcion': 'Conexión hidráulica OFT 04x04', 'unidad': unidades},
            {'nombre': 'Conexion OFT 04x06', 'descripcion': 'Conexión hidráulica OFT 04x06', 'unidad': unidades},
            {'nombre': 'Conexion OFT 06x06', 'descripcion': 'Conexión hidráulica OFT 06x06', 'unidad': unidades},
            {'nombre': 'Conexion OFT 08x08', 'descripcion': 'Conexión hidráulica OFT 08x08', 'unidad': unidades},
            {'nombre': 'Conexion OFT 10x10', 'descripcion': 'Conexión hidráulica OFT 10x10', 'unidad': unidades},
            {'nombre': 'Conexion OFT 12x12', 'descripcion': 'Conexión hidráulica OFT 12x12', 'unidad': unidades},
            {'nombre': 'Conexion OFT 16x16', 'descripcion': 'Conexión hidráulica OFT 16x16', 'unidad': unidades},
            
            # CONEXIONES OFT45° y OFT90°
            {'nombre': 'Conexion OFT45° 04x04', 'descripcion': 'Conexión hidráulica OFT 45° 04x04', 'unidad': unidades},
            {'nombre': 'Conexion OFT45° 06x06', 'descripcion': 'Conexión hidráulica OFT 45° 06x06', 'unidad': unidades},
            {'nombre': 'Conexion OFT90° 08x08', 'descripcion': 'Conexión hidráulica OFT 90° 08x08', 'unidad': unidades},
            {'nombre': 'Conexion OFT90° 10x10', 'descripcion': 'Conexión hidráulica OFT 90° 10x10', 'unidad': unidades},
            
            # CONEXIONES MB y MJ
            {'nombre': 'Conexion MB 04x02', 'descripcion': 'Conexión hidráulica MB 04x02', 'unidad': unidades},
            {'nombre': 'Conexion MB 04x04', 'descripcion': 'Conexión hidráulica MB 04x04', 'unidad': unidades},
            {'nombre': 'Conexion MB 04x06', 'descripcion': 'Conexión hidráulica MB 04x06', 'unidad': unidades},
            {'nombre': 'Conexion MJ 06x06', 'descripcion': 'Conexión hidráulica MJ 06x06', 'unidad': unidades},
            {'nombre': 'Conexion MJ 08x08', 'descripcion': 'Conexión hidráulica MJ 08x08', 'unidad': unidades},
            {'nombre': 'Conexion MJ 10x10', 'descripcion': 'Conexión hidráulica MJ 10x10', 'unidad': unidades},
            {'nombre': 'Conexion MJ 12x12', 'descripcion': 'Conexión hidráulica MJ 12x12', 'unidad': unidades},
            {'nombre': 'Conexion MJ 16x16', 'descripcion': 'Conexión hidráulica MJ 16x16', 'unidad': unidades},
            
            # CONEXIONES ORFS MACHO
            {'nombre': 'Conexion ORFS MACHO 04x04', 'descripcion': 'Conexión hidráulica ORFS MACHO 04x04', 'unidad': unidades},
            {'nombre': 'Conexion ORFS MACHO 06x06', 'descripcion': 'Conexión hidráulica ORFS MACHO 06x06', 'unidad': unidades},
            {'nombre': 'Conexion ORFS MACHO 08x08', 'descripcion': 'Conexión hidráulica ORFS MACHO 08x08', 'unidad': unidades},
            {'nombre': 'Conexion ORFS MACHO 10x10', 'descripcion': 'Conexión hidráulica ORFS MACHO 10x10', 'unidad': unidades},
            {'nombre': 'Conexion ORFS MACHO 12x12', 'descripcion': 'Conexión hidráulica ORFS MACHO 12x12', 'unidad': unidades},
            {'nombre': 'Conexion ORFS MACHO 16x16', 'descripcion': 'Conexión hidráulica ORFS MACHO 16x16', 'unidad': unidades},
            
            # ESPIGAS SOLDABLES
            {'nombre': 'Espiga soldable 1/4', 'descripcion': 'Espiga soldable de 1/4 pulgada', 'unidad': unidades},
            {'nombre': 'Espiga soldable 3/8', 'descripcion': 'Espiga soldable de 3/8 pulgada', 'unidad': unidades},
            {'nombre': 'Espiga soldable 1/2', 'descripcion': 'Espiga soldable de 1/2 pulgada', 'unidad': unidades},
            {'nombre': 'Espiga soldable 5/8', 'descripcion': 'Espiga soldable de 5/8 pulgada', 'unidad': unidades},
            {'nombre': 'Espiga soldable 3/4', 'descripcion': 'Espiga soldable de 3/4 pulgada', 'unidad': unidades},
            {'nombre': 'Espiga soldable 1"', 'descripcion': 'Espiga soldable de 1 pulgada', 'unidad': unidades},
            
            # ELECTRODOS (se venden por Kg)
            {'nombre': 'Electrodo 6011', 'descripcion': 'Electrodo para soldadura 6011', 'unidad': kg},
            {'nombre': 'Electrodo 6013', 'descripcion': 'Electrodo para soldadura 6013', 'unidad': kg},
            {'nombre': 'Electrodo 7018', 'descripcion': 'Electrodo para soldadura 7018', 'unidad': kg},
        ]
        
        # Crear productos
        created_count = 0
        updated_count = 0
        
        for producto_data in productos_data:
            nombre = producto_data['nombre']
            
            # Verificar si existe
            producto_existente = Producto.objects.filter(nombre=nombre).first()
            
            if producto_existente:
                if options['sobrescribir']:
                    # Actualizar producto existente
                    producto_existente.descripcion = producto_data['descripcion']
                    producto_existente.unidad_medida = producto_data['unidad']
                    producto_existente.save()
                    updated_count += 1
                    self.stdout.write(f'🔄 Actualizado: {nombre}')
                else:
                    self.stdout.write(f'⚠️  Ya existe: {nombre} (usa --sobrescribir para actualizar)')
            else:
                # Crear nuevo producto
                Producto.objects.create(
                    nombre=nombre,
                    descripcion=producto_data['descripcion'],
                    unidad_medida=producto_data['unidad'],
                    precio=Decimal('1.00'),  # Precio temporal
                    precio_compra=Decimal('0.70'),  # Precio temporal
                    stock=0,  # Stock inicial
                    activo=True
                )
                created_count += 1
                self.stdout.write(f'✅ Creado: {nombre}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Proceso completado!'
                f'\n   📦 Productos creados: {created_count}'
                f'\n   🔄 Productos actualizados: {updated_count}'
                f'\n   📋 Total en catálogo: {Producto.objects.count()}'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                '\n⚠️  IMPORTANTE: Los productos se crearon con precios temporales.'
                '\n   Actualiza los precios desde el admin de Django.'
            )
        )