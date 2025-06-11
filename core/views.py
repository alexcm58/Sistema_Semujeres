from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from .models import Documento, Usuario
from .forms import CrearUsuarioForm, EditarUsuarioForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from .models import AnexoRequerido, Documento
from .forms import AnexoForm  # Asegúrate de tener este form
from .models import Usuario  # Asegúrate de importar Usuario si lo necesitas


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if user.is_superuser or user.rol == 'admin':
                return redirect('admin_revision_documentacion')
            elif user.rol == 'usuario':
                return redirect('usuario_dashboard')
        else:
            return render(request, 'core/login.html', {'error': 'Usuario o contraseña incorrectos'})

    return render(request, 'core/login.html')




def es_admin(user):
    return user.is_authenticated and user.rol == 'admin'

@user_passes_test(es_admin)
def admin_revision_documentacion(request):
    entidades = Usuario.objects.filter(rol='usuario')
    entidad_seleccionada = None
    documentos = []

    if request.method == 'GET':
        entidad_id = request.GET.get('entidad')
        if entidad_id:
            entidad_seleccionada = Usuario.objects.get(id=entidad_id)
            documentos = Documento.objects.filter(usuario=entidad_seleccionada)

    elif request.method == 'POST':
        entidad_id = request.GET.get('entidad')
        if entidad_id:
            entidad_seleccionada = Usuario.objects.get(id=entidad_id)
            documentos = Documento.objects.filter(usuario=entidad_seleccionada)

            for doc in documentos:
                estado = request.POST.get(f'estado_{doc.id}')
                observaciones = request.POST.get(f'observaciones_{doc.id}')
                if estado:
                    doc.estado = estado
                doc.observaciones = observaciones
                doc.save()
            return redirect(f'{request.path}?entidad={entidad_id}')
        
    if documentos:
        total = documentos.count()
        validados = documentos.filter(estado='validado').count()
        porcentaje_validados = round((validados / total) * 100, 2) if total > 0 else 0
    else:
        porcentaje_validados = 0

    return render(request, 'core/admin_revision_documentacion.html', {
        'entidades': entidades,
        'entidad_seleccionada': entidad_seleccionada,
        'documentos': documentos,
        'porcentaje_validados': porcentaje_validados,   
    })

@user_passes_test(es_admin)
def admin_crear_usuario(request):
    if request.method == 'POST':
        form = CrearUsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.set_password(form.cleaned_data['password'])
            usuario.is_active = True
            usuario.save()
            messages.success(request, 'Usuario creado con éxito.')
            return redirect('admin_crear_usuario')
    else:
        form = CrearUsuarioForm()
    return render(request, 'core/admin_crear_usuario.html', {'form': form})


@login_required
def usuario_dashboard(request):
    documentos = Documento.objects.filter(usuario=request.user)

    if request.method == 'POST':
        for doc in documentos:
            archivo = request.FILES.get(f'documento_{doc.id}')
            if archivo and not doc.archivo:
                doc.archivo = archivo
                doc.save()

    # Cálculo del porcentaje validado
    total = documentos.count()
    validados = documentos.filter(estado='validado').count()
    porcentaje_validados = round((validados / total) * 100, 2) if total > 0 else 0

    return render(request, 'core/usuario_dashboard.html', {
        'documentos': documentos,
        'porcentaje_validados': porcentaje_validados,
    })



def cerrar_sesion(request):
    logout(request)
    return redirect('login')  # nombre de la URL del login

@user_passes_test(es_admin)
def admin_gestion_usuarios(request):
    usuarios = Usuario.objects.all()
    return render(request, 'core/admin_gestion_usuarios.html', {
        'entidades': usuarios,
    })

@user_passes_test(es_admin)
def admin_lista_usuarios(request):
    usuarios = Usuario.objects.all()


    return render(request, 'core/admin_lista_usuarios.html', {
            'entidades': usuarios,
        })

@user_passes_test(es_admin)
def admin_eliminar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado correctamente.')
        return redirect('admin_lista_usuarios')
    
    # En caso de acceso por GET (opcional, puede redirigir o lanzar error)
    return redirect('admin_lista_usuarios')


@user_passes_test(es_admin)
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == 'POST':
        form = EditarUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('admin_lista_usuarios')
    else:
        form = EditarUsuarioForm(instance=usuario)

    return render(request, 'core/admin_editar_usuario.html', {'form': form, 'usuario': usuario})

@user_passes_test(es_admin)
def admin_perfil(request):
    usuario = request.user

    if request.method == 'POST':
        form = EditarUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('admin_perfil')  # Usar el name del path, no el archivo HTML
    else:
        form = EditarUsuarioForm(instance=usuario)

    return render(request, 'core/admin_perfil.html', {
        'form': form,
        'usuario': usuario,
    })


def es_admin(user):
    return user.is_authenticated and user.rol == 'admin'

from .models import Usuario, AnexoRequerido, Documento

def sincronizar_documentos_por_usuario():
    usuarios = Usuario.objects.all()
    anexos = AnexoRequerido.objects.all()

    for usuario in usuarios:
        for anexo in anexos:
            Documento.objects.get_or_create(usuario=usuario, anexo=anexo)

def es_admin(user):
    return user.is_authenticated and user.rol == 'admin'

@user_passes_test(es_admin)
def admin_anexos(request):
    anexos = AnexoRequerido.objects.all().order_by('nombre')

    if request.method == 'POST':
        form = AnexoForm(request.POST)
        if form.is_valid():
            form.save()
            sincronizar_documentos_por_usuario()  # ⬅️ importante
            return redirect('admin_anexos')
    else:
        form = AnexoForm()

    return render(request, 'core/admin_anexos.html', {
        'anexos': anexos,
        'form': form,
    })
@user_passes_test(es_admin)
def eliminar_anexo(request, anexo_id):
    anexo = get_object_or_404(AnexoRequerido, id=anexo_id)
    anexo.delete()
    Documento.objects.filter(anexo=anexo).delete()  # Limpieza relacionada
    return redirect('admin_anexos')

