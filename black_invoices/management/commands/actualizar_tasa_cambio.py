import requests
from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import TasaCambio, ConfiguracionSistema

class Command(BaseCommand):
    help = 'Actualiza la tasa de cambio usando APIs externas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar actualización aunque ya exista tasa para hoy',
        )
        parser.add_argument(
            '--manual',
            type=float,
            help='Establecer tasa manualmente (ejemplo: --manual 36.50)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('💱 Actualizando tasa de cambio...\n')
        
        hoy = date.today()
        config = ConfiguracionSistema.get_config()
        
        # Verificar si ya existe tasa para hoy
        if not options['force']:
            tasa_hoy = TasaCambio.objects.filter(fecha=hoy).first()
            if tasa_hoy:
                self.stdout.write(
                    self.style.WARNING(f'Ya existe tasa para hoy: {tasa_hoy}')
                )
                self.stdout.write('Usa --force para actualizar')
                return
        
        # Tasa manual
        if options['manual']:
            self.actualizar_tasa_manual(hoy, Decimal(str(options['manual'])))
            return
        
        # Verificar si API está activa
        if not config.api_tasa_activa:
            self.stdout.write(
                self.style.WARNING('API de tasa desactivada en configuración')
            )
            return
        
        # Intentar múltiples APIs
        apis = [
            {
                'name': 'ExchangeRate-API',
                'url': 'https://api.exchangerate-api.com/v4/latest/USD',
                'parser': self.parse_exchangerate_api
            },
            {
                'name': 'Fixer.io (Free)',
                'url': 'https://api.fixer.io/latest?base=USD&symbols=VES',
                'parser': self.parse_fixer_api
            },
            {
                'name': 'CurrencyAPI (Free)',
                'url': 'https://api.currencyapi.com/v3/latest?apikey=demo&currencies=VES&base_currency=USD',
                'parser': self.parse_currencyapi
            }
        ]
        
        for api in apis:
            try:
                self.stdout.write(f'🔍 Intentando {api["name"]}...')
                tasa = self.obtener_tasa_desde_api(api['url'], api['parser'])
                
                if tasa:
                    self.actualizar_tasa_automatica(hoy, tasa, api['name'])
                    return
                    
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'❌ Error con {api["name"]}: {str(e)}')
                )
                continue
        
        # Si todas las APIs fallan, usar tasa de emergencia
        self.stdout.write(
            self.style.ERROR('❌ Todas las APIs fallaron')
        )
        self.usar_tasa_emergencia(hoy)
    
    def obtener_tasa_desde_api(self, url, parser_func):
        """Obtiene tasa desde una API específica"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return parser_func(data)
            
        except requests.RequestException as e:
            raise Exception(f"Error de conexión: {str(e)}")
        except Exception as e:
            raise Exception(f"Error al procesar respuesta: {str(e)}")
    
    def parse_exchangerate_api(self, data):
        """Parser para ExchangeRate-API"""
        if 'rates' in data and 'VES' in data['rates']:
            return Decimal(str(data['rates']['VES']))
        return None
    
    def parse_fixer_api(self, data):
        """Parser para Fixer.io"""
        if 'rates' in data and 'VES' in data['rates']:
            return Decimal(str(data['rates']['VES']))
        return None
    
    def parse_currencyapi(self, data):
        """Parser para CurrencyAPI"""
        if 'data' in data and 'VES' in data['data'] and 'value' in data['data']['VES']:
            return Decimal(str(data['data']['VES']['value']))
        return None
    
    def actualizar_tasa_manual(self, fecha, tasa):
        """Actualiza tasa manualmente"""
        self.stdout.write(f'📝 Estableciendo tasa manual: {tasa}')
        self.guardar_tasa(fecha, tasa, 'Manual')
    
    def actualizar_tasa_automatica(self, fecha, tasa, fuente):
        """Actualiza tasa desde API"""
        self.stdout.write(f'✅ Tasa obtenida de {fuente}: {tasa}')
        self.guardar_tasa(fecha, tasa, fuente)
    
    def usar_tasa_emergencia(self, fecha):
        """Usa la última tasa disponible como emergencia"""
        ultima_tasa = TasaCambio.objects.filter(activo=True).first()
        
        if ultima_tasa:
            nueva_tasa = ultima_tasa.tasa_usd_ves
            self.stdout.write(
                self.style.WARNING(f'🚨 Usando tasa de emergencia: {nueva_tasa}')
            )
            self.guardar_tasa(fecha, nueva_tasa, 'Emergencia - última disponible')
        else:
            # Tasa por defecto
            tasa_defecto = Decimal('36.50')
            self.stdout.write(
                self.style.ERROR(f'🚨 Usando tasa por defecto: {tasa_defecto}')
            )
            self.guardar_tasa(fecha, tasa_defecto, 'Por defecto - sin datos')
    
    def guardar_tasa(self, fecha, tasa, fuente):
        """Guarda la tasa en la base de datos"""
        try:
            # Usar get_or_create para manejar la restricción UNIQUE
            tasa_obj, created = TasaCambio.objects.get_or_create(
                fecha=fecha,
                defaults={
                    'tasa_usd_ves': tasa,
                    'fuente': fuente,
                    'activo': True
                }
            )
            
            if not created:
                # Actualizar tasa existente
                tasa_obj.tasa_usd_ves = tasa
                tasa_obj.fuente = fuente
                tasa_obj.activo = True
                tasa_obj.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Tasa actualizada: {tasa_obj}')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Nueva tasa creada: {tasa_obj}')
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error al guardar: {str(e)}')
            )