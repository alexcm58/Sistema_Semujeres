# Django - Vistas, autenticación y utilidades
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils.text import slugify

# Python estándar
from datetime import datetime
from io import BytesIO

# Modelos y formularios del proyecto
from .models import Documento, Usuario, AnexoRequerido
from .forms import CrearUsuarioForm, EditarUsuarioForm, AnexoForm

# ReportLab - Generación de PDFs
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Matplotlib - Gráficos para insertar en PDF
import matplotlib
matplotlib.use('Agg')  # Backend sin GUI (necesario para entornos web/macOS)
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.platypus import Image as RLImage



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




@user_passes_test(es_admin)
def reporte_general_pdf(request):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    title = styles['Title']
    elements = []

    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
    fecha_str = ahora.strftime("%d de %B de %Y")

    # 📄 PORTADA
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", ParagraphStyle('encabezado', fontSize=14, alignment=1)))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📄 Reporte Trimestral de Documentación Institucional", title))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", normal))
    elements.append(Spacer(1, 20))

    # 🔢 Datos generales
    entidades = Usuario.objects.filter(rol='usuario')
    total_entidades = entidades.count()
    total_esperado = Documento.objects.count()
    total_subidos = Documento.objects.exclude(archivo='').count()
    total_validados = Documento.objects.filter(estado='validado').count()
    total_rechazados = Documento.objects.filter(estado='rechazado').count()
    porcentaje_global = (total_validados / total_esperado * 100) if total_esperado else 0

    resumen = [
        ['Indicador', 'Valor'],
        ['Entidades registradas', total_entidades],
        ['Documentos esperados', total_esperado],
        ['Documentos subidos', total_subidos],
        ['Documentos validados', total_validados],
        ['Documentos rechazados', total_rechazados],
        ['Porcentaje de avance (validado)', f'{porcentaje_global:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='LEFT')
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
    ]))
    elements.append(Paragraph("📊 Resumen Ejecutivo:", styles['Heading2']))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 20))

    # 📋 TABLA POR ENTIDAD
    data = [['Entidad', 'Subidos', 'Validados', 'Rechazados', 'Esperados', 'Avance %']]
    porcentajes = {}
    for entidad in entidades:
        docs = Documento.objects.filter(usuario=entidad)
        total = docs.count()
        subidos = docs.exclude(archivo='').count()
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        porcentaje = (validados / total * 100) if total else 0
        nombre = entidad.get_full_name() if hasattr(entidad, 'get_full_name') and entidad.get_full_name() else entidad.username
        data.append([nombre, subidos, validados, rechazados, total, f'{porcentaje:.1f}%'])
        porcentajes[nombre] = porcentaje

    tabla_entidades = Table(data, repeatRows=1)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
    ])
    for i in range(1, len(data)):
        porcentaje = float(data[i][5].replace('%', ''))
        if porcentaje >= 80:
            bg_color = colors.lightgreen
        elif porcentaje >= 50:
            bg_color = colors.lightyellow
        else:
            bg_color = colors.pink
        style.add('BACKGROUND', (0, i), (-1, i), bg_color)
    tabla_entidades.setStyle(style)

    elements.append(Paragraph("📋 Avance por Entidad (con base en validados):", styles['Heading2']))
    elements.append(tabla_entidades)
    elements.append(Spacer(1, 20))

    # 📊 GRÁFICO 1: Porcentaje validados por entidad
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.bar(porcentajes.keys(), porcentajes.values(), color='#7B1F26')
    ax1.set_ylabel('% Validado')
    ax1.set_title('Porcentaje de Documentos Validados por Entidad')
    ax1.set_ylim(0, 100)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    img_buffer1 = BytesIO()
    plt.savefig(img_buffer1, format='png')
    plt.close(fig1)
    img_buffer1.seek(0)
    elements.append(Image(img_buffer1, width=500, height=250))
    elements.append(Spacer(1, 20))

    # 📊 GRÁFICO 2: Anexos con más rechazos
    anexos = AnexoRequerido.objects.all()
    anexo_labels = []
    anexo_rechazados = []
    for anexo in anexos:
        rechazados = Documento.objects.filter(anexo=anexo, estado='rechazado').count()
        if rechazados > 0:
            anexo_labels.append(anexo.nombre)
            anexo_rechazados.append(rechazados)

    if anexo_labels:
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        ax2.bar(anexo_labels, anexo_rechazados, color='tomato')
        ax2.set_title('Anexos con Mayor Número de Rechazos')
        ax2.set_ylabel('Cantidad Rechazada')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        img_buffer2 = BytesIO()
        plt.savefig(img_buffer2, format='png')
        plt.close(fig2)
        img_buffer2.seek(0)
        elements.append(Image(img_buffer2, width=500, height=250))
        elements.append(Spacer(1, 20))

    # 🖊️ PIE
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de Seguimiento del Modelo para la Igualdad entre Mujeres y Hombres del Estado de Zacatecas.",
        ParagraphStyle('pie', fontSize=9, alignment=1, textColor=colors.grey)
    )
    elements.append(pie)

    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"reporte_trimestral_{slugify(nombre_mes)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response



@user_passes_test(es_admin)
def reporte_entidad_pdf(request, entidad_id):
    entidad = Usuario.objects.get(id=entidad_id)
    docs = Documento.objects.filter(usuario=entidad)
    subidos = docs.exclude(archivo='').count()
    total = docs.count()
    validados = docs.filter(estado='validado').count()
    rechazados = docs.filter(estado='rechazado').count()
    pendientes = total - validados - rechazados
    porcentaje_validados = (validados / total * 100) if total else 0

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    ahora = datetime.now()
    fecha_str = ahora.strftime("%d de %B de %Y")
    nombre_entidad = entidad.get_full_name() if hasattr(entidad, 'get_full_name') else entidad.username

    # 🧾 PORTADA
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", ParagraphStyle('encabezado', fontSize=14, alignment=1)))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"📄 Reporte Personal de Documentación - {nombre_entidad}", styles['Title']))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # 📊 RESUMEN
    resumen = [
        ['Indicador', 'Valor'],
        ['Documentos requeridos', total],
        ['Documentos subidos', subidos],
        ['Documentos validados', validados],
        ['Documentos rechazados', rechazados],
        ['Porcentaje validado', f'{porcentaje_validados:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='LEFT')
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
    ]))
    elements.append(Paragraph("📊 Resumen Ejecutivo:", styles['Heading2']))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 20))

    # 📋 DETALLE POR DOCUMENTO
    data = [['Anexo', 'Estado', 'Observaciones']]
    for d in docs:
        data.append([
            d.anexo.nombre,
            d.estado.title(),
            d.observaciones or ''
        ])
    tabla_detalle = Table(data)
    tabla_detalle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER')
    ]))
    elements.append(Paragraph("📋 Estado de los Documentos Requeridos:", styles['Heading2']))
    elements.append(tabla_detalle)
    elements.append(Spacer(1, 20))

    # 📊 GRÁFICO DE ESTADO
    fig, ax = plt.subplots()
    ax.bar(['Validados', 'Rechazados', 'Pendientes'], [validados, rechazados, pendientes], color=['green', 'red', 'orange'])
    ax.set_title('Resumen de Validación de Documentos')
    plt.tight_layout()

    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png')
    plt.close(fig)
    img_buffer.seek(0)
    elements.append(Image(img_buffer, width=450, height=250))
    elements.append(Spacer(1, 20))

    # 🖊️ PIE
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de Seguimiento del Modelo para la Igualdad entre Mujeres y Hombres del Estado de Zacatecas.",
        ParagraphStyle('pie', fontSize=9, alignment=1, textColor=colors.grey)
    )
    elements.append(pie)

    # FINAL
    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"reporte_{slugify(nombre_entidad)}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


@user_passes_test(es_admin)
def eliminar_todos_anexos(request):
    AnexoRequerido.objects.all().delete()
    messages.success(request, "Todos los anexos han sido eliminados.")
    return redirect('admin_anexos')

def reporte_anexos_pdf(request):


    # 1. Obtener datos reales desde el modelo AnexoRequerido y Documento
    anexos = AnexoRequerido.objects.all()
    data = []

    for anexo in anexos:
        cumplidos = Documento.objects.filter(anexo=anexo, estado='validado').count()
        data.append({
            'nombre': anexo.nombre,
            'descripcion': anexo.descripcion or "—",
            'cumplieron': cumplidos,
        })

    # 2. Preparar PDF
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    fecha_str = datetime.now().strftime("%d de %B de %Y")
    elements.append(Paragraph("📄 Reporte de Cumplimiento de Anexos", styles['Title']))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # 3. Tabla resumen
    tabla_data = [["Anexo", "Descripción", "Entidades que cumplieron"]]
    for d in data:
        tabla_data.append([d['nombre'], d['descripcion'], d['cumplieron']])

    tabla = Table(tabla_data, hAlign='LEFT')
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#7B1F26")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
    ]))
    elements.append(Paragraph("📌 Detalle de cumplimiento por anexo:", styles['Heading2']))
    elements.append(tabla)
    elements.append(Spacer(1, 20))

    # 4. Gráfico
    df = pd.DataFrame(data)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.barh(df["nombre"], df["cumplieron"], color="#7B1F26")
    ax.set_xlabel("Número de entidades")
    ax.set_title("Cumplimiento por anexo")
    plt.tight_layout()

    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png')
    plt.close(fig)
    img_buffer.seek(0)
    elements.append(RLImage(img_buffer, width=400, height=200))

    # 5. Pie de página
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "Este reporte resume el cumplimiento de cada anexo requerido por las entidades del estado.",
        styles['Italic']
    ))

    # 6. Finalizar PDF
    pdf.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_anexos.pdf"'
    return response
