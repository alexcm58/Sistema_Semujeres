from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.shortcuts import render
from django.shortcuts import render, redirect
from .forms import CrearUsuarioForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import user_passes_test
from .models import Usuario
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Documento, DOCUMENTOS_REQUERIDOS
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from .models import Usuario
from django.contrib.auth import logout
from django.shortcuts import redirect



def login_view(request):
    if request.method == 'POST':
        correo = request.POST.get('correo')
        password = request.POST.get('password')

        try:
            usuario = Usuario.objects.get(correo=correo)
            user = authenticate(request, username=usuario.username, password=password)

            if user is not None:
                login(request, user)
                
                if user.is_superuser:
                    return redirect('administrador_menu')  # 👈 redirige a vista personalizada
                else:
                    return redirect('usuario_dashboard')
            else:
                return render(request, 'core/login.html', {'error': 'Contraseña incorrecta'})

        except Usuario.DoesNotExist:
            return render(request, 'core/login.html', {'error': 'Correo no encontrado'})

    return render(request, 'core/login.html')



def dashboard(request):
    return render(request, "core/dashboard.html")


def es_admin(user):
    return user.is_authenticated and user.rol == 'admin'

@user_passes_test(es_admin)
def crear_usuario(request):
    if request.method == 'POST':
        form = CrearUsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.password = make_password(form.cleaned_data['password'])
            usuario.save()
            return redirect('lista_usuarios')
    else:
        form = CrearUsuarioForm()
    return render(request, 'core/crear_usuario.html', {'form': form})


@login_required
def usuario_dashboard(request):
    documentos = Documento.objects.filter(usuario=request.user)

    # Crear documentos si aún no existen
    for doc in DOCUMENTOS_REQUERIDOS:
        Documento.objects.get_or_create(usuario=request.user, nombre_documento=doc)

    documentos = Documento.objects.filter(usuario=request.user)
    return render(request, 'core/usuario_dashboard.html', {'documentos': documentos})


@login_required
def administrador_menu(request):
    return render(request, 'core/administrador_menu.html')


def cerrar_sesion(request):
    logout(request)
    return redirect('login')  # nombre de la URL del login

