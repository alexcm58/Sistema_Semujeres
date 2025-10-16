from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings



# ----------------------------
# Roles de usuario
# ----------------------------
ROLES = [
    ('usuario', 'Usuario'),
    ('admin', 'Administrador'),
]
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

# ... Asegúrate de que ROLES esté definido en este scope ...


class Usuario(AbstractUser):
    # CORRECCIÓN DE USERNAME
    # Redeclaramos el campo username para añadir el error_messages
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_("Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."),
        validators=[AbstractUser.username_validator],
        error_messages={
            'unique': "Ya existe un usuario con este nombre."  # <-- Mensaje en español
        },
    )

    nombre_responsable = models.CharField(max_length=100)
    entidad_federativa = models.CharField(max_length=100)
    
    # CORRECCIÓN DE CORREO (Ya estaba correcta, se mantiene)
    correo = models.EmailField(
        unique=True,
        error_messages={
            'unique': "Ya existe un usuario con este Correo."  # <-- Mensaje en español
        }
    )
    rol = models.CharField(max_length=10, choices=ROLES, default='usuario')

    def __str__(self):
        return f"{self.username} - {self.entidad_federativa}"

# ----------------------------
# Estados de validación
# ----------------------------
ESTADOS = [
    ('pendiente', '🟡 Pendiente'),
    ('validado', '✅ Validado'),
    ('rechazado', '❌ Rechazado'),
]

# ----------------------------
# Documentos requeridos por el sistema
# ----------------------------
class AnexoRequerido(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    obligatorio = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

# ----------------------------
# Documentos que cada usuario debe subir
# ----------------------------
class Documento(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    anexo = models.ForeignKey(AnexoRequerido, on_delete=models.CASCADE)
    archivo = models.FileField(upload_to='documentos/', blank=True, null=True)
    fecha_subida = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    observaciones = models.TextField(blank=True)

    class Meta:
        unique_together = ('usuario', 'anexo')  # Evita duplicados por usuario y anexo

    def __str__(self):
        return f"{self.usuario.username} - {self.anexo.nombre}"
    

class AnexoHistorico(models.Model):
    entidad = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    anexo_requerido = models.ForeignKey('AnexoRequerido', on_delete=models.CASCADE)
    archivo = models.FileField(upload_to='anexos_historicos/')
    fecha_subida = models.DateTimeField(auto_now_add=True)


class AnexoUsuario(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    anexo_requerido = models.ForeignKey(AnexoRequerido, on_delete=models.CASCADE)
    archivo = models.FileField(upload_to='anexos/', null=True, blank=True)
    estado = models.CharField(max_length=20, default='pendiente')
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.usuario} - {self.anexo_requerido}"
