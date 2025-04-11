from django.urls import path
from . import views



urlpatterns = [
    path('dashboard/', views.usuario_dashboard, name='usuario_dashboard'),
    path('administrador/', views.administrador_menu, name='administrador_menu'),  # 👈 nueva ruta
    path('login/', views.login_view, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
]
