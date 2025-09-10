# Sistema de Privilegios - Doña Clara System

## Descripción General

El sistema utiliza un modelo de control de acceso basado en roles (RBAC - Role-Based Access Control) implementado a través del modelo `NivelAcceso` y el mixin `EmpleadoRolMixin`.

## Arquitectura del Sistema

### Componentes Principales

1. **Modelo `NivelAcceso`**: Define los diferentes niveles de acceso en el sistema
2. **Modelo `Empleado`**: Cada empleado tiene asignado un nivel de acceso
3. **Mixin `EmpleadoRolMixin`**: Controla el acceso a las vistas según el rol del empleado
4. **Modelo `User`**: Usuario de Django, opcionalmente vinculado a un empleado

### Flujo de Autenticación y Autorización

```
Usuario se autentica → Django User → Empleado → NivelAcceso → Permisos
```

## Niveles de Acceso Disponibles

### 1. Administrador
**Descripción**: Acceso completo al sistema
**Permisos**:
- ✅ Gestión completa de empleados (crear, editar, listar, asignar usuarios)
- ✅ Gestión completa de usuarios del sistema
- ✅ Gestión completa de clientes (crear, editar, listar, eliminar)
- ✅ Gestión completa de productos (crear, editar, listar, actualizar stock)
- ✅ Gestión completa de ventas (crear, listar, cancelar, registrar pagos)
- ✅ Acceso a todas las configuraciones (tasa de cambio, exportar/importar datos)
- ✅ Visualización de todos los reportes
- ✅ Acceso al panel de administración de Django (si `is_staff=True`)

### 2. Secretaria
**Descripción**: Acceso a operaciones comerciales básicas y reportes
**Permisos**:
- ❌ Gestión de empleados
- ❌ Gestión de usuarios del sistema
- ✅ Gestión básica de clientes (crear, editar, listar)
- ❌ Eliminar clientes
- ✅ Gestión de productos (crear, editar, listar, actualizar stock)
- ✅ Gestión de ventas (crear, listar, registrar pagos)
- ❌ Cancelar ventas
- ✅ Visualización de reportes básicos (productos más vendidos, ventas pendientes)
- ❌ Configuraciones del sistema
- ❌ Exportar/importar datos

### 3. Supervisor
**Descripción**: Supervisión de operaciones y reportes avanzados
**Permisos**:
- ❌ Gestión de empleados
- ❌ Gestión de usuarios del sistema
- ✅ Gestión completa de clientes
- ✅ Gestión completa de productos
- ✅ Gestión completa de ventas (incluye cancelaciones)
- ✅ Visualización de todos los reportes
- ✅ Configuración básica (tasa de cambio)
- ❌ Exportar/importar datos

### 4. Vendedor
**Descripción**: Acceso básico para realizar ventas
**Permisos**:
- ❌ Gestión de empleados
- ❌ Gestión de usuarios del sistema
- ✅ Visualización de clientes
- ✅ Crear nuevos clientes
- ❌ Editar/eliminar clientes existentes
- ✅ Visualización de productos
- ❌ Crear/editar productos
- ✅ Crear ventas
- ✅ Visualización de ventas propias
- ✅ Registrar pagos (ventas pendientes)
- ❌ Cancelar ventas
- ✅ Reportes básicos de ventas
- ❌ Configuraciones

## Implementación Técnica

### EmpleadoRolMixin

```python
class EmpleadoRolMixin(LoginRequiredMixin):
    roles_permitidos = ['Administrador']  # Por defecto solo administradores
    
    def dispatch(self, request, *args, **kwargs):
        # Verificaciones:
        # 1. Usuario autenticado
        # 2. Tiene empleado asociado
        # 3. Rol del empleado está en roles_permitidos
```

### Uso en Vistas

```python
class MiVista(EmpleadoRolMixin, ListView):
    roles_permitidos = ['Administrador', 'Secretaria']
    # resto de la vista...
```

## Configuración de Roles por Vista

### Gestión de Empleados
```python
EmpleadoListView: ['Administrador']
EmpleadoCreateView: ['Administrador']
EmpleadoUpdateView: ['Administrador']
EmpleadoDetailView: ['Administrador']
AsignarUsuarioEmpleadoView: ['Administrador']
```

### Gestión de Usuarios
```python
UsuariosListView: ['Administrador']
CrearUsuarioView: ['Administrador']
```

### Gestión de Clientes
```python
ClienteListView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
ClienteCreateView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
ClienteUpdateView: ['Administrador', 'Secretaria', 'Supervisor']
ClienteDetailView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
ClienteDeleteView: ['Administrador']
```

### Gestión de Productos
```python
ProductoListView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
ProductoCreateView: ['Administrador', 'Secretaria', 'Supervisor']
ProductoUpdateView: ['Administrador', 'Secretaria', 'Supervisor']
ProductoDetailView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
ProductoStockUpdateView: ['Administrador', 'Secretaria', 'Supervisor']
```

### Gestión de Ventas
```python
VentaListView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
VentaCreateView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
VentaDetailView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
VentasPendientesView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
RegistrarPagoView: ['Administrador', 'Secretaria', 'Supervisor', 'Vendedor']
cancelar_venta: ['Administrador', 'Supervisor']
```

### Configuración del Sistema
```python
TasaCambioListView: ['Administrador', 'Supervisor']
TasaCambioCreateView: ['Administrador']
TasaCambioUpdateView: ['Administrador']
TasaCambioManualView: ['Administrador']
export_database_view: ['Administrador']
import_database_view: ['Administrador']
```

## Ejemplo: ¿Qué puede ver una Secretaria?

Una empleada con nivel "Secretaria" al iniciar sesión tendrá acceso a:

### Menú Principal
- ✅ **Productos**: Lista, crear, editar, actualizar stock
- ❌ **Empleados**: No visible
- ✅ **Clientes**: Lista, crear, editar (sin eliminar)
- ✅ **Ventas**: Lista, crear, registrar pagos
- ✅ **Recibos de Venta**: Lista de recibos
- ❌ **Configuración**: No visible

### Funcionalidades Específicas
- ✅ Registrar nuevas ventas
- ✅ Cobrar ventas pendientes (abonos)
- ✅ Registrar nuevos clientes
- ✅ Buscar y consultar productos
- ✅ Ver reportes de productos más vendidos
- ❌ Cancelar ventas ya registradas
- ❌ Eliminar clientes o productos
- ❌ Gestionar empleados o usuarios
- ❌ Modificar configuraciones del sistema

### Interfaz de Usuario
- El sidebar mostrará solo las opciones permitidas
- Los botones de acciones restringidas no aparecerán
- Los mensajes de error redirigirán al inicio si intenta acceder a funciones no permitidas

## Seguridad

### Principios Implementados
1. **Principle of Least Privilege**: Cada rol tiene solo los permisos mínimos necesarios
2. **Defense in Depth**: Múltiples capas de verificación (autenticación + autorización)
3. **Fail Secure**: Si no se puede verificar el rol, se deniega el acceso

### Verificaciones de Seguridad
1. **Usuario autenticado**: Verificación de Django
2. **Empleado asociado**: El usuario debe tener un empleado vinculado
3. **Nivel de acceso válido**: El empleado debe tener un nivel asignado
4. **Rol permitido**: El nivel debe estar en la lista de roles permitidos para la vista

## Mantenimiento

### Agregar Nuevos Roles
1. Crear migración para agregar el nuevo `NivelAcceso`
2. Actualizar las listas `roles_permitidos` en las vistas correspondientes
3. Actualizar la documentación
4. Actualizar las plantillas del sidebar si es necesario

### Modificar Permisos
1. Identificar las vistas afectadas
2. Modificar las listas `roles_permitidos`
3. Probar el acceso con usuarios de diferentes roles
4. Actualizar la documentación

## Consideraciones de Implementación

### Separación de Responsabilidades
- **Empleados**: Información laboral y de contacto
- **Usuarios**: Acceso al sistema y autenticación
- **Niveles de Acceso**: Definición de permisos
- **Vistas**: Implementación de restricciones

### Flexibilidad
- Un empleado puede existir sin usuario (empleados que no usan el sistema)
- Un usuario puede existir sin empleado (usuarios técnicos o temporales)
- Los niveles de acceso son configurables desde la administración
- Las listas de roles permitidos son fácilmente modificables en el código