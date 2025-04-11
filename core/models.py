from django.contrib.auth.models import AbstractUser
from django.db import models

ROLES = [
    ('usuario', 'Usuario'),
    ('admin', 'Administrador'),
]




class Usuario(AbstractUser):
    nombre_responsable = models.CharField(max_length=100)
    entidad_federativa = models.CharField(max_length=100)
    correo = models.EmailField(unique=True)
    rol = models.CharField(max_length=10, choices=ROLES, default='usuario')

    def __str__(self):
        return f"{self.username} - {self.entidad_federativa}"

from django.db import models
from django.conf import settings

ESTADOS = [
    ('pendiente', '🟡 Pendiente'),
    ('aprobado', '✅ Aprobado'),
    ('rechazado', '❌ Rechazado'),
]

DOCUMENTOS_REQUERIDOS = [
    'Modelo', 'Manual', 'Integración comité', 'Nombramientos honoríficos',
    'Anexo 1', 'Compromiso con la igualdad', 'Difusión Política para la igualdad',
    'Anexo 2', 'Anexo 3', 'Anexo 4', 'Anexo 5', 'Anexo 6'
]

class Documento(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre_documento = models.CharField(max_length=100)
    archivo = models.FileField(upload_to='documentos/', blank=True, null=True)
    fecha_subida = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.nombre_documento}"
