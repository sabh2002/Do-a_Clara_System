from datetime import date, datetime
from decimal import Decimal
import json


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder para manejar objetos Decimal"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)
import math as m
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from black_invoices.forms.user_profile_form import UserProfileForm
from .models import *
from .forms.producto_forms import ProductoForm
from .forms.cliente_forms import ClienteForm
from .forms.empleado_form import EmpleadoForm, AsignarUsuarioEmpleadoForm, CrearUsuarioForm
from .forms.ventas_form import FacturaForm, DetalleFacturaFormSet
from django.core.serializers.json import DjangoJSONEncoder
from django.core import serializers
from django.db.models import Sum, Count, F, Max, Avg
from django.db.models.functions import TruncMonth, TruncDay
from datetime import datetime, timedelta
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import io
from .mixins import EmpleadoRolMixin
import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from .models import *
from django.db.models import Case, When, F, DecimalField, Value
from decimal import Decimal

###################     Dashboard       #################
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'black_invoices/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Dashboard'

        # Fechas para filtros
        hoy = datetime.now().date()
        inicio_mes = hoy.replace(day=1)
        inicio_anio = hoy.replace(month=1, day=1)

        # Estadísticas generales
        context['total_ventas_hoy'] = Factura.objects.filter(
            fecha_fac__date=hoy
        ).aggregate(total=Sum('total_fac'))['total'] or 0

        context['total_ventas_mes'] = Factura.objects.filter(
            fecha_fac__gte=inicio_mes
        ).aggregate(total=Sum('total_fac'))['total'] or 0

        context['total_ventas_anio'] = Factura.objects.filter(
            fecha_fac__gte=inicio_anio
        ).aggregate(total=Sum('total_fac'))['total'] or 0

        # Productos más vendidos
        context['productos_top'] = DetalleFactura.objects.values(
            'producto__nombre'
        ).annotate(
            total=Sum('cantidad')
        ).order_by('-total')[:5]

        # Ventas por empleado este mes
        context['ventas_empleados'] = Factura.objects.filter(
            fecha_fac__gte=inicio_mes
        ).values(
            'empleado__nombre', 'empleado__apellido'
        ).annotate(
            total=Sum('total_fac'),
            cantidad=Count('id')
        ).order_by('-total')

        # Datos para gráfico de ventas por día (últimos 15 días)
        quince_dias_atras = hoy - timedelta(days=14)
        ventas_por_dia = Factura.objects.filter(
            fecha_fac__date__gte=quince_dias_atras
        ).annotate(
            dia=TruncDay('fecha_fac')
        ).values('dia').annotate(
            total=Sum('total_fac')
        ).order_by('dia')

        # Formatear para Chart.js
        labels = []
        datos = []

        for venta in ventas_por_dia:
            labels.append(venta['dia'].strftime('%d/%m'))
            datos.append(float(venta['total']))

        context['chart_labels'] = labels
        context['chart_data'] = datos

        # Alertas de stock bajo
        context['productos_stock_bajo'] = Producto.objects.filter(
            stock__lte=5,  # Umbral configurable
            activo=True
        ).order_by('stock')

        # =================== MÉTRICAS DE GANANCIAS CORREGIDAS ===================
        from .models import DetalleGanancia, NotaEntrega
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Verificar datos en DetalleGanancia
            total_registros = DetalleGanancia.objects.count()
            print(f"DEBUG DASHBOARD: Total registros DetalleGanancia: {total_registros}")
            
            # Ganancias realizadas (ventas de contado + créditos pagados)
            ganancias_hoy = DetalleGanancia.get_ganancias_realizadas(
                fecha_inicio=hoy, fecha_fin=hoy
            )
            print(f"DEBUG DASHBOARD: Ganancias hoy: {ganancias_hoy}")
            context['ganancias_realizadas_hoy'] = ganancias_hoy
            
            ganancias_mes = DetalleGanancia.get_ganancias_realizadas(
                fecha_inicio=inicio_mes
            )
            print(f"DEBUG DASHBOARD: Ganancias mes: {ganancias_mes}")
            context['ganancias_realizadas_mes'] = ganancias_mes
            
            ganancias_anio = DetalleGanancia.get_ganancias_realizadas(
                fecha_inicio=inicio_anio
            )
            print(f"DEBUG DASHBOARD: Ganancias año: {ganancias_anio}")
            context['ganancias_realizadas_anio'] = ganancias_anio
            
            # Ganancias pendientes (ventas a crédito no pagadas)
            pendientes_total = DetalleGanancia.get_ganancias_pendientes()
            print(f"DEBUG DASHBOARD: Ganancias pendientes total: {pendientes_total}")
            context['ganancias_pendientes_total'] = pendientes_total
            
            pendientes_mes = DetalleGanancia.get_ganancias_pendientes(
                fecha_inicio=inicio_mes
            )
            print(f"DEBUG DASHBOARD: Ganancias pendientes mes: {pendientes_mes}")
            context['ganancias_pendientes_mes'] = pendientes_mes
            
            # Ganancias totales (realizadas + pendientes)
            context['ganancias_totales_mes'] = ganancias_mes + pendientes_mes
            context['ganancias_totales_anio'] = ganancias_anio + pendientes_total
            
            # ✅ NUEVO: Margen promedio del mes
            margen_promedio_mes = DetalleGanancia.objects.filter(
                fecha_venta__gte=inicio_mes,
                venta__credito=False  # Solo ventas completadas de contado
            ).aggregate(
                promedio=Avg('margen_porcentaje')
            )['promedio'] or Decimal('0.00')
            
            context['margen_promedio_mes'] = float(margen_promedio_mes)
            print(f"DEBUG DASHBOARD: Margen promedio mes: {margen_promedio_mes}")
            
            print(f"DEBUG DASHBOARD: ✅ Métricas de ganancias calculadas correctamente")
            
        except Exception as e:
            print(f"ERROR DASHBOARD: Falló cálculo de ganancias: {e}")
            # Fallback seguro con valores en cero
            context['ganancias_realizadas_hoy'] = Decimal('0.00')
            context['ganancias_realizadas_mes'] = Decimal('0.00')
            context['ganancias_realizadas_anio'] = Decimal('0.00')
            context['ganancias_pendientes_total'] = Decimal('0.00')
            context['ganancias_pendientes_mes'] = Decimal('0.00')
            context['ganancias_totales_mes'] = Decimal('0.00')
            context['ganancias_totales_anio'] = Decimal('0.00')
            context['margen_promedio_mes'] = 0.0
        
        # Top productos por ganancia (este mes)
        context['productos_top_ganancia'] = DetalleGanancia.get_ganancias_por_producto(
            fecha_inicio=inicio_mes, limit=5
        )
        
        # Incluir ventas a crédito en totales (notas de entrega)
        ventas_credito_hoy = NotaEntrega.objects.filter(
            fecha_nota__date=hoy
        ).aggregate(total=Sum('total'))['total'] or 0
        
        ventas_credito_mes = NotaEntrega.objects.filter(
            fecha_nota__gte=inicio_mes
        ).aggregate(total=Sum('total'))['total'] or 0
        
        ventas_credito_anio = NotaEntrega.objects.filter(
            fecha_nota__gte=inicio_anio
        ).aggregate(total=Sum('total'))['total'] or 0
        
        # Totales combinados (facturas + notas de entrega)
        context['total_ventas_hoy'] += ventas_credito_hoy
        context['total_ventas_mes'] += ventas_credito_mes
        context['total_ventas_anio'] += ventas_credito_anio

        return context

        return context
class BaseListView(LoginRequiredMixin, ListView):
    template_name = 'lista_generica.html'
    context_object_name = 'objetos'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = self.titulo
        return context


######################      CLIENTES        #####################3
class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'black_invoices/clientes/clientes_list.html'
    context_object_name = 'clientes'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Lista de Clientes'
        context['create_url'] = reverse_lazy('black_invoices:cliente_create')

        # Estadísticas adicionales
        clientes = self.get_queryset()
        hoy = date.today()

        context['estadisticas'] = {
            'total_clientes': clientes.count(),
            'con_email': clientes.filter(email__isnull=False).exclude(email='').count(),
            'registrados_hoy': clientes.filter(fecha_registro__date=hoy).count(),
            'registrados_mes': clientes.filter(
                fecha_registro__month=hoy.month,
                fecha_registro__year=hoy.year
            ).count()
        }

        return context

class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'black_invoices/clientes/cliente_form.html'
    success_url = reverse_lazy('black_invoices:cliente_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Registrar Cliente'
        context['action'] = 'Registrar'
        return context

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Cliente {form.instance.nombre_completo} (Cédula: {form.instance.cedula_formateada}) registrado exitosamente.'
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Por favor corrija los errores en el formulario.'
        )
        return super().form_invalid(form)

class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'black_invoices/clientes/cliente_detail.html'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = self.get_object()

        # Obtener historial de ventas/facturas del cliente
        facturas = Factura.objects.filter(cliente=cliente).order_by('-fecha_fac')
        context['facturas'] = facturas

        # Estadísticas del cliente
        context['estadisticas_cliente'] = {
            'total_facturas': facturas.count(),
            'total_gastado': sum(f.total_fac for f in facturas),
            'ultima_compra': facturas.first().fecha_fac if facturas.exists() else None,
            'primera_compra': facturas.last().fecha_fac if facturas.exists() else None,
        }

        return context

class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'black_invoices/clientes/cliente_form.html'

    def get_success_url(self):
        return reverse_lazy('black_invoices:cliente_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Cliente: {self.object.nombre_completo}'
        context['action'] = 'Actualizar'
        return context

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Cliente {form.instance.nombre_completo} actualizado exitosamente'
        )
        return super().form_valid(form)

class ClienteDeleteView(EmpleadoRolMixin, DeleteView):
    model = Cliente
    template_name = 'black_invoices/clientes/cliente_delete.html'
    success_url = reverse_lazy('black_invoices:cliente_list')
    context_object_name = 'cliente'
    roles_permitidos = ['Administrador']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = self.get_object()
        context['titulo'] = f'Eliminar Cliente: {cliente.nombre_completo}'
        
        # Obtener información de facturas relacionadas que se eliminarán
        facturas = cliente.facturas.all()
        context['facturas_a_eliminar'] = facturas
        context['total_facturas'] = facturas.count()
        context['total_monto'] = sum(f.total_fac for f in facturas)
        
        return context

    def form_valid(self, form):
        cliente = self.get_object()
        nombre_cliente = cliente.nombre_completo
        num_facturas = cliente.facturas.count()
        
        messages.success(
            self.request,
            f'Cliente {nombre_cliente} y {num_facturas} factura(s) relacionada(s) eliminado(s) exitosamente'
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Por favor corrija los errores en el formulario.'
        )
        return super().form_invalid(form)

# Función de búsqueda avanzada (opcional para AJAX)
def buscar_cliente_por_cedula(request):
    """
    Función para búsqueda AJAX de cliente por cédula
    """
    if request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cedula = request.GET.get('cedula', '')

        if cedula:
            try:
                # Normalizar cédula
                cedula_normalizada = cedula.replace('-', '').upper()
                cliente = Cliente.objects.get(cedula=cedula_normalizada)

                data = {
                    'encontrado': True,
                    'cliente': {
                        'id': cliente.id,
                        'nombre_completo': cliente.nombre_completo,
                        'cedula_formateada': cliente.cedula_formateada,
                        'telefono': cliente.telefono,
                        'direccion': cliente.direccion,
                        'email': cliente.email or 'No registrado'
                    }
                }
            except Cliente.DoesNotExist:
                data = {'encontrado': False, 'mensaje': 'Cliente no encontrado'}
        else:
            data = {'encontrado': False, 'mensaje': 'Cédula requerida'}

        return JsonResponse(data)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

######################      PRODUCTOS       ###############
class ProductoListView(LoginRequiredMixin, ListView):
    model = Producto
    template_name = 'black_invoices/productos/productos_list.html'
    context_object_name = 'productos'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Lista de Productos'
        context['create_url'] = reverse_lazy('black_invoices:producto_create')
        return context

class ProductoCreateView(LoginRequiredMixin, CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'black_invoices/productos/producto_form.html'
    success_url = reverse_lazy('black_invoices:producto_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Producto'
        context['action'] = 'Crear'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Producto creado exitosamente.')
        return super().form_valid(form)

class ProductoStockUpdateView(LoginRequiredMixin, UpdateView):
    model = Producto
    template_name = 'black_invoices/productos/producto_stock.html'
    fields = ['stock']
    success_url = reverse_lazy('black_invoices:producto_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Actualizar Stock: {self.object.nombre}'
        return context

    def form_valid(self, form):
        # Guardar stock anterior para mensaje
        stock_anterior = self.object.stock

        # Guardar formulario
        response = super().form_valid(form)

        # Mostrar mensaje con el cambio
        messages.success(
            self.request,
            f'Stock de {self.object.nombre} actualizado de {stock_anterior} a {self.object.stock}'
        )

        return response

# En views.py, añade estas clases

class ProductoDetailView(LoginRequiredMixin, DetailView):
    model = Producto
    template_name = 'black_invoices/productos/producto_detail.html'
    context_object_name = 'producto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Detalles del Producto: {self.object.nombre}'

        # Obtener historial de ventas de este producto (opcional)
        context['detalles_ventas'] = DetalleFactura.objects.filter(
            producto=self.object
        ).order_by('-factura__fecha_fac')[:10]  # Últimas 10 ventas

        # Información adicional del producto con nuevos campos
        context['precios_formateados'] = self.object.get_precios_formateados_completos()
        context['precios_iva'] = self.object.get_precios_iva_formateados()
        context['stock_status'] = self.object.get_stock_status()
        context['margen_ganancia'] = self.object.get_margen_ganancia()

        return context

class ProductoUpdateView(LoginRequiredMixin, UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'black_invoices/productos/producto_form.html'

    def get_success_url(self):
        return reverse_lazy('black_invoices:producto_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Producto: {self.object.nombre}'
        context['action'] = 'Actualizar'
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Producto {self.object.nombre} actualizado exitosamente.')
        return super().form_valid(form)
class ProductosMasVendidosView(LoginRequiredMixin, ListView):
    model = Producto
    template_name = 'black_invoices/productos/productos_mas_vendidos.html'
    context_object_name = 'productos'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Productos Más Vendidos'

        # Obtener parámetros de fecha del request
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')

        # Filtros base
        filtros = {}

        if fecha_inicio:
            try:
                fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                filtros['factura__fecha_fac__date__gte'] = fecha_inicio_obj
                context['fecha_inicio'] = fecha_inicio
            except ValueError:
                pass

        if fecha_fin:
            try:
                fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                filtros['factura__fecha_fac__date__lte'] = fecha_fin_obj
                context['fecha_fin'] = fecha_fin
            except ValueError:
                pass

        # Si no hay filtros de fecha, usar el mes actual por defecto
        if not fecha_inicio and not fecha_fin:
            hoy = datetime.now().date()
            inicio_mes = hoy.replace(day=1)
            filtros['factura__fecha_fac__date__gte'] = inicio_mes
            context['periodo_default'] = f"Mes actual ({inicio_mes.strftime('%B %Y')})"

        # Consulta principal: productos más vendidos
        productos_vendidos = DetalleFactura.objects.filter(
            **filtros
        ).exclude(
            factura__ventas__status__vent_cancelada=True  # Excluir ventas canceladas
        ).values(
            'producto__id',
            'producto__nombre',
            'producto__precio'
        ).annotate(
            total_vendido=Sum('cantidad'),
            total_ingresos=Sum(F('cantidad') * F('producto__precio')),
            numero_ventas=Count('factura', distinct=True)
        ).order_by('-total_vendido')

        context['productos_vendidos'] = productos_vendidos

        # Estadísticas adicionales
        if productos_vendidos:
            context['producto_top'] = productos_vendidos[0]
            context['total_productos_diferentes'] = productos_vendidos.count()
            context['total_unidades_vendidas'] = sum(p['total_vendido'] for p in productos_vendidos)
            context['total_ingresos_productos'] = sum(p['total_ingresos'] for p in productos_vendidos)
        else:
            context['producto_top'] = None
            context['total_productos_diferentes'] = 0
            context['total_unidades_vendidas'] = 0
            context['total_ingresos_productos'] = 0

        return context

########################        EMPLEADOS       #############
class EmpleadoListView(EmpleadoRolMixin, ListView):
    model = Empleado
    template_name = 'black_invoices/empleados/empleados_list.html'
    context_object_name = 'empleados'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Lista de Empleados'
        return context

class EmpleadoCreateView(EmpleadoRolMixin, CreateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'black_invoices/empleados/empleado_form.html'
    success_url = reverse_lazy('black_invoices:empleado_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Empleado'
        context['accion'] = 'Crear'
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Crear empleado
                empleado = form.save()
                
                # Si se seleccionó crear usuario, crearlo y asignarlo
                if form.cleaned_data.get('crear_usuario'):
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        password=form.cleaned_data['password'],
                        first_name=empleado.nombre,
                        last_name=empleado.apellido,
                        email=empleado.email or '',
                        is_staff=form.cleaned_data.get('is_staff', False)
                    )
                    
                    # Asignar usuario al empleado
                    empleado.user = user
                    empleado.save()
                    
                    messages.success(
                        self.request, 
                        f'Empleado {empleado.nombre_completo} y usuario "{user.username}" '
                        f'creados exitosamente. El empleado ya tiene acceso al sistema.'
                    )
                else:
                    messages.success(
                        self.request, 
                        f'Empleado {empleado.nombre_completo} registrado exitosamente. '
                        f'Para darle acceso al sistema, asígnele un usuario desde la lista de empleados.'
                    )
                
                return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f'Error al registrar empleado: {str(e)}')
            return self.form_invalid(form)

class EmpleadoUpdateView(EmpleadoRolMixin, UpdateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'black_invoices/empleados/empleado_form.html'
    success_url = reverse_lazy('black_invoices:empleado_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Empleado: {self.object.nombre}'
        context['accion'] = 'Actualizar'
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Actualizar usuario
                user = self.object.user
                user.username = form.cleaned_data['username']
                user.first_name = form.cleaned_data['nombre']
                user.last_name = form.cleaned_data['apellido']

                # Actualizar contraseña si se proporcionó
                if form.cleaned_data['password']:
                    user.set_password(form.cleaned_data['password'])

                user.save()

                # Guardar cambios en empleado
                empleado = form.save()

                messages.success(self.request, f'Empleado {empleado.nombre} actualizado exitosamente')
                return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f'Error al actualizar empleado: {str(e)}')
            return self.form_invalid(form)


# ===== NUEVAS VISTAS PARA GESTIÓN SEPARADA DE USUARIOS =====

class CrearUsuarioView(EmpleadoRolMixin, FormView):
    """Vista para crear usuarios del sistema (separado de empleados)"""
    template_name = 'black_invoices/usuarios/crear_usuario.html'
    form_class = CrearUsuarioForm
    success_url = reverse_lazy('black_invoices:usuarios_list')
    roles_permitidos = ['Administrador']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Usuario del Sistema'
        return context
    
    def form_valid(self, form):
        try:
            user = form.save()
            messages.success(
                self.request, 
                f'Usuario "{user.username}" creado exitosamente. '
                f'Ahora puede asignarlo a un empleado si es necesario.'
            )
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f'Error al crear usuario: {str(e)}')
            return self.form_invalid(form)


class UsuariosListView(EmpleadoRolMixin, ListView):
    """Vista para listar usuarios del sistema"""
    model = User
    template_name = 'black_invoices/usuarios/usuarios_list.html'
    context_object_name = 'usuarios'
    roles_permitidos = ['Administrador']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Gestión de Usuarios del Sistema'
        # Información adicional útil
        context['usuarios_sin_empleado'] = User.objects.filter(empleado__isnull=True).count()
        context['usuarios_con_empleado'] = User.objects.filter(empleado__isnull=False).count()
        return context


class AsignarUsuarioEmpleadoView(EmpleadoRolMixin, FormView):
    """Vista para asignar un usuario a un empleado"""
    template_name = 'black_invoices/empleados/asignar_usuario.html'
    form_class = AsignarUsuarioEmpleadoForm
    roles_permitidos = ['Administrador']
    
    def get_success_url(self):
        return reverse_lazy('black_invoices:empleado_detail', kwargs={'pk': self.kwargs['pk']})
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['empleado'] = self.get_empleado()
        return kwargs
    
    def get_empleado(self):
        return get_object_or_404(Empleado, pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        empleado = self.get_empleado()
        context['empleado'] = empleado
        context['titulo'] = f'Asignar Usuario a {empleado.nombre_completo}'
        return context
    
    def form_valid(self, form):
        try:
            empleado = self.get_empleado()
            usuario = form.cleaned_data['usuario']
            
            # Asignar usuario al empleado
            empleado.user = usuario
            empleado.save()
            
            messages.success(
                self.request,
                f'Usuario "{usuario.username}" asignado exitosamente a {empleado.nombre_completo}'
            )
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f'Error al asignar usuario: {str(e)}')
            return self.form_invalid(form)


class EmpleadoDetailView(EmpleadoRolMixin, DetailView):
    """Vista para ver detalles de un empleado"""
    model = Empleado
    template_name = 'black_invoices/empleados/empleado_detail.html'
    context_object_name = 'empleado'
    roles_permitidos = ['Administrador', 'Supervisor']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        empleado = self.get_object()
        context['titulo'] = f'Empleado: {empleado.nombre_completo}'
        
        # Información adicional
        context['puede_asignar_usuario'] = (
            not empleado.user and 
            User.objects.filter(empleado__isnull=True).exists()
        )
        
        return context


#######################     FACTURAS        ######################
class FacturaListView(LoginRequiredMixin, ListView):
    model = Factura
    template_name = 'black_invoices/facturas/facturas_list.html'
    context_object_name = 'facturas'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Lista de Recibos'
        return context

class FacturaDetailView(LoginRequiredMixin, DetailView):
    model = Factura
    template_name = 'black_invoices/facturas/factura_detail.html'
    context_object_name = 'factura'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        factura = self.get_object()

        # Detalles de la factura
        context['detalles'] = factura.get_detalles().order_by('id')
        context['titulo'] = f'Detalle de Factura N° {factura.numero_factura or factura.id}'

        # Información de totales con IVA
        context['totales_formateados'] = factura.get_totales_formateados()

        # Configuración del sistema para mostrar IVA
        config = ConfiguracionSistema.get_config()
        context['config_sistema'] = config

        # Información de la venta asociada (si existe)
        try:
            venta = factura.ventas
            context['venta'] = venta
        except:
            context['venta'] = None

        return context

def ingresar(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('black_invoices:inicio')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')

    return render(request, 'black_invoices/usuarios/login.html')



#####################       VENTAS      #######################
from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.urls import reverse_lazy
from django.contrib import messages


class VentaCreateView(LoginRequiredMixin, View):
    """Vista optimizada para crear ventas - Maneja ventas grandes (200+ productos)"""
    template_name = 'black_invoices/ventas/venta_form.html'

    def get(self, request):
        # Obtener tasa de cambio actual
        tasa_actual = TasaCambio.get_tasa_actual()

        context = {
            'titulo': 'Crear Venta',
            'clientes': Cliente.objects.all(),
            'productos': Producto.objects.filter(activo=True, stock__gt=0),
            'opciones_venta': [
                {'id': 'contado', 'nombre': 'Contado'},
                {'id': 'credito', 'nombre': 'Crédito'}
            ],
            'tasa_cambio': tasa_actual.tasa_usd_ves if tasa_actual else 1
        }
        return render(request, self.template_name, context)

    def post(self, request):
        # ✅ LOGGING MEJORADO PARA DEBUG
        import time
        start_time = time.time()
        print(f"DEBUG VENTA: Iniciando creación de venta - Timestamp: {start_time}")
        
        try:
            with transaction.atomic():
                # 1. Verificar que el usuario tenga empleado asociado
                if not hasattr(request.user, 'empleado'):
                    messages.error(request, 'No tienes un perfil de empleado asociado.')
                    return redirect('black_invoices:venta_create')

                # 2. Obtener cliente y método de pago
                cliente_id = request.POST.get('cliente')
                metodo_pago = request.POST.get('metodo_pag')

                if not cliente_id:
                    messages.error(request, 'Debe seleccionar un cliente.')
                    return redirect('black_invoices:venta_create')

                # ✅ 3. RECOPILAR DETALLES DE PRODUCTOS - OPTIMIZADO
                productos = []
                total_forms = int(request.POST.get('form-TOTAL_FORMS', 0))
                
                print(f"DEBUG VENTA: Total forms detectados: {total_forms}")
                
                # Procesamiento optimizado por lotes
                batch_size = 50  # Procesar de 50 en 50 para ventas muy grandes
                
                for batch_start in range(0, total_forms, batch_size):
                    batch_end = min(batch_start + batch_size, total_forms)
                    batch_time = time.time()
                    
                    print(f"DEBUG VENTA: Procesando lote {batch_start}-{batch_end}")
                    
                    for i in range(batch_start, batch_end):
                        producto_id = request.POST.get(f'form-{i}-producto')
                        cantidad_str = request.POST.get(f'form-{i}-cantidad')

                        if producto_id and cantidad_str:
                            try:
                                cantidad = float(cantidad_str)
                                if cantidad > 0:
                                    productos.append({
                                        'id': producto_id,
                                        'cantidad': cantidad
                                    })
                            except ValueError:
                                print(f"DEBUG VENTA: Valor inválido en form-{i}: {cantidad_str}")
                                continue
                    
                    batch_time_elapsed = time.time() - batch_time
                    print(f"DEBUG VENTA: Lote {batch_start}-{batch_end} procesado en {batch_time_elapsed:.2f}s")

                if not productos:
                    messages.error(request, 'Debe agregar al menos un producto a la venta.')
                    return redirect('black_invoices:venta_create')
                
                print(f"DEBUG VENTA: Total productos válidos: {len(productos)}")

                # ✅ 4. VALIDACIÓN PREVIA DE STOCK - OPTIMIZADA
                print("DEBUG VENTA: Iniciando validación de stock...")
                stock_validation_time = time.time()
                
                # Obtener todos los productos de una vez para evitar múltiples queries
                producto_ids = [prod['id'] for prod in productos]
                productos_db = {
                    str(p.id): p for p in Producto.objects.filter(
                        id__in=producto_ids
                    ).select_related('unidad_medida')
                }
                
                # Validar stock de todos los productos
                stock_errors = []
                for prod in productos:
                    producto_db = productos_db.get(prod['id'])
                    if not producto_db:
                        stock_errors.append(f"Producto ID {prod['id']} no encontrado")
                        continue
                        
                    if prod['cantidad'] > producto_db.stock:
                        stock_errors.append(
                            f"Stock insuficiente para {producto_db.nombre}. "
                            f"Disponible: {producto_db.stock}, solicitado: {prod['cantidad']}"
                        )
                
                if stock_errors:
                    for error in stock_errors[:5]:  # Mostrar máximo 5 errores
                        messages.error(request, error)
                    if len(stock_errors) > 5:
                        messages.error(request, f"Y {len(stock_errors) - 5} errores más de stock...")
                    return redirect('black_invoices:venta_create')
                
                stock_validation_elapsed = time.time() - stock_validation_time
                print(f"DEBUG VENTA: Validación de stock completada en {stock_validation_elapsed:.2f}s")

                # 4. Determinar tipo de venta
                cliente = Cliente.objects.get(pk=cliente_id)
                es_credito = request.POST.get('tipo_venta') == 'credito'

                # 5. Crear estados necesarios
                if es_credito:
                    estado, created = StatusVentas.objects.get_or_create(
                        nombre="Pendiente",
                        defaults={
                            'vent_espera': True,
                            'vent_cancelada': False
                        }
                    )
                else:
                    estado, created = StatusVentas.objects.get_or_create(
                        nombre="Completada",
                        defaults={
                            'vent_espera': False,
                            'vent_cancelada': False
                        }
                    )

                if es_credito:
                    # ==================== FLUJO CRÉDITO: NOTA DE ENTREGA ====================
                    print("DEBUG VENTA: Creando nota de entrega...")
                    nota_creation_time = time.time()
                    
                    # Crear nota de entrega
                    config = ConfiguracionSistema.get_config()
                    nota = NotaEntrega.objects.create(
                        cliente=cliente,
                        empleado=request.user.empleado,
                        numero_nota=config.get_siguiente_numero_nota_entrega()
                    )

                    # ✅ PROCESAR PRODUCTOS EN LOTES PARA NOTAS DE ENTREGA - CORREGIDO
                    detalles_batch = []
                    stock_updates = []
                    
                    for i, prod in enumerate(productos):
                        producto_db = productos_db[prod['id']]
                        cantidad = Decimal(str(prod['cantidad']))

                        # ✅ CALCULAR SUBTOTAL MANUALMENTE ANTES DE BULK_CREATE
                        subtotal = cantidad * producto_db.precio

                        # Preparar detalle para creación en lote
                        detalles_batch.append(DetalleNotaEntrega(
                            nota_entrega=nota,
                            producto=producto_db,
                            cantidad=cantidad,
                            precio_unitario=producto_db.precio,
                            subtotal_linea=subtotal  # ✅ ASIGNAR SUBTOTAL MANUALMENTE
                        ))
                        
                        # Preparar actualización de stock
                        stock_updates.append({
                            'producto': producto_db,
                            'nueva_cantidad': producto_db.stock - cantidad
                        })
                        
                        # Crear en lotes de 100 para evitar memoria excesiva
                        if len(detalles_batch) >= 100 or i == len(productos) - 1:
                            DetalleNotaEntrega.objects.bulk_create(detalles_batch)
                            
                            # Actualizar stock en lote
                            for stock_update in stock_updates:
                                stock_update['producto'].stock = stock_update['nueva_cantidad']
                                
                            Producto.objects.bulk_update(
                                [su['producto'] for su in stock_updates], 
                                ['stock']
                            )
                            
                            # Limpiar lotes
                            detalles_batch = []
                            stock_updates = []
                            
                            print(f"DEBUG VENTA: Procesado lote hasta producto {i+1}/{len(productos)}")

                    # Calcular totales de la nota
                    nota.calcular_totales()

                    # Crear venta referenciando nota de entrega
                    venta = Ventas.objects.create(
                        empleado=request.user.empleado,
                        nota_entrega=nota,
                        status=estado,
                        credito=True,
                        monto_pagado=0
                    )
                    
                    nota_creation_elapsed = time.time() - nota_creation_time
                    print(f"DEBUG VENTA: Nota de entrega creada en {nota_creation_elapsed:.2f}s")

                    # Mensaje específico para crédito
                    tasa_actual = TasaCambio.get_tasa_actual()
                    if tasa_actual:
                        total_bs = nota.total * tasa_actual.tasa_usd_ves
                        messages.success(
                            request,
                            f'Venta a crédito #{venta.id} creada exitosamente. '
                            f'Nota de Entrega #{nota.numero_nota} generada. '
                            f'Total: ${nota.total:,.2f} ({total_bs:,.2f} Bs). '
                            f'Al completar el pago se generará la Factura Fiscal.'
                        )
                    else:
                        messages.success(
                            request,
                            f'Venta a crédito #{venta.id} creada exitosamente. '
                            f'Nota de Entrega #{nota.numero_nota} generada. '
                            f'Total: ${nota.total:,.2f}.'
                        )

                else:
                    # ==================== FLUJO CONTADO: FACTURA DIRECTA ====================
                    print("DEBUG VENTA: Creando factura...")
                    factura_creation_time = time.time()
                    
                    # Crear factura inmediatamente
                    factura = Factura(
                        cliente=cliente,
                        empleado=request.user.empleado,
                        metodo_pag=metodo_pago
                    )
                    factura.save()

                    # Obtener tipo de factura
                    try:
                        tipo_factura = TipoFactura.objects.get(credito_fac=False, contado_fac=True)
                    except TipoFactura.DoesNotExist:
                        tipo_factura = TipoFactura.objects.create(
                            credito_fac=False,
                            contado_fac=True
                        )

                    # ✅ PROCESAR PRODUCTOS EN LOTES PARA FACTURAS - CORREGIDO
                    detalles_batch = []
                    stock_updates = []
                    
                    for i, prod in enumerate(productos):
                        producto_db = productos_db[prod['id']]
                        cantidad = Decimal(str(prod['cantidad']))

                        # ✅ CALCULAR SUBTOTAL MANUALMENTE ANTES DE BULK_CREATE
                        subtotal = producto_db.precio * cantidad

                        # Preparar detalle para creación en lote
                        detalles_batch.append(DetalleFactura(
                            factura=factura,
                            producto=producto_db,
                            cantidad=cantidad,
                            tipo_factura=tipo_factura,
                            sub_total=subtotal  # ✅ ASIGNAR SUBTOTAL MANUALMENTE
                        ))
                        
                        # Preparar actualización de stock
                        stock_updates.append({
                            'producto': producto_db,
                            'nueva_cantidad': producto_db.stock - cantidad
                        })
                        
                        # Crear en lotes de 100
                        if len(detalles_batch) >= 100 or i == len(productos) - 1:
                            DetalleFactura.objects.bulk_create(detalles_batch)
                            
                            # Actualizar stock en lote
                            for stock_update in stock_updates:
                                stock_update['producto'].stock = stock_update['nueva_cantidad']
                                
                            Producto.objects.bulk_update(
                                [su['producto'] for su in stock_updates], 
                                ['stock']
                            )
                            
                            # Limpiar lotes
                            detalles_batch = []
                            stock_updates = []
                            
                            print(f"DEBUG VENTA: Procesado lote hasta producto {i+1}/{len(productos)}")

                    # Calcular totales de la factura
                    factura.calcular_total_mejorado()

                    # Crear venta referenciando factura
                    venta = Ventas.objects.create(
                        empleado=request.user.empleado,
                        factura=factura,
                        status=estado,
                        credito=False,
                        monto_pagado=factura.total_fac
                    )
                    
                    factura_creation_elapsed = time.time() - factura_creation_time
                    print(f"DEBUG VENTA: Factura creada en {factura_creation_elapsed:.2f}s")

                    # Mensaje específico para contado
                    tasa_actual = TasaCambio.get_tasa_actual()
                    if tasa_actual:
                        total_bs = factura.total_fac * tasa_actual.tasa_usd_ves
                        messages.success(
                            request,
                            f'Venta #{venta.id} completada exitosamente. '
                            f'Factura Fiscal #{factura.numero_factura} generada. '
                            f'Total: ${factura.total_fac:,.2f} ({total_bs:,.2f} Bs). '
                            f'Pago recibido.'
                        )
                    else:
                        messages.success(
                            request,
                            f'Venta #{venta.id} completada exitosamente. '
                            f'Factura Fiscal #{factura.numero_factura} generada. '
                            f'Total: ${factura.total_fac:,.2f}. Pago recibido.'
                        )
                
                # ✅ CREAR REGISTROS DE GANANCIA OPTIMIZADO
                print("DEBUG VENTA: Creando registros de ganancia...")
                ganancia_time = time.time()
                
                venta.crear_registros_ganancia()
                
                ganancia_elapsed = time.time() - ganancia_time
                print(f"DEBUG VENTA: Registros de ganancia creados en {ganancia_elapsed:.2f}s")

                total_elapsed = time.time() - start_time
                print(f"DEBUG VENTA: ✅ Venta creada exitosamente en {total_elapsed:.2f}s total")
                print(f"DEBUG VENTA: Productos procesados: {len(productos)}")
                
                # ✅ REDIRECCIÓN GARANTIZADA A DETALLE DE VENTA
                return redirect('black_invoices:venta_detail', pk=venta.id)

        except Exception as e:
            total_elapsed = time.time() - start_time
            print(f"ERROR VENTA: Error después de {total_elapsed:.2f}s: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error al crear la venta: {str(e)}")
            return redirect('black_invoices:venta_create')
class VentaListView(LoginRequiredMixin, ListView):
    model = Ventas
    template_name = 'black_invoices/ventas/ventas_list.html'
    context_object_name = 'ventas'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Lista de Ventas'
        context['create_url'] = reverse_lazy('black_invoices:venta_create')

        return context

class VentasPendientesView(EmpleadoRolMixin, ListView):

    model = Ventas
    template_name = 'black_invoices/ventas/ventas_pendientes.html'
    context_object_name = 'ventas'
    roles_permitidos = ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']

    def get_queryset(self):
        from django.db.models import Case, When, F

        return Ventas.objects.filter(
            credito=True,
            status__vent_cancelada=False
        ).annotate(
            total_documento=Case(
                When(factura__isnull=False, then=F('factura__total_fac')),
                When(nota_entrega__isnull=False, then=F('nota_entrega__total')),
                default=Value(Decimal('0.0')),     # <-- CAMBIA ESTA LÍNEA
                output_field=DecimalField()
            )
        ).exclude(
            monto_pagado__gte=F('total_documento')
        ).order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Abonos (Crédito)'
        return context


class RegistrarPagoView(EmpleadoRolMixin, UpdateView):
    model = Ventas
    template_name = 'black_invoices/ventas/registrar_pago.html'
    fields = []
    roles_permitidos = ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Registrar Pago - Venta #{self.object.id}'
        context['venta'] = self.object
        context['metodos_pago'] = PagoVenta.METODOS_PAGO_CHOICES

        # Agregar tasa de cambio actual
        tasa_actual = TasaCambio.get_tasa_actual()
        context['tasa_cambio'] = tasa_actual.tasa_usd_ves if tasa_actual else 1

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        try:
            monto = float(request.POST.get('monto', 0))
            metodo_pago = request.POST.get('metodo_pago', 'efectivo')
            referencia = request.POST.get('referencia', '').strip()

            if monto <= 0:
                messages.error(request, 'El monto debe ser mayor a cero.')
                return self.get(request, *args, **kwargs)

            if monto > (self.object.saldo_pendiente + Decimal(0.01)):
                messages.error(request, f'El monto excede el saldo pendiente (${self.object.saldo_pendiente}).')
                return self.get(request, *args, **kwargs)

            # Validar referencia para métodos que la requieren
            if metodo_pago in ['pago_movil', 'transferencia'] and not referencia:
                messages.error(request, f'La referencia es obligatoria para {dict(PagoVenta.METODOS_PAGO_CHOICES)[metodo_pago]}.')
                return self.get(request, *args, **kwargs)

            # Registrar pago usando el método con transacciones atómicas
            pago = self.object.registrar_pago(monto, metodo_pago, referencia)

            metodo_display = dict(PagoVenta.METODOS_PAGO_CHOICES).get(metodo_pago, metodo_pago)

            # ==================== LÓGICA DE CONVERSIÓN A FACTURA ====================
            if self.object.completada and self.object.credito:
                # Venta completada y es a crédito
                if self.object.nota_entrega and not self.object.nota_entrega.convertida_a_factura:
                    try:
                        # Convertir nota de entrega a factura fiscal
                        factura = self.object.nota_entrega.convertir_a_factura()

                        messages.success(
                            request,
                            f'Pago de ${monto} registrado vía {metodo_display}. '
                            f'Venta completada y Factura Fiscal #{factura.numero_factura} generada automáticamente.'
                        )
                    except Exception as e:
                        # Si falla la conversión, registrar el pago pero alertar
                        messages.warning(
                            request,
                            f'Pago de ${monto} registrado vía {metodo_display}. '
                            f'Venta completada, pero hubo un error al generar la factura: {str(e)}'
                        )
                else:
                    # Ya tiene factura o ya fue convertida
                    messages.success(
                        request,
                        f'Pago de ${monto} registrado vía {metodo_display}. '
                        f'Venta completada.'
                    )
            elif self.object.completada and not self.object.credito:
                # Venta de contado completada (caso raro, pero por si acaso)
                messages.success(
                    request,
                    f'Pago de ${monto} registrado vía {metodo_display}. '
                    f'Venta completada.'
                )
            else:
                # Pago parcial - venta aún pendiente
                messages.success(
                    request,
                    f'Pago de ${monto} registrado vía {metodo_display}. '
                    f'Saldo pendiente: ${self.object.saldo_pendiente}'
                )

            return redirect('black_invoices:ventas_pendientes')

        except ValueError:
            messages.error(request, 'Por favor ingrese un monto válido.')
            return self.get(request, *args, **kwargs)
        except Exception as e:
            messages.error(request, f'Error al procesar el pago: {str(e)}')
            return self.get(request, *args, **kwargs)

class VentaDetailView(LoginRequiredMixin, DetailView):
    model = Ventas
    template_name = 'black_invoices/ventas/venta_detail.html'
    context_object_name = 'venta'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        venta = self.object
        context['titulo'] = f'Detalle de venta #{venta.id}'

        # Obtener detalles según el tipo de documento - ACTUALIZADO
        if venta.factura:
            context['detalles'] = venta.factura.detallefactura_set.all()
            context['totales_formateados'] = venta.factura.get_totales_formateados()
        elif venta.nota_entrega:
            context['detalles'] = venta.nota_entrega.detalles_nota.all()
            context['totales_formateados'] = venta.nota_entrega.get_totales_formateados()
        else:
            context['detalles'] = []
            context['totales_formateados'] = {}

        # Estado de la venta con nuevos campos - USANDO PROPIEDADES ACTUALIZADAS
        context['saldo_pendiente'] = venta.saldo_pendiente if venta.credito else 0
        context['completada'] = venta.completada

        # Historial de pagos si es a crédito
        if venta.credito:
            context['pagos'] = venta.pagos.all().order_by('-fecha')
            context['resumen_pagos'] = venta.resumen_pagos()

        return context

@login_required
def cancelar_venta(request, pk):
    try:
        venta = Ventas.objects.get(pk=pk)

        # Comprobar que la venta no esté ya cancelada
        if venta.status.vent_cancelada:
            messages.warning(request, 'La venta ya está cancelada.')
        else:
            try:
                # Obtener empleado que realiza la cancelación
                empleado_cancelador = request.user.empleado

                # Usar el método correcto del modelo con transacciones atómicas
                venta.cancelar_venta()
                messages.success(request, f'Venta #{venta.id} cancelada exitosamente. Stock restaurado.')

            except ValueError as e:
                messages.error(request, f'Error al cancelar venta: {str(e)}')

    except Ventas.DoesNotExist:
        messages.error(request, 'Venta no encontrada.')
    except AttributeError:
        messages.error(request, 'Usuario sin permisos de empleado para cancelar ventas.')

    return redirect('black_invoices:venta_list')


from django.db.models import Q

class VentaUpdateView(LoginRequiredMixin, View):
    """Vista para modificar ventas existentes - CORREGIDA"""
    template_name = 'black_invoices/ventas/venta_edit_form.html'

    def get(self, request, pk):
        try:
            venta = Ventas.objects.get(pk=pk)
        except Ventas.DoesNotExist:
            messages.error(request, 'Venta no encontrada.')
            return redirect('black_invoices:venta_list')
        
        # Verificar si la venta puede ser modificada
        if venta.status.vent_cancelada:
            messages.error(request, 'No se puede modificar una venta cancelada.')
            return redirect('black_invoices:venta_detail', pk=pk)

        # Obtener tasa de cambio actual
        tasa_actual = TasaCambio.get_tasa_actual()
        
        # Obtener datos actuales de la venta
        cliente_actual = None
        metodo_pago_actual = None
        
        if venta.factura:
            cliente_actual = venta.factura.cliente
            metodo_pago_actual = venta.factura.metodo_pag
        elif venta.nota_entrega:
            cliente_actual = venta.nota_entrega.cliente
            metodo_pago_actual = 'credito'  # Las notas de entrega son siempre a crédito

        # ✅ OBTENER PRODUCTOS DE LA VENTA CORREGIDO
        productos_actuales = []
        
        if venta.factura:
            detalles = venta.factura.detallefactura_set.all()
            print(f"DEBUG: Factura tiene {detalles.count()} detalles")
            
            for detalle in detalles:
                # Restaurar stock temporal para mostrar correctamente
                stock_mostrado = detalle.producto.stock + int(detalle.cantidad or 0)
                
                producto_data = {
                    'id': detalle.producto.id,
                    'nombre': detalle.producto.nombre,
                    'cantidad': float(detalle.cantidad or 0),
                    'precio': float(detalle.producto.precio or 0),
                    'stock': stock_mostrado,  # Stock + cantidad actual para edición
                    'subtotal': float(detalle.sub_total or 0)
                }
                productos_actuales.append(producto_data)
                print(f"DEBUG: Producto agregado de factura: {producto_data}")
                
        elif venta.nota_entrega:
            detalles = venta.nota_entrega.detalles_nota.all()
            print(f"DEBUG: Nota tiene {detalles.count()} detalles")
            
            for detalle in detalles:
                # Restaurar stock temporal para mostrar correctamente
                stock_mostrado = detalle.producto.stock + int(detalle.cantidad or 0)
                
                producto_data = {
                    'id': detalle.producto.id,
                    'nombre': detalle.producto.nombre,
                    'cantidad': float(detalle.cantidad or 0),
                    'precio': float(detalle.precio_unitario or 0),
                    'stock': stock_mostrado,  # Stock + cantidad actual para edición
                    'subtotal': float(detalle.subtotal_linea or 0)
                }
                productos_actuales.append(producto_data)
                print(f"DEBUG: Producto agregado de nota: {producto_data}")
        else:
            print("DEBUG: La venta no tiene ni factura ni nota de entrega")
            
        print(f"DEBUG: Total productos encontrados: {len(productos_actuales)}")
        
        # Serializar productos para JavaScript con protección
        try:
            productos_json = json.dumps(productos_actuales, cls=DecimalEncoder)
            # Test de parsing para validar JSON
            json.loads(productos_json)
            print(f"DEBUG: JSON generado correctamente")
            productos_json_seguro = productos_json
        except Exception as e:
            print(f"ERROR: Falló serialización JSON: {e}")
            # Fallback seguro
            productos_json_seguro = "[]"
        
        # ✅ PREPARAR PRODUCTOS PARA RENDERIZADO DIRECTO EN TEMPLATE
        productos_de_la_venta = []
        for producto_data in productos_actuales:
            productos_de_la_venta.append({
                'id': producto_data['id'],
                'nombre': producto_data['nombre'],
                'cantidad': producto_data['cantidad'],  # ✅ Cantidad correcta
                'precio': producto_data['precio'],
                'stock': producto_data['stock'],
                'subtotal': producto_data['subtotal']
            })
        
        print(f"DEBUG GET: productos_de_la_venta preparados: {len(productos_de_la_venta)} items")
        print(f"DEBUG GET: Ejemplo producto 0: {productos_de_la_venta[0] if productos_de_la_venta else 'Sin productos'}")

        context = {
            'titulo': f'Modificar Venta #{venta.id}',
            'venta': venta,
            'cliente_actual': cliente_actual,
            'metodo_pago_actual': metodo_pago_actual,
            'clientes': Cliente.objects.all(),
            'productos_de_la_venta': productos_de_la_venta,  # Para renderizado directo
            'productos': Producto.objects.filter(activo=True),
            'productos_actuales': productos_json_seguro,  # JSON para JavaScript
            'tipos_venta': [
                {'id': 'contado', 'nombre': 'Contado'},
                {'id': 'credito', 'nombre': 'Crédito'}
            ],
            'metodos_pago': [
                {'id': 'efectivo', 'nombre': 'Efectivo'},
                {'id': 'tarjeta', 'nombre': 'Tarjeta'},
                {'id': 'transferencia', 'nombre': 'Transferencia'},
                {'id': 'credito', 'nombre': 'Crédito'},
                {'id': 'otro', 'nombre': 'Otro'}
            ],
            'tasa_cambio': tasa_actual.tasa_usd_ves if tasa_actual else 1
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        try:
            with transaction.atomic():
                venta = Ventas.objects.get(pk=pk)
                
                # Verificar si la venta puede ser modificada
                if venta.status.vent_cancelada:
                    messages.error(request, 'No se puede modificar una venta cancelada.')
                    return redirect('black_invoices:venta_detail', pk=pk)
                
                # Verificar que el usuario tenga empleado asociado
                if not hasattr(request.user, 'empleado'):
                    messages.error(request, 'No tienes un perfil de empleado asociado.')
                    return redirect('black_invoices:venta_detail', pk=pk)

                # Guardar estado anterior para auditoría
                estado_anterior = self._capturar_estado_venta(venta)
                
                # Obtener datos del formulario
                cliente_id = request.POST.get('cliente')
                metodo_pago = request.POST.get('metodo_pag')
                tipo_venta = request.POST.get('tipo_venta')
                
                if not cliente_id:
                    messages.error(request, 'Debe seleccionar un cliente.')
                    return redirect('black_invoices:venta_update', pk=pk)

                # ✅ RECOPILAR PRODUCTOS NUEVOS DEL FORMULARIO - MEJORADO CON DEBUG
                productos_nuevos = []
                
                # Método más robusto para recopilar productos
                print("DEBUG POST: Recopilando productos del formulario...")
                print("DEBUG POST: Claves POST:", list(request.POST.keys()))
                
                # Buscar todos los campos que sigan el patrón productos[X][campo]
                productos_dict = {}
                
                for key, value in request.POST.items():
                    if key.startswith('productos[') and '][' in key:
                        # Extraer índice y campo: productos[0][id] -> índice=0, campo=id
                        try:
                            # Ejemplo: productos[0][id] -> ['productos', '0', 'id']
                            parts = key.replace('[', '|').replace(']', '').split('|')
                            if len(parts) >= 3:
                                indice = int(parts[1])
                                campo = parts[2]
                                
                                if indice not in productos_dict:
                                    productos_dict[indice] = {}
                                    
                                productos_dict[indice][campo] = value
                                print(f"DEBUG POST: productos[{indice}][{campo}] = {value}")
                        except (ValueError, IndexError) as e:
                            print(f"DEBUG POST: Error procesando {key}: {e}")
                            continue
                
                print(f"DEBUG POST: productos_dict completo: {productos_dict}")
                
                # Convertir dict a lista y validar
                for indice in sorted(productos_dict.keys()):
                    prod_data = productos_dict[indice]
                    
                    try:
                        producto_id = prod_data.get('id')
                        cantidad_str = prod_data.get('cantidad', '0')
                        precio_str = prod_data.get('precio', '0')
                        
                        print(f"DEBUG POST: Procesando índice {indice} - ID: {producto_id}, Cantidad: {cantidad_str}, Precio: {precio_str}")
                        
                        # Validar que producto_id no esté vacío
                        if not producto_id or producto_id == '':
                            print(f"DEBUG POST: Producto {indice} sin ID, ignorando")
                            continue
                        
                        producto_id = int(producto_id)
                        
                        # ✅ NORMALIZAR FORMATO: Reemplazar comas por puntos antes de convertir a float
                        cantidad_str = cantidad_str.replace(',', '.')
                        precio_str = precio_str.replace(',', '.')
                        
                        cantidad = float(cantidad_str) if cantidad_str else 0
                        precio = float(precio_str) if precio_str else 0
                        
                        if producto_id > 0 and cantidad > 0:
                            productos_nuevos.append({
                                'id': producto_id,
                                'cantidad': cantidad,
                                'precio': precio
                            })
                            print(f"DEBUG POST: ✅ Producto válido agregado: ID={producto_id}, Cant={cantidad}, Precio={precio}")
                        else:
                            print(f"DEBUG POST: ⚠️ Producto inválido - ID: {producto_id}, Cantidad: {cantidad}")
                            
                    except (ValueError, TypeError) as e:
                        print(f"DEBUG POST: ❌ Error procesando producto {indice}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                print(f"DEBUG POST: Total productos nuevos recopilados: {len(productos_nuevos)}")
                print(f"DEBUG POST: Productos nuevos: {productos_nuevos}")
                
                if not productos_nuevos:
                    print("DEBUG POST: ❌ ERROR - No se encontraron productos válidos")
                    messages.error(request, 'Debe agregar al menos un producto a la venta.')
                    return redirect('black_invoices:venta_update', pk=pk)

                # Calcular cambios en stock
                detalles_anteriores = self._obtener_detalles_anteriores(venta)
                detalles_nuevos = {str(prod['id']): prod['cantidad'] for prod in productos_nuevos}
                
                print(f"DEBUG POST: Detalles anteriores: {detalles_anteriores}")
                print(f"DEBUG POST: Detalles nuevos: {detalles_nuevos}")
                
                # Validar y actualizar stock
                venta.actualizar_stock_inteligente(detalles_anteriores, detalles_nuevos)
                
                # Determinar tipo de venta
                cliente = Cliente.objects.get(pk=cliente_id)
                es_credito = tipo_venta == 'credito'
                
                # Actualizar la venta según el tipo
                if es_credito:
                    # Crear o actualizar nota de entrega
                    nota_entrega = self._actualizar_nota_entrega(venta, cliente, productos_nuevos)
                    
                    # Actualizar venta
                    venta.credito = True
                    venta.factura = None
                    venta.nota_entrega = nota_entrega
                    venta.monto_pagado = 0
                    
                    # Establecer estado pendiente
                    estado_pendiente, _ = StatusVentas.objects.get_or_create(
                        nombre="Pendiente",
                        defaults={'vent_espera': True, 'vent_cancelada': False}
                    )
                    venta.status = estado_pendiente
                else:
                    # Crear o actualizar factura
                    factura = self._actualizar_factura(venta, cliente, metodo_pago, productos_nuevos)
                    
                    # Actualizar venta
                    venta.credito = False
                    venta.factura = factura
                    venta.nota_entrega = None
                    venta.monto_pagado = factura.total_fac
                    
                    # Establecer estado completado
                    estado_completado, _ = StatusVentas.objects.get_or_create(
                        nombre="Completada",
                        defaults={'vent_espera': False, 'vent_cancelada': False}
                    )
                    venta.status = estado_completado
                
                venta.save()
                
                # Recrear registros de ganancia
                venta.crear_registros_ganancia()
                
                # Registrar cambio en historial
                estado_nuevo = self._capturar_estado_venta(venta)
                self._crear_registro_historial(venta, estado_anterior, estado_nuevo, request.user)
                
                messages.success(request, f'Venta #{venta.id} modificada exitosamente.')
                return redirect('black_invoices:venta_detail', pk=venta.id)

        except Exception as e:
            print(f"ERROR POST: Error al modificar la venta: {str(e)}")
            messages.error(request, f"Error al modificar la venta: {str(e)}")
            return redirect('black_invoices:venta_update', pk=pk)
    
    def _obtener_detalles_anteriores(self, venta):
        """Obtiene los productos y cantidades actuales de la venta"""
        detalles = {}
        if venta.factura:
            for detalle in venta.factura.detallefactura_set.all():
                detalles[str(detalle.producto.id)] = float(detalle.cantidad)
        elif venta.nota_entrega:
            for detalle in venta.nota_entrega.detalles_nota.all():
                detalles[str(detalle.producto.id)] = float(detalle.cantidad)
        return detalles
    
    def _actualizar_factura(self, venta, cliente, metodo_pago, productos):
        """Crea o actualiza la factura de la venta"""
        # Eliminar factura anterior si existe
        if venta.factura:
            venta.factura.delete()
        
        # Crear nueva factura
        factura = Factura.objects.create(
            cliente=cliente,
            empleado=venta.empleado,
            metodo_pag=metodo_pago
        )
        
        # Crear detalles
        tipo_factura, _ = TipoFactura.objects.get_or_create(
            contado_fac=True,
            defaults={'credito_fac': False}
        )
        
        for prod in productos:
            producto = Producto.objects.get(pk=prod['id'])
            # ✅ CONVERTIR CANTIDAD A DECIMAL
            cantidad_decimal = Decimal(str(prod['cantidad']))
            
            DetalleFactura.objects.create(
                factura=factura,
                tipo_factura=tipo_factura,
                producto=producto,
                cantidad=cantidad_decimal,
                sub_total=producto.precio * cantidad_decimal
            )
        
        # Calcular totales
        factura.calcular_total_mejorado()
        
        return factura
    
    def _actualizar_nota_entrega(self, venta, cliente, productos):
        """Crea o actualiza la nota de entrega de la venta"""
        # Eliminar nota anterior si existe
        if venta.nota_entrega:
            venta.nota_entrega.delete()
        
        # Crear nueva nota de entrega
        config = ConfiguracionSistema.get_config()
        nota = NotaEntrega.objects.create(
            numero_nota=config.get_siguiente_numero_nota_entrega(),
            cliente=cliente,
            empleado=venta.empleado
        )
        
        # Crear detalles
        for prod in productos:
            producto = Producto.objects.get(pk=prod['id'])
            # ✅ CONVERTIR CANTIDAD A DECIMAL
            cantidad_decimal = Decimal(str(prod['cantidad']))
            
            DetalleNotaEntrega.objects.create(
                nota_entrega=nota,
                producto=producto,
                cantidad=cantidad_decimal,
                precio_unitario=producto.precio,
                subtotal_linea=cantidad_decimal * producto.precio  # ✅ CALCULAR SUBTOTAL MANUALMENTE
            )
        
        # Calcular totales
        nota.calcular_totales()
        
        return nota
    
    def _capturar_estado_venta(self, venta):
        """Captura el estado actual de la venta para auditoría"""
        cliente_id = None
        if venta.factura:
            cliente_id = venta.factura.cliente.id
        elif venta.nota_entrega:
            cliente_id = venta.nota_entrega.cliente.id
            
        estado = {
            'cliente_id': cliente_id,
            'tipo_venta': 'credito' if venta.credito else 'contado',
            'total_venta': float(venta.total_venta),
            'productos': []
        }
        
        if venta.factura:
            estado['metodo_pago'] = venta.factura.metodo_pag
            for detalle in venta.factura.detallefactura_set.all():
                estado['productos'].append({
                    'producto_id': detalle.producto.id,
                    'cantidad': float(detalle.cantidad),
                    'precio': float(detalle.producto.precio)
                })
        elif venta.nota_entrega:
            for detalle in venta.nota_entrega.detalles_nota.all():
                estado['productos'].append({
                    'producto_id': detalle.producto.id,
                    'cantidad': float(detalle.cantidad),
                    'precio': float(detalle.precio_unitario)
                })
        
        return estado
    
    def _crear_registro_historial(self, venta, estado_anterior, estado_nuevo, usuario):
        """Crea el registro de historial de modificación"""
        descripcion = "Venta modificada: "
        cambios = []
        
        if estado_anterior.get('cliente_id') != estado_nuevo.get('cliente_id'):
            cambios.append("cliente")
        if estado_anterior.get('tipo_venta') != estado_nuevo.get('tipo_venta'):
            cambios.append("tipo de venta")
        if estado_anterior.get('metodo_pago') != estado_nuevo.get('metodo_pago'):
            cambios.append("método de pago")
        if estado_anterior.get('productos') != estado_nuevo.get('productos'):
            cambios.append("productos")
        
        descripcion += ", ".join(cambios)
        
        # Solo crear el registro si existe el modelo VentaHistorial
        try:
            VentaHistorial.objects.create(
                venta=venta,
                usuario_modificacion=usuario,
                tipo_modificacion='completa',
                descripcion=descripcion,
                datos_anteriores=estado_anterior,
                datos_nuevos=estado_nuevo
            )
        except NameError:
            # Si no existe el modelo VentaHistorial, simplemente registrar en log
            print(f"HISTORIAL: {descripcion} por {usuario.username}")
class ReporteGananciasView(LoginRequiredMixin, TemplateView):
    """Vista para reportes detallados de ganancias"""
    template_name = 'black_invoices/reportes/ganancias_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Reporte de Ganancias'
        
        # Fechas para filtros
        hoy = datetime.now().date()
        inicio_mes = hoy.replace(day=1)
        inicio_anio = hoy.replace(month=1, day=1)
        
        # Parámetros de filtro desde GET
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        
        if fecha_inicio:
            try:
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            except ValueError:
                fecha_inicio = inicio_mes
        else:
            fecha_inicio = inicio_mes
            
        if fecha_fin:
            try:
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            except ValueError:
                fecha_fin = hoy
        else:
            fecha_fin = hoy
        
        context['fecha_inicio'] = fecha_inicio
        context['fecha_fin'] = fecha_fin
        
        # Ganancias por producto en el período
        context['ganancias_por_producto'] = DetalleGanancia.get_ganancias_por_producto(
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, limit=50
        )
        
        # Resumen de ganancias
        context['total_ganancias_realizadas'] = DetalleGanancia.get_ganancias_realizadas(
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )
        
        context['total_ganancias_pendientes'] = DetalleGanancia.get_ganancias_pendientes(
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )
        
        context['total_ganancias_combinadas'] = (
            context['total_ganancias_realizadas'] + context['total_ganancias_pendientes']
        )
        
        # Estadísticas por tipo de venta
        ganancias_contado = DetalleGanancia.objects.filter(
            fecha_venta__gte=fecha_inicio,
            fecha_venta__lte=fecha_fin,
            venta__credito=False,
            venta__status__vent_cancelada=False
        ).aggregate(total=Sum('ganancia_total'))['total'] or 0
        
        ganancias_credito = DetalleGanancia.objects.filter(
            fecha_venta__gte=fecha_inicio,
            fecha_venta__lte=fecha_fin,
            venta__credito=True,
            venta__status__vent_cancelada=False
        ).aggregate(total=Sum('ganancia_total'))['total'] or 0
        
        context['ganancias_contado'] = ganancias_contado
        context['ganancias_credito'] = ganancias_credito
        
        # Ganancias por empleado
        ganancias_por_empleado = DetalleGanancia.objects.filter(
            fecha_venta__gte=fecha_inicio,
            fecha_venta__lte=fecha_fin,
            venta__status__vent_cancelada=False
        ).values(
            'venta__empleado__nombre',
            'venta__empleado__apellido'
        ).annotate(
            total_ganancia=Sum('ganancia_total'),
            total_ventas=Count('venta', distinct=True),
            margen_promedio=Avg('margen_porcentaje')
        ).order_by('-total_ganancia')
        
        context['ganancias_por_empleado'] = ganancias_por_empleado
        
        return context

class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Empleado
    form_class = UserProfileForm
    template_name = 'black_invoices/usuarios/perfil_form.html' # Nueva plantilla
    success_url = reverse_lazy('black_invoices:perfil_usuario_editar') # Redirige a la misma página

    def get_object(self, queryset=None):
        # Devuelve la instancia de Empleado asociada al usuario logueado.
        # get_object_or_404 es más seguro aquí.
        return get_object_or_404(Empleado, user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Configurar Mi Perfil'
        context['action_text'] = 'Guardar Cambios'
        return context

    def form_valid(self, form):
        # El método save del UserProfileForm ya maneja la actualización de User y Empleado.
        form.save()
        messages.success(self.request, 'Tu perfil ha sido actualizado exitosamente.')
        return super().form_valid(form) # Esto redirigirá a success_url

    def form_invalid(self, form):
        # Construir un mensaje de error más detallado para mostrar todos los errores
        error_list_html = "<ul>"
        for field, errors in form.errors.items():
            field_label = form.fields[field].label if field != '__all__' and field in form.fields else "Error general"
            for error in errors:
                error_list_html += f"<li><strong>{field_label}:</strong> {error}</li>"
        if form.non_field_errors():
             for error in form.non_field_errors():
                error_list_html += f"<li><strong>Error general:</strong> {error}</li>"
        error_list_html += "</ul>"

        messages.error(self.request, f"Error al actualizar el perfil. Por favor, corrija los problemas indicados:{error_list_html}", extra_tags='safe')
        return super().form_invalid(form)

def logout_view(request):
    logout(request)
    return redirect('black_invoices:login')


def ingresar(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('black_invoices:inicio')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')

    return render(request, 'black_invoices/usuarios/login.html')

#################    PDF    ######################
""" class FacturaPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            factura = Factura.objects.get(pk=pk)
        except Factura.DoesNotExist:
            return HttpResponse("Factura no encontrada", status=404)

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # --- Membrete y Logo ---
        logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/logo2.png')
        if os.path.exists(logo_path):
            p.drawImage(logo_path, - 40, height - 180, width=320, height=150, preserveAspectRatio=True, mask='auto')

        # Obtener información de la empresa desde configuración
        config = ConfiguracionSistema.get_config()

        # Nombre de la empresa
        p.setFont("Helvetica-Bold", 12)
        p.drawString(180, height - 50, config.nombre_empresa)

        # RIF
        p.setFont("Helvetica-Bold", 11)
        p.drawString(180, height - 65, f"RIF: {config.rif_empresa}")

        # Dirección y teléfonos
        p.setFont("Helvetica", 10)
        p.drawString(180, height - 80, "Vda. 18 Casa Nro 48 Urb. Francisco de Miranda")
        p.drawString(180, height - 95, "Telf: 0424-5439427 / 0424-5874882 / 0257-2532558")
        p.drawString(180, height - 110, "Guanare Edo. Portuguesa")

        # --- Datos generales ---
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, height - 130, "NOTA DE ENTREGA")
        p.setFont("Helvetica", 10)
        fecha_impresion = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        p.drawString(400, height - 130, f"Fecha impresión: {fecha_impresion}")
        p.drawString(400, height - 145, f"Nº Control: {factura.id:06d}")
        p.drawString(400, height - 160, f"Fecha: {factura.fecha_fac.strftime('%d-%m-%Y %H:%M')}")
        p.setFont("Helvetica-Bold", 10)
        p.drawString(400, height - 175, f"VENDEDOR: {factura.empleado.nombre_completo}")
        p.setFont("Helvetica", 10)
        p.drawString(400, height - 190, f"CONDICIÓN: {factura.get_metodo_pag_display()}")

        # --- Datos del cliente ---
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, height - 160, f"CLIENTE:")
        p.setFont("Helvetica", 10)
        p.drawString(50, height - 175, f"TLF: {factura.cliente.telefono}")
        p.drawString(50, height - 190, f"NOMBRE: {factura.cliente.nombre_completo}")
        p.drawString(50, height - 205, f"DIRECCIÓN FISCAL: {factura.cliente.direccion}")

        # --- Tabla de productos ---
        detalles = factura.detallefactura_set.all()
        data = [["#", "Código", "Producto", "Cant.", "Garantía", "Precio", "Desc.", "Total"]]

        for idx, detalle in enumerate(detalles, 1):
            codigo = str(detalle.producto.id)  # Mostrar el id del producto
            data.append([
                str(idx),
                codigo,
                detalle.producto.nombre,
                str(detalle.cantidad),
                "Sí",  # Presentación (añadido según imagen)
                f"{detalle.producto.precio:,.2f}",
                "0,00",  # Descuento
                f"{detalle.sub_total:,.2f}"
            ])

        # Añadir solo una fila vacía para mantener el espacio
        if len(data) < 3:  # Si solo tenemos el encabezado y un producto
            data.append(["", "", "", "", "", "", "", ""])  # Solo una fila vacía

        # Añadir fila de totales
        data.append(["", "", "", "", "", "", "TOTAL", f"{factura.total_fac:,.2f}"])

        # Crear tabla con 8 columnas (añadimos Presen.)
        table = Table(data, colWidths=[25, 60, 160, 40, 50, 60, 50, 60])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.black),  # Grid para todas las filas excepto la última
            ('LINEABOVE', (6, -1), (7, -1), 0.5, colors.black),  # Línea solo arriba de "TOTAL" y su valor
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (3, 1), (7, -1), 'RIGHT'),  # Alinear a la derecha desde Cant. hasta Total
            ('FONTNAME', (6, -1), (7, -1), 'Helvetica-Bold'),  # Negrita para "TOTAL" y su valor
        ]))

        table.wrapOn(p, width, height)
        table.drawOn(p, 40, height - 320 - 20 * min(len(data), 6))  # Ajustar altura según número de filas

        # --- Sección de descuentos (como en la imagen 2) ---
        p.setFont("Helvetica", 8)
        p.drawString(430, 130, "DESC. POR PRODUCTOS")
        p.drawString(550, 130, "0,00 BS")
        p.drawString(430, 120, "DESC. (30.00)")
        p.drawString(550, 120, "0,00 BS")

        # Línea horizontal debajo de descuentos
        p.line(430, 115, 580, 115)

        # Total general
        p.setFont("Helvetica-Bold", 9)
        p.drawString(430, 100, "TOTAL")
        p.drawString(550, 100, f"{factura.total_fac:,.2f} BS")

        # --- Nota y pie de página ---
        # Nota completa con saltos de línea adecuados
        p.setFont("Helvetica", 8)
        nota = "NO SE ACEPTAN PAGOS DE DIVISAS EN EFECTIVO HECHOS AL ASESOR DE VENTA NI AL SUPERVISOR, ASÍ COMO TAMPOCO BS EN EFECTIVO, PAGO MÓVIL O TRANSFERENCIAS A LAS CUENTAS PERSONALES DEL ASESOR O DEL SUPERVISOR. SOLO SE RECONOCERÁN LOS PAGOS HECHOS A LAS CUENTAS DE LA EMPRESA."

        # Dividir nota en líneas de máximo 100 caracteres
        nota_lineas = []
        for i in range(0, len(nota), 100):
            nota_lineas.append(nota[i:i+100])

        # Dibujar cada línea de la nota
        for i, linea in enumerate(nota_lineas):
            p.drawString(40, 80 - (i * 10), linea)

        # Referencias y tasa de cambio
        # p.drawString(40, 50, f"REFERENCIA: {getattr(factura, 'referencia', '')}")
        # p.drawString(200, 50, f"T.C.: {getattr(factura, 'tasa_cambio', '---')}")

        # Paginación (ajustada para no sobreponerse)
        p.drawString(470, 30, f"Página 1 de 1")

        # Footer
        p.setFont("Helvetica", 8)
        p.drawString(40, 30, f"{config.nombre_empresa} - Todos los derechos reservados")

        p.showPage()
        p.save()
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Recibo_Venta_{factura.id}.pdf"'
        return response

class NotaEntregaPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            nota = NotaEntrega.objects.get(pk=pk)
        except NotaEntrega.DoesNotExist:
            return HttpResponse("Nota de Entrega no encontrada", status=404)

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # --- Membrete y Logo ---
        logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/logo2.png')
        if os.path.exists(logo_path):
            p.drawImage(logo_path, -40, height - 180, width=320, height=150, preserveAspectRatio=True, mask='auto')

        # Obtener información de la empresa desde configuración
        config = ConfiguracionSistema.get_config()

        # Información de empresa
        p.setFont("Helvetica-Bold", 12)
        p.drawString(180, height - 50, config.nombre_empresa)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(180, height - 65, f"RIF: {config.rif_empresa}")
        p.setFont("Helvetica", 10)
        p.drawString(180, height - 80, "Vda. 18 Casa Nro 48 Urb. Francisco de Miranda")
        p.drawString(180, height - 95, "Telf: 0424-5439427 / 0424-5874882 / 0257-2532558")
        p.drawString(180, height - 110, "Guanare Edo. Portuguesa")

        # --- Datos generales ---
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, height - 130, "NOTA DE ENTREGA")
        p.setFont("Helvetica", 10)
        fecha_impresion = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        p.drawString(400, height - 130, f"Fecha impresión: {fecha_impresion}")
        p.drawString(400, height - 145, f"Nº Nota: {nota.numero_nota:06d}")
        p.drawString(400, height - 160, f"Fecha: {nota.fecha_nota.strftime('%d-%m-%Y %H:%M')}")
        p.setFont("Helvetica-Bold", 10)
        p.drawString(400, height - 175, f"VENDEDOR: {nota.empleado.nombre_completo}")

        # --- Datos del cliente ---
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, height - 160, f"CLIENTE:")
        p.setFont("Helvetica", 10)
        p.drawString(50, height - 175, f"TLF: {nota.cliente.telefono}")
        p.drawString(50, height - 190, f"NOMBRE: {nota.cliente.nombre_completo}")
        p.drawString(50, height - 205, f"DIRECCIÓN: {nota.cliente.direccion}")

        # --- Tabla de productos ---
        detalles = nota.detalles_nota.all()
        data = [["#", "Código", "Producto", "Cant.", "Unidad", "Precio", "Total"]]

        for idx, detalle in enumerate(detalles, 1):
            codigo = detalle.producto.sku or str(detalle.producto.id)
            unidad = detalle.producto.unidad_medida.abreviatura if detalle.producto.unidad_medida else "UN"
            data.append([
                str(idx),
                codigo,
                detalle.producto.nombre,
                str(detalle.cantidad),
                unidad,
                f"${detalle.precio_unitario:,.2f}",
                f"${detalle.subtotal_linea:,.2f}"
            ])

        # Fila de totales
        data.append(["", "", "", "", "", "TOTAL", f"${nota.total:,.2f}"])

        # Crear tabla
        table = Table(data, colWidths=[25, 60, 180, 40, 40, 60, 60])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
            ('LINEABOVE', (5, -1), (6, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (3, 1), (6, -1), 'RIGHT'),
            ('FONTNAME', (5, -1), (6, -1), 'Helvetica-Bold'),
        ]))

        table.wrapOn(p, width, height)
        table.drawOn(p, 40, height - 350)

        # --- Nota importante ---
        p.setFont("Helvetica", 8)
        nota_texto = "NOTA IMPORTANTE: Este documento es una NOTA DE ENTREGA. La Factura Fiscal se generará al completar el pago."
        p.drawString(40, 100, nota_texto)

        # Footer
        p.setFont("Helvetica", 8)
        p.drawString(40, 30, f"{config.nombre_empresa} - Sistema de Ventas")

        p.showPage()
        p.save()
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Nota_Entrega_{nota.numero_nota}.pdf"'
        return response  """

class FacturaPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            factura = Factura.objects.get(pk=pk)
        except Factura.DoesNotExist:
            return HttpResponse("Factura no encontrada", status=404)

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Obtener información de la empresa desde configuración
        config = ConfiguracionSistema.get_config()
        tasa_actual = TasaCambio.get_tasa_actual()
        tasa_usd_ves = tasa_actual.tasa_usd_ves if tasa_actual else Decimal('1.0')

        def draw_header(page_num, total_pages):
            """Dibuja el header en cada página"""
            # --- Membrete y Logo ---
            logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/logo2.png')
            if os.path.exists(logo_path):
                p.drawImage(logo_path, -40, height - 140, width=290, height=120, preserveAspectRatio=True, mask='auto')

            # Información de empresa
            p.setFont("Helvetica-Bold", 12)
            p.drawString(180, height - 50, config.nombre_empresa)
            p.setFont("Helvetica-Bold", 11)
            p.drawString(180, height - 65, f"RIF: {config.rif_empresa}")
            p.setFont("Helvetica", 10)
            p.drawString(180, height - 80, "Vda. 18 Casa Nro 48 Urb. Francisco de Miranda")
            p.drawString(180, height - 95, "Telf: 0424-5439427 / 0424-5874882 / 0257-2532558")
            p.drawString(180, height - 110, "Guanare Edo. Portuguesa")

            # --- Datos generales ---
            p.setFont("Helvetica-Bold", 13)
            p.drawString(50, height - 140, f"FACTURA FISCAL Nº: {factura.numero_factura:04d}")
            p.setFont("Helvetica", 10)
            fecha_impresion = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            p.drawString(400, height - 140, f"Fecha impresión: {fecha_impresion}")
            p.drawString(400, height - 155, f"Nº Control: {factura.id:04d}")
            p.drawString(400, height - 170, f"Fecha: {factura.fecha_fac.strftime('%d-%m-%Y %H:%M')}")
            p.setFont("Helvetica-Bold", 10)
            p.drawString(400, height - 185, f"VENDEDOR: {factura.empleado.nombre_completo}")
            p.setFont("Helvetica", 10)
            p.drawString(400, height - 200, f"CONDICIÓN: {factura.get_metodo_pag_display()}")

            # --- Datos del cliente (solo en primera página) ---
            if page_num == 1:
                p.setFont("Helvetica-Bold", 10)
                p.drawString(50, height - 170, f"CLIENTE:")
                p.setFont("Helvetica", 10)
                p.drawString(50, height - 185, f"TLF: {factura.cliente.telefono}")
                p.drawString(50, height - 200, f"NOMBRE: {factura.cliente.nombre_completo}")
                p.drawString(50, height - 215, f"DIRECCIÓN FISCAL: {factura.cliente.direccion}")

        def draw_table_header():
            """Retorna el header de la tabla como lista"""
            return ["#", "Código", "Producto", "Cant.", "Garantía", "Precio", "Precio Bs", "Total"]

        # --- Preparar datos de productos ---
        detalles = factura.detallefactura_set.all()
        productos_data = []

        for idx, detalle in enumerate(detalles, 1):
            codigo = str(detalle.producto.id)
            precio_bs = detalle.producto.precio * tasa_usd_ves
            
            productos_data.append([
                str(idx),
                codigo,
                detalle.producto.nombre[:25] + "..." if len(detalle.producto.nombre) > 28 else detalle.producto.nombre,
                str(detalle.cantidad),
                "Sí",
                f"${detalle.producto.precio:,.2f}",
                f"{precio_bs:,.2f}",
                f"${detalle.sub_total:,.2f}"
            ])

        # --- Calcular paginación CON MÁS ESPACIO RESERVADO ---
        # Espacio disponible para tabla en primera página (después del header completo)
        first_page_table_start = height - 240
        # RESERVAR MÁS ESPACIO para totales, notas y footer (220 puntos en lugar de 150)
        first_page_available_space = first_page_table_start - 220
        
        # Espacio disponible en páginas subsecuentes (solo header básico)
        other_pages_table_start = height - 230  # Aumentado de 200 a 230 para dar más espacio
        # RESERVAR ESPACIO para footer (100 puntos para asegurar que no se superponga)
        other_pages_available_space = other_pages_table_start - 100
        
        # Altura aproximada por fila (incluyendo padding)
        row_height = 14  # Un poco más de espacio por fila
        header_height = 25  # Más espacio para el header
        
        # Calcular filas por página (MÁS CONSERVADOR)
        first_page_max_rows = int((first_page_available_space - header_height) / row_height)
        other_pages_max_rows = int((other_pages_available_space - header_height) / row_height)
        
        # Límites estrictos para evitar superposición
        first_page_max_rows = max(6, min(first_page_max_rows, 18))  # Máximo 10 productos en primera página
        other_pages_max_rows = max(10, min(other_pages_max_rows, 18))  # Máximo 15 en otras páginas

        # --- Dividir productos en páginas ---
        product_pages = []
        current_index = 0
        
        # Primera página
        if productos_data:
            first_page_products = productos_data[:first_page_max_rows]
            product_pages.append(first_page_products)
            current_index = first_page_max_rows
            
            # Páginas subsecuentes
            while current_index < len(productos_data):
                next_page_products = productos_data[current_index:current_index + other_pages_max_rows]
                product_pages.append(next_page_products)
                current_index += other_pages_max_rows

        total_pages = len(product_pages) if product_pages else 1

        # --- Generar páginas ---
        for page_num, page_products in enumerate(product_pages, 1):
            # Dibujar header
            draw_header(page_num, total_pages)
            
            # Preparar datos de la tabla para esta página
            table_data = [draw_table_header()]
            table_data.extend(page_products)
            
            # Solo añadir fila de totales en la última página
            is_last_page = page_num == len(product_pages)
            if is_last_page:
                table_data.append(["", "", "", "", "", "", "TOTAL", f"${factura.total_fac:,.2f}"])
            
            # Crear y configurar tabla
            table = Table(table_data, colWidths=[25, 60, 140, 40, 50, 60, 60, 60])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -2 if is_last_page else -1), 0.5, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (3, 1), (6, -1), 'RIGHT'),
            ]))
            
            if is_last_page:
                table.setStyle(TableStyle([
                    ('LINEABOVE', (5, -1), (6, -1), 0.5, colors.black),
                    ('FONTNAME', (5, -1), (6, -1), 'Helvetica-Bold'),
                ], add=True))
            
            # Posición de la tabla según la página
            if page_num == 1:
                table_y = first_page_table_start
            else:
                table_y = other_pages_table_start
            
            # Dibujar tabla
            table.wrapOn(p, width, height)
            table_width, table_height = table.wrap(width, height)
            table.drawOn(p, 40, table_y - table_height)
            
            # Solo dibujar totales y notas en la última página
            if is_last_page:
                # Calcular posición para totales
                totals_y = table_y - table_height - 40  # Más separación
                
                # Verificar que hay espacio suficiente para totales
                if totals_y > 120:  # Necesitamos al menos 120 puntos para totales + footer
                    # --- Sección de totales ---
                    p.setFont("Helvetica", 8)
                    subtotal_bs = factura.subtotal * tasa_usd_ves
                    iva_bs = factura.iva * tasa_usd_ves
                    total_bs = factura.total_fac * tasa_usd_ves

                    # Subtotal
                    p.drawString(430, totals_y, "SUBTOTAL")
                    p.drawString(500, totals_y, f"${factura.subtotal:,.2f}")
                    p.drawString(550, totals_y, f"{subtotal_bs:,.2f} Bs")

                    # IVA
                    p.drawString(430, totals_y - 10, f"IVA ({config.porcentaje_iva}%)")
                    p.drawString(500, totals_y - 10, f"${factura.iva:,.2f}")
                    p.drawString(550, totals_y - 10, f"{iva_bs:,.2f} Bs")

                    # Línea horizontal
                    p.line(430, totals_y - 15, 580, totals_y - 15)

                    # Total general
                    p.setFont("Helvetica-Bold", 9)
                    p.drawString(430, totals_y - 30, "TOTAL")
                    p.drawString(500, totals_y - 30, f"${factura.total_fac:,.2f}")
                    p.drawString(550, totals_y - 30, f"{total_bs:,.2f} Bs")

                    # --- Nota importante ---
                    notes_y = totals_y - 70
                    if notes_y > 80:  # Solo si hay espacio suficiente
                        p.setFont("Helvetica", 8)
                        nota = "NOTA: NO SE ACEPTAN PAGOS DE DIVISAS EN EFECTIVO HECHOS AL ASESOR DE VENTA NI AL SUPERVISOR, ASÍ COMO TAMPOCO BS EN EFECTIVO, PAGO MÓVIL O TRANSFERENCIAS A LAS CUENTAS PERSONALES DEL ASESOR O DEL SUPERVISOR. SOLO SE RECONOCERÁN LOS PAGOS HECHOS A LAS CUENTAS DE LA EMPRESA."
                        
                        # Dividir nota en líneas
                        nota_lineas = []
                        for i in range(0, len(nota), 100):
                            nota_lineas.append(nota[i:i+100])
                        
                        for i, linea in enumerate(nota_lineas):
                            if notes_y - (i * 10) > 60:  # Asegurar espacio para footer
                                p.drawString(40, notes_y - (i * 10), linea)
                else:
                    # Si no hay espacio, crear nueva página para totales
                    p.showPage()
                    draw_header(page_num, total_pages)  # Header en la nueva página
                    
                    # Dibujar totales en la nueva página
                    totals_y = height - 200
                    p.setFont("Helvetica", 8)
                    subtotal_bs = factura.subtotal * tasa_usd_ves
                    iva_bs = factura.iva * tasa_usd_ves
                    total_bs = factura.total_fac * tasa_usd_ves

                    # Subtotal
                    p.drawString(430, totals_y, "SUBTOTAL")
                    p.drawString(500, totals_y, f"${factura.subtotal:,.2f}")
                    p.drawString(550, totals_y, f"{subtotal_bs:,.2f} Bs")

                    # IVA
                    p.drawString(430, totals_y - 10, f"IVA ({config.porcentaje_iva}%)")
                    p.drawString(500, totals_y - 10, f"${factura.iva:,.2f}")
                    p.drawString(550, totals_y - 10, f"{iva_bs:,.2f} Bs")

                    # Línea horizontal
                    p.line(430, totals_y - 15, 580, totals_y - 15)

                    # Total general
                    p.setFont("Helvetica-Bold", 9)
                    p.drawString(430, totals_y - 30, "TOTAL")
                    p.drawString(500, totals_y - 30, f"${factura.total_fac:,.2f}")
                    p.drawString(550, totals_y - 30, f"{total_bs:,.2f} Bs")

                    # Nota
                    p.setFont("Helvetica", 8)
                    nota = "NO SE ACEPTAN PAGOS DE DIVISAS EN EFECTIVO HECHOS AL ASESOR DE VENTA NI AL SUPERVISOR, ASÍ COMO TAMPOCO BS EN EFECTIVO, PAGO MÓVIL O TRANSFERENCIAS A LAS CUENTAS PERSONALES DEL ASESOR O DEL SUPERVISOR. SOLO SE RECONOCERÁN LOS PAGOS HECHOS A LAS CUENTAS DE LA EMPRESA."
                    
                    nota_lineas = []
                    for i in range(0, len(nota), 100):
                        nota_lineas.append(nota[i:i+100])
                    
                    notes_start_y = totals_y - 70
                    for i, linea in enumerate(nota_lineas):
                        p.drawString(40, notes_start_y - (i * 10), linea)
            
            # Footer en cada página
            p.setFont("Helvetica", 8)
            p.drawString(470, 30, f"Página {page_num} de {total_pages}")
            p.drawString(40, 30, f"{config.nombre_empresa} - Todos los derechos reservados")
            
            # Nueva página si no es la última
            if page_num < len(product_pages):
                p.showPage()

        p.save()
        buffer.seek(0)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Factura_{factura.id}.pdf"'
        return response


class NotaEntregaPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            nota = NotaEntrega.objects.get(pk=pk)
        except NotaEntrega.DoesNotExist:
            return HttpResponse("Nota de Entrega no encontrada", status=404)

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Obtener información de la empresa desde configuración
        config = ConfiguracionSistema.get_config()
        tasa_actual = TasaCambio.get_tasa_actual()
        tasa_usd_ves = tasa_actual.tasa_usd_ves if tasa_actual else Decimal('1.0')

        def draw_header(page_num, total_pages):
            """Dibuja el header en cada página"""
            # --- Membrete y Logo ---
            logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/logo2.png')
            if os.path.exists(logo_path):
                p.drawImage(logo_path, -40, height - 140, width=290, height=120, preserveAspectRatio=True, mask='auto')

            # Información de empresa
            p.setFont("Helvetica-Bold", 12)
            p.drawString(180, height - 50, config.nombre_empresa)
            p.setFont("Helvetica-Bold", 11)
            p.drawString(180, height - 65, f"RIF: {config.rif_empresa}")
            p.setFont("Helvetica", 10)
            p.drawString(180, height - 80, "Vda. 18 Casa Nro 48 Urb. Francisco de Miranda")
            p.drawString(180, height - 95, "Telf: 0424-5439427 / 0424-5874882 / 0257-2532558")
            p.drawString(180, height - 110, "Guanare Edo. Portuguesa")

            # --- Datos generales ---
            p.setFont("Helvetica-Bold", 13)
            p.drawString(50, height - 140, f"NOTA DE ENTREGA Nº: {nota.numero_nota:04d}")
            p.setFont("Helvetica", 10)
            fecha_impresion = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            p.drawString(400, height - 140, f"Fecha impresión: {fecha_impresion}")
            p.drawString(400, height - 155, f"Nº Nota: {nota.numero_nota:06d}")
            p.drawString(400, height - 170, f"Fecha: {nota.fecha_nota.strftime('%d-%m-%Y %H:%M')}")
            p.setFont("Helvetica-Bold", 10)
            p.drawString(400, height - 185, f"VENDEDOR: {nota.empleado.nombre_completo}")

            # --- Datos del cliente (solo en primera página) ---
            if page_num == 1:
                p.setFont("Helvetica-Bold", 10)
                p.drawString(50, height - 170, f"CLIENTE:")
                p.setFont("Helvetica", 10)
                p.drawString(50, height - 185, f"TLF: {nota.cliente.telefono}")
                p.drawString(50, height - 200, f"NOMBRE: {nota.cliente.nombre_completo}")
                p.drawString(50, height - 215, f"DIRECCIÓN: {nota.cliente.direccion}")

        def draw_table_header():
            """Retorna el header de la tabla como lista"""
            return ["#", "Código", "Producto", "Cant.", "Unidad", "Precio", "Total"]

        # --- Preparar datos de productos ---
        detalles = nota.detalles_nota.all()
        productos_data = []

        for idx, detalle in enumerate(detalles, 1):
            codigo = detalle.producto.sku or str(detalle.producto.id)
            unidad = detalle.producto.unidad_medida.abreviatura if detalle.producto.unidad_medida else "UN"
            
            productos_data.append([
                str(idx),
                codigo,
                detalle.producto.nombre[:28] + "..." if len(detalle.producto.nombre) > 28 else detalle.producto.nombre,
                str(detalle.cantidad),
                unidad,
                f"${detalle.precio_unitario:,.2f}",
                f"${detalle.subtotal_linea:,.2f}"
            ])

        # --- Calcular paginación CON MÁS ESPACIO RESERVADO ---
        first_page_table_start = height - 240
        # RESERVAR MÁS ESPACIO para totales, notas y footer
        first_page_available_space = first_page_table_start - 220
        other_pages_table_start = height - 200
        # RESERVAR ESPACIO para footer
        other_pages_available_space = other_pages_table_start - 100
        row_height = 14
        header_height = 25
        
        # Calcular filas por página (MÁS CONSERVADOR)
        first_page_max_rows = int((first_page_available_space - header_height) / row_height)
        other_pages_max_rows = int((other_pages_available_space - header_height) / row_height)
        
        # Límites estrictos
        first_page_max_rows = max(6, min(first_page_max_rows, 18
        
        ))
        other_pages_max_rows = max(10, min(other_pages_max_rows, 18))

        # --- Dividir productos en páginas ---
        product_pages = []
        current_index = 0
        
        if productos_data:
            first_page_products = productos_data[:first_page_max_rows]
            product_pages.append(first_page_products)
            current_index = first_page_max_rows
            
            while current_index < len(productos_data):
                next_page_products = productos_data[current_index:current_index + other_pages_max_rows]
                product_pages.append(next_page_products)
                current_index += other_pages_max_rows

        total_pages = len(product_pages) if product_pages else 1

        # --- Generar páginas ---
        for page_num, page_products in enumerate(product_pages, 1):
            # Dibujar header
            draw_header(page_num, total_pages)
            
            # Preparar datos de la tabla
            table_data = [draw_table_header()]
            table_data.extend(page_products)
            
            # Solo añadir totales en la última página
            is_last_page = page_num == len(product_pages)
            if is_last_page:
                table_data.append(["", "", "", "", "", "TOTAL", f"${nota.total:,.2f}"])
            
            # Crear tabla
            table = Table(table_data, colWidths=[25, 60, 180, 40, 40, 80, 80])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -2 if is_last_page else -1), 0.5, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (3, 1), (6, -1), 'RIGHT'),
            ]))
            
            if is_last_page:
                table.setStyle(TableStyle([
                    ('LINEABOVE', (5, -1), (6, -1), 0.5, colors.black),
                    ('FONTNAME', (5, -1), (6, -1), 'Helvetica-Bold'),
                ], add=True))
            
            # Posición de la tabla
            if page_num == 1:
                table_y = first_page_table_start
            else:
                table_y = other_pages_table_start
            
            # Dibujar tabla
            table.wrapOn(p, width, height)
            table_width, table_height = table.wrap(width, height)
            table.drawOn(p, 40, table_y - table_height)
            
            # Solo totales y notas en la última página
            if is_last_page:
                totals_y = table_y - table_height - 40
                
                # Verificar espacio para totales
                if totals_y > 120:
                    # --- Totales ---
                    p.setFont("Helvetica", 10)
                    
                    p.drawString(450, totals_y, "SUBTOTAL")
                    p.drawString(520, totals_y, f"${nota.subtotal:,.2f}")

                    p.drawString(450, totals_y - 15, f"IVA ({config.porcentaje_iva}%)")
                    p.drawString(520, totals_y - 15, f"${nota.iva:,.2f}")

                    p.line(450, totals_y - 20, 580, totals_y - 20)

                    p.setFont("Helvetica-Bold", 11)
                    p.drawString(450, totals_y - 35, "TOTAL")
                    p.drawString(520, totals_y - 35, f"${nota.total:,.2f}")

                    # --- Nota importante ---
                    notes_y = totals_y - 70
                    if notes_y > 80:
                        p.setFont("Helvetica", 8)
                        nota_texto = "NOTA IMPORTANTE: Este documento es una NOTA DE ENTREGA. La Factura Fiscal se generará al completar el pago."
                        p.drawString(40, notes_y, nota_texto)
                else:
                    # Nueva página para totales si no hay espacio
                    p.showPage()
                    draw_header(page_num, total_pages)
                    
                    totals_y = height - 200
                    p.setFont("Helvetica", 10)
                    
                    p.drawString(450, totals_y, "SUBTOTAL")
                    p.drawString(520, totals_y, f"${nota.subtotal:,.2f}")

                    p.drawString(450, totals_y - 15, f"IVA ({config.porcentaje_iva}%)")
                    p.drawString(520, totals_y - 15, f"${nota.iva:,.2f}")

                    p.line(450, totals_y - 20, 580, totals_y - 20)

                    p.setFont("Helvetica-Bold", 11)
                    p.drawString(450, totals_y - 35, "TOTAL")
                    p.drawString(520, totals_y - 35, f"${nota.total:,.2f}")

                    p.setFont("Helvetica", 8)
                    nota_texto = "NOTA IMPORTANTE: Este documento es una NOTA DE ENTREGA. La Factura Fiscal se generará al completar el pago."
                    p.drawString(40, totals_y - 70, nota_texto)
            
            # Footer en cada página
            p.setFont("Helvetica", 8)
            p.drawString(470, 30, f"Página {page_num} de {total_pages}")
            p.drawString(40, 30, f"{config.nombre_empresa} - Sistema de Ventas")
            
            # Nueva página si no es la última
            if page_num < len(product_pages):
                p.showPage()

        p.save()
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Nota_Entrega_{nota.numero_nota}.pdf"'
        return response

from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from django.contrib.auth.decorators import login_required, user_passes_test # Para vistas basadas en funciones
from django.utils.decorators import method_decorator
import io
import json # Para la importación, para leer el archivo temporalmente
from datetime import datetime
import os # Para manejar archivos temporales
from django.conf import settings # Para la carpeta de archivos temporales
from .forms.backup_forms import DatabaseImportForm # Importar el nuevo formulario
from django.core.files.storage import FileSystemStorage
def export_database_view(request):
    try:
        # Usaremos un buffer en memoria para no escribir al disco innecesariamente en el servidor
        buffer = io.StringIO()
        call_command('dumpdata', 'black_invoices', indent=2, stdout=buffer) # Solo datos de black_invoices
        # Si quieres TODO: call_command('dumpdata', indent=2, stdout=buffer, exclude=['contenttypes', 'auth.Permission'])

        buffer.seek(0)

        # Crear la respuesta HTTP para descargar el archivo
        response = HttpResponse(buffer.getvalue(), content_type='application/json')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response['Content-Disposition'] = f'attachment; filename="backup_corporacion_agricola_{timestamp}.json"'

        messages.success(request, "Exportación de datos completada exitosamente.")
        return response
    except Exception as e:
        messages.error(request, f"Error durante la exportación de datos: {str(e)}")
        # Considera redirigir a una página de error o de vuelta a configuraciones
        return redirect(request.META.get('HTTP_REFERER', reverse_lazy('black_invoices:inicio')))

def import_database_view(request):
    if request.method == 'POST':
        form = DatabaseImportForm(request.POST, request.FILES)
        if form.is_valid():
            backup_file = request.FILES['backup_file']

            # Guardar el archivo temporalmente de forma segura
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'temp_backups')) # Crea una subcarpeta 'temp_backups' en tu MEDIA_ROOT
            if not os.path.exists(fs.location):
                os.makedirs(fs.location)

            filename = fs.save(backup_file.name, backup_file)
            uploaded_file_path = fs.path(filename)

            try:
                # Validar que es un JSON y limpiar datos problemáticos
                with open(uploaded_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Limpiar referencias de foreign keys que puedan causar problemas
                for obj in data:
                    if obj['model'] == 'black_invoices.empleado':
                        # Si el empleado tiene user_id pero no existe ese usuario, ponerlo como null
                        user_id = obj['fields'].get('user')
                        if user_id:
                            try:
                                from django.contrib.auth.models import User
                                User.objects.get(pk=user_id)
                            except User.DoesNotExist:
                                obj['fields']['user'] = None
                                print(f"Empleado {obj['pk']}: user_id {user_id} no existe, establecido como null")
                
                # Guardar los datos limpiados en un archivo temporal con extensión .json
                base_path = os.path.splitext(uploaded_file_path)[0]
                cleaned_file_path = f"{base_path}_cleaned.json"
                with open(cleaned_file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Ejecutar loaddata con los datos limpiados
                call_command('loaddata', cleaned_file_path)
                
                # Eliminar archivo temporal limpiado
                if os.path.exists(cleaned_file_path):
                    os.remove(cleaned_file_path)
                    
                messages.success(request, "Importación de datos completada exitosamente.")
            except json.JSONDecodeError:
                messages.error(request, "Error: El archivo proporcionado no es un JSON válido.")
            except Exception as e:
                messages.error(request, f"Error durante la importación de datos: {str(e)}")
            finally:
                # Eliminar el archivo temporal después de usarlo
                if os.path.exists(uploaded_file_path):
                    os.remove(uploaded_file_path)

            return redirect('black_invoices:importar_datos') # Redirige a la misma página para ver el mensaje
    else:
        form = DatabaseImportForm()

    return render(request, 'black_invoices/configuracion/importar_datos.html', {
        'titulo': 'Importar Base de Datos',
        'form': form
    })

from reportlab.lib.units import inch # Para márgenes más intuitivos

class ProductosMasVendidosPDFView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            # ... (tu código para obtener filtros y productos_vendidos es el mismo) ...
            fecha_inicio = request.GET.get('fecha_inicio')
            fecha_fin = request.GET.get('fecha_fin')

            filtros = {}
            periodo_texto = "Período no especificado" # Default

            if fecha_inicio:
                try:
                    fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                    filtros['factura__fecha_fac__date__gte'] = fecha_inicio_obj
                    periodo_texto = f"Desde: {fecha_inicio_obj.strftime('%d/%m/%Y')} "
                except ValueError: pass

            if fecha_fin:
                try:
                    fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                    filtros['factura__fecha_fac__date__lte'] = fecha_fin_obj
                    if fecha_inicio: # Si ya hay texto de inicio
                        periodo_texto += f"Hasta: {fecha_fin_obj.strftime('%d/%m/%Y')}"
                    else:
                        periodo_texto = f"Hasta: {fecha_fin_obj.strftime('%d/%m/%Y')}"
                except ValueError: pass

            if not fecha_inicio and not fecha_fin:
                hoy = datetime.now().date()
                inicio_mes = hoy.replace(day=1)
                # Por defecto, si no hay filtro, podrías querer el mes actual o todo.
                # Aquí asumo mes actual si no se especifica nada.
                filtros['factura__fecha_fac__date__gte'] = inicio_mes
                filtros['factura__fecha_fac__date__lte'] = hoy # Hasta hoy
                periodo_texto = f"Período: {inicio_mes.strftime('%B %Y')}"


            productos_vendidos = DetalleFactura.objects.filter(
                **filtros
            ).exclude(
                factura__ventas__status__vent_cancelada=True
            ).values(
                'producto__nombre',
                'producto__precio'
            ).annotate(
                total_vendido=Sum('cantidad'),
                total_ingresos=Sum(F('cantidad') * F('producto__precio')),
                numero_ventas=Count('factura', distinct=True)
            ).order_by('-total_vendido')[:20]


            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            # Márgenes
            margin_left = 0.75 * inch
            margin_right = 0.75 * inch
            margin_top = 0.75 * inch
            margin_bottom = 0.75 * inch

            content_width = width - margin_left - margin_right

            # Posición Y actual, comenzando desde arriba (después del margen superior)
            current_y = height - margin_top

            # --- Membrete y Logo ---
            logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/logo2.png')
            logo_height = 60 # Altura estimada del logo + texto empresa
            if os.path.exists(logo_path):
                p.drawImage(logo_path, - 40, height - 145, width=290, height=120, preserveAspectRatio=True, mask='auto')

            p.setFont("Helvetica-Bold", 12)
            p.drawString(margin_left + 140, current_y - 0, "CORPORACION AGRICOLA DOÑA CLARA, C.A.")
            p.setFont("Helvetica-Bold", 11)
            p.drawString(margin_left + 140, current_y - 25, "RIF: J-40723051-4")
            p.setFont("Helvetica", 10)
            p.drawString(margin_left + 140, current_y - 40, "Vda. 18 Casa Nro 48")
            p.drawString(margin_left + 140, current_y - 55, " Urb. Francisco de Miranda Guanare Edo. Portuguesa")
            p.drawString(margin_left + 140, current_y - 70, "Teléfonos: 0424-5439427 / 0424-5874882 / 0257-2532558")
            current_y -= (logo_height + 30) # Espacio para el membrete + un poco más

            # --- Título del reporte ---
            p.setFont("Helvetica-Bold", 14)
            p.drawString(margin_left, current_y, "REPORTE - PRODUCTOS MÁS VENDIDOS")
            current_y -= 20

            # --- Período y Fecha de generación ---
            p.setFont("Helvetica", 11)
            p.drawString(margin_left, current_y, periodo_texto)
            fecha_actual_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            p.drawRightString(width - margin_right, current_y, f"Generado: {fecha_actual_str}")
            current_y -= 30 # Espacio

            # --- Estadísticas generales (RESUMEN) ---
            if productos_vendidos:
                producto_top = productos_vendidos[0]
                total_unidades = sum(item['total_vendido'] for item in productos_vendidos)
                total_ingresos_global = sum(item['total_ingresos'] for item in productos_vendidos)

                p.setFont("Helvetica-Bold", 11)
                p.drawString(margin_left, current_y, "RESUMEN:")
                current_y -= 20
                p.setFont("Helvetica", 10)

                resumen_y_start = current_y
                p.drawString(margin_left, current_y, f"Producto #1: {producto_top['producto__nombre']}")
                current_y -= 15
                p.drawString(margin_left, current_y, f"Unidades vendidas (Top 1): {producto_top['total_vendido']}")
                current_y = resumen_y_start # Volver al Y del inicio de la segunda columna de resumen

                p.drawString(margin_left + content_width / 2, current_y, f"Total productos diferentes (Top 20): {productos_vendidos.count()}")
                current_y -= 15
                p.drawString(margin_left + content_width / 2, current_y, f"Total unidades vendidas (Top 20): {total_unidades}")
                current_y -= 15
                p.drawString(margin_left + content_width / 2, current_y, f"Total ingresos (Top 20): ${total_ingresos_global:,.2f}")
                current_y -= 30 # Espacio después del resumen
            else:
                p.setFont("Helvetica", 10)
                p.drawString(margin_left, current_y, "No hay datos de resumen para el período seleccionado.")
                current_y -= 30


            # --- Tabla de productos ---
            p.setFont("Helvetica-Bold", 12)
            p.drawString(margin_left, current_y, "DETALLE DE PRODUCTOS:")
            current_y -= 25 # Espacio antes de la tabla (un poco más)

            data = [["#", "Producto", "Unid. Vendidas", "Precio Unit.", "Ventas", "Total Ingresos"]]

            for idx, producto in enumerate(productos_vendidos, 1):
                nombre_prod = producto['producto__nombre']
                # El truncado se manejará mejor con el wordwrap de la tabla
                data.append([
                    str(idx),
                    nombre_prod,
                    str(producto['total_vendido']),
                    f"${producto['producto__precio']:,.2f}",
                    str(producto['numero_ventas']),
                    f"${producto['total_ingresos']:,.2f}"
                ])

            if not productos_vendidos: # Si no hay productos en la lista
                data.append(["", "No hay productos para detallar en el período.", "", "", "", ""])

            # Anchos de columna ajustados para usar mejor el content_width
            # Suma debe ser igual o menor a content_width
            # Ejemplo: # (5%), Producto (35%), Unid. (15%), Precio (15%), Ventas (10%), Ingresos (20%)
            col_widths = [
                0.05 * content_width, # #
                0.30 * content_width, # Producto (más espacio)
                0.15 * content_width, # Unid. Vendidas
                0.15 * content_width, # Precio Unit.
                0.10 * content_width, # Ventas
                0.25 * content_width  # Total Ingresos (más espacio)
            ]

            table = Table(data, colWidths=col_widths, repeatRows=1) # repeatRows=1 para repetir encabezado en nueva página
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                ('TOPPADDING', (0, 0), (-1, 0), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (2, 1), (2, -1), 'CENTER'), # Unid. Vendidas centrado
                ('ALIGN', (4, 1), (4, -1), 'CENTER'), # Ventas (número) centrado
                ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Precio Unit. a la derecha
                ('ALIGN', (5, 1), (5, -1), 'RIGHT'),  # Total Ingresos a la derecha
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (1,1), (1,-1), 2), # Padding para columna producto
                ('RIGHTPADDING', (1,1), (1,-1), 2),
                # ('WORDWRAP', (1, 0), (1, -1), 'CJK') # Usar CJK para mejor word wrap si hay caracteres especiales
                                                    # O simplemente no especificar y dejar que ReportLab maneje
            ]))

            # Usar wrapOn para obtener el ancho y alto reales que la tabla ocupará
            table_width_actual, table_height_actual = table.wrapOn(p, content_width, current_y - margin_bottom)

            # Calcular la posición Y para dibujar la tabla
            # Se resta la altura de la tabla desde la posición Y actual
            # Esto asegura que la tabla comience DESPUÉS del texto "DETALLE DE PRODUCTOS:"
            table_draw_y = current_y - table_height_actual

            # Si la tabla es muy grande y se sale del margen inferior, la movemos a una nueva página
            if table_draw_y < margin_bottom:
                p.showPage() # Nueva página
                current_y = height - margin_top # Reiniciar Y para la nueva página
                # Redibujar membrete en la nueva página si es necesario (o usar PageTemplates de Platypus)
                # Por simplicidad aquí, no lo redibujo, pero para reportes multi-página es crucial
                # O mejor aún, usar el sistema de flujo de Platypus (Story) para manejo automático de páginas.
                # Aquí solo ajustamos el Y para la tabla en la nueva página:
                table_draw_y = current_y - table_height_actual
                # Podrías necesitar redibujar el título "DETALLE DE PRODUCTOS" también si va a una nueva página.


            table.drawOn(p, margin_left, table_draw_y)
            current_y = table_draw_y - 20 # Espacio después de la tabla

            # --- Pie de página ---
            p.setFont("Helvetica", 8)
            p.line(margin_left, margin_bottom + 15, width - margin_right, margin_bottom + 15) # Línea arriba del footer
            p.drawString(width - margin_right - p.stringWidth("Página 1 de 1", "Helvetica", 8), margin_bottom, f"Página 1 de 1") # Alineado a la derecha
            p.drawString(margin_left, margin_bottom, "Doña Clara C.A. - Todos los derechos reservados")

            p.showPage()
            p.save()
            buffer.seek(0)

            response = HttpResponse(buffer, content_type='application/pdf')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            response['Content-Disposition'] = f'attachment; filename="Productos_Mas_Vendidos_{timestamp}.pdf"'
            return response

        except Exception as e:
            messages.error(request, f'Error al generar el reporte PDF: {str(e)}')
            # Considera redirigir a una página más genérica o a la página anterior
            # si 'productos_mas_vendidos' no existe o no es el lugar correcto.
            return redirect(request.META.get('HTTP_REFERER', reverse_lazy('black_invoices:inicio')))

class TasaCambioListView(EmpleadoRolMixin, ListView):
    model = TasaCambio
    template_name = 'black_invoices/configuracion/tasa_cambio_list.html'
    context_object_name = 'tasas'
    roles_permitidos = ['Administrador', 'Supervisor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Gestión de Tasa de Cambio'
        context['tasa_actual'] = TasaCambio.get_tasa_actual()
        return context

class TasaCambioCreateView(EmpleadoRolMixin, CreateView):
    model = TasaCambio
    template_name = 'black_invoices/configuracion/tasa_cambio_form.html'
    fields = ['fecha', 'tasa_usd_ves', 'activo']
    success_url = reverse_lazy('black_invoices:tasa_cambio_list')
    roles_permitidos = ['Administrador', 'Supervisor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Agregar Tasa de Cambio'
        context['boton'] = 'Guardar'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Tasa de cambio creada exitosamente')
        return super().form_valid(form)

class TasaCambioUpdateView(EmpleadoRolMixin, UpdateView):
    model = TasaCambio
    template_name = 'black_invoices/configuracion/tasa_cambio_form.html'
    fields = ['fecha', 'tasa_usd_ves', 'activo']
    success_url = reverse_lazy('black_invoices:tasa_cambio_list')
    roles_permitidos = ['Administrador', 'Supervisor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Tasa de Cambio'
        context['boton'] = 'Actualizar'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Tasa de cambio actualizada exitosamente')
        return super().form_valid(form)

class TasaCambioManualView(EmpleadoRolMixin, CreateView):
    """Vista para actualización manual rápida de la tasa de cambio"""
    model = TasaCambio
    template_name = 'black_invoices/configuracion/tasa_cambio_manual.html'
    fields = ['tasa_usd_ves']
    success_url = reverse_lazy('black_invoices:tasa_cambio_list')
    roles_permitidos = ['Administrador', 'Supervisor']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Actualización Manual de Tasa'
        context['tasa_actual'] = TasaCambio.get_tasa_actual()
        context['boton'] = 'Actualizar Tasa'
        return context

    def form_valid(self, form):
        from django.utils import timezone
        from django.db import transaction
        
        hoy = timezone.now().date()
        
        # Usar transacción para garantizar consistencia
        with transaction.atomic():
            # Verificar si ya existe una tasa para hoy
            existing_tasa = TasaCambio.objects.filter(fecha=hoy).first()
            
            if existing_tasa:
                # Si existe, actualizar los valores en lugar de crear nueva
                existing_tasa.tasa_usd_ves = form.cleaned_data['tasa_usd_ves']
                existing_tasa.fuente = f'Manual - {self.request.user.empleado.nombre}'
                existing_tasa.activo = True
                existing_tasa.save()
                
                messages.success(
                    self.request,
                    f'Tasa actualizada exitosamente: 1 USD = {existing_tasa.tasa_usd_ves:,.4f} VES'
                )
                # Retornar respuesta de redirección manualmente
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(self.success_url)
            else:
                # Si no existe, crear nueva
                form.instance.fecha = hoy
                form.instance.fuente = f'Manual - {self.request.user.empleado.nombre}'
                form.instance.activo = True
                
                messages.success(
                    self.request,
                    f'Tasa creada exitosamente: 1 USD = {form.instance.tasa_usd_ves:,.4f} VES'
                )
                return super().form_valid(form)


# En views.py - Agregar esta nueva vista
from django.http import JsonResponse
from django.views import View
from django.db.models import Q

class ProductoSearchAPIView(View):
    def get(self, request):
        query = request.GET.get('q', '').strip()

        # Buscar productos activos con stock
        if query and len(query) >= 1:
            # Búsqueda por query
            productos = Producto.objects.filter(
                Q(nombre__icontains=query) | Q(sku__icontains=query),
                activo=True,
                stock__gt=0
            ).select_related('unidad_medida')[:10]
        else:
            # Sin query, mostrar los primeros 10 productos
            productos = Producto.objects.filter(
                activo=True,
                stock__gt=0
            ).select_related('unidad_medida')[:10]

        # Formatear datos para Select2
        data = []
        for p in productos:
            data.append({
                'id': p.id,
                'text': f"{p.sku} - {p.nombre}",
                'nombre': p.nombre,
                'sku': p.sku,
                'precio': float(p.precio),
                'stock': float(p.stock),
                'unidad': p.unidad_medida.abreviatura if p.unidad_medida else 'UN',
                'precio_formateado': f"${p.precio:,.2f}",
                'stock_formateado': f"{p.stock:,.1f}"
            })

        return JsonResponse({'results': data})