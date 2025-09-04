# Crear archivo: black_invoices/management/commands/check_system.py

from django.core.management.base import BaseCommand
from django.db import connection
from ...models import *

class Command(BaseCommand):
    help = 'Verifica que todos los modelos y el sistema estén funcionando correctamente'

    def handle(self, *args, **kwargs):
        self.stdout.write('🔍 Verificando el sistema...\n')
        
        # 1. Verificar modelos
        try:
            self.stdout.write('📋 Verificando modelos:')
            
            # UnidadMedida
            unidades_count = UnidadMedida.objects.count()
            self.stdout.write(f'   ✓ UnidadMedida: {unidades_count} registros')
            
            # TasaCambio
            tasas_count = TasaCambio.objects.count()
            tasa_actual = TasaCambio.get_tasa_actual()
            self.stdout.write(f'   ✓ TasaCambio: {tasas_count} registros')
            if tasa_actual:
                self.stdout.write(f'     Tasa actual: 1 USD = {tasa_actual.tasa_usd_ves} VES')
            
            # Producto
            productos_count = Producto.objects.count()
            productos_con_unidad = Producto.objects.filter(unidad_medida__isnull=False).count()
            self.stdout.write(f'   ✓ Producto: {productos_count} registros')
            self.stdout.write(f'     Con unidad de medida: {productos_con_unidad}')
            
            # Otros modelos principales
            clientes_count = Cliente.objects.count()
            empleados_count = Empleado.objects.count()
            facturas_count = Factura.objects.count()
            
            self.stdout.write(f'   ✓ Cliente: {clientes_count} registros')
            self.stdout.write(f'   ✓ Empleado: {empleados_count} registros')
            self.stdout.write(f'   ✓ Factura: {facturas_count} registros')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error en modelos: {str(e)}'))
            return
        
        # 2. Verificar métodos de Producto
        try:
            self.stdout.write('\n🧪 Probando métodos de Producto:')
            if productos_count > 0:
                producto = Producto.objects.first()
                
                # Probar métodos nuevos
                margen = producto.get_margen_ganancia()
                ganancia = producto.get_ganancia_unitaria()
                precios = producto.get_precios_formateados_completos()
                
                self.stdout.write(f'   ✓ Margen de ganancia: {margen}%')
                self.stdout.write(f'   ✓ Ganancia unitaria: ${ganancia}')
                self.stdout.write(f'   ✓ Precios formateados: ✓')
                
                # Probar validación de cantidad
                es_valido, mensaje = producto.validar_cantidad_segun_unidad(1.5)
                self.stdout.write(f'   ✓ Validación cantidad: {mensaje}')
                
            else:
                self.stdout.write('   ⚠️  No hay productos para probar')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error en métodos: {str(e)}'))
        
        # 3. Verificar base de datos
        try:
            self.stdout.write('\n💾 Verificando base de datos:')
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                tabla_count = len([t for t in tables if 'black_invoices' in t[0]])
                self.stdout.write(f'   ✓ Tablas de black_invoices: {tabla_count}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error en BD: {str(e)}'))
        
        self.stdout.write(
            self.style.SUCCESS('\n🎉 Verificación completada!')
        )