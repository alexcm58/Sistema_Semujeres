from django.urls import path
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from . import views



urlpatterns = [
    # Dashboard y sesiones
    path('dashboard/', views.usuario_dashboard, name='usuario_dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),

    # Administración de usuarios
    path('revision/', views.admin_revision_documentacion, name='admin_revision_documentacion'),
    path('crear_usuario/', views.admin_crear_usuario, name='admin_crear_usuario'),
    path('gestion_usuarios/', views.admin_gestion_usuarios, name='admin_gestion_usuarios'),
    path('lista_usuarios/', views.admin_lista_usuarios, name='admin_lista_usuarios'),
    path('eliminar_usuario/<int:usuario_id>/', views.admin_eliminar_usuario, name='eliminar_usuario'),
    path('editar_usuario/<int:usuario_id>/', views.editar_usuario, name='admin_editar_usuario'),
    path('perfil_admin/', views.admin_perfil, name='admin_perfil'),

    # Administración de anexos
    path('admin_anexos/', views.admin_anexos, name='admin_anexos'),
    path('admin/anexos/eliminar/<int:anexo_id>/', views.eliminar_anexo, name='eliminar_anexo'),
    path('reporte/general/pdf/', views.reporte_general_pdf, name='reporte_general_pdf'),
    path('reporte/entidad/<int:entidad_id>/pdf/', views.reporte_entidad_pdf, name='reporte_entidad_pdf'),
    path('anexos/eliminar_todos/', views.eliminar_todos_anexos, name='eliminar_todos_anexos'),
    path('anexos/reporte_pdf/', views.reporte_anexos_pdf, name='reporte_anexos_pdf'),
    path('olvido_contrasena/', views.olvido_contrasena, name='olvido_contrasena'),
    path('limpiar_anexos/', views.limpiar_anexos_subidos, name='limpiar_anexos'),
    path('respaldar_anexos/', views.respaldar_anexos, name='respaldar_anexos'),
    path('reporte_anexos_pdf/', views.reporte_anexos_pdf, name='reporte_anexos_pdf'),
    path('vista_respaldo_anexos/', views.vista_respaldo_anexos, name='vista_respaldo_anexos'),
    path('limpiar_respaldo/', views.limpiar_respaldo, name='limpiar_respaldo'),
    path('descargar_respaldo_zip/', views.descargar_respaldo_zip, name='descargar_respaldo_zip'),
    path("cambiar_contrasena/", views.cambiar_contrasena, name="cambiar_contrasena"),

    # Redireccionamiento por defecto
    path('', lambda request: redirect('login')),
]
