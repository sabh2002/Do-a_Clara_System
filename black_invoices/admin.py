# Actualización del admin.py para el modelo Cliente

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
    list_display = ('nombre', 'precio', 'stock', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'descripcion')
    list_editable = ('precio', 'stock')

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'empleado', 'fecha_fac', 'total_fac', 'metodo_pag')
    list_filter = ('metodo_pag', 'fecha_fac')
    search_fields = ('cliente__cedula', 'cliente__nombre', 'empleado__nombre')
    date_hierarchy = 'fecha_fac'

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

# ==== MODIFICAR EL ProductoAdmin EXISTENTE ====
# INSTRUCCIONES: 
# 1. Buscar @admin.register(Producto) en tu admin.py
# 2. REEMPLAZAR la línea list_display por esta:

    list_display = ('nombre', 'precio_venta_formateado', 'precio_compra_formateado', 'unidad_medida', 'stock', 'activo')

# 3. AGREGAR estos métodos DENTRO de la clase ProductoAdmin:

    def precio_venta_formateado(self, obj):
        """Muestra el precio de venta formateado"""
        return f"${obj.precio:,.2f}"
    precio_venta_formateado.short_description = 'Precio Venta (USD)'
    
    def precio_compra_formateado(self, obj):
        """Muestra el precio de compra formateado"""
        return f"${obj.precio_compra:,.2f}"
    precio_compra_formateado.short_description = 'Precio Compra (USD)'

# 4. AGREGAR al final de la clase ProductoAdmin:

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

# 5. MODIFICAR list_filter para incluir unidad_medida:
    list_filter = ('activo', 'unidad_medida')

# 6. MODIFICAR search_fields para mejor búsqueda:
    search_fields = ('nombre', 'descripcion', 'unidad_medida__nombre')
# Registros simples para los modelos más básicos
admin.site.register(NivelAcceso)
admin.site.register(StatusVentas)
admin.site.register(TipoFactura)
admin.site.register(TablaConfig)
admin.site.register(ConsultaComision)
admin.site.register(TasaCambio)
admin.site.register(UnidadMedida)