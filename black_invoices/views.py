from datetime import date, datetime
from decimal import Decimal
import json
import math as m
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

from black_invoices.forms.user_profile_form import UserProfileForm
from .models import *
from .forms.producto_forms import ProductoForm
from .forms.cliente_forms import ClienteForm
from .forms.empleado_form import EmpleadoForm
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
from .models import *


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
                # Crear usuario
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'] or '12345678',  # Contraseña temporal si no se proporciona
                    first_name=form.cleaned_data['nombre'],
                    last_name=form.cleaned_data['apellido']
                )
                
                # Crear empleado
                empleado = form.save(commit=False)
                empleado.user = user
                empleado.save()
                
                messages.success(self.request, f'Empleado {empleado.nombre} creado exitosamente')
                return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f'Error al crear empleado: {str(e)}')
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
            context['estado_autorizacion'] = venta.estado_autorizacion
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

""" class VentaCreateView(LoginRequiredMixin, CreateView):
    model = Factura
    form_class = FacturaForm
    template_name = 'black_invoices/ventas/venta_form.html'
    success_url = reverse_lazy('black_invoices:venta_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Venta'
        
        if self.request.POST:
            context['detalles_formset'] = DetalleFacturaFormSet(self.request.POST)
        else:
            context['detalles_formset'] = DetalleFacturaFormSet()
        context['clientes'] = Cliente.objects.all() #.objects.filter(activo=True)
        context['productos'] = Producto.objects.all() #.objects.filter(activo=True)
        
        # Añadir opciones de crédito
        context['opciones_venta'] = [
            {'id': 'contado', 'nombre': 'Contado'},
            {'id': 'credito', 'nombre': 'Crédito'}
        ]
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['detalles_formset']
        
        try:
            with transaction.atomic():
                # Verificar que el usuario tenga un empleado asociado
                if not hasattr(self.request.user, 'empleado'):
                    messages.error(self.request, 'No tienes un perfil de empleado asociado.')
                    return self.form_invalid(form)
                
                # Crear la factura pero no guardarla aún
                factura = form.save(commit=False)
                factura.empleado = self.request.user.empleado
                factura.save()
                
                # Validar el formset directamente
                if formset.is_valid():
                    detalles = formset.save(commit=False)
                    
                    if not detalles:
                        # Si no hay detalles, intentar procesarlos manualmente
                        total_forms = int(self.request.POST.get('form-TOTAL_FORMS', 0))
                        
                        # Información de diagnóstico
                        print(f"Total de formularios: {total_forms}")
                        print(f"Datos POST: {self.request.POST}")
                        
                        # Crear manualmente los detalles
                        for i in range(total_forms):
                            producto_id = self.request.POST.get(f'form-{i}-producto')
                            cantidad_str = self.request.POST.get(f'form-{i}-cantidad')
                            
                            if producto_id and cantidad_str:
                                # Determinar tipo de factura basado en tipo_venta
                                es_credito = self.request.POST.get('tipo_venta') == 'credito'
                                tipo_factura = TipoFactura.objects.get(pk=2 if es_credito else 1)
                                
                                producto = Producto.objects.get(pk=producto_id)
                                cantidad = Decimal(str(cantidad_str))
                                
                                # Verificar stock
                                if cantidad > producto.stock:
                                    raise ValueError(f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}")
                                
                                # Crear detalle
                                subtotal = producto.precio * cantidad
                                detalle = DetalleFactura(
                                    factura=factura,
                                    producto=producto,
                                    cantidad=cantidad,
                                    tipo_factura=tipo_factura,
                                    sub_total=subtotal
                                )
                                detalle.save()
                                
                                # Reducir stock
                                producto.stock -= cantidad
                                producto.save(update_fields=['stock'])
                                
                                # Agregar al array de detalles
                                detalles.append(detalle)
                        
                        if not detalles:
                            raise ValueError("Debe agregar al menos un producto a la venta. Verifique que seleccionó un producto y una cantidad.")
                    else:
                        # Procesar los detalles del formset
                        total_factura = 0
                        
                        for detalle in detalles:
                            detalle.factura = factura
                            
                            # Verificar stock
                            if detalle.cantidad > detalle.producto.stock:
                                raise ValueError(f"Stock insuficiente para {detalle.producto.nombre}. Disponible: {detalle.producto.stock}")
                            
                            # Calcular subtotal
                            subtotal = detalle.cantidad * detalle.producto.precio
                            detalle.sub_total = subtotal
                            detalle.save()
                            
                            # Reducir stock
                            detalle.producto.stock -= detalle.cantidad
                            detalle.producto.save(update_fields=['stock'])
                            
                            total_factura += subtotal
                    
                    # Calcular el total en cualquier caso
                    total_factura = sum(detalle.sub_total for detalle in detalles)
                    
                    # Actualizar total de factura
                    factura.total_fac = total_factura
                    factura.total_venta = total_factura
                    factura.save()
                    
                    # Crear venta
                    es_credito = self.request.POST.get('tipo_venta') == 'credito'
                    
                    if es_credito:
                        estado = StatusVentas.objects.get(nombre="Pendiente")
                    else:
                        estado = StatusVentas.objects.get(nombre="Completada")
                    
                    venta = Ventas.objects.create(
                        empleado=factura.empleado,
                        factura=factura,
                        status=estado,
                        credito=es_credito,
                        monto_pagado=0 if es_credito else factura.total_fac
                    )
                    
                    if es_credito:
                        messages.success(self.request, f'Venta a crédito #{venta.id} creada exitosamente.')
                    else:
                        messages.success(self.request, f'Venta #{venta.id} creada exitosamente.')
                    
                    # Necesario para que la vista funcione correctamente
                    self.object = factura
                    
                    return redirect('black_invoices:venta_detail', pk=venta.id)
                else:
                    # Mostrar errores específicos del formset
                    print(f"Formset inválido. Errores: {formset.errors}")
                    for i, form_errors in enumerate(formset.errors):
                        if form_errors:
                            messages.error(self.request, f"Error en producto {i+1}: {form_errors}")
                    return self.form_invalid(form)
                    
        except Exception as e:
                messages.error(self.request, f"Error: {str(e)}")
                print(f"Excepción: {type(e).__name__}: {str(e)}")
                return self.form_invalid(form) """
class VentaCreateView(LoginRequiredMixin, View):
    template_name = 'black_invoices/ventas/venta_form.html'
    
    def get(self, request):
        # Obtener tasa de cambio actual
        tasa_actual = TasaCambio.get_tasa_actual()
        
        context = {
            'titulo': 'Crear Venta',
            'clientes': Cliente.objects.all(),
            'productos': Producto.objects.filter(activo=True, stock__gt=0),  # Solo productos activos con stock
            'opciones_venta': [
                {'id': 'contado', 'nombre': 'Contado'},
                {'id': 'credito', 'nombre': 'Crédito'}
            ],
            'tasa_cambio': tasa_actual.tasa_usd_ves if tasa_actual else 1
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
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
                
                # 3. Recopilar detalles de productos
                productos = []
                total_forms = int(request.POST.get('form-TOTAL_FORMS', 0))
                
                for i in range(total_forms):
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
                            continue  # Ignorar cantidades inválidas
                
                if not productos:
                    messages.error(request, 'Debe agregar al menos un producto a la venta.')
                    return redirect('black_invoices:venta_create')
                
                # 4. Crear la factura
                cliente = Cliente.objects.get(pk=cliente_id)
                factura = Factura(
                    cliente=cliente,
                    empleado=request.user.empleado,
                    metodo_pag=metodo_pago
                )
                factura.save()
                
                # 5. Procesar los productos
                total_factura = 0
                es_credito = request.POST.get('tipo_venta') == 'credito'
                
                # Obtener o crear el tipo de factura
                try:
                    tipo_factura = TipoFactura.objects.get(credito_fac=es_credito, contado_fac=not es_credito)
                except TipoFactura.DoesNotExist:
                    # Crear el tipo de factura si no existe
                    tipo_factura = TipoFactura.objects.create(
                        credito_fac=es_credito,
                        contado_fac=not es_credito,
                        plazo_credito=30 if es_credito else None
                    )
                
                for prod in productos:
                    try:
                        producto = Producto.objects.get(pk=prod['id'])
                        cantidad = Decimal(str(prod['cantidad']))  # Convertir a Decimal desde el inicio
                        
                        # Solo verificar disponibilidad - NO DESCONTAR STOCK AÚN
                        # El stock se descontará cuando se autorice la venta
                        if cantidad > producto.stock:
                            raise ValueError(f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}")
                        
                        # Calcular subtotal (ambos son Decimal ahora)
                        subtotal = producto.precio * cantidad
                        total_factura += subtotal
                        
                        # Crear detalle
                        detalle = DetalleFactura(
                            factura=factura,
                            producto=producto,
                            cantidad=cantidad,
                            tipo_factura=tipo_factura,
                            sub_total=subtotal
                        )
                        detalle.save()
                        
                        # *** NO DESCONTAMOS STOCK AQUÍ - se hará en la autorización ***
                        
                    except Producto.DoesNotExist:
                        raise ValueError(f"El producto con ID {prod['id']} no existe.")
                
                # 6. Actualizar el total de la factura usando calcular_total_mejorado
                factura.calcular_total_mejorado()
                
                # 7. Crear la venta con sistema de autorización
                # TODAS las ventas inician como "Pendiente de Autorización"
                try:
                    estado_pendiente_autorizacion = StatusVentas.objects.get(nombre="Pendiente de Autorización")
                except StatusVentas.DoesNotExist:
                    # Si no existe, crear el estado
                    estado_pendiente_autorizacion = StatusVentas.objects.create(
                        nombre="Pendiente de Autorización",
                        vent_espera=True,
                        vent_cancelada=False
                    )
                
                venta = Ventas.objects.create(
                    empleado=factura.empleado,
                    factura=factura,
                    status=estado_pendiente_autorizacion,
                    credito=es_credito,
                    monto_pagado=0,  # Nunca se paga hasta que se autorice
                    requiere_autorizacion=True,
                    autorizada=False
                )
                
                # 8. Mensaje de éxito con información de autorización requerida
                tasa_actual = TasaCambio.get_tasa_actual()
                if tasa_actual:
                    total_bs = factura.total_fac * tasa_actual.tasa_usd_ves
                    messages.success(
                        request, 
                        f'Venta {"a crédito " if es_credito else ""}#{venta.id} creada exitosamente. '
                        f'Total: ${factura.total_fac:,.2f} ({total_bs:,.2f} Bs). '
                        f'⚠️ REQUIERE AUTORIZACIÓN para proceder.'
                    )
                else:
                    messages.success(
                        request, 
                        f'Venta {"a crédito " if es_credito else ""}#{venta.id} creada exitosamente. '
                        f'⚠️ REQUIERE AUTORIZACIÓN para proceder.'
                    )
                
                return redirect('black_invoices:venta_detail', pk=venta.id)
                
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
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
    roles_permitidos = ['Administrador', 'Supervisor', 'Vendedor']
    
    def get_queryset(self):
        return Ventas.objects.filter(
            credito=True, 
            status__vent_cancelada=False
        ).exclude(
            monto_pagado__gte=F('factura__total_fac')
        ).order_by('-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Abonos (Crédito)'
        return context
    
""" class RegistrarPagoView(EmpleadoRolMixin, UpdateView):
    model = Ventas
    template_name = 'black_invoices/ventas/registrar_pago.html'
    fields = []
    roles_permitidos = ['Administrador', 'Supervisor', 'Vendedor']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Registrar Pago - Venta #{self.object.id}'
        context['venta'] = self.object
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # VALIDAR que esté autorizada
        if not self.object.autorizada:
            messages.error(request, 'No se pueden registrar pagos en ventas no autorizadas.')
            return redirect('black_invoices:ventas_pendientes')
        
        try:
            monto = float(request.POST.get('monto', 0))
            metodo_pago = request.POST.get('metodo_pago', 'efectivo')  # NUEVO
            referencia = request.POST.get('referencia_pago', '')      # NUEVO
            
            if monto <= 0:
                messages.error(request, 'El monto debe ser mayor a cero.')
                return self.get(request, *args, **kwargs)
            
            if monto > (self.object.saldo_pendiente + Decimal(0.01)):
                messages.error(request, f'El monto excede el saldo pendiente (${self.object.saldo_pendiente}).')
                return self.get(request, *args, **kwargs)
            
            # Registrar pago
            from decimal import Decimal
            monto_decimal = Decimal(str(monto))
            self.object.monto_pagado += monto_decimal
            
            if self.object.completada and self.object.credito:
                estado_completado = StatusVentas.objects.get(nombre="Completada")
                self.object.status = estado_completado
                
            self.object.save(update_fields=['monto_pagado', 'status'])
            
            # CREAR REGISTRO CON MÉTODO DE PAGO
            PagoVenta.objects.create(
                venta=self.object,
                monto=monto_decimal,
                metodo_pago=metodo_pago,           # NUEVO
                referencia_pago=referencia if referencia else None  # NUEVO
            )
            
            metodo_nombre = dict(PagoVenta.METODOS_PAGO_CHOICES)[metodo_pago]
            
            if self.object.completada:
                messages.success(request, f'Pago de ${monto} vía {metodo_nombre} registrado. Venta completada.')
            else:
                messages.success(request, f'Pago de ${monto} vía {metodo_nombre} registrado. Saldo: ${self.object.saldo_pendiente}')
            
            return redirect('black_invoices:ventas_pendientes')
            
        except ValueError:
            messages.error(request, 'Por favor ingrese un monto válido.')
            return self.get(request, *args, **kwargs) """
class RegistrarPagoView(EmpleadoRolMixin, UpdateView):
    model = Ventas
    template_name = 'black_invoices/ventas/registrar_pago.html'
    fields = []  # No usamos campos del modelo directamente
    roles_permitidos = ['Administrador', 'Supervisor', 'Vendedor']
    
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
            
            # Mensaje diferenciado según el estado
            if self.object.completada:
                messages.success(
                    request, 
                    f'Pago de ${monto} registrado vía {metodo_display}. La venta ha sido completada.'
                )
            else:
                messages.success(
                    request, 
                    f'Pago de ${monto} registrado vía {metodo_display}. Saldo pendiente: ${self.object.saldo_pendiente}'
                )
            
            return redirect('black_invoices:ventas_pendientes')
            
        except ValueError:
            messages.error(request, 'Por favor ingrese un monto válido.')
            return self.get(request, *args, **kwargs)
        except Exception as e:
            messages.error(request, f'Error al procesar el pago: {str(e)}')
            return self.get(request, *args, **kwargs)
class VentasAutorizacionView(EmpleadoRolMixin, ListView):
    model = Ventas
    template_name = 'black_invoices/ventas/ventas_autorizacion.html'
    context_object_name = 'ventas'
    roles_permitidos = ['Administrador', 'Supervisor']
    
    def get_queryset(self):
        return Ventas.objects.filter(
            requiere_autorizacion=True,
            autorizada=False,
            status__vent_cancelada=False
        ).order_by('-fecha_venta')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Ventas Pendientes de Autorización'
        return context

class AutorizarVentaView(EmpleadoRolMixin, View):
    roles_permitidos = ['Administrador', 'Supervisor']
    
    def post(self, request, pk):
        try:
            venta = Ventas.objects.get(pk=pk)
            accion = request.POST.get('accion')
            comentarios = request.POST.get('comentarios', '')
            empleado = request.user.empleado
            
            if accion == 'autorizar':
                try:
                    # Usar el método del modelo que ya tiene transacciones atómicas
                    venta.autorizar_venta(empleado, comentarios)
                    messages.success(request, f'Venta #{venta.id} autorizada exitosamente.')
                except ValueError as e:
                    messages.error(request, f'Error al autorizar venta: {str(e)}')
                    return redirect('black_invoices:ventas_autorizacion')
                
            elif accion == 'rechazar':
                try:
                    # Usar el método del modelo para rechazar
                    venta.rechazar_venta(empleado, comentarios)
                    messages.success(request, f'Venta #{venta.id} rechazada exitosamente.')
                except ValueError as e:
                    messages.error(request, f'Error al rechazar venta: {str(e)}')
                    return redirect('black_invoices:ventas_autorizacion')
            
        except Ventas.DoesNotExist:
            messages.error(request, 'Venta no encontrada.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('black_invoices:ventas_autorizacion')

        
class VentaDetailView(LoginRequiredMixin, DetailView):
    model = Ventas
    template_name = 'black_invoices/ventas/venta_detail.html'
    context_object_name = 'venta'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        venta = self.object
        context['titulo'] = f'Detalle de venta #{venta.id}'

        context['detalles'] = venta.factura.detallefactura_set.all()
        
        # Información de totales formateados
        context['totales_formateados'] = venta.factura.get_totales_formateados()
        
        # Estado de la venta con nuevos campos
        context['estado_autorizacion'] = venta.estado_autorizacion
        context['saldo_pendiente'] = venta.saldo_pendiente if venta.credito else 0
        context['completada'] = venta.completada
        
        # Historial de pagos si es a crédito
        if venta.credito:
            context['pagos'] = venta.pagos.all().order_by('-fecha')
            context['resumen_pagos'] = venta.resumen_pagos()
        
        # Información de comisión
        try:
            context['comision'] = venta.comision
        except:
            context['comision'] = None
        
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
                venta.cancelar_venta_autorizada(empleado_cancelador, "Cancelación desde vista")
                messages.success(request, f'Venta #{venta.id} cancelada exitosamente. Stock restaurado.')
                
            except ValueError as e:
                messages.error(request, f'Error al cancelar venta: {str(e)}')
    
    except Ventas.DoesNotExist:
        messages.error(request, 'Venta no encontrada.')
    except AttributeError:
        messages.error(request, 'Usuario sin permisos de empleado para cancelar ventas.')
    
    return redirect('black_invoices:venta_list')


######################      COMISIONES      ###############
from django.db.models import Q

class RangosComisionesListView(LoginRequiredMixin, ListView):
    model = ConsultaComision
    template_name = 'black_invoices/comisiones/rangos_list.html'
    context_object_name = 'rangos'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Rangos de Comisiones'
        return context

class RangosComisionesCreateView(LoginRequiredMixin, CreateView):
    model = ConsultaComision
    template_name = 'black_invoices/comisiones/rangos_form.html'
    fields = ['rango_inferior', 'rango_superior', 'porcentaje']
    success_url = reverse_lazy('black_invoices:rangos_comisiones_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Añadir Rango de Comisión'
        context['boton'] = 'Guardar'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Rango de comisión creado exitosamente')
        return super().form_valid(form)

class RangosComisionesUpdateView(LoginRequiredMixin, UpdateView):
    model = ConsultaComision
    template_name = 'black_invoices/comisiones/rangos_form.html'
    fields = ['rango_inferior', 'rango_superior', 'porcentaje']
    success_url = reverse_lazy('black_invoices:rangos_comisiones_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Rango de Comisión'
        context['boton'] = 'Actualizar'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Rango de comisión actualizado exitosamente')
        return super().form_valid(form)

class RangosComisionesDeleteView(LoginRequiredMixin, DeleteView):
    model = ConsultaComision
    template_name = 'black_invoices/comisiones/rangos_confirm_delete.html'
    success_url = reverse_lazy('black_invoices:rangos_comisiones_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Eliminar Rango de Comisión'
        return context
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Rango de comisión eliminado exitosamente')
        return super().delete(request, *args, **kwargs)
class ComisionListView(LoginRequiredMixin, ListView):
    model = Empleado
    template_name = 'black_invoices/comisiones/comision_list.html'
    context_object_name = 'empleados'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Comisiones'
        
        if hasattr(self.request.user, 'empleado'):
            empleado = self.request.user.empleado
            mes_actual = datetime.now().month
            anio_actual = datetime.now().year
            
            # Filtrar empleados según el nivel de acceso
            es_admin = empleado.nivel_acceso.nombre == 'Administrador'
            context['es_administrador'] = es_admin
            
            if es_admin:
                empleados = Empleado.objects.filter(activo=True)
            else:
                empleados = Empleado.objects.filter(id=empleado.id)
            
            # Calcular comisiones para cada empleado
            comisiones = []
            for emp in empleados:
                # Obtener ventas completadas
                ventas_completadas = Ventas.objects.filter(
                    empleado=emp,
                    factura__fecha_fac__month=mes_actual,
                    factura__fecha_fac__year=anio_actual
                ).exclude(status__vent_cancelada=True).filter(
                    # Solo ventas completadas (contado o crédito pagado)
                    Q(credito=False) | Q(credito=True, monto_pagado__gte=F('factura__total_fac'))
                )
                
                # Calcular comisión
                total_comision = emp.get_comisiones_mes(mes_actual, anio_actual)
                
                comisiones.append({
                    'empleado': emp,
                    'ventas': ventas_completadas.count(),
                    'comision': total_comision
                })
            
            context['comisiones'] = comisiones
            
            # Cálculo para el empleado actual (para el widget)
            context['total_mes'] = empleado.get_comisiones_mes(mes_actual, anio_actual)
            context['total_anio'] = sum(
                empleado.get_comisiones_mes(m, anio_actual) 
                for m in range(1, mes_actual + 1)
            )
        
        return context
    
# Agregar esta vista al archivo views.py existente

class HistorialComisionesView(LoginRequiredMixin, ListView):
    model = Ventas
    template_name = 'black_invoices/comisiones/historial_comisiones.html'
    context_object_name = 'ventas'
    
    def get_queryset(self):
        # Obtener todas las ventas completadas (no canceladas)
        queryset = Ventas.objects.exclude(
            status__vent_cancelada=True
        ).select_related(
            'empleado', 'empleado__nivel_acceso', 'factura', 'factura__cliente', 'status'
        ).filter(
            # Solo ventas completadas (contado o crédito pagado)
            Q(credito=False) | Q(credito=True, monto_pagado__gte=F('factura__total_fac'))
        ).order_by('-factura__fecha_fac')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Historial de Comisiones'
        
        # Obtener todas las ventas para cálculos
        ventas = self.get_queryset()
        
        # Preparar datos de historial con comisiones calculadas
        historial_comisiones = []
        total_comisiones_general = Decimal('0.00')
        total_ventas_calculadas = 0
        
        for venta in ventas:
            # Calcular comisión para esta venta
            total_venta = venta.factura.total_fac
            rango_comision = ConsultaComision.objects.filter(
                rango_inferior__lte=total_venta,
                rango_superior__gte=total_venta
            ).first()
            
            porcentaje = rango_comision.porcentaje if rango_comision else Decimal('0.00')
            comision_venta = (total_venta * porcentaje / Decimal('100.00')) if rango_comision else Decimal('0.00')
            total_comisiones_general += comision_venta
            total_ventas_calculadas += 1
            
            # Determinar estado de la venta
            if venta.status.vent_cancelada:
                estado = 'Cancelada'
            elif venta.status.vent_espera or (venta.credito and venta.monto_pagado < venta.factura.total_fac):
                estado = 'Pendiente'
            else:
                estado = 'Completada'
            
            historial_comisiones.append({
                'venta_id': venta.id,
                'empleado_nombre': f"{venta.empleado.nombre} {venta.empleado.apellido}",
                'empleado_nivel': venta.empleado.nivel_acceso.nombre,
                'fecha_venta': venta.factura.fecha_fac,
                'numero_recibo': venta.factura.id,
                'cliente_nombre': f"{venta.factura.cliente.nombre} {venta.factura.cliente.apellido}",
                'total_venta': total_venta,
                'porcentaje_comision': porcentaje,
                'monto_comision': comision_venta,
                'estado_venta': estado,
                'es_credito': venta.credito
            })
        
        context['historial_comisiones'] = historial_comisiones
        
        # Estadísticas generales
        context['estadisticas'] = {
            'total_comisiones': total_comisiones_general,
            'total_ventas': total_ventas_calculadas,
            'promedio_comision': total_comisiones_general / total_ventas_calculadas if total_ventas_calculadas > 0 else Decimal('0.00')
        }
        
        # Datos para filtros
        context['empleados_unicos'] = Empleado.objects.filter(
            activo=True
        ).values('id', 'nombre', 'apellido').distinct()
        
        context['niveles_acceso'] = NivelAcceso.objects.all()
        
        # Meses del año actual
        año_actual = datetime.now().year
        context['meses_año'] = [
            {'numero': 1, 'nombre': 'Enero'},
            {'numero': 2, 'nombre': 'Febrero'},
            {'numero': 3, 'nombre': 'Marzo'},
            {'numero': 4, 'nombre': 'Abril'},
            {'numero': 5, 'nombre': 'Mayo'},
            {'numero': 6, 'nombre': 'Junio'},
            {'numero': 7, 'nombre': 'Julio'},
            {'numero': 8, 'nombre': 'Agosto'},
            {'numero': 9, 'nombre': 'Septiembre'},
            {'numero': 10, 'nombre': 'Octubre'},
            {'numero': 11, 'nombre': 'Noviembre'},
            {'numero': 12, 'nombre': 'Diciembre'},
        ]
        context['año_actual'] = año_actual
        
        # Porcentajes de comisión disponibles
        context['porcentajes_comision'] = ConsultaComision.objects.values_list(
            'porcentaje', flat=True
        ).distinct().order_by('porcentaje')
        
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
class FacturaPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            factura = Factura.objects.get(pk=pk)
        except Factura.DoesNotExist:
            return HttpResponse("Factura no encontrada", status=404)

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # --- Membrete y Logo ---
        logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/the_black.jpeg')
        if os.path.exists(logo_path):
            p.drawImage(logo_path, 40, height - 110, width=120, height=60, preserveAspectRatio=True, mask='auto')
        
        # Nombre de la empresa (ajustado a la izquierda)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(180, height - 50, "INDUSTRIA & HERRAMIENTA EL NEGRITO, C.A.")
        
        # RIF (ajustado para no sobreponerse)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(180, height - 65, "RIF: J-406050717")
        
        # Dirección y teléfonos
        p.setFont("Helvetica", 10)
        p.drawString(180, height - 80, "CR 10 ENTRE CALLES 4 Y 5 EDIF DOÑA EDITH PISO 1 OF 2")
        p.drawString(180, height - 95, "BARRIO MATURIN GUANARE PORTUGUESA")
        p.drawString(180, height - 110, "Teléfonos: 0257-5143082 / 0257-5143082")

        # --- Datos generales ---
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, height - 130, "NOTA DE ENTREGA")
        p.setFont("Helvetica", 10)
        fecha_impresion = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        p.drawString(400, height - 130, f"Fecha impresión: {fecha_impresion}")
        p.drawString(400, height - 145, f"Nº Control: {factura.id:06d}")
        p.drawString(400, height - 160, f"Fecha: {factura.fecha_fac.strftime('%d-%m-%Y %H:%M')}")
        p.setFont("Helvetica-Bold", 10)
        p.drawString(400, height - 175, f"VENDEDOR: {factura.empleado.nombre} {factura.empleado.apellido}")
        p.setFont("Helvetica", 10)
        p.drawString(400, height - 190, f"CONDICIÓN: {factura.get_metodo_pag_display()}")

        # --- Datos del cliente ---
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, height - 160, f"CLIENTE:")
        p.setFont("Helvetica", 10)
        p.drawString(50, height - 175, f"TLF: {factura.cliente.telefono}")
        p.drawString(50, height - 190, f"NOMBRE: {factura.cliente.nombre} {factura.cliente.apellido}")
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
        p.drawString(40, 30, "The Black System - Todos los derechos reservados")

        p.showPage()
        p.save()
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Recibo_Venta_{factura.id}.pdf"'
        return response

def comision_detail(request, empleado_id):
    try:
        empleado = Empleado.objects.get(id=empleado_id)
        mes_actual = datetime.now().month
        anio_actual = datetime.now().year
        ventas = Ventas.objects.filter(
            empleado=empleado,
            factura__fecha_fac__month=mes_actual,
            factura__fecha_fac__year=anio_actual
        ).exclude(status__vent_cancelada=True).filter(
            Q(credito=False) | Q(credito=True, monto_pagado__gte=F('factura__total_fac'))
        )
        total_comision = Decimal('0.00')
        ventas_detalle = []
        for venta in ventas:
            total_venta = venta.factura.total_fac
            rango_comision = ConsultaComision.objects.filter(
                rango_inferior__lte=total_venta,
                rango_superior__gte=total_venta
            ).first()
            porcentaje = rango_comision.porcentaje if rango_comision else Decimal('0.00')
            comision_venta = (total_venta * porcentaje / Decimal('100.00')) if rango_comision else Decimal('0.00')
            total_comision += comision_venta
            ventas_detalle.append({
                'factura': venta.factura,
                'comision': comision_venta,
                'porcentaje': porcentaje,
                'venta_id': venta.id
            })
        porcentaje_promedio = ''
        if ventas_detalle:
            suma_porcentajes = sum([v['porcentaje'] for v in ventas_detalle])
            porcentaje_promedio = suma_porcentajes / len(ventas_detalle)
            porcentaje_promedio = f"{porcentaje_promedio:.2f}"  # String para mostrar
        comision_data = {
            'empleado': empleado,
            'ventas': ventas.count(),
            'comision': total_comision,
            'porcentaje': porcentaje_promedio
        }
        context = {
            'titulo': f'Detalle de Comisión - {empleado.nombre} {empleado.apellido}',
            'comision': comision_data,
            'ventas_detalle': ventas_detalle
        }
        return render(request, 'black_invoices/comisiones/comision_detail.html', context)
    except Empleado.DoesNotExist:
        messages.error(request, 'El empleado no existe.')
        return redirect('black_invoices:comision_list')
    except Exception as e:
        messages.error(request, f'Error al cargar el detalle de comisión: {str(e)}')
        return redirect('black_invoices:comision_list')

class ComisionPDFView(LoginRequiredMixin, View):
    def get(self, request, empleado_id):
        try:
            empleado = Empleado.objects.get(id=empleado_id)
            mes_actual = datetime.now().month
            anio_actual = datetime.now().year
            
            # Definir fecha actual
            fecha_actual = datetime.now().strftime("%d/%m/%Y")
            
            # Obtener ventas completadas
            ventas = Ventas.objects.filter(
                empleado=empleado,
                factura__fecha_fac__month=mes_actual,
                factura__fecha_fac__year=anio_actual
            ).exclude(status__vent_cancelada=True).filter(
                Q(credito=False) | Q(credito=True, monto_pagado__gte=F('factura__total_fac'))
            )
            
            # Calcular comisiones
            total_comision = Decimal('0.00')
            ventas_detalle = []
            for venta in ventas:
                total_venta = venta.factura.total_fac
                rango_comision = ConsultaComision.objects.filter(
                    rango_inferior__lte=total_venta,
                    rango_superior__gte=total_venta
                ).first()
                porcentaje = rango_comision.porcentaje if rango_comision else Decimal('0.00')
                comision_venta = (total_venta * porcentaje / Decimal('100.00')) if rango_comision else Decimal('0.00')
                total_comision += comision_venta
                ventas_detalle.append({
                    'factura': venta.factura,
                    'comision': comision_venta,
                    'porcentaje': porcentaje,
                    'venta_id': venta.id
                })

            # Crear el PDF
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            
            # --- Membrete y Logo ---
            logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/the_black.jpeg')
            if os.path.exists(logo_path):
                p.drawImage(logo_path, 40, height - 110, width=120, height=60, preserveAspectRatio=True, mask='auto')
            
            # Nombre de la empresa y RIF
            p.setFont("Helvetica-Bold", 12)
            p.drawString(180, height - 50, "INDUSTRIA & HERRAMIENTA EL NEGRITO, C.A.")
            p.setFont("Helvetica-Bold", 11)
            p.drawString(180, height - 65, "RIF: J-406050717")
            
            # Dirección y teléfonos
            p.setFont("Helvetica", 10)
            p.drawString(180, height - 80, "CR 10 ENTRE CALLES 4 Y 5 EDIF DOÑA EDITH PISO 1 OF 2")
            p.drawString(180, height - 95, "BARRIO MATURIN GUANARE PORTUGUESA")
            p.drawString(180, height - 110, "Teléfonos: 0257-5143082 / 0257-5143082")
            
            # --- Título del reporte ---
            p.setFont("Helvetica-Bold", 13)
            p.drawString(50, height - 130, "REPORTE DE COMISIÓN")
            
            # --- Datos del empleado ---
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, height - 160, "Información del Empleado:")
            p.setFont("Helvetica", 10)
            p.drawString(50, height - 180, f"Nombre: {empleado.nombre} {empleado.apellido}")
            p.drawString(50, height - 195, f"Nivel de Acceso: {empleado.nivel_acceso.nombre}")
            
            # --- Añadir información de resumen de comisión ---
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, height - 225, "Resumen de Comisión:")
            p.setFont("Helvetica", 10)
            p.drawString(50, height - 245, f"Ventas Completadas: {ventas.count()}")
            p.drawString(50, height - 260, f"Total Comisión: ${total_comision:.2f}")
            
            # --- Detalle de las ventas (tabla) ---
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, height - 290, "Detalle de Ventas:")
            
            # Definir datos para la tabla
            data = [["Fecha", "Recibo #", "Cliente", "Total Venta", "% Comisión", "Comisión"]]
            
            for venta in ventas_detalle:
                data.append([
                    venta['factura'].fecha_fac.strftime("%d/%m/%Y"),
                    f"{venta['factura'].id}",
                    f"{venta['factura'].cliente.nombre} {venta['factura'].cliente.apellido}",
                    f"${venta['factura'].total_fac:.2f}",
                    f"{venta['porcentaje']}%",
                    f"${venta['comision']:.2f}"
                ])
            
            # Si no hay ventas, añadir una fila de "Sin datos"
            if len(data) == 1:
                data.append(["Sin datos", "", "", "", "", ""])
            
            # Configurar ancho de columnas
            col_widths = [70, 60, 150, 80, 80, 80]
            
            # Crear y configurar la tabla
            table = Table(data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (3, 1), (5, -1), 'RIGHT'),  # Alinear columnas numéricas a la derecha
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            
            # Calcular posición de la tabla
            table_height = len(data) * 20  # Estimación aproximada
            table_y = height - 320 - table_height  # Ajustar según necesidad
            
            # Dibujar la tabla
            table.wrapOn(p, width - 100, table_height)
            table.drawOn(p, 50, max(table_y, 100))  # Mínimo 100 para evitar que se salga
            
            # --- Información adicional ---
            # Si hay espacio, añadir información de rangos de comisión
            rangos = ConsultaComision.objects.all().order_by('rango_inferior')
            if rangos.exists() and table_y > 150:
                p.setFont("Helvetica-Bold", 10)
                p.drawString(50, table_y - 30, "Rangos de Comisión:")
                
                y_pos = table_y - 50
                p.setFont("Helvetica", 9)
                for i, rango in enumerate(rangos):
                    p.drawString(50, y_pos - (i * 15), 
                                f"${rango.rango_inferior:.2f} a ${rango.rango_superior:.2f}: {rango.porcentaje}%")
            
            # --- Pie de página ---
            p.setFont("Helvetica", 8)
            p.drawString(470, 30, f"Página 1 de 1")
            p.drawString(40, 30, "The Black System - Todos los derechos reservados")
            
            # Finalizar y devolver PDF
            p.showPage()
            p.save()
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Comision_{empleado.nombre}_{empleado.apellido}_{fecha_actual}.pdf"'
            return response
        
        except Exception as e:
            messages.error(request, f'Error al generar el PDF: {str(e)}')
            return redirect('black_invoices:comision_list')
        
    
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
        response['Content-Disposition'] = f'attachment; filename="backup_theblacksystem_{timestamp}.json"'
        
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
                # Validar que es un JSON (opcional pero recomendado)
                with open(uploaded_file_path, 'r') as f:
                    json.load(f) # Intenta parsear, si falla, no es JSON válido

                # Ejecutar loaddata
                # ¡ADVERTENCIA! loaddata puede sobreescribir datos si las PKs coinciden o causar errores.
                # Es altamente recomendable que el admin sepa lo que está haciendo.
                # Considera hacer un backup ANTES de importar.
                call_command('loaddata', uploaded_file_path)
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
            logo_path = os.path.join(settings.BASE_DIR, 'black_invoices/static/img/the_black.jpeg')
            logo_height = 60 # Altura estimada del logo + texto empresa
            if os.path.exists(logo_path):
                p.drawImage(logo_path, margin_left, current_y - 70, width=120, height=60, 
                            preserveAspectRatio=True, mask='auto')
            
            p.setFont("Helvetica-Bold", 12)
            p.drawString(margin_left + 140, current_y - 10, "INDUSTRIA & HERRAMIENTA EL NEGRITO, C.A.")
            p.setFont("Helvetica-Bold", 11)
            p.drawString(margin_left + 140, current_y - 25, "RIF: J-406050717")
            p.setFont("Helvetica", 10)
            p.drawString(margin_left + 140, current_y - 40, "CR 10 ENTRE CALLES 4 Y 5 EDIF DOÑA EDITH PISO 1 OF 2")
            p.drawString(margin_left + 140, current_y - 55, "BARRIO MATURIN GUANARE PORTUGUESA")
            p.drawString(margin_left + 140, current_y - 70, "Teléfonos: 0257-5143082 / 0257-5143082")
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
            p.drawString(margin_left, margin_bottom, "The Black System - Todos los derechos reservados")

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
    fields = ['fecha', 'tasa_usd_ves', 'activa']
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
    fields = ['fecha', 'tasa_usd_ves', 'activa']
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