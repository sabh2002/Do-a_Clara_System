from django.core.management.base import BaseCommand
from django.db import transaction
from black_invoices.models import Ventas, DetalleGanancia
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Pobla los registros de ganancias históricas para ventas existentes que no tienen DetalleGanancia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecuta sin hacer cambios reales, solo muestra lo que haría',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Muestra información detallada del proceso',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Tamaño del lote para procesar ventas (default: 100)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        batch_size = options['batch_size']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('MODO DRY-RUN: No se realizarán cambios reales')
            )

        # Obtener ventas que no tienen registros de ganancias
        ventas_sin_ganancias = Ventas.objects.filter(
            detalleganancia__isnull=True,
            status__vent_cancelada=False
        ).select_related('empleado').prefetch_related('detalles_factura', 'detalles_nota')

        total_ventas = ventas_sin_ganancias.count()
        
        if total_ventas == 0:
            self.stdout.write(
                self.style.SUCCESS('No hay ventas sin registros de ganancias.')
            )
            return

        self.stdout.write(
            f'Encontradas {total_ventas} ventas sin registros de ganancias.'
        )

        if verbose:
            self.stdout.write('Procesando ventas...')

        registros_creados = 0
        errores = 0
        
        # Procesar en lotes
        for i in range(0, total_ventas, batch_size):
            batch = ventas_sin_ganancias[i:i + batch_size]
            
            if verbose:
                self.stdout.write(
                    f'Procesando lote {i//batch_size + 1} ({len(batch)} ventas)...'
                )
            
            with transaction.atomic():
                for venta in batch:
                    try:
                        if self._procesar_venta(venta, dry_run, verbose):
                            registros_creados += 1
                    except Exception as e:
                        errores += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'Error procesando venta {venta.id}: {str(e)}'
                            )
                        )
                        if verbose:
                            logger.exception(f'Error en venta {venta.id}')

        # Resumen final
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(f'RESUMEN:')
        )
        self.stdout.write(f'Ventas procesadas: {total_ventas}')
        self.stdout.write(f'Registros creados: {registros_creados}')
        if errores > 0:
            self.stdout.write(
                self.style.ERROR(f'Errores: {errores}')
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'NOTA: Este fue un dry-run. Para aplicar los cambios, '
                    'ejecute el comando sin --dry-run'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('¡Proceso completado exitosamente!')
            )

    def _procesar_venta(self, venta, dry_run, verbose):
        """Procesa una venta individual y crea sus registros de ganancia"""
        
        # Obtener detalles según el tipo de venta
        if hasattr(venta, 'factura') and venta.factura:
            detalles = venta.detalles_factura.all()
        elif hasattr(venta, 'nota_entrega') and venta.nota_entrega:
            detalles = venta.detalles_nota.all()
        else:
            if verbose:
                self.stdout.write(
                    self.style.WARNING(
                        f'Venta {venta.id}: No tiene factura ni nota de entrega'
                    )
                )
            return False

        if not detalles.exists():
            if verbose:
                self.stdout.write(
                    self.style.WARNING(f'Venta {venta.id}: No tiene detalles')
                )
            return False

        registros_creados = 0
        ganancia_total = Decimal('0.00')

        for detalle in detalles:
            # Calcular datos del detalle
            if hasattr(detalle, 'producto'):  # Detalle de factura
                producto = detalle.producto
                cantidad = detalle.cantidad
                precio_venta = producto.precio
                subtotal = detalle.sub_total
            else:  # Detalle de nota de entrega
                producto = detalle.producto
                cantidad = detalle.cantidad
                precio_venta = detalle.precio_unitario
                subtotal = detalle.subtotal_linea

            # Usar precio actual como costo (esto es una aproximación para datos históricos)
            costo_unitario = producto.precio_actual or Decimal('0.00')
            costo_total = costo_unitario * cantidad
            ganancia_unitaria = precio_venta - costo_unitario
            ganancia_total_producto = ganancia_unitaria * cantidad
            
            # Calcular margen
            if precio_venta > 0:
                margen = (ganancia_unitaria / precio_venta) * 100
            else:
                margen = Decimal('0.00')

            ganancia_total += ganancia_total_producto

            if verbose:
                self.stdout.write(
                    f'  Producto: {producto.nombre} | '
                    f'Cant: {cantidad} | '
                    f'Ganancia: ${ganancia_total_producto:.2f}'
                )

            if not dry_run:
                DetalleGanancia.objects.create(
                    venta=venta,
                    producto=producto,
                    cantidad=cantidad,
                    precio_venta=precio_venta,
                    costo_unitario=costo_unitario,
                    ganancia_unitaria=ganancia_unitaria,
                    ganancia_total=ganancia_total_producto,
                    margen_porcentaje=margen,
                    fecha_registro=venta.fecha_venta,
                    es_historico=True
                )
                registros_creados += 1

        if verbose:
            self.stdout.write(
                f'Venta {venta.id}: {registros_creados} registros creados. '
                f'Ganancia total: ${ganancia_total:.2f}'
            )

        return True

    def _confirmar_accion(self):
        """Solicita confirmación del usuario"""
        respuesta = input('¿Desea continuar? [y/N]: ').lower().strip()
        return respuesta in ['y', 'yes', 'sí', 'si']