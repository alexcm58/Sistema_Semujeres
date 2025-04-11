# core/forms.py

from django import forms
from .models import Usuario  # asegúrate que es tu modelo personalizado

class CrearUsuarioForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Usuario
        fields = [
            'username',
            'nombre_responsable',
            'entidad_federativa',
            'correo',
            'rol',
            'password',
            'is_active',
        ]
