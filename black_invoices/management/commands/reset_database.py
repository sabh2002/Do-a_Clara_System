from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.apps import apps
from black_invoices.models import *
import os


class Command(BaseCommand):
    help = 'Vacía completamente la base de datos y resetea todos los IDs a empezar desde 1'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma que deseas vaciar TODA la base de datos (ACCIÓN IRREVERSIBLE)',
        )
        parser.add_argument(
            '--keep-admin',
            action='store_true',
            help='Mantener el usuario administrador (no eliminar usuarios)',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.ERROR(
                    '⚠️  ADVERTENCIA: Esta acción eliminará TODOS los datos de la base de datos.'
                )
            )
            self.stdout.write('Para confirmar, ejecuta el comando con el parámetro --confirm:')
            self.stdout.write('python manage.py reset_database --confirm')
            return

        self.stdout.write(
            self.style.WARNING('🗑️  Iniciando limpieza completa de la base de datos...')
        )

        try:
            with transaction.atomic():
                # Obtener todos los modelos de la aplicación black_invoices
                app_models = apps.get_app_config('black_invoices').get_models()
                
                # Contar registros antes de eliminar
                total_records = 0
                for model in app_models:
                    count = model.objects.count()
                    if count > 0:
                        total_records += count
                        self.stdout.write(f'  📊 {model.__name__}: {count} registros')

                self.stdout.write(f'\n🔢 Total de registros a eliminar: {total_records}')

                if total_records == 0:
                    self.stdout.write(self.style.SUCCESS('✅ La base de datos ya está vacía.'))
                    return

                # Eliminar todos los datos (orden específico para evitar errores de FK)
                deletion_order = [
                    # Primero los detalles
                    DetalleFactura,
                    DetalleNotaEntrega,
                    
                    # Luego las ventas
                    Ventas,
                    
                    # Después los documentos principales
                    Factura,
                    NotaEntrega,
                    
                    # Datos maestros
                    Cliente,
                    Producto,
                    Empleado,
                    
                    # Configuraciones
                    TasaCambio,
                    UnidadMedida,
                    ConfiguracionSistema,
                    
                    # Catálogos básicos
                    NivelAcceso,
                    StatusVentas,
                    TipoFactura,
                ]

                # Agregar modelos que no estén en la lista pero existan en la app
                models_not_in_order = []
                for model in app_models:
                    if model not in deletion_order:
                        models_not_in_order.append(model)
                
                # Agregar los modelos restantes al final
                deletion_order.extend(models_not_in_order)

                # Eliminar datos en orden específico
                deleted_total = 0
                for model in deletion_order:
                    try:
                        count = model.objects.count()
                        if count > 0:
                            deleted = model.objects.all().delete()
                            deleted_count = deleted[0] if deleted[0] else 0
                            deleted_total += deleted_count
                            self.stdout.write(
                                f'  🗑️  {model.__name__}: {deleted_count} registros eliminados'
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  Error eliminando {model.__name__}: {str(e)}')
                        )

                # Resetear secuencias de autoincremento (IDs)
                self.stdout.write('\n🔄 Reseteando secuencias de IDs...')
                self._reset_sequences(app_models)

                # Opcional: No eliminar usuarios admin si se especifica
                if not options['keep_admin']:
                    from django.contrib.auth.models import User, Group, Permission
                    from django.contrib.contenttypes.models import ContentType
                    from django.contrib.sessions.models import Session
                    from django.contrib.admin.models import LogEntry
                    
                    # Limpiar datos de autenticación y admin
                    LogEntry.objects.all().delete()
                    Session.objects.all().delete()
                    User.objects.all().delete()
                    self.stdout.write('  🗑️  Usuarios y sesiones eliminados')

                self.stdout.write(f'\n✅ Base de datos completamente limpia!')
                self.stdout.write(f'📈 Total de registros eliminados: {deleted_total}')
                self.stdout.write('🆔 Todos los IDs han sido reseteados y comenzarán desde 1')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error durante la limpieza: {str(e)}')
            )
            raise CommandError(f'Error: {str(e)}')

    def _reset_sequences(self, models):
        """Resetea las secuencias de autoincremento para SQLite y PostgreSQL"""
        with connection.cursor() as cursor:
            # Detectar tipo de base de datos
            db_vendor = connection.vendor

            if db_vendor == 'sqlite':
                # Para SQLite
                for model in models:
                    table_name = model._meta.db_table
                    try:
                        # Resetear secuencia en SQLite
                        cursor.execute(
                            f"DELETE FROM sqlite_sequence WHERE name='{table_name}'"
                        )
                        self.stdout.write(f'    🔄 Secuencia reseteada: {table_name}')
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'    ⚠️  Error reseteando {table_name}: {str(e)}')
                        )
                        
            elif db_vendor == 'postgresql':
                # Para PostgreSQL
                for model in models:
                    table_name = model._meta.db_table
                    pk_field = model._meta.pk.column
                    try:
                        cursor.execute(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', '{pk_field}'), 1, false)"
                        )
                        self.stdout.write(f'    🔄 Secuencia reseteada: {table_name}')
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'    ⚠️  Error reseteando {table_name}: {str(e)}')
                        )
                        
            elif db_vendor == 'mysql':
                # Para MySQL
                for model in models:
                    table_name = model._meta.db_table
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = 1")
                        self.stdout.write(f'    🔄 Secuencia reseteada: {table_name}')
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'    ⚠️  Error reseteando {table_name}: {str(e)}')
                        )
            else:
                self.stdout.write(
                    self.style.WARNING(f'    ⚠️  Base de datos {db_vendor} no soportada para reset de secuencias')
                )