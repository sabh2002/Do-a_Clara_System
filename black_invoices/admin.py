# black_invoices/admin.py - VERSIÓN CORREGIDA COMPLETA

from django.contrib import admin
from .models import *

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'nivel_acceso', 'fecha_contratacion', 'activo')
    list_filter = ('nivel_acceso', 'activo')
    search_fields = ('nombre', 'apellido')
    date_hierarchy = 'fecha_contratacion'

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('cedula_formateada', 'nombre_completo', 'telefono', 'email', 'fecha_registro')
    list_filter = ('fecha_registro', 'fecha_actualizacion')
    search_fields = ('cedula', 'nombre', 'apellido', 'telefono')
    ordering = ('apellido', 'nombre')
    date_hierarchy = 'fecha_registro'
    
    # Campos de solo lectura
    readonly_fields = ('fecha_registro', 'fecha_actualizacion')
    
    # Organización de campos en el formulario de admin
    fieldsets = (
        ('Información Personal', {
            'fields': ('cedula', 'nombre', 'apellido')
        }),
        ('Información de Contacto', {
            'fields': ('telefono', 'email', 'direccion')
        }),
        ('Información del Sistema', {
            'fields': ('fecha_registro', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    def nombre_completo(self, obj):
        """Mostrar nombre completo en la lista"""
        return obj.nombre_completo
    nombre_completo.short_description = 'Nombre Completo'
    
    def cedula_formateada(self, obj):
        """Mostrar cédula formateada en la lista"""
        return obj.cedula_formateada
    cedula_formateada.short_description = 'Cédula'
    
    # Acciones personalizadas
    actions = ['exportar_clientes_csv']
    
    def exportar_clientes_csv(self, request, queryset):
        """Acción personalizada para exportar clientes seleccionados"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="clientes.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Cédula', 'Nombre', 'Apellido', 'Teléfono', 'Email', 'Dirección'])
        
        for cliente in queryset:
            writer.writerow([
                cliente.cedula,
                cliente.nombre,
                cliente.apellido,
                cliente.telefono,
                cliente.email or 'No registrado',
                cliente.direccion
            ])
        
        return response
    exportar_clientes_csv.short_description = "Exportar clientes seleccionados a CSV"

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_venta_formateado', 'precio_compra_formateado', 'unidad_medida', 'stock', 'activo')
    list_filter = ('activo', 'unidad_medida')
    search_fields = ('nombre', 'descripcion', 'unidad_medida__nombre')
    list_editable = ('stock',)
    
    def precio_venta_formateado(self, obj):
        """Muestra el precio de venta formateado"""
        return f"${obj.precio:,.2f}"
    precio_venta_formateado.short_description = 'Precio Venta (USD)'
    
    def precio_compra_formateado(self, obj):
        """Muestra el precio de compra formateado"""
        return f"${obj.precio_compra:,.2f}"
    precio_compra_formateado.short_description = 'Precio Compra (USD)'

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'unidad_medida')
        }),
        ('Precios', {
            'fields': ('precio_compra', 'precio')
        }),
        ('Inventario', {
            'fields': ('stock', 'activo')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')

@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'permite_decimales', 'activo', 'created_at')
    list_filter = ('permite_decimales', 'activo')
    search_fields = ('nombre', 'abreviatura', 'descripcion')
    ordering = ('nombre',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'abreviatura', 'descripcion')
        }),
        ('Configuración', {
            'fields': ('permite_decimales', 'activo')
        }),
    )

@admin.register(TasaCambio)
class TasaCambioAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tasa_usd_ves_formateada', 'fuente', 'activo', 'created_at')
    list_filter = ('fuente', 'activo', 'fecha')
    search_fields = ('fecha', 'fuente')
    ordering = ('-fecha',)
    date_hierarchy = 'fecha'
    
    def tasa_usd_ves_formateada(self, obj):
        """Muestra la tasa formateada"""
        return f"1 USD = {obj.tasa_usd_ves:,.4f} VES"
    tasa_usd_ves_formateada.short_description = 'Tasa de Cambio'
    
    # Campos de solo lectura para proteger datos históricos
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Información de la Tasa', {
            'fields': ('fecha', 'tasa_usd_ves', 'fuente')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Información del Sistema', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

""" @admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'empleado', 'fecha_fac', 'total_fac', 'metodo_pag')
    list_filter = ('metodo_pag', 'fecha_fac')
    search_fields = ('cliente__cedula', 'cliente__nombre', 'empleado__nombre')
    date_hierarchy = 'fecha_fac' """

@admin.register(DetalleFactura)
class DetalleFacturaAdmin(admin.ModelAdmin):
    list_display = ('factura', 'producto', 'cantidad', 'sub_total')
    list_filter = ('factura', 'producto')
    search_fields = ('factura__id', 'producto__nombre')

@admin.register(Ventas)
class VentasAdmin(admin.ModelAdmin):
    list_display = ('id', 'empleado', 'fecha_venta', 'status')
    list_filter = ('status', 'fecha_venta')
    search_fields = ('empleado__nombre',)
    date_hierarchy = 'fecha_venta'

@admin.register(Comision)
class ComisionAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'monto_venta', 'fecha_comision', 'total_comision')
    list_filter = ('fecha_comision',)
    search_fields = ('empleado__nombre',)
    date_hierarchy = 'fecha_comision'

# Registros simples para los modelos más básicos
admin.site.register(NivelAcceso)
admin.site.register(StatusVentas)
admin.site.register(TipoFactura)
admin.site.register(TablaConfig)
admin.site.register(ConsultaComision)

@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'porcentaje_iva', 'aplicar_iva', 'api_tasa_activa', 'updated_at')
    
    fieldsets = (
        ('Información de la Empresa', {
            'fields': ('nombre_empresa', 'rif_empresa', 'direccion_empresa', 'telefono_empresa')
        }),
        ('Configuración de IVA', {
            'fields': ('aplicar_iva', 'porcentaje_iva')
        }),
        ('Numeración de Documentos', {
            'fields': ('numero_factura_actual', 'numero_nota_entrega_actual'),
            'classes': ('collapse',)
        }),
        ('API de Tasa de Cambio', {
            'fields': ('api_tasa_activa', 'api_tasa_url'),
            'classes': ('collapse',)
        }),
        ('Fechas del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Solo permitir una configuración
        return not ConfiguracionSistema.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar la configuración
        return False

@admin.register(NotaEntrega)
class NotaEntregaAdmin(admin.ModelAdmin):
    list_display = ('numero_nota', 'cliente', 'empleado', 'fecha_nota', 'total_formateado', 'saldo_pendiente_formateado', 'convertida_a_factura')
    list_filter = ('convertida_a_factura', 'fecha_nota', 'empleado')
    search_fields = ('numero_nota', 'cliente__nombre', 'cliente__cedula')
    date_hierarchy = 'fecha_nota'
    ordering = ('-numero_nota',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('numero_nota', 'cliente', 'empleado')
        }),
        ('Totales', {
            'fields': ('subtotal', 'iva', 'total', 'monto_pagado')
        }),
        ('Estado', {
            'fields': ('observaciones', 'convertida_a_factura', 'factura_generada')
        }),
    )
    
    readonly_fields = ('numero_nota', 'subtotal', 'iva', 'total')
    
    def total_formateado(self, obj):
        """Muestra el total formateado"""
        return f"${obj.total:,.2f}"
    total_formateado.short_description = 'Total'
    
    def saldo_pendiente_formateado(self, obj):
        """Muestra el saldo pendiente formateado"""
        saldo = obj.saldo_pendiente
        if saldo > 0:
            return f"${saldo:,.2f}"
        return "PAGADO"
    saldo_pendiente_formateado.short_description = 'Saldo Pendiente'
    
    def save_model(self, request, obj, form, change):
        if not obj.numero_nota:
            config = ConfiguracionSistema.get_config()
            obj.numero_nota = config.get_siguiente_numero_nota_entrega()
        super().save_model(request, obj, form, change)

@admin.register(DetalleNotaEntrega)
class DetalleNotaEntregaAdmin(admin.ModelAdmin):
    list_display = ('nota_entrega', 'producto', 'cantidad', 'precio_unitario_formateado', 'subtotal_linea_formateado')
    list_filter = ('nota_entrega', 'producto')
    search_fields = ('nota_entrega__numero_nota', 'producto__nombre')
    
    def precio_unitario_formateado(self, obj):
        return f"${obj.precio_unitario:,.2f}"
    precio_unitario_formateado.short_description = 'Precio Unit.'
    
    def subtotal_linea_formateado(self, obj):
        return f"${obj.subtotal_linea:,.2f}"
    subtotal_linea_formateado.short_description = 'Subtotal'

# ==== MODIFICAR FacturaAdmin EXISTENTE ====
# Reemplazar la configuración del FacturaAdmin con esta versión mejorada:

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero_factura_display', 'cliente', 'empleado', 'fecha_fac', 'subtotal_formateado', 'iva_formateado', 'total_formateado', 'metodo_pag')
    list_filter = ('metodo_pag', 'fecha_fac')
    search_fields = ('numero_factura', 'cliente__cedula', 'cliente__nombre', 'empleado__nombre')
    date_hierarchy = 'fecha_fac'
    ordering = ('-numero_factura',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('numero_factura', 'cliente', 'empleado', 'metodo_pag')
        }),
        ('Totales', {
            'fields': ('subtotal', 'iva', 'total_fac', 'total_venta')
        }),
    )
    
    readonly_fields = ('numero_factura', 'subtotal', 'iva', 'total_fac', 'total_venta')
    
    def numero_factura_display(self, obj):
        return f"#{obj.numero_factura}" if obj.numero_factura else "Sin número"
    numero_factura_display.short_description = 'N° Factura'
    
    def subtotal_formateado(self, obj):
        return f"${obj.subtotal:,.2f}"
    subtotal_formateado.short_description = 'Subtotal'
    
    def iva_formateado(self, obj):
        return f"${obj.iva:,.2f}"
    iva_formateado.short_description = 'IVA'
    
    def total_formateado(self, obj):
        return f"${obj.total_fac:,.2f}"
    total_formateado.short_description = 'Total'
    
    def save_model(self, request, obj, form, change):
        if not obj.numero_factura:
            config = ConfiguracionSistema.get_config()
            obj.numero_factura = config.get_siguiente_numero_factura()
        super().save_model(request, obj, form, change)