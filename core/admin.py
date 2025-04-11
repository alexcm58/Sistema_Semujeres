from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ['username', 'correo', 'entidad_federativa', 'rol', 'is_active']

    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {
            'fields': ('nombre_responsable', 'entidad_federativa', 'correo', 'rol')
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {
            'fields': ('nombre_responsable', 'entidad_federativa', 'correo', 'rol')
        }),
    )

admin.site.register(Usuario, UsuarioAdmin)
