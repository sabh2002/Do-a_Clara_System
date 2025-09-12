# En Corporacion Agricola Doña Clara C.A./black_invoices/forms/user_profile_form.py
from django import forms
from django.contrib.auth.models import User
from ..models import Empleado

class UserProfileForm(forms.ModelForm):
    username = forms.CharField(
        label='Nombre de Usuario',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Requerido. Dejar como está o elegir uno nuevo."
    )
    email = forms.EmailField(
        label='Correo Electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        required=False # O True si el email es obligatorio para tu lógica de negocio
    )
    # Los campos 'nombre' y 'apellido' vienen del modelo Empleado a través de Meta
    
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password', 'placeholder': 'Dejar en blanco para no cambiar'}),
        required=False,
        label='Nueva Contraseña'
    )
    confirm_new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password', 'placeholder': 'Confirmar nueva contraseña'}),
        required=False,
        label='Confirmar Nueva Contraseña'
    )

    class Meta:
        model = Empleado
        fields = ['nombre', 'apellido'] # Campos del modelo Empleado
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Se espera que 'instance' sea una instancia de Empleado
        super().__init__(*args, **kwargs)
        self.user_instance = None
        if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
            self.user_instance = self.instance.user
            self.fields['username'].initial = self.user_instance.username
            self.fields['email'].initial = self.user_instance.email
            # 'nombre' y 'apellido' se llenan a través de la instancia del Empleado

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.user_instance and self.user_instance.username != username:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("Este nombre de usuario ya está en uso. Por favor, elige otro.")
        return username
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.user_instance and email and self.user_instance.email != email:
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError("Este correo electrónico ya está en uso por otro usuario.")
        return email

    def clean_confirm_new_password(self):
        new_password = self.cleaned_data.get("new_password")
        confirm_new_password = self.cleaned_data.get("confirm_new_password")
        if new_password and new_password != confirm_new_password:
            raise forms.ValidationError("Las nuevas contraseñas no coinciden.")
        return confirm_new_password

    def save(self, commit=True):
        # Guardar la instancia de Empleado (nombre, apellido)
        empleado = super().save(commit=False) # No guarda aún en la BD

        # Actualizar la instancia de User asociada
        if self.user_instance:
            self.user_instance.username = self.cleaned_data['username']
            self.user_instance.email = self.cleaned_data['email']
            # Actualizar first_name y last_name del User desde el Empleado
            self.user_instance.first_name = empleado.nombre 
            self.user_instance.last_name = empleado.apellido

            new_password = self.cleaned_data.get("new_password")
            if new_password:
                self.user_instance.set_password(new_password)
            
            if commit:
                self.user_instance.save()
        
        if commit:
            empleado.save() # Ahora guarda el Empleado

        return empleado