from django.urls import path
from django.conf.urls.static import static
from . import views
from django.shortcuts import redirect


urlpatterns = [
    path('dashboard/', views.usuario_dashboard, name='usuario_dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('revision/', views.admin_revision_documentacion, name='admin_revision_documentacion'),
    path('crear_usuario/', views.admin_crear_usuario, name='admin_crear_usuario'),
    path('gestion_usuarios/', views.admin_gestion_usuarios, name='admin_gestion_usuarios'),
    path('lista_usuarios/', views.admin_lista_usuarios, name='admin_lista_usuarios'),
    path('eliminar_usuario/<int:usuario_id>/', views.admin_eliminar_usuario, name='eliminar_usuario'),
    path('editar_usuario/<int:usuario_id>/', views.editar_usuario, name='admin_editar_usuario'),
    path('perfil_admin', views.admin_perfil, name='admin_perfil'),
    path('admin_anexos', views.admin_anexos, name='admin_anexos'),
    path('admin/anexos/eliminar/<int:anexo_id>/', views.eliminar_anexo, name='eliminar_anexo'),
    # En urls.py
path('reporte/general/pdf/', views.reporte_general_pdf, name='reporte_general_pdf'),
path('reporte/entidad/<int:entidad_id>/pdf/', views.reporte_entidad_pdf, name='reporte_entidad_pdf'),
path('anexos/eliminar_todos/', views.eliminar_todos_anexos, name='eliminar_todos_anexos'),
path('anexos/reporte_pdf/', views.reporte_anexos_pdf, name='reporte_anexos_pdf'),



     path('', lambda request: redirect('login')),
    # buscar como añadir linea para enviar cualquier otra url a login
]

