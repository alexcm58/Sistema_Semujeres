# core/forms.py

from django import forms
from .models import Usuario
from .models import AnexoRequerido

# forms.py
class CrearUsuarioForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirmar contraseña")

    class Meta:
        model = Usuario
        fields = [
            'username',
            'entidad_federativa',
            'correo',
            'rol',
            'password',
            'confirm_password',
            'is_active',
        ]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Las contraseñas no coinciden")

class EditarUsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'username',
            'entidad_federativa',
            'correo',
        ]

class EditarPerfilAdminForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['username', 'entidad_federativa', 'correo']


class AnexoForm(forms.ModelForm):
    class Meta:
        model = AnexoRequerido
        fields = ['nombre', 'descripcion', 'obligatorio']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'obligatorio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class RecuperarContrasenaForm(forms.Form):
    email = forms.EmailField(
        label='Correo institucional',
        widget=forms.EmailInput(attrs={
            'placeholder': 'Ingresa tu correo',
            'class': 'input-login'
        })
    )