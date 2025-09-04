from decimal import Decimal
from django.utils import timezone
from django.db import models
from django.core.validators import MinValueValidator, RegexValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


# Create your models here.
class NivelAcceso(models.Model):
    nombre = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Nivel de Acceso"
        verbose_name_plural = "Niveles de Acceso"

    def __str__(self):
        return self.nombre
    

class Cliente(models.Model):
    # Validador para cédula venezolana (V o E seguido de 6-8 dígitos)
    cedula_validator = RegexValidator(
        regex=r'^[VE]-?\d{6,8}$',
        message='La cédula debe tener el formato V12345678 o E12345678'
    )
    
    cedula = models.CharField(
        max_length=12, 
        unique=True,
        validators=[cedula_validator],
        verbose_name="Cédula",
        help_text="Formato: V12345678 o E12345678"
    )
    nombre = models.CharField(max_length=20, verbose_name="Nombre")
    apellido = models.CharField(max_length=20, verbose_name='Apellido')
    
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
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.cedula} - {self.nombre} {self.apellido}"
    
    def clean(self):
        """Validaciones personalizadas"""
        super().clean()
        
        # Normalizar cédula (remover guiones y convertir a mayúsculas)
        if self.cedula:
            self.cedula = self.cedula.replace('-', '').upper()
            
            # Validar que tenga el formato correcto después de normalizar
            if not self.cedula.startswith(('V', 'E')):
                raise ValidationError({'cedula': 'La cédula debe comenzar con V o E'})
            
            # Validar que después de V o E solo haya números
            numero_parte = self.cedula[1:]
            if not numero_parte.isdigit():
                raise ValidationError({'cedula': 'Después de V o E solo debe haber números'})
            
            # Validar longitud de la parte numérica
            if len(numero_parte) < 6 or len(numero_parte) > 8:
                raise ValidationError({'cedula': 'La cédula debe tener entre 6 y 8 dígitos después de V o E'})
    
    def save(self, *args, **kwargs):
        self.full_clean()  # Ejecutar validaciones antes de guardar
        super().save(*args, **kwargs)
    
    @property
    def nombre_completo(self):
        """Retorna el nombre completo del cliente"""
        return f"{self.nombre} {self.apellido}"
    
    @property
    def cedula_formateada(self):
        """Retorna la cédula con formato legible"""
        if self.cedula and len(self.cedula) > 1:
            return f"{self.cedula[0]}-{self.cedula[1:]}"
        return self.cedula

class Producto(models.Model):
    # Constantes para validaciones
    PRECIO_MINIMO = 0.01
    PRECIO_MAXIMO = 5000.00
    STOCK_MINIMO = 0
    STOCK_MAXIMO = 100000

    nombre = models.CharField(
        max_length=20,
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
    
    stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Stock disponible",
        validators=[
            MaxValueValidator(STOCK_MAXIMO, message=f"El stock no puede ser mayor a {STOCK_MAXIMO:,} unidades")
        ],
        help_text=f"Cantidad disponible (Máximo: {STOCK_MAXIMO:,} unidades)"
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
        if not self.unidad_medida.permite_decimales:
            # Si no permite decimales, verificar que sea entero
            if cantidad != int(cantidad):
                return False, f"La unidad '{self.unidad_medida.nombre}' no permite cantidades decimales"
        
        return True, "OK"
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
    
    def get_comisiones_mes(self, mes, anio):
        """Calcular comisiones solo de ventas completadas"""
        from decimal import Decimal
        
        total = Decimal('0.00')
        # Obtener ventas del mes donde el empleado fue vendedor
        ventas = Ventas.objects.filter(
            empleado=self,
            factura__fecha_fac__month=mes,
            factura__fecha_fac__year=anio
        ).exclude(
            status__vent_cancelada=True
        )
        
        for venta in ventas:
            # Solo calcular comisión si la venta está completada
            completada = False
            if hasattr(venta, 'completada'):
                completada = venta.completada
            else:
                # Verificar manualmente si la venta está completada
                completada = not venta.credito or venta.monto_pagado >= venta.factura.total_fac
            
            if completada:
                # Buscar el porcentaje en la tabla de rangos de comisión
                total_factura = venta.factura.total_fac
                rango_comision = ConsultaComision.objects.filter(
                    rango_inferior__lte=total_factura,
                    rango_superior__gte=total_factura
                ).first()
                
                if rango_comision:
                    # Calcular comisión basada en el monto de la venta
                    comision = total_factura * rango_comision.porcentaje / Decimal('100.00')
                    total += comision
        
        return total
class ConsultaComision(models.Model):
    rango_inferior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Rango Inferior"
    )
    rango_superior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Rango Superior"
    )
    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Porcentaje de Comisión"
    )

    class Meta:
        verbose_name = "Rango de Comisión"
        verbose_name_plural = "Rangos de Comisiones"
        ordering = ['rango_inferior']

    def __str__(self):
        return f"{self.porcentaje}% para ventas entre ${self.rango_inferior} y ${self.rango_superior}"
    
    def calcular_comision(self, monto_venta):
        """Calcula la comisión para un monto de venta"""
        if self.rango_inferior <= monto_venta <= self.rango_superior:
            return (monto_venta * self.porcentaje) / 100
        return 0
    
class Comision(models.Model):
    empleado = models.ForeignKey(
        'Empleado',
        on_delete=models.PROTECT,
        verbose_name="Empleado"
    )
    monto_venta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monto de venta"
    )
    fecha_comision = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Comisión"
    )
    venta = models.OneToOneField(
        'Ventas',
        on_delete=models.PROTECT,
        verbose_name="Venta Asociada"
    )
    total_comision = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Total de Comisión",
        editable=False  # No se puede editar manualmente
    )
    

    class Meta:
        verbose_name = "Comisión"
        verbose_name_plural = "Comisiones"
        ordering = ['-fecha_comision']  # Ordenar por fecha descendente (más reciente primero)

    def __str__(self):
        return f"Comisión de {self.empleado} - ${self.total_comision}"

    def save(self, *args, **kwargs):
        """
        Sobrescribimos el método save para calcular automáticamente 
        la comisión antes de guardar
        """
        if not self.total_comision:
        # Obtenemos el total de la factura en lugar del total_venta de la venta
            monto_venta = self.venta.factura.total_venta
            
            rango = ConsultaComision.objects.filter(
                rango_inferior__lte=monto_venta,
                rango_superior__gte=monto_venta
            ).first()
            
            if rango:
                self.total_comision = rango.calcular_comision(monto_venta)
            else:
                self.total_comision = 0

        super().save(*args, **kwargs)

    def get_mes_actual(self):
        """
        Obtiene el total de comisiones del mes actual para este empleado
        """
        mes_actual = self.fecha_comision.month
        año_actual = self.fecha_comision.year
        return Comision.objects.filter(
            empleado=self.empleado,
            fecha_comision__month=mes_actual,
            fecha_comision__year=año_actual
        ).aggregate(
            total=models.Sum('total_comision')
        )['total'] or 0
    
    
class Ventas(models.Model):
    empleado = models.ForeignKey(
        'Empleado',
        on_delete=models.PROTECT,
        verbose_name="Empleado"
    )
    factura = models.OneToOneField(
        'Factura',
        on_delete=models.PROTECT,
        verbose_name="Factura"
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
    
    # NUEVOS CAMPOS PARA AUTORIZACIÓN
    requiere_autorizacion = models.BooleanField(
        default=True, 
        verbose_name="Requiere Autorización"
    )
    autorizada = models.BooleanField(
        default=False, 
        verbose_name="Venta Autorizada"
    )
    autorizada_por = models.ForeignKey(
        'Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventas_autorizadas',
        verbose_name="Autorizada por"
    )
    fecha_autorizacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Autorización"
    )
    comentarios_autorizacion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Comentarios de Autorización"
    )
    requiere_autorizacion = models.BooleanField(default=True, verbose_name="Requiere Autorización")
    autorizada = models.BooleanField(default=False, verbose_name="Venta Autorizada")
    autorizada_por = models.ForeignKey('Empleado', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_autorizadas', verbose_name="Autorizada por")
    fecha_autorizacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Autorización")
    comentarios_autorizacion = models.TextField(blank=True, null=True, verbose_name="Comentarios de Autorización")
    
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha_venta']

    def __str__(self):
        return f"Venta {self.id} - {self.empleado}"

    def registrar_pago(self, monto, metodo_pago='efectivo', referencia_pago=None):
        """Registra un pago parcial con validaciones de autorización"""
        from decimal import Decimal
        from django.utils import timezone
        
        # VALIDACIÓN: Solo ventas autorizadas pueden recibir pagos
        if not self.autorizada:
            raise ValueError("No se pueden registrar pagos en ventas no autorizadas")
        
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
        
        # VALIDACIÓN: No exceder el saldo pendiente
        if monto > self.saldo_pendiente:
            raise ValueError(f"El monto (${monto}) excede el saldo pendiente (${self.saldo_pendiente})")
        
        # VALIDACIÓN: Método de pago válido
        metodos_validos = [choice[0] for choice in PagoVenta.METODOS_PAGO_CHOICES]
        if metodo_pago not in metodos_validos:
            raise ValueError(f"Método de pago no válido. Opciones: {metodos_validos}")
        
        # ACTUALIZAR el monto pagado
        self.monto_pagado += monto
        
        # CAMBIAR ESTADO si se completó el pago
        if self.completada and self.credito:
            estado_completado = StatusVentas.objects.get(nombre="Completada")
            self.status = estado_completado
            
        self.save(update_fields=['monto_pagado', 'status'])
        
        # CREAR REGISTRO DE PAGO con método y referencia
        pago = PagoVenta.objects.create(
            venta=self,
            monto=monto,
            metodo_pago=metodo_pago,
            referencia_pago=referencia_pago if referencia_pago else None
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

    def autorizar_venta(self, empleado_autorizador, comentarios=""):
        """Autoriza la venta, descuenta stock y cambia su estado"""
        from django.utils import timezone
        
        if empleado_autorizador.nivel_acceso.nombre not in ['Administrador', 'Supervisor']:
            raise ValueError("Solo administradores o supervisores pueden autorizar ventas")
        
        if self.autorizada:
            raise ValueError("Esta venta ya está autorizada")
        
        # DESCONTAR STOCK AL AUTORIZAR
        detalles = self.factura.detallefactura_set.all()
        for detalle in detalles:
            # Verificar stock nuevamente al momento de autorizar
            if detalle.cantidad > detalle.producto.stock:
                raise ValueError(f"Stock insuficiente para {detalle.producto.nombre}. "
                            f"Disponible: {detalle.producto.stock}, Requerido: {detalle.cantidad}")
            
            # Descontar stock
            detalle.producto.stock -= detalle.cantidad
            detalle.producto.save(update_fields=['stock'])
        
        # Marcar como autorizada
        self.autorizada = True
        self.autorizada_por = empleado_autorizador
        self.fecha_autorizacion = timezone.now()
        self.comentarios_autorizacion = comentarios
        
        # Cambiar estado según el tipo de venta
        if self.credito:
            # Si es crédito y no tiene pagos, va a pendiente
            if self.monto_pagado <= 0:
                estado_nuevo = StatusVentas.objects.get(nombre="Pendiente")
            else:
                # Si ya tiene pagos, verificar si está completada
                estado_nuevo = StatusVentas.objects.get(
                    nombre="Completada" if self.completada else "Pendiente"
                )
        else:
            # Si es contado, va directo a completada y se marca como pagada
            estado_nuevo = StatusVentas.objects.get(nombre="Completada")
            self.monto_pagado = self.factura.total_fac
        
        self.status = estado_nuevo
        self.save()
        
        return True
        
    def rechazar_venta(self, empleado_autorizador, comentarios=""):
        """Rechaza la venta (no se descuenta stock porque nunca se descontó)"""
        from django.utils import timezone
        
        if empleado_autorizador.nivel_acceso.nombre not in ['Administrador', 'Supervisor']:
            raise ValueError("Solo administradores o supervisores pueden rechazar ventas")
        
        if self.autorizada:
            raise ValueError("No se puede rechazar una venta ya autorizada")
        
        # NO necesitamos restaurar stock porque nunca se descontó
        # Solo marcamos como rechazada
        
        self.autorizada = False
        self.autorizada_por = empleado_autorizador
        self.fecha_autorizacion = timezone.now()
        self.comentarios_autorizacion = f"RECHAZADA: {comentarios}"
        
        # Cambiar a estado cancelada
        estado_cancelado = StatusVentas.objects.get(vent_cancelada=True)
        self.status = estado_cancelado
        self.save()
    
        return True

    def cancelar_venta_autorizada(self, empleado_cancelador, comentarios=""):
        """Cancela una venta YA AUTORIZADA y restaura el stock"""
        from django.utils import timezone
        
        if empleado_cancelador.nivel_acceso.nombre not in ['Administrador', 'Supervisor']:
            raise ValueError("Solo administradores o supervisores pueden cancelar ventas autorizadas")
        
        if not self.autorizada:
            # Si no está autorizada, usar rechazar_venta en su lugar
            return self.rechazar_venta(empleado_cancelador, comentarios)
        
        if self.status.vent_cancelada:
            raise ValueError("Esta venta ya está cancelada")
        
        # RESTAURAR STOCK (porque ya se había descontado al autorizar)
        detalles = self.factura.detallefactura_set.all()
        for detalle in detalles:
            detalle.producto.stock += detalle.cantidad
            detalle.producto.save(update_fields=['stock'])
        
        # Marcar como cancelada
        self.comentarios_autorizacion += f"\nCANCELADA el {timezone.now().strftime('%d/%m/%Y %H:%M')} por {empleado_cancelador.nombre}: {comentarios}"
        
        # Cambiar a estado cancelada
        estado_cancelado = StatusVentas.objects.get(vent_cancelada=True)
        self.status = estado_cancelado
        self.save()
    
        return True
    @property
    def estado_autorizacion(self):
        """Retorna el estado de autorización de la venta"""
        if not self.requiere_autorizacion:
            return "No requiere autorización"
        elif self.autorizada:
            return "Autorizada"
        elif self.status.vent_cancelada and self.autorizada_por:
            return "Rechazada"
        else:
            return "Pendiente de autorización"

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
    def crear_estado_pendiente_autorizacion():
        StatusVentas.objects.get_or_create(
        nombre="Pendiente de Autorización",
        defaults={
            'vent_espera': True,
            'vent_cancelada': False
        }
    )
    
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
        on_delete=models.PROTECT,  # Protege contra eliminación
        verbose_name="Cliente",
        related_name='facturas'  # Permite cliente.facturas.all()
    )
    
    empleado = models.ForeignKey(
        'Empleado',
        on_delete=models.PROTECT,
        verbose_name="Empleado",
        related_name='facturas_generadas'
    )
    
    total_venta = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Total de Venta",
        default=0
    )

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_fac']  # Ordena por fecha descendente
    
    def __str__(self):
        return f"Factura #{self.id} - Cliente: {self.cliente.nombre}"
    
    def calcular_total(self):
        """
        Calcula el total de la factura basado en sus detalles
        """
        total = self.detallefactura_set.aggregate(
            total=models.Sum(models.F('cantidad') * models.F('producto__precio'))
        )['total'] or 0
        
        self.total_fac = total
        self.total_venta = total
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
            # Cambiar esto:
            # sub_total=Decimal(str(producto.precio_pro)) * Decimal(str(cantidad))
            
            # Por esto:
            sub_total=Decimal(str(producto.precio)) * Decimal(str(cantidad))
        )
        self.calcular_total()
        return detalle
    
class DetalleFactura(models.Model):
    factura = models.ForeignKey(
        'Factura',
        on_delete=models.PROTECT,
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
    cantidad = models.PositiveIntegerField(
        verbose_name="Cantidad",
        validators=[MinValueValidator(1)]
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
        # Calcula el subtotal antes de guardar
        self.sub_total = self.calcular_subtotal()
        super().save(*args, **kwargs)
        # Actualiza el total de la factura
        self.factura.calcular_total()
    

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
    
class TablaConfig(models.Model):
    empleado = models.ForeignKey(
        'Empleado',
        on_delete=models.PROTECT,
        verbose_name="Empleado"
    )
    monto_fact = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monto Factura"
    )
    porcent_comis = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Porcentaje Comisión"
    )
    fecha_config = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Configuración"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Configuración Activa"
    )

    class Meta:
        verbose_name = "Configuración"
        verbose_name_plural = "Configuraciones"
        ordering = ['-fecha_config']

    def __str__(self):
        return f"Config {self.empleado} - {self.porcent_comis}%"

    def aplicar_comision(self, monto_venta):
        """Calcula la comisión según la configuración"""
        if monto_venta >= self.monto_fact:
            return (monto_venta * self.porcent_comis) / 100
        return 0
    
    @classmethod
    def get_tasa_actual(cls):
        """Obtiene la tasa de cambio más reciente y activa"""
        return cls.objects.filter(activa=True).first()
    
    def save(self, *args, **kwargs):
        # Si esta tasa se marca como activa, desactivar las demás
        if self.activa:
            TasaCambio.objects.filter(activa=True).update(activa=False)
        super().save(*args, **kwargs)

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