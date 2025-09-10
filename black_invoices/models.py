from decimal import Decimal
from django.utils import timezone
from django.db import models
from django.core.validators import MinValueValidator, RegexValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


# Create your models here.
class NivelAcceso(models.Model):
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Nivel de Acceso"
        verbose_name_plural = "Niveles de Acceso"

    def __str__(self):
        return self.nombre
    

class Cliente(models.Model):
    TIPO_DOCUMENTO_CHOICES = [
        ('V', 'V - Venezolano'),
        ('E', 'E - Extranjero'),
        ('J', 'J - Jurídico'),
        ('G', 'G - Gubernamental'),
    ]
    
    # Campo separado para tipo de documento
    tipo_documento = models.CharField(
        max_length=1,
        choices=TIPO_DOCUMENTO_CHOICES,
        default='V',
        verbose_name="Tipo de Documento"
    )
    
    # Campo para el número sin el prefijo
    numero_documento = models.CharField(
        max_length=9,
        verbose_name="Número de Documento",
        help_text="Solo números, entre 6 y 9 dígitos"
    )
    
    # Campo calculado para mostrar cédula completa
    cedula = models.CharField(
        max_length=12, 
        unique=True,
        verbose_name="Cédula/RIF",
        editable=False  # No editable directamente
    )
    
    nombre_completo = models.CharField(max_length=100, verbose_name="Nombre Completo")
    
    # Hacer email opcional y no único
    email = models.EmailField(
        max_length=254, 
        blank=True, 
        null=True,
        verbose_name="Correo Electrónico (Opcional)"
    )
    
    telefono = models.CharField(max_length=15, verbose_name="Teléfono")
    direccion = models.CharField(max_length=200, verbose_name="Dirección")
    
    # Campos de auditoría
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Registro"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Actualización"
    )

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre_completo']

    def __str__(self):
        return f"{self.cedula} - {self.nombre_completo}"
    
    def clean(self):
        """Validaciones personalizadas"""
        super().clean()
        
        # Validar número de documento
        if self.numero_documento:
            # Remover espacios y validar que solo tenga números
            self.numero_documento = self.numero_documento.replace(' ', '').replace('-', '')
            
            if not self.numero_documento.isdigit():
                raise ValidationError({'numero_documento': 'El número de documento debe contener solo dígitos'})
            
            # Validar longitud según el tipo
            if self.tipo_documento in ['V', 'E']:
                if len(self.numero_documento) < 6 or len(self.numero_documento) > 8:
                    raise ValidationError({'numero_documento': 'Para cédulas V/E debe tener entre 6 y 8 dígitos'})
            elif self.tipo_documento in ['J', 'G']:
                if len(self.numero_documento) < 8 or len(self.numero_documento) > 9:
                    raise ValidationError({'numero_documento': 'Para RIF J/G debe tener entre 8 y 9 dígitos'})
    
    def save(self, *args, **kwargs):
        # Construir la cédula completa antes de guardar
        if self.tipo_documento and self.numero_documento:
            self.cedula = f"{self.tipo_documento}{self.numero_documento}"
        
        self.full_clean()  # Ejecutar validaciones antes de guardar
        super().save(*args, **kwargs)
    
    @property
    def cedula_formateada(self):
        """Retorna la cédula con formato legible"""
        if self.cedula:
            return self.cedula
        return f"{self.tipo_documento}{self.numero_documento}" if self.tipo_documento and self.numero_documento else ""

class Producto(models.Model):
    # Constantes para validaciones
    PRECIO_MINIMO = 0.01
    PRECIO_MAXIMO = 5000.00
    STOCK_MINIMO = 0
    STOCK_MAXIMO = 100000
    sku = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="SKU/Código",
        help_text="Código único del producto"
    )
    nombre = models.CharField(
        max_length=50,
        verbose_name="Nombre",
        unique=True
    )
    
    descripcion = models.TextField(
        max_length=200,
        verbose_name='Descripción',
        help_text="Describe las características del producto"
    )
    
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio",
        validators=[
            MinValueValidator(PRECIO_MINIMO, message=f"El precio no puede ser menor a ${PRECIO_MINIMO}"),
            MaxValueValidator(PRECIO_MAXIMO, message=f"El precio no puede ser mayor a ${PRECIO_MAXIMO:,.2f}")
        ],
        help_text=f"Precio en dólares (Máximo: ${PRECIO_MAXIMO:,.2f})"
    )
    
    stock = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name="Stock disponible",
        validators=[
            MinValueValidator(Decimal('0'), message="El stock no puede ser negativo"),
            MaxValueValidator(STOCK_MAXIMO, message=f"El stock no puede ser mayor a {STOCK_MAXIMO:,} unidades")
        ],
        help_text=f"Cantidad disponible (Máximo: {STOCK_MAXIMO:,} unidades). Permite hasta 3 decimales."
    )

    activo = models.BooleanField(
        default=True,
        verbose_name="Producto activo"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última modificación"
    )
    precio_compra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio de Compra",
        validators=[
            MinValueValidator(0.01, message="El precio de compra no puede ser menor a $0.01"),
            MaxValueValidator(5000.00, message="El precio de compra no puede ser mayor a $5,000.00")
        ],
        help_text="Precio de compra en dólares",
        default=0.01
    )
    
    unidad_medida = models.ForeignKey(
        'UnidadMedida',
        on_delete=models.PROTECT,
        verbose_name="Unidad de Medida",
        help_text="Unidad en la que se vende este producto",
        null=True,      # Permitir nulos temporalmente
        blank=True      # Permitir vacío en formularios
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
    
    def clean(self):
        """Validaciones personalizadas del modelo"""
        super().clean()
        
        # Validación de precio
        if self.precio is not None:
            if self.precio < self.PRECIO_MINIMO:
                raise ValidationError({
                    'precio': f'El precio no puede ser menor a ${self.PRECIO_MINIMO}'
                })
            elif self.precio > self.PRECIO_MAXIMO:
                raise ValidationError({
                    'precio': f'El precio no puede ser mayor a ${self.PRECIO_MAXIMO:,.2f}'
                })
        
        # Validación de stock
        if self.stock is not None:
            if self.stock < self.STOCK_MINIMO:
                raise ValidationError({
                    'stock': f'El stock no puede ser menor a {self.STOCK_MINIMO}'
                })
            elif self.stock > self.STOCK_MAXIMO:
                raise ValidationError({
                    'stock': f'El stock no puede ser mayor a {self.STOCK_MAXIMO:,} unidades'
                })
    
    def save(self, *args, **kwargs):
        """Ejecutar validaciones antes de guardar"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def stock_available(self):
        """Verifica si hay stock disponible"""
        return self.stock > 0
    
    def is_low_stock(self, threshold=5):
        """Verifica si el stock está bajo"""
        return self.stock <= threshold
    
    def get_stock_status(self):
        """Retorna el estado del stock"""
        if self.stock <= 0:
            return 'sin_stock'
        elif self.stock <= 5:
            return 'stock_bajo'
        elif self.stock <= 20:
            return 'stock_medio'
        else:
            return 'stock_alto'
    
    def get_stock_badge_class(self):
        """Retorna la clase CSS para el badge de stock"""
        status = self.get_stock_status()
        return {
            'sin_stock': 'badge-danger',
            'stock_bajo': 'badge-warning',
            'stock_medio': 'badge-info',
            'stock_alto': 'badge-success'
        }.get(status, 'badge-secondary')
    
    def precio_en_rango_permitido(self):
        """Verifica si el precio está en el rango permitido"""
        return self.PRECIO_MINIMO <= self.precio <= self.PRECIO_MAXIMO
    
    def stock_en_rango_permitido(self):
        """Verifica si el stock está en el rango permitido"""
        return self.STOCK_MINIMO <= self.stock <= self.STOCK_MAXIMO
    
    def get_precio_bolivares(self):
        """Calcula el precio en bolívares usando la tasa actual"""
        from decimal import Decimal
        tasa_actual = TasaCambio.get_tasa_actual()
        if tasa_actual:
            return self.precio * tasa_actual.tasa_usd_ves
        return Decimal('0.00')
    
    def get_precio_formateado(self):
        """Retorna ambos precios formateados"""
        precio_ves = self.get_precio_bolivares()
        return {
            'usd': f"${self.precio:,.2f}",
            'ves': f"{precio_ves:,.2f} Bs",
            'precio_usd': self.precio,
            'precio_ves': precio_ves
        }
    
    @classmethod
    def get_productos_precio_alto(cls):
        """Retorna productos con precio cercano al límite (>$4000)"""
        return cls.objects.filter(precio__gte=4000, activo=True)
    
    @classmethod
    def get_productos_stock_alto(cls):
        """Retorna productos con stock alto (>50000)"""
        return cls.objects.filter(stock__gte=50000, activo=True)
    
    @classmethod
    def get_limites_validacion(cls):
        """Retorna los límites de validación para uso en formularios/templates"""
        return {
            'precio_minimo': cls.PRECIO_MINIMO,
            'precio_maximo': cls.PRECIO_MAXIMO,
            'stock_minimo': cls.STOCK_MINIMO,
            'stock_maximo': cls.STOCK_MAXIMO
        }
    def get_margen_ganancia(self):
        """Calcula el margen de ganancia"""
        if self.precio_compra > 0:
            margen = ((self.precio - self.precio_compra) / self.precio_compra) * 100
            return round(margen, 2)
        return 0

    def get_ganancia_unitaria(self):
        """Calcula la ganancia por unidad"""
        return self.precio - self.precio_compra

    def get_precios_formateados_completos(self):
        """Retorna todos los precios formateados"""
        tasa_actual = TasaCambio.get_tasa_actual()
        if tasa_actual:
            precio_venta_ves = self.precio * tasa_actual.tasa_usd_ves
            precio_compra_ves = self.precio_compra * tasa_actual.tasa_usd_ves
        else:
            precio_venta_ves = 0
            precio_compra_ves = 0
            
        return {
            'venta_usd': f"${self.precio:,.2f}",
            'venta_ves': f"{precio_venta_ves:,.2f} Bs",
            'compra_usd': f"${self.precio_compra:,.2f}",
            'compra_ves': f"{precio_compra_ves:,.2f} Bs",
            'margen': f"{self.get_margen_ganancia():.1f}%",
            'ganancia_usd': f"${self.get_ganancia_unitaria():,.2f}"
        }

    def validar_cantidad_segun_unidad(self, cantidad):
        """Valida si la cantidad es correcta según la unidad de medida"""
        if not self.unidad_medida:
            return False, "El producto no tiene unidad de medida asignada"
            
        if not self.unidad_medida.permite_decimales:
            # Si no permite decimales, verificar que sea entero
            if cantidad != int(cantidad):
                return False, f"La unidad '{self.unidad_medida.nombre}' no permite cantidades decimales"
        
        return True, "OK"
    def get_precio_con_iva(self):
        """Calcula el precio con IVA incluido"""
        config = ConfiguracionSistema.get_config()
        iva = config.calcular_iva(self.precio)
        return self.precio + iva
    
    def get_precios_iva_formateados(self):
        """Retorna precios con y sin IVA en ambas monedas"""
        config = ConfiguracionSistema.get_config()
        tasa_actual = TasaCambio.get_tasa_actual()
        
        # Precios sin IVA
        precio_sin_iva_usd = self.precio
        precio_con_iva_usd = self.get_precio_con_iva()
        
        if tasa_actual:
            precio_sin_iva_ves = precio_sin_iva_usd * tasa_actual.tasa_usd_ves
            precio_con_iva_ves = precio_con_iva_usd * tasa_actual.tasa_usd_ves
        else:
            precio_sin_iva_ves = precio_con_iva_ves = 0
        
        return {
            'sin_iva_usd': f"${precio_sin_iva_usd:,.2f}",
            'sin_iva_ves': f"{precio_sin_iva_ves:,.2f} Bs",
            'con_iva_usd': f"${precio_con_iva_usd:,.2f}",
            'con_iva_ves': f"{precio_con_iva_ves:,.2f} Bs",
            'iva_porcentaje': config.porcentaje_iva
        }
class Empleado(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Usuario')
    nombre = models.CharField(max_length=20, verbose_name= "Nombre")
    apellido = models.CharField(max_length=20, verbose_name='Apellido')
    nivel_acceso = models.ForeignKey(NivelAcceso, on_delete=models.PROTECT)
    fecha_contratacion = models.DateField(auto_now_add=True, verbose_name='Fecha de contratación')
    activo =  models.BooleanField(default=True, verbose_name='Activo')


    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ["apellido", "nombre"]

    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    
    
class Ventas(models.Model):
    empleado = models.ForeignKey(
        'Empleado',
        on_delete=models.PROTECT,
        verbose_name="Empleado"
    )
    factura = models.OneToOneField(
        'Factura',
        on_delete=models.CASCADE,
        verbose_name="Factura",
        null=True,  # NUEVO
        blank=True
    )
    status = models.ForeignKey(
        'StatusVentas',
        on_delete=models.PROTECT,
        verbose_name="Estado de la Venta"
    )
    fecha_venta = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Venta"
    )
    credito = models.BooleanField(default=False, verbose_name="Venta a Crédito")
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Monto Pagado")
    nota_entrega = models.OneToOneField(
        'NotaEntrega',
        on_delete=models.CASCADE,
        verbose_name="Nota de Entrega",
        null=True,
        blank=True
    )
        
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha_venta']

    def __str__(self):
        return f"Venta {self.id} - {self.empleado}"
    

    def procesar_venta(self):
        from django.db import transaction
    
        with transaction.atomic():
            # Descontar stock inmediatamente
            detalles = self.factura.detallefactura_set.all()
            for detalle in detalles:
                if detalle.cantidad > detalle.producto.stock:
                    raise ValueError(f"Stock insuficiente para {detalle.producto.nombre}")
                
                detalle.producto.stock -= detalle.cantidad
                detalle.producto.save(update_fields=['stock'])
            
            # Establecer estado según tipo de venta
            if self.credito:
                if self.monto_pagado <= 0:
                    self.status = StatusVentas.objects.get(nombre="Pendiente")
                else:
                    self.status = StatusVentas.objects.get(
                        nombre="Completada" if self.completada else "Pendiente"
                    )
            else:
                # Contado = pagado completo
                self.status = StatusVentas.objects.get(nombre="Completada")
                self.monto_pagado = self.factura.total_fac
            
            self.save()

    def registrar_pago(self, monto, metodo_pago='efectivo', referencia=None):
        """Registra un pago parcial con validaciones - ACTUALIZADO"""
        from decimal import Decimal
        from django.utils import timezone
        from django.db import transaction
        
        # VALIDACIÓN: Solo ventas a crédito pueden recibir pagos parciales
        if not self.credito:
            raise ValueError("Esta venta es de contado y ya está pagada completamente")
        
        # VALIDACIÓN: No se pueden registrar pagos en ventas canceladas
        if self.status.vent_cancelada:
            raise ValueError("No se pueden registrar pagos en ventas canceladas")
        
        # VALIDACIÓN: Monto debe ser positivo
        if monto <= 0:
            raise ValueError("El monto debe ser mayor a cero")
        
        # VALIDACIÓN: Convertir monto a Decimal para evitar errores de tipo
        if not isinstance(monto, Decimal):
            monto = Decimal(str(monto))
        
        # VALIDACIÓN: No exceder el saldo pendiente - USANDO TOTAL_VENTA
        if monto > self.saldo_pendiente:
            raise ValueError(f"El monto (${monto}) excede el saldo pendiente (${self.saldo_pendiente})")
        
        # VALIDACIÓN: Método de pago válido
        metodos_validos = [choice[0] for choice in PagoVenta.METODOS_PAGO_CHOICES]
        if metodo_pago not in metodos_validos:
            raise ValueError(f"Método de pago no válido. Opciones: {metodos_validos}")
        
        with transaction.atomic():
            # ACTUALIZAR el monto pagado
            self.monto_pagado += monto
            
            # CAMBIAR ESTADO si se completó el pago
            if self.completada and self.credito:
                estado_completado, created = StatusVentas.objects.get_or_create(
                    nombre="Completada",
                    defaults={
                        'vent_espera': False,
                        'vent_cancelada': False
                    }
                )
                self.status = estado_completado
                
            self.save(update_fields=['monto_pagado', 'status'])
            
            # CREAR REGISTRO DE PAGO con método y referencia
            pago = PagoVenta.objects.create(
                venta=self,
                monto=monto,
                metodo_pago=metodo_pago,
                referencia=referencia if referencia else None
            )
        
        return pago
    
    def registrar_pago_con_metodo(self, monto, metodo_pago='efectivo', referencia=''):
        """Registra un pago parcial con método de pago"""
        from decimal import Decimal
        
        if monto <= 0:
            return False
        
        # Convertir monto a Decimal para evitar error de tipo de datos
        if not isinstance(monto, Decimal):
            monto = Decimal(str(monto))
        
        self.monto_pagado += monto
        
        # Cambiar estado si se completó el pago
        if self.completada and self.credito:
            estado_completado = StatusVentas.objects.get(nombre="Completada")
            self.status = estado_completado
            
        self.save(update_fields=['monto_pagado', 'status'])
        
        # Crear registro de pago con método
        PagoVenta.objects.create(
            venta=self,
            monto=monto,
            metodo_pago=metodo_pago,
            referencia=referencia,
            fecha=timezone.now()
        )
        
        return True

# También agregar este método helper para obtener el resumen de pagos
    def resumen_pagos(self):
        """Retorna un resumen de los pagos realizados por método"""
        from django.db.models import Sum
        
        if not self.pagos.exists():
            return {}
        
        resumen = {}
        for metodo_codigo, metodo_nombre in PagoVenta.METODOS_PAGO_CHOICES:
            total_metodo = self.pagos.filter(metodo_pago=metodo_codigo).aggregate(
                total=Sum('monto')
            )['total'] or Decimal('0.00')
            
            if total_metodo > 0:
                resumen[metodo_codigo] = {
                    'nombre': metodo_nombre,
                    'total': total_metodo,
                    'pagos': self.pagos.filter(metodo_pago=metodo_codigo).count()
                }
        
        return resumen

    def cancelar_venta(self):
        """Cancela la venta y restaura el stock - ACTUALIZADO"""
        from django.db import transaction
        
        if self.status.vent_cancelada:
            raise ValueError("Esta venta ya está cancelada")
        
        with transaction.atomic():
            # Restaurar stock según el tipo de documento
            if self.factura:
                detalles = self.factura.detallefactura_set.all()
                for detalle in detalles:
                    detalle.producto.stock += detalle.cantidad
                    detalle.producto.save(update_fields=['stock'])
            elif self.nota_entrega:
                detalles = self.nota_entrega.detalles_nota.all()
                for detalle in detalles:
                    detalle.producto.stock += detalle.cantidad
                    detalle.producto.save(update_fields=['stock'])
            
            # Marcar como cancelada
            estado_cancelado, created = StatusVentas.objects.get_or_create(
                vent_cancelada=True,
                defaults={
                    'nombre': 'Cancelada',
                    'vent_espera': False
                }
            )
            self.status = estado_cancelado
            self.save()
    @property
    def saldo_pendiente(self):
        """Calcula el saldo pendiente de pago para ventas a crédito"""
        if not self.credito:
            return Decimal('0.00')
        return max(Decimal('0.00'), self.total_venta - self.monto_pagado)
    
    @property
    def completada(self):
        """Verifica si la venta está completamente pagada"""
        if not self.credito:
            return True  # Las ventas de contado están completadas por definición
        return self.monto_pagado >= self.total_venta
    @property
    def documento_fiscal(self):
        """Retorna el documento fiscal asociado (Factura o Nota)"""
        return self.factura or self.nota_entrega
    
    @property
    def tipo_documento(self):
        """Retorna el tipo de documento"""
        if self.factura:
            return "Factura"
        elif self.nota_entrega:
            return "Nota de Entrega"
        return "Sin Documento"
    @property
    def numero_documento(self):
        """Retorna el número del documento"""
        if self.factura:
            return self.factura.numero_factura
        elif self.nota_entrega:
            return self.nota_entrega.numero_nota
        return "N/A"
    @property
    def total_venta(self):
        """Total de la venta desde el documento fiscal"""
        if self.factura:
            return self.factura.total_fac
        elif self.nota_entrega:
            return self.nota_entrega.total
        return Decimal('0.00')
    

class PagoVenta(models.Model):
    METODOS_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta de Débito/Crédito'),
        ('pago_movil', 'Pago Móvil'),
        ('transferencia', 'Transferencia Bancaria'),
        ('otro', 'Otro')
    ]
    
    venta = models.ForeignKey(Ventas, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto Pagado")
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO_CHOICES,
        default='efectivo',
        verbose_name="Método de Pago"
    )
    referencia = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Referencia/Número",
        help_text="Número de referencia, confirmación o voucher"
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Pago")
    
    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"Pago #{self.id} de Venta #{self.venta.id} - {self.get_metodo_pago_display()}"
class StatusVentas(models.Model):
    
    nombre = models.CharField(  # Añadimos un nombre descriptivo
        max_length=50,
        verbose_name="Nombre del Estado"
    )
    vent_cancelada = models.BooleanField(
        default=False,
        verbose_name="Venta Cancelada"
    )
    vent_espera = models.BooleanField(
        default=False,
        verbose_name="Venta en Espera"
    )
    
    class Meta:
        verbose_name = "Estado de Venta"
        verbose_name_plural = "Estados de Venta"
        
    def __str__(self):
        if self.vent_cancelada:
            return "Cancelada"
        elif self.vent_espera:
            return "En Espera"
        return "Completada"
    
    def get_estado(self):
        """Retorna el estado actual de la venta"""
        if self.vent_cancelada:
            return "CANCELADA"
        elif self.vent_espera:
            return "EN ESPERA"
        return "COMPLETADA"
    
    
class Factura(models.Model):
    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
        ('credito', 'Crédito'),
        ('otro', 'Otro')
    ]
    
    fecha_fac = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Facturación"
    )
    
    total_fac = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Total Factura",
        default=0
    )
    
    metodo_pag = models.CharField(  # Corregido: CharField con choices
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        default='efectivo',
        verbose_name="Método de Pago"
    )
    
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.CASCADE,  # Eliminación en cascada
        verbose_name="Cliente",
        related_name='facturas'  # Permite cliente.facturas.all()
    )
    
    empleado = models.ForeignKey(
        'Empleado',
        on_delete=models.PROTECT,
        verbose_name="Empleado",
        related_name='facturas_generadas'
    )
    
# Campo eliminado - ahora es una propiedad que retorna total_fac
    numero_factura = models.PositiveIntegerField(
        verbose_name="Número de Factura",
        unique=True,
        null=True,  # Temporal para migración
        blank=True
    )
    
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Subtotal (sin IVA)",
        default=0
    )
    
    iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="IVA",
        default=0
    )

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_fac']  # Ordena por fecha descendente
    
    def __str__(self):
        return f"Factura #{self.id} - Cliente: {self.cliente.nombre}"
    
    @property
    def total_venta(self):
        """Propiedad para mantener compatibilidad - retorna total_fac"""
        return self.total_fac
    
    def calcular_total(self):
        """
        Calcula el total de la factura basado en sus detalles
        """
        total = self.detallefactura_set.aggregate(
            total=models.Sum(models.F('cantidad') * models.F('producto__precio'))
        )['total'] or 0
        
        self.total_fac = total
        self.save()
        return total
    
    def get_detalles(self):
        """
        Retorna todos los detalles de la factura
        """
        return self.detallefactura_set.all()
    
    def agregar_detalle(self, producto, cantidad):
        """
        Agrega un nuevo detalle a la factura
        """
        from decimal import Decimal
        
        detalle = self.detallefactura_set.create(
            producto=producto,
            cantidad=cantidad,
            sub_total=Decimal(str(producto.precio)) * Decimal(str(cantidad))
        )
        self.calcular_total()
        return detalle
    def save(self, *args, **kwargs):
        # Asignar número de factura si no tiene
        if not self.numero_factura:
            config = ConfiguracionSistema.get_config()
            self.numero_factura = config.get_siguiente_numero_factura()
        
        super().save(*args, **kwargs)
    
    def calcular_total_mejorado(self):
        """
        Calcula totales con IVA incluido
        """
        config = ConfiguracionSistema.get_config()
        
        # Calcular subtotal (sin IVA)
        subtotal = self.detallefactura_set.aggregate(
            total=models.Sum(models.F('cantidad') * models.F('producto__precio'))
        )['total'] or 0
        
        # Calcular IVA
        iva = config.calcular_iva(subtotal)
        
        # Calcular total
        total = subtotal + iva
        
        # Actualizar campos
        self.subtotal = subtotal
        self.iva = iva
        self.total_fac = total
        
        self.save(update_fields=['subtotal', 'iva', 'total_fac'])
        
        return {
            'subtotal': subtotal,
            'iva': iva,
            'total': total
        }
    
    def get_totales_formateados(self):
        """Retorna totales en USD y VES formateados"""
        tasa_actual = TasaCambio.get_tasa_actual()
        
        if tasa_actual:
            subtotal_ves = self.subtotal * tasa_actual.tasa_usd_ves
            iva_ves = self.iva * tasa_actual.tasa_usd_ves
            total_ves = self.total_fac * tasa_actual.tasa_usd_ves
        else:
            subtotal_ves = iva_ves = total_ves = 0
        
        return {
            'subtotal_usd': f"${self.subtotal:,.2f}",
            'subtotal_ves': f"{subtotal_ves:,.2f} Bs",
            'iva_usd': f"${self.iva:,.2f}",
            'iva_ves': f"{iva_ves:,.2f} Bs",
            'total_usd': f"${self.total_fac:,.2f}",
            'total_ves': f"{total_ves:,.2f} Bs",
            'tasa_cambio': tasa_actual.tasa_usd_ves if tasa_actual else 1
        }
    
class DetalleFactura(models.Model):
    factura = models.ForeignKey(
        'Factura',
        on_delete=models.CASCADE,
        verbose_name="Factura"
    )
    tipo_factura = models.ForeignKey(
        'TipoFactura',
        on_delete=models.PROTECT,
        verbose_name="Tipo de Factura"
    )
    producto = models.ForeignKey(
        'Producto',
        on_delete=models.PROTECT,
        verbose_name="Producto"
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Cantidad",
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    sub_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Sub-Total",
        editable=False  # Se calcula automáticamente
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )

    class Meta:
        verbose_name = "Detalle de Factura"
        verbose_name_plural = "Detalles de Factura"
        ordering = ['-factura', 'producto']

    def __str__(self):
        return f"Detalle #{self.id} - Factura #{self.factura.id}"

    def save(self, *args, **kwargs):
        # Calcular subtotal de la línea
        self.sub_total = self.cantidad * self.producto.precio
        super().save(*args, **kwargs)
        
        # Actualizar totales de la factura con IVA
        self.factura.calcular_total_mejorado()
    

    def validar_stock(self):
        """Valida si hay suficiente stock"""
        return self.producto.stock >= self.cantidad

    def calcular_subtotal(self):
        """Calcula el subtotal del detalle"""
        return self.cantidad * self.producto.precio

    def validar_stock(self):
        """Valida si hay suficiente stock"""
        return self.producto.stock >= self.cantidad


class TipoFactura(models.Model):
    PLAZO_CHOICES = [
        (30, '30 días'),
        (60, '60 días'),
        (90, '90 días')
    ]

    credito_fac = models.BooleanField(
        default=False,
        verbose_name="Factura a Crédito"
    )
    contado_fac = models.BooleanField(
        default=True,
        verbose_name="Factura de Contado"
    )
    plazo_credito = models.IntegerField(
        choices=PLAZO_CHOICES,
        null=True,
        blank=True,
        verbose_name="Plazo de Crédito"
    )

    class Meta:
        verbose_name = "Tipo de Factura"
        verbose_name_plural = "Tipos de Factura"

    def __str__(self):
        if self.credito_fac:
            return f"Crédito - {self.get_plazo_credito_display()}"
        return "Contado"

class UnidadMedida(models.Model):
    """
    Modelo para las unidades de medida de los productos
    (Kg, gramos, metros, cm, unidades, etc.)
    """
    nombre = models.CharField(
        max_length=30,
        verbose_name="Nombre",
        unique=True,
        help_text="Ejemplo: Kilogramos, Metros, Unidades"
    )
    
    abreviatura = models.CharField(
        max_length=10,
        verbose_name="Abreviatura",
        unique=True,
        help_text="Ejemplo: kg, m, un, cm, g"
    )
    
    descripcion = models.TextField(
        max_length=200,
        verbose_name="Descripción",
        blank=True,
        help_text="Descripción detallada de la unidad de medida"
    )
    
    permite_decimales = models.BooleanField(
        default=True,
        verbose_name="Permite Decimales",
        help_text="Si se pueden vender cantidades decimales (ej: 2.5 kg)"
    )
    
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"
    
    def clean(self):
        """Validaciones personalizadas"""
        super().clean()
        
        # Convertir abreviatura a minúsculas
        if self.abreviatura:
            self.abreviatura = self.abreviatura.lower()
        
        # Validar que no existan espacios en abreviatura
        if self.abreviatura and ' ' in self.abreviatura:
            raise ValidationError({
                'abreviatura': 'La abreviatura no puede contener espacios'
            })

class TasaCambio(models.Model):
    """
    Modelo para manejar las tasas de cambio USD/VES
    """
    fecha = models.DateField(
        verbose_name="Fecha",
        unique=True
    )
    
    tasa_usd_ves = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name="Tasa USD -> VES",
        help_text="Cuántos bolívares equivale 1 dólar"
    )
    
    fuente = models.CharField(
        max_length=50,
        verbose_name="Fuente",
        default="BCV",
        help_text="Fuente de la tasa (BCV, Manual, API)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )

    class Meta:
        verbose_name = "Tasa de Cambio"
        verbose_name_plural = "Tasas de Cambio"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.fecha}: 1 USD = {self.tasa_usd_ves:,.2f} VES"
    
    @classmethod
    def get_tasa_actual(cls):
        """Obtiene la tasa de cambio más reciente activa"""
        return cls.objects.filter(activo=True).first()
    
    @classmethod
    def get_tasa_fecha(cls, fecha):
        """Obtiene la tasa de cambio para una fecha específica"""
        return cls.objects.filter(fecha=fecha, activo=True).first()
    
    def save(self, *args, **kwargs):
        """Al guardar una tasa activa, desactivar las demás"""
        if self.activo:
            # Desactivar todas las demás tasas
            TasaCambio.objects.filter(activo=True).update(activo=False)
        super().save(*args, **kwargs)

class ConfiguracionSistema(models.Model):
    """
    Configuración general del sistema (IVA, empresa, etc.)
    """
    
    # Información de la empresa
    nombre_empresa = models.CharField(
        max_length=100,
        verbose_name="Nombre de la Empresa",
        default="Corporación Agrícola Doña Clara"
    )
    
    rif_empresa = models.CharField(
        max_length=20,
        verbose_name="RIF de la Empresa",
        default='J-40723051-4',
        help_text="Ejemplo: J-12345678-9"
    )
    
    direccion_empresa = models.TextField(
        verbose_name="Dirección de la Empresa",
        max_length=300
    )
    
    telefono_empresa = models.CharField(
        max_length=60,
        verbose_name="Teléfono"
    )
    
    # Configuración de IVA
    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Porcentaje de IVA",
        default=16.00,
        help_text="Porcentaje de IVA aplicable (16% por defecto)"
    )
    
    aplicar_iva = models.BooleanField(
        default=True,
        verbose_name="Aplicar IVA",
        help_text="Si se debe aplicar IVA a las ventas"
    )
    
    # Numeración de documentos
    numero_factura_actual = models.PositiveIntegerField(
        default=1,
        verbose_name="Número de Factura Actual",
        help_text="Próximo número de factura a generar"
    )
    
    numero_nota_entrega_actual = models.PositiveIntegerField(
        default=1,
        verbose_name="Número de Nota de Entrega Actual",
        help_text="Próximo número de nota de entrega a generar"
    )
    
    # API de tasa de cambio
    api_tasa_activa = models.BooleanField(
        default=True,
        verbose_name="API de Tasa Activa",
        help_text="Si debe actualizarse automáticamente la tasa de cambio"
    )
    
    api_tasa_url = models.URLField(
        default="https://api.exchangerate-api.com/v4/latest/USD",
        verbose_name="URL de API de Tasa",
        help_text="URL para obtener la tasa de cambio"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )

    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuración del Sistema"

    def __str__(self):
        return f"Configuración - {self.nombre_empresa}"
    
    @classmethod
    def get_config(cls):
        """Obtiene la configuración actual (singleton)"""
        config, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'nombre_empresa': 'CORPORACION AGRICOLA DOÑA CLARA, C.A.',
                'rif_empresa': 'J-40723051-4',
                'direccion_empresa': 'Vda. 18 Casa Nro 48 Urb. Francisco de Miranda Guanare Edo. Portuguesa',
                'telefono_empresa': '0424-5439427 / 0424-5874882 / 0257-2532558',
            }
        )
        return config
    
    def calcular_iva(self, monto_base):
        """Calcula el IVA de un monto base"""
        if self.aplicar_iva:
            return (monto_base * self.porcentaje_iva) / 100
        return 0
    
    def calcular_total_con_iva(self, monto_base):
        """Calcula el total incluyendo IVA"""
        iva = self.calcular_iva(monto_base)
        return monto_base + iva
    
    def get_siguiente_numero_factura(self):
        """Obtiene y actualiza el siguiente número de factura"""
        numero = self.numero_factura_actual
        self.numero_factura_actual += 1
        self.save(update_fields=['numero_factura_actual'])
        return numero
    
    def get_siguiente_numero_nota_entrega(self):
        """Obtiene y actualiza el siguiente número de nota de entrega"""
        numero = self.numero_nota_entrega_actual
        self.numero_nota_entrega_actual += 1
        self.save(update_fields=['numero_nota_entrega_actual'])
        return numero

class NotaEntrega(models.Model):
    """
    Modelo para notas de entrega (ventas a crédito)
    """
    numero_nota = models.PositiveIntegerField(
        verbose_name="Número de Nota",
        unique=True
    )
    
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.CASCADE,
        verbose_name="Cliente",
        related_name='notas_entrega'
    )
    
    empleado = models.ForeignKey(
        'Empleado',
        on_delete=models.PROTECT,
        verbose_name="Empleado",
        related_name='notas_entrega_generadas'
    )
    
    fecha_nota = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Nota"
    )
    
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Subtotal (sin IVA)",
        default=0
    )
    
    iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="IVA",
        default=0
    )
    
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Total con IVA",
        default=0
    )
    
    monto_pagado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Monto Pagado",
        default=0
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones"
    )
    
    convertida_a_factura = models.BooleanField(
        default=False,
        verbose_name="Convertida a Factura"
    )
    
    factura_generada = models.OneToOneField(
        'Factura',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Factura Generada",
        related_name='nota_entrega_origen'
    )

    class Meta:
        verbose_name = "Nota de Entrega"
        verbose_name_plural = "Notas de Entrega"
        ordering = ['-fecha_nota']

    def __str__(self):
        return f"Nota #{self.numero_nota} - {self.cliente.nombre}"
    
    @property
    def saldo_pendiente(self):
        """Calcula el saldo pendiente de pago"""
        return self.total - self.monto_pagado
    
    @property
    def esta_pagada(self):
        """Verifica si la nota está completamente pagada"""
        return self.monto_pagado >= self.total
    
    def calcular_totales(self):
        """Calcula subtotal, IVA y total basado en los detalles"""
        config = ConfiguracionSistema.get_config()
        
        # Calcular subtotal
        self.subtotal = self.detalles_nota.aggregate(
            total=models.Sum(models.F('cantidad') * models.F('precio_unitario'))
        )['total'] or 0
        
        # Calcular IVA
        self.iva = config.calcular_iva(self.subtotal)
        
        # Calcular total
        self.total = self.subtotal + self.iva
        
        self.save(update_fields=['subtotal', 'iva', 'total'])
        return {'subtotal': self.subtotal, 'iva': self.iva, 'total': self.total}
    def convertir_a_factura(self):
        from django.db import transaction
        """Convierte la nota de entrega a factura fiscal"""
        if self.convertida_a_factura:
            raise ValueError("Esta nota ya fue convertida a factura")
        
        with transaction.atomic():
            # Crear factura
            factura = Factura.objects.create(
                cliente=self.cliente,
                empleado=self.empleado,
                metodo_pag='credito',
                subtotal=self.subtotal,
                iva=self.iva,
                total_fac=self.total
            )
            
            # Copiar detalles
            for detalle_nota in self.detalles_nota.all():
                DetalleFactura.objects.create(
                    factura=factura,
                    producto=detalle_nota.producto,
                    cantidad=detalle_nota.cantidad,
                    tipo_factura=TipoFactura.objects.get(credito_fac=True),
                    sub_total=detalle_nota.subtotal_linea
                )
            
            # Marcar como convertida
            self.convertida_a_factura = True
            self.factura_generada = factura
            self.save()
            
            # Actualizar venta
            venta = self.ventas  # relación inversa
            venta.factura = factura
            venta.nota_entrega = None
            venta.save()
        
            return factura
    # En models.py - Agregar al modelo NotaEntrega
    def get_totales_formateados(self):
        """Retorna totales en USD y VES formateados (similar a Factura)"""
        tasa_actual = TasaCambio.get_tasa_actual()
        
        if tasa_actual:
            subtotal_ves = self.subtotal * tasa_actual.tasa_usd_ves
            iva_ves = self.iva * tasa_actual.tasa_usd_ves
            total_ves = self.total * tasa_actual.tasa_usd_ves
        else:
            subtotal_ves = iva_ves = total_ves = 0
        
        return {
            'subtotal_usd': f"${self.subtotal:,.2f}",
            'subtotal_ves': f"{subtotal_ves:,.2f} Bs",
            'iva_usd': f"${self.iva:,.2f}",
            'iva_ves': f"{iva_ves:,.2f} Bs",
            'total_usd': f"${self.total:,.2f}",
            'total_ves': f"{total_ves:,.2f} Bs",
            'tasa_cambio': tasa_actual.tasa_usd_ves if tasa_actual else 1
    }
    def convertir_a_factura(self):
        """Convierte la nota de entrega a factura fiscal"""
        from django.db import transaction
        
        if self.convertida_a_factura:
            raise ValueError("Esta nota ya fue convertida a factura")
        
        with transaction.atomic():
            # Crear factura
            factura = Factura.objects.create(
                cliente=self.cliente,
                empleado=self.empleado,
                metodo_pag='credito',
                subtotal=self.subtotal,
                iva=self.iva,
                total_fac=self.total
            )
            
            # Copiar detalles
            tipo_factura, created = TipoFactura.objects.get_or_create(
                credito_fac=True,
                contado_fac=False,
                defaults={'plazo_credito': 30}
            )
            
            for detalle_nota in self.detalles_nota.all():
                DetalleFactura.objects.create(
                    factura=factura,
                    producto=detalle_nota.producto,
                    cantidad=detalle_nota.cantidad,
                    tipo_factura=tipo_factura,
                    sub_total=detalle_nota.subtotal_linea
                )
            
            # Marcar como convertida
            self.convertida_a_factura = True
            self.factura_generada = factura
            self.save(update_fields=['convertida_a_factura', 'factura_generada'])
            
            # Actualizar venta
            venta = self.ventas  # relación inversa OneToOne
            venta.factura = factura
            venta.nota_entrega = None
            venta.save(update_fields=['factura', 'nota_entrega'])
            
            return factura
class DetalleNotaEntrega(models.Model):
    """
    Detalles de una nota de entrega
    """
    nota_entrega = models.ForeignKey(
        'NotaEntrega',
        on_delete=models.CASCADE,
        verbose_name="Nota de Entrega",
        related_name='detalles_nota'
    )
    
    producto = models.ForeignKey(
        'Producto',
        on_delete=models.PROTECT,
        verbose_name="Producto"
    )
    
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Cantidad",
        validators=[MinValueValidator(0.001)]
    )
    
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Unitario",
        validators=[MinValueValidator(0.01)]
    )
    
    subtotal_linea = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Subtotal",
        editable=False
    )

    class Meta:
        verbose_name = "Detalle de Nota de Entrega"
        verbose_name_plural = "Detalles de Nota de Entrega"
        ordering = ['producto__nombre']

    def __str__(self):
        unidad = self.producto.unidad_medida.abreviatura if self.producto.unidad_medida else "un"
        return f"{self.producto.nombre} - {self.cantidad} {unidad}"
    
    def save(self, *args, **kwargs):
        # Calcular subtotal de la línea
        self.subtotal_linea = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
        
        # Actualizar totales de la nota
        self.nota_entrega.calcular_totales()

