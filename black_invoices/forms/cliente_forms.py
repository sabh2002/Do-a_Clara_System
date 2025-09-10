from django import forms
from django.core.exceptions import ValidationError
from ..models import Cliente


class ClienteForm(forms.ModelForm):
    # Campo separado para el prefijo del teléfono
    prefijo_telefono = forms.ChoiceField(
        choices=[
            ('0416', '0416'),
            ('0426', '0426'), 
            ('0414', '0414'),
            ('0424', '0424'),
            ('0412', '0412'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'prefijo_telefono'
        }),
        label='Prefijo',
        initial='0416'
    )
    
    # Campo para el número sin prefijo
    numero_telefono = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234567',
            'id': 'numero_telefono',
            'pattern': '[0-9]{7}',
            'title': 'Ingrese 7 dígitos'
        }),
        label='Número'
    )

    class Meta:
        model = Cliente
        fields = ['tipo_documento', 'numero_documento', 'nombre_completo', 'email', 'direccion']
        widgets = {
            'tipo_documento': forms.Select(attrs={
                'class': 'form-control',
                'id': 'tipo_documento'
            }),
            'numero_documento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12345678',
                'pattern': '[0-9]{6,9}',
                'title': 'Solo números, entre 6 y 9 dígitos'
            }),
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del cliente o empresa'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'ejemplo@email.com (Opcional)'
            }),
            'direccion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dirección completa'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si estamos editando un cliente existente, separar el teléfono
        if self.instance and self.instance.pk and self.instance.telefono:
            telefono = self.instance.telefono
            # Buscar el prefijo en el teléfono
            for prefijo, _ in self.fields['prefijo_telefono'].choices:
                if telefono.startswith(prefijo):
                    self.fields['prefijo_telefono'].initial = prefijo
                    self.fields['numero_telefono'].initial = telefono[4:]  # Remover prefijo
                    break
        
        # Hacer email opcional visualmente
        self.fields['email'].required = False
        self.fields['email'].help_text = "Campo opcional"
    
    def clean_numero_documento(self):
        """Validación personalizada para número de documento"""
        numero = self.cleaned_data.get('numero_documento')
        tipo = self.cleaned_data.get('tipo_documento')
        
        if numero:
            # Limpiar el número
            numero = numero.replace(' ', '').replace('-', '')
            
            if not numero.isdigit():
                raise ValidationError('El número debe contener solo dígitos')
            
            # Validar longitud según el tipo
            if tipo in ['V', 'E']:
                if len(numero) < 6 or len(numero) > 8:
                    raise ValidationError('Para cédulas V/E debe tener entre 6 y 8 dígitos')
            elif tipo in ['J', 'G']:
                if len(numero) < 8 or len(numero) > 9:
                    raise ValidationError('Para RIF J/G debe tener entre 8 y 9 dígitos')
            
            # Verificar que no exista otro cliente con la misma cédula completa
            cedula_completa = f"{tipo}{numero}"
            existing = Cliente.objects.filter(cedula=cedula_completa)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('Ya existe un cliente con este documento')
        
        return numero
    
    def clean_numero_telefono(self):
        """Validación para el número de teléfono"""
        numero = self.cleaned_data.get('numero_telefono')
        
        if numero:
            # Remover espacios y validar que solo tenga números
            numero = numero.replace(' ', '')
            if not numero.isdigit():
                raise ValidationError('El número debe contener solo dígitos')
            
            if len(numero) != 7:
                raise ValidationError('El número debe tener exactamente 7 dígitos')
        
        return numero
    
    def clean(self):
        """Validación general del formulario"""
        cleaned_data = super().clean()
        prefijo = cleaned_data.get('prefijo_telefono')
        numero = cleaned_data.get('numero_telefono')
        
        # Combinar prefijo y número para formar el teléfono completo
        if prefijo and numero:
            telefono_completo = f"{prefijo}{numero}"
            cleaned_data['telefono'] = telefono_completo
        
        return cleaned_data
    
    def save(self, commit=True):
        """Guardar con el teléfono combinado"""
        instance = super().save(commit=False)
        
        # Asignar el teléfono combinado
        if hasattr(self, 'cleaned_data') and 'telefono' in self.cleaned_data:
            instance.telefono = self.cleaned_data['telefono']
        
        if commit:
            instance.save()
        return instance