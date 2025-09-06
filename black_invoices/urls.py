from django.urls import path
from . import views

app_name = 'black_invoices'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='inicio'),
    
    path('facturas/', views.FacturaListView.as_view(), name='factura_list'),
    path('facturas/<int:pk>/pdf/', views.FacturaPDFView.as_view(), name='factura_pdf'),
    path('facturas/<int:pk>/', views.FacturaDetailView.as_view(), name='factura_detail'),

    # path('facturas/crear/', views.FacturaCreateView.as_view(), name='factura_create'),
    # # Clientes
    path('clientes/', views.ClienteListView.as_view(), name='cliente_list'),
    path('clientes/<int:pk>/', views.ClienteDetailView.as_view(), name='cliente_detail'),
    path('clientes/editar/<int:pk>/', views.ClienteUpdateView.as_view(), name='cliente_update'),
    #Productos
    path('productos/<int:pk>/', views.ProductoDetailView.as_view(), name='producto_detail'),
    path('productos/editar/<int:pk>/', views.ProductoUpdateView.as_view(), name='producto_update'),
    path('productos/', views.ProductoListView.as_view(), name='producto_list'),
    path('productos/crear/', views.ProductoCreateView.as_view(), name='producto_create'),
    path('productos/<int:pk>/stock/', views.ProductoStockUpdateView.as_view(), name='producto_stock'),
    

    path('clientes/crear/', views.ClienteCreateView.as_view(), name='cliente_create'),
    # # Ventas
    path('ventas/', views.VentaListView.as_view(), name='venta_list'),
    path('ventas/crear/', views.VentaCreateView.as_view(), name='venta_create'),
    path('ventas/<int:pk>/', views.VentaDetailView.as_view(), name='venta_detail'),
    path('ventas/<int:pk>/cancelar/', views.cancelar_venta, name='cancelar_venta'),
    path('ventas/pendientes/', views.VentasPendientesView.as_view(), name='ventas_pendientes'),
    path('ventas/<int:pk>/pago/', views.RegistrarPagoView.as_view(), name='registrar_pago'),

    # # Empleados
    path('empleados/', views.EmpleadoListView.as_view(), name='empleado_list'),
    path('empleados/crear/', views.EmpleadoCreateView.as_view(), name='empleado_create'),
    path('empleados/<int:pk>/editar/', views.EmpleadoUpdateView.as_view(), name='empleado_update'),
    path('accounts/login/', views.ingresar, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/editar/', views.UserProfileUpdateView.as_view(), name='perfil_usuario_editar'),
    path('configuracion/exportar-datos/', views.export_database_view, name='exportar_datos'),
    path('configuracion/importar-datos/', views.import_database_view, name='importar_datos'),
    path('productos/mas-vendidos/', views.ProductosMasVendidosView.as_view(), name='productos_mas_vendidos'),
    path('productos/mas-vendidos/pdf', views.ProductosMasVendidosPDFView.as_view(), name='productos_mas_vendidos_pdf'),
    path('configuracion/tasa-cambio/', views.TasaCambioListView.as_view(), name='tasa_cambio_list'),
    path('configuracion/tasa-cambio/crear/', views.TasaCambioCreateView.as_view(), name='tasa_cambio_create'),
    path('configuracion/tasa-cambio/editar/<int:pk>/', views.TasaCambioUpdateView.as_view(), name='tasa_cambio_update'),
    # ...
# URL para editar perfil

]
