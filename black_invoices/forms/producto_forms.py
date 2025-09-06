from django import forms
from ..models import Producto, UnidadMedida

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'descripcion', 'unidad_medida', 'precio_compra', 'precio', 'stock', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Nombre del producto'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Descripción del producto'
            }),
            'unidad_medida': forms.Select(attrs={
                'class': 'form-control'
            }),
            'precio_compra': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0.01', 
                'step': '0.01',
                'placeholder': 'Precio de compra en USD'
            }),
            'precio': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0.01', 
                'step': '0.01',
                'placeholder': 'Precio de venta en USD'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '0',
                'step': '0.001',
                'placeholder': 'Cantidad en inventario (ej: 25.5)'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        
        labels = {
            'precio_compra': 'Precio de Compra (USD)',
            'precio': 'Precio de Venta (USD)',
            'unidad_medida': 'Unidad de Medida',
            'stock': 'Stock Disponible'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar solo unidades de medida activas
        self.fields['unidad_medida'].queryset = UnidadMedida.objects.filter(activo=True)
        
        # Agregar clases CSS adicionales
        for field_name, field in self.fields.items():
            if field_name != 'activo':
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        """Validaciones personalizadas del formulario"""
        cleaned_data = super().clean()
        precio_compra = cleaned_data.get('precio_compra')
        precio_venta = cleaned_data.get('precio')
        
        # Validar que el precio de venta sea mayor al de compra
        if precio_compra and precio_venta:
            if precio_venta <= precio_compra:
                raise forms.ValidationError(
                    'El precio de venta debe ser mayor al precio de compra'
                )
        
        return cleaned_data


# ==== CREAR NUEVO FORMULARIO PARA BÚSQUEDA RÁPIDA ====

class ProductoSearchForm(forms.Form):
    """Formulario para búsqueda rápida de productos en ventas"""
    
    busqueda = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar producto por nombre...',
            'autocomplete': 'off'
        })
    )
    
    unidad_medida = forms.ModelChoiceField(
        queryset=UnidadMedida.objects.filter(activo=True),
        required=False,
        empty_label="Todas las unidades",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    solo_con_stock = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )