# forms/venta_forms.py
from django import forms
from django.forms import inlineformset_factory
from ..models import Factura, DetalleFactura, Producto, Cliente, TipoFactura, PagoVenta, Ventas
from decimal import Decimal

class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = ['cliente', 'metodo_pag']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control select2'}),
            'metodo_pag': forms.Select(attrs={'class': 'form-control'})
        }

# Formset mejorado para manejar cantidades decimales con incrementos enteros
class DetalleFacturaForm(forms.ModelForm):
    class Meta:
        model = DetalleFactura
        fields = ['producto', 'cantidad', 'tipo_factura']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control select2 producto-select'}),
            # ✅ CORREGIDO: step="any" permite enteros y decimales sin conflictos de validación
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control cantidad', 
                'min': '0.001', 
                'step': 'any',  # Permite cualquier valor decimal o entero
                'placeholder': 'Ej: 1, 2.5, 10.75'
            }),
            'tipo_factura': forms.Select(attrs={'class': 'form-control'})
        }
    
    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        cantidad = cleaned_data.get('cantidad')
        
        if producto and cantidad:
            # Validar cantidad según unidad de medida
            es_valida, mensaje = producto.validar_cantidad_segun_unidad(cantidad)
            if not es_valida:
                raise forms.ValidationError(mensaje)
            
            # Validar stock disponible
            if cantidad > producto.stock:
                raise forms.ValidationError(
                    f'Stock insuficiente para {producto.nombre}. '
                    f'Disponible: {producto.stock}, solicitado: {cantidad}'
                )
        
        return cleaned_data

# Formset para detalles de factura
DetalleFacturaFormSet = inlineformset_factory(
    Factura, 
    DetalleFactura, 
    form=DetalleFacturaForm,
    extra=1, 
    can_delete=True,
    min_num=1,
    validate_min=True
)

# ✅ FORMULARIO CORREGIDO - SIN CAMPO OBSERVACIONES
class PagoVentaForm(forms.ModelForm):
    """Formulario para registrar pagos de ventas a crédito"""
    
    class Meta:
        model = PagoVenta
        fields = ['monto', 'metodo_pago', 'referencia']  # Solo los campos que existen
        widgets = {
            'monto': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01',
                'placeholder': 'Monto del pago'
            }),
            'metodo_pago': forms.Select(attrs={'class': 'form-control'}),
            'referencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de referencia (opcional)',
                'maxlength': '50'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.venta = kwargs.pop('venta', None)
        super().__init__(*args, **kwargs)
        
        # Si se proporciona la venta, establecer límites
        if self.venta:
            saldo_pendiente = self.venta.saldo_pendiente
            self.fields['monto'].widget.attrs['max'] = str(saldo_pendiente)
            self.fields['monto'].help_text = f'Saldo pendiente: ${saldo_pendiente:,.2f}'
    
    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        
        if self.venta and monto:
            if monto > self.venta.saldo_pendiente:
                raise forms.ValidationError(
                    f'El monto no puede ser mayor al saldo pendiente '
                    f'(${self.venta.saldo_pendiente:,.2f})'
                )
        
        return monto
    
    def clean(self):
        cleaned_data = super().clean()
        metodo_pago = cleaned_data.get('metodo_pago')
        referencia = cleaned_data.get('referencia', '').strip()
        
        # Validar referencia para métodos que la requieren
        if metodo_pago in ['pago_movil', 'transferencia'] and not referencia:
            metodo_display = dict(PagoVenta.METODOS_PAGO_CHOICES).get(metodo_pago, metodo_pago)
            raise forms.ValidationError(
                f'La referencia es obligatoria para {metodo_display}'
            )
        
        return cleaned_data