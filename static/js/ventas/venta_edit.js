$(document).ready(function() {
    console.log('=== VENTA EDIT JS INICIADO ===');
    console.log('venta_edit.js cargado correctamente');
    
    // ✅ VALIDACIÓN ROBUSTA DE VARIABLES
    if (typeof productosActuales === 'undefined') {
        console.error('❌ productosActuales no está definido');
        productosActuales = [];
    }
    if (typeof tasaCambio === 'undefined') {
        console.error('❌ tasaCambio no está definido');
        tasaCambio = 1;
    }
    
    console.log('✅ productosActuales:', productosActuales);
    console.log('✅ tasaCambio:', tasaCambio);
    
    // ✅ INICIALIZACIÓN SEGURA
    try {
        inicializarFormulario();
        console.log('✅ Formulario inicializado');
    } catch(e) {
        console.error('❌ Error inicializando formulario:', e);
    }
    
    try {
        actualizarTotales(); // Solo calcular totales de productos existentes
        console.log('✅ Totales actualizados');
    } catch(e) {
        console.error('❌ Error actualizando totales:', e);
    }
    
    // ✅ EVENT LISTENERS ROBUSTOS CON DELAYS
    setTimeout(function() {
        // Botón Agregar Producto
        const btnAgregar = $('#agregarProducto');
        if (btnAgregar.length > 0) {
            btnAgregar.off('click').on('click', function() {
                console.log('✅ Botón Agregar Producto clickeado');
                try {
                    $('#modalProducto').modal('show');
                } catch(e) {
                    console.error('❌ Error mostrando modal:', e);
                }
            });
            console.log('✅ Event listener Agregar Producto registrado');
        } else {
            console.error('❌ Botón Agregar Producto NO encontrado');
        }
        
        // Botón Limpiar Productos
        const btnLimpiar = $('#limpiarProductos');
        if (btnLimpiar.length > 0) {
            btnLimpiar.off('click').on('click', function() {
                console.log('✅ Botón Limpiar Productos clickeado');
                try {
                    limpiarTodosLosProductos();
                } catch(e) {
                    console.error('❌ Error limpiando productos:', e);
                }
            });
            console.log('✅ Event listener Limpiar Productos registrado');
        } else {
            console.error('❌ Botón Limpiar Productos NO encontrado');
        }
        
        // Select Tipo Venta
        const selectTipo = $('#tipoVenta');
        if (selectTipo.length > 0) {
            selectTipo.off('change').on('change', function() {
                console.log('✅ Tipo Venta cambiado a:', $(this).val());
                try {
                    toggleMetodoPago();
                } catch(e) {
                    console.error('❌ Error toggle método pago:', e);
                }
            });
            console.log('✅ Event listener Tipo Venta registrado');
        } else {
            console.error('❌ Select Tipo Venta NO encontrado');
        }
        
    }, 200); // Delay de 200ms para asegurar DOM completo
    
    $(document).on('click', '.seleccionar-producto', function() {
        agregarProducto($(this));
    });
    
    $(document).on('click', '.eliminar-producto', function() {
        console.log('Botón Eliminar Producto clickeado');
        eliminarProducto($(this));
    });
    
    $(document).on('input', '.cantidad-input', function() {
        actualizarSubtotal($(this));
    });
    
    // Búsqueda de productos en modal
    $('#buscarProducto').on('input', function() {
        const filtro = $(this).val().toLowerCase();
        $('#tablaProductosModal tbody tr').each(function() {
            const texto = $(this).text().toLowerCase();
            $(this).toggle(texto.includes(filtro));
        });
    });
    
    // Validación del formulario
    $('#formVentaEdit').submit(function(e) {
        if (!validarFormulario()) {
            e.preventDefault();
        }
    });
    
    // Inicializar select2 si existe
    if (typeof $.fn.select2 !== 'undefined') {
        $('.select2').select2({
            theme: 'bootstrap4',
            width: '100%'
        });
    } else {
        console.warn('Select2 no está disponible');
    }
    
    // NO inicializar DataTable en el modal para evitar conflictos
    // La búsqueda funciona con el filtro simple por texto
    console.log('DataTable deshabilitado intencionalmente para evitar conflictos');
});

function inicializarFormulario() {
    toggleMetodoPago();
    actualizarTotales();
}

// Función eliminada - los productos ahora se renderizan directamente desde Django

function toggleMetodoPago() {
    const tipoVenta = $('#tipoVenta').val();
    const metodoPagoDiv = $('#metodoPagoDiv');
    
    if (tipoVenta === 'credito') {
        metodoPagoDiv.hide();
        $('#metodoPago').prop('required', false);
    } else {
        metodoPagoDiv.show();
        $('#metodoPago').prop('required', true);
    }
}

function agregarProducto(boton) {
    const id = boton.data('id');
    const nombre = boton.data('nombre');
    const precio = parseFloat(boton.data('precio'));
    const stock = parseInt(boton.data('stock'));
    
    // Verificar si el producto ya está en la tabla
    if ($(`#producto_${id}`).length > 0) {
        mostrarAlerta('warning', 'Este producto ya está agregado a la venta');
        return;
    }
    
    if (stock <= 0) {
        mostrarAlerta('error', 'Este producto no tiene stock disponible');
        return;
    }
    
    agregarProductoATabla(id, nombre, precio, 1, stock, true);
    $('#modalProducto').modal('hide');
}

function agregarProductoATabla(id, nombre, precio, cantidad, stock, esNuevo = true) {
    console.log(`agregarProductoATabla llamado con:`, {id, nombre, precio, cantidad, stock, esNuevo});
    
    // Eliminar fila vacía si existe
    $('.empty-row').remove();
    
    const subtotal = precio * cantidad;
    contadorFormas++;
    
    // Determinar color del badge según el stock
    let badgeClass = 'badge-info';
    if (stock <= 5) badgeClass = 'badge-danger';
    else if (stock <= 10) badgeClass = 'badge-warning';
    
    const fila = `
        <tr id="producto_${id}">
            <td>
                <strong>${nombre}</strong>
                <input type="hidden" name="productos[${contadorFormas}][id]" value="${id}">
                <br><small class="text-muted">ID: ${id}</small>
            </td>
            <td>
                <span class="badge ${badgeClass}">${stock} unidades</span>
            </td>
            <td>
                <strong>$${precio.toFixed(2)}</strong>
                <input type="hidden" name="productos[${contadorFormas}][precio]" value="${precio}">
            </td>
            <td>
                <input type="number" 
                       class="form-control cantidad-input" 
                       name="productos[${contadorFormas}][cantidad]" 
                       value="${cantidad}" 
                       min="1" 
                       max="${stock}"
                       data-precio="${precio}"
                       data-stock="${stock}"
                       data-nombre="${nombre}"
                       required>
            </td>
            <td class="subtotal-cell">
                <strong>$${subtotal.toFixed(2)}</strong>
            </td>
            <td>
                <button type="button" class="btn btn-danger btn-sm eliminar-producto" title="Eliminar ${nombre}">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>
    `;
    
    console.log(`Agregando fila HTML:`, fila);
    $('#productosBody').append(fila);
    console.log(`Filas en tabla después de agregar:`, $('#productosBody tr').length);
    
    if (esNuevo) {
        actualizarTotales();
        mostrarAlerta('success', `Producto "${nombre}" agregado correctamente`);
    }
}

function eliminarProducto(boton) {
    if (confirm('¿Está seguro de eliminar este producto de la venta?')) {
        boton.closest('tr').remove();
        actualizarTotales();
        mostrarAlerta('info', 'Producto eliminado');
    }
}

function actualizarSubtotal(input) {
    const cantidad = parseInt(input.val()) || 0;
    const precio = parseFloat(input.data('precio'));
    const stock = parseInt(input.data('stock'));
    
    // Validar cantidad
    if (cantidad > stock) {
        input.val(stock);
        mostrarAlerta('warning', `Cantidad ajustada al stock disponible (${stock})`);
        return;
    }
    
    if (cantidad < 1) {
        input.val(1);
        return;
    }
    
    const subtotal = precio * cantidad;
    input.closest('tr').find('.subtotal-cell').text(`$${subtotal.toFixed(2)}`);
    
    actualizarTotales();
}

function actualizarTotales() {
    let subtotal = 0;
    
    // Recalcular subtotal basado en productos visibles en la tabla
    $('#productosBody tr').each(function() {
        if ($(this).find('.cantidad-input').length > 0) {
            const cantidad = parseFloat($(this).find('.cantidad-input').val()) || 0;
            const precio = parseFloat($(this).find('.cantidad-input').data('precio')) || 0;
            const subtotalProducto = cantidad * precio;
            subtotal += subtotalProducto;
            
            // Actualizar subtotal individual en la fila
            $(this).find('.subtotal-cell strong').text(`$${subtotalProducto.toFixed(2)}`);
        }
    });
    
    const iva = subtotal * 0.16;
    const total = subtotal + iva;
    
    $('#subtotalVenta').text(`$${subtotal.toFixed(2)}`);
    $('#ivaVenta').text(`$${iva.toFixed(2)}`);
    $('#totalVenta').text(`$${total.toFixed(2)}`);
    
    console.log(`Totales actualizados - Subtotal: ${subtotal}, IVA: ${iva}, Total: ${total}`);
}

function validarFormulario() {
    // Validar que hay al menos un producto con input de cantidad
    const productosConCantidad = $('#productosBody tr').filter(function() {
        return $(this).find('.cantidad-input').length > 0;
    });
    
    if (productosConCantidad.length === 0) {
        mostrarAlerta('error', 'Debe agregar al menos un producto a la venta');
        return false;
    }
    
    // Validar cliente
    if (!$('select[name="cliente"]').val()) {
        mostrarAlerta('error', 'Debe seleccionar un cliente');
        return false;
    }
    
    // Validar tipo de venta
    if (!$('#tipoVenta').val()) {
        mostrarAlerta('error', 'Debe seleccionar el tipo de venta');
        return false;
    }
    
    // Validar método de pago para ventas de contado
    if ($('#tipoVenta').val() === 'contado' && !$('#metodoPago').val()) {
        mostrarAlerta('error', 'Debe seleccionar un método de pago para ventas de contado');
        return false;
    }
    
    // Validar cantidades
    let validacionOk = true;
    $('.cantidad-input').each(function() {
        const cantidad = parseInt($(this).val()) || 0;
        const stock = parseInt($(this).data('stock'));
        
        if (cantidad <= 0) {
            mostrarAlerta('error', 'Todas las cantidades deben ser mayores a 0');
            validacionOk = false;
            return false;
        }
        
        if (cantidad > stock) {
            mostrarAlerta('error', 'Hay productos con cantidad mayor al stock disponible');
            validacionOk = false;
            return false;
        }
    });
    
    return validacionOk;
}

function limpiarTodosLosProductos() {
    if (confirm('¿Está seguro de eliminar TODOS los productos de la venta? Esta acción no se puede deshacer. Tendrá que recargar la página para recuperar los productos originales.')) {
        // Encontrar y remover solo las filas con productos (que tienen .cantidad-input)
        $('#productosBody tr').each(function() {
            if ($(this).find('.cantidad-input').length > 0) {
                $(this).remove();
            }
        });
        
        // Si no quedan filas con productos, agregar mensaje vacío
        if ($('#productosBody tr').filter(function() { return $(this).find('.cantidad-input').length > 0; }).length === 0) {
            $('#productosBody').append(`
                <tr class="empty-row">
                    <td colspan="6" class="text-center text-muted">
                        <i class="fas fa-info-circle"></i> No hay productos en la venta
                        <br><small>Use "Agregar Más Productos" para agregar productos</small>
                    </td>
                </tr>
            `);
        }
        
        contadorFormas = 0;
        actualizarTotales();
        mostrarAlerta('warning', 'Todos los productos han sido eliminados de la venta');
    }
}

// Función eliminada - los productos originales están siempre cargados desde Django

function mostrarAlerta(tipo, mensaje) {
    // Remover alertas anteriores
    $('.alert-temp').remove();
    
    let claseAlerta;
    switch (tipo) {
        case 'success':
            claseAlerta = 'alert-success';
            break;
        case 'error':
            claseAlerta = 'alert-danger';
            break;
        case 'warning':
            claseAlerta = 'alert-warning';
            break;
        case 'info':
            claseAlerta = 'alert-info';
            break;
        default:
            claseAlerta = 'alert-info';
    }
    
    const alerta = `
        <div class="alert ${claseAlerta} alert-dismissible fade show alert-temp" role="alert">
            ${mensaje}
            <button type="button" class="close" data-dismiss="alert">
                <span>&times;</span>
            </button>
        </div>
    `;
    
    $('.container-fluid').prepend(alerta);
    
    // Auto-ocultar después de 5 segundos
    setTimeout(function() {
        $('.alert-temp').fadeOut();
    }, 5000);
}