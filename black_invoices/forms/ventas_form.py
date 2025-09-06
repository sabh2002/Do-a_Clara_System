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

# Formset mejorado para manejar cantidades decimales
class DetalleFacturaForm(forms.ModelForm):
    class Meta:
        model = DetalleFactura
        fields = ['producto', 'cantidad', 'tipo_factura']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control select2 producto-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control cantidad', 'min': '0.001', 'step': '0.001'}),
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
                    f'Disponible: {producto.stock}'
                )
        
        return cleaned_data

DetalleFacturaFormSet = inlineformset_factory(
    Factura, DetalleFactura,
    form=DetalleFacturaForm,
    extra=1, 
    can_delete=True
)

class PagoVentaForm(forms.ModelForm):
    """Formulario para registrar pagos en ventas a crédito"""
    
    class Meta:
        model = PagoVenta
        fields = ['monto', 'metodo_pago', 'referencia']
        widgets = {
            'monto': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0.01', 
                'step': '0.01',
                'placeholder': 'Monto a pagar'
            }),
            'metodo_pago': forms.Select(attrs={'class': 'form-control'}),
            'referencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de referencia (opcional)',
                'maxlength': '50'
            })
        }
        
    def __init__(self, *args, venta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.venta = venta
        
        if venta:
            # Establecer máximo según saldo pendiente
            self.fields['monto'].widget.attrs['max'] = str(venta.saldo_pendiente)
            
    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto and self.venta:
            if monto > self.venta.saldo_pendiente:
                raise forms.ValidationError(
                    f'El monto no puede exceder el saldo pendiente: ${self.venta.saldo_pendiente}'
                )
        return monto
    
    def clean(self):
        cleaned_data = super().clean()
        metodo_pago = cleaned_data.get('metodo_pago')
        referencia = cleaned_data.get('referencia', '').strip()
        
        # Validar referencia para métodos que la requieren
        if metodo_pago in ['pago_movil', 'transferencia'] and not referencia:
            metodo_display = dict(PagoVenta.METODOS_PAGO_CHOICES).get(metodo_pago, metodo_pago)
            raise forms.ValidationError(f'La referencia es obligatoria para {metodo_display}')
        
        return cleaned_data