from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from ..models import Empleado

class EmpleadoForm(forms.ModelForm):
    """Formulario para registrar empleados con opción de crear usuario"""
    
    # Opción para crear usuario
    crear_usuario = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Crear usuario del sistema",
        help_text="Marque esta opción si desea crear un usuario de acceso al sistema para este empleado"
    )
    
    # Campos opcionales para usuario
    username = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Nombre de usuario",
        help_text="Nombre único para acceder al sistema"
    )
    
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Contraseña",
        help_text="Contraseña para acceder al sistema"
    )
    
    password_confirm = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirmar contraseña"
    )
    
    is_staff = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Acceso a administración Django",
        help_text="¿Puede acceder al panel de administración de Django?"
    )
    
    class Meta:
        model = Empleado
        fields = ['cedula', 'nombre', 'apellido', 'email', 'telefono', 'direccion', 'nivel_acceso', 'activo']
        widgets = {
            'cedula': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'V12345678 o E12345678',
                'pattern': '^[VE]-?[0-9]{6,8}$'
            }),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'empleado@empresa.com (opcional)'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '04161234567'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'nivel_acceso': forms.Select(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer email y teléfono opcionales visualmente
        self.fields['email'].required = False
        self.fields['telefono'].required = False
        self.fields['direccion'].required = False
    
    def clean_cedula(self):
        """Validación personalizada para cédula"""
        cedula = self.cleaned_data.get('cedula')
        
        if cedula:
            # Normalizar: remover guiones y convertir a mayúsculas
            cedula = cedula.replace('-', '').upper()
            
            # Validaciones básicas
            if not cedula.startswith(('V', 'E')):
                raise ValidationError('La cédula debe comenzar con V o E')
            
            numero_parte = cedula[1:]
            if not numero_parte.isdigit():
                raise ValidationError('Después de V o E solo debe haber números')
            
            if len(numero_parte) < 6 or len(numero_parte) > 8:
                raise ValidationError('La cédula debe tener entre 6 y 8 dígitos')
            
            # Verificar que no exista otra cédula igual (excepto si es edición)
            existing = Empleado.objects.filter(cedula=cedula)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('Ya existe un empleado con esta cédula')
        
        return cedula
    
    def clean_username(self):
        """Validación para nombre de usuario"""
        username = self.cleaned_data.get('username')
        crear_usuario = self.cleaned_data.get('crear_usuario')
        
        if crear_usuario and not username:
            raise ValidationError('Debe proporcionar un nombre de usuario')
        
        if username and User.objects.filter(username=username).exists():
            raise ValidationError('Este nombre de usuario ya existe')
            
        return username
    
    def clean(self):
        """Validaciones generales del formulario"""
        cleaned_data = super().clean()
        crear_usuario = cleaned_data.get('crear_usuario')
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if crear_usuario:
            if not username:
                self.add_error('username', 'Nombre de usuario es requerido')
            if not password:
                self.add_error('password', 'Contraseña es requerida')
            if not password_confirm:
                self.add_error('password_confirm', 'Debe confirmar la contraseña')
            
            if password and password_confirm and password != password_confirm:
                self.add_error('password_confirm', 'Las contraseñas no coinciden')
        
        return cleaned_data


class AsignarUsuarioEmpleadoForm(forms.Form):
    """Formulario para asignar un usuario existente a un empleado"""
    
    usuario = forms.ModelChoiceField(
        queryset=User.objects.none(),  # Se configurará en __init__
        empty_label="Seleccione un usuario",
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Usuario del sistema que se asignará a este empleado"
    )
    
    def __init__(self, *args, **kwargs):
        empleado = kwargs.pop('empleado', None)
        super().__init__(*args, **kwargs)
        
        # Solo mostrar usuarios que no están asignados a empleados
        # o el usuario actual del empleado si existe
        usuarios_disponibles = User.objects.filter(empleado__isnull=True)
        if empleado and empleado.user:
            usuarios_disponibles = usuarios_disponibles.union(
                User.objects.filter(pk=empleado.user.pk)
            )
            
        self.fields['usuario'].queryset = usuarios_disponibles


class CrearUsuarioForm(forms.Form):
    """Formulario para crear nuevos usuarios (separado de empleados)"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Nombre de usuario único para el sistema"
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Contraseña para acceder al sistema"
    )
    
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirmar contraseña"
    )
    
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Nombre"
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Apellido"
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    is_staff = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="¿Puede acceder al panel de administración?",
        label="Acceso a administración"
    )
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError('Este nombre de usuario ya existe')
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise ValidationError('Las contraseñas no coinciden')
        
        return cleaned_data
    
    def save(self):
        """Crear el usuario con los datos del formulario"""
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
            email=self.cleaned_data.get('email', ''),
            is_staff=self.cleaned_data.get('is_staff', False)
        )
        return user