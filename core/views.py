# --------------------
# Django - Vistas, autenticación y utilidades
# --------------------
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.http import HttpResponse
from django.utils.text import slugify
from django.core.files.storage import default_storage
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
from django.core.files.base import ContentFile

# --------------------
# Modelos y formularios del proyecto
# --------------------
from .models import Documento, Usuario, AnexoRequerido, AnexoHistorico
from .forms import CrearUsuarioForm, EditarUsuarioForm, AnexoForm
from .models import AnexoRequerido
# --------------------
# Python estándar
# --------------------
from datetime import datetime
from io import BytesIO
import os
import zipfile

# --------------------
# ReportLab - Generación de PDFs
# --------------------
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Image as RLImage

# --------------------
# Matplotlib y Pandas - Gráficos para PDF
# --------------------
import matplotlib
matplotlib.use('Agg')  # Backend sin GUI (necesario para entornos web/macOS)
import matplotlib.pyplot as plt
import pandas as pd

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

def cerrar_sesion(request):
    logout(request)
    return redirect('login')  # nombre de la URL del login



@user_passes_test(es_admin)
def admin_revision_documentacion(request):
    entidades = Usuario.objects.filter(rol='usuario')
    entidad_seleccionada = None
    documentos = []

    if request.method == 'GET':
        entidad_id = request.GET.get('entidad')
        if entidad_id:
            entidad_seleccionada = get_object_or_404(Usuario, id=entidad_id)

            # 🔹 Aseguramos que existan los documentos
            for anexo in AnexoRequerido.objects.all():
                Documento.objects.get_or_create(usuario=entidad_seleccionada, anexo=anexo)

            documentos = Documento.objects.filter(usuario=entidad_seleccionada)

    elif request.method == 'POST':
        entidad_id = request.GET.get('entidad')
        if entidad_id:
            entidad_seleccionada = get_object_or_404(Usuario, id=entidad_id)

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
    # 🔹 Asegurar que el usuario tenga documentos creados
    for anexo in AnexoRequerido.objects.all():
        Documento.objects.get_or_create(usuario=request.user, anexo=anexo)

    documentos = Documento.objects.filter(usuario=request.user)

    if request.method == 'POST':
        for doc in documentos:
            archivo = request.FILES.get(f'documento_{doc.id}')
            if archivo:
                # ⚠️ opcional: si quieres permitir reemplazar archivos
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

def sincronizar_documentos_por_usuario():
    usuarios = Usuario.objects.all()
    anexos = AnexoRequerido.objects.all()

    for usuario in usuarios:
        for anexo in anexos:
            Documento.objects.get_or_create(usuario=usuario, anexo=anexo)


    anexo = get_object_or_404(AnexoRequerido, id=anexo_id)
    anexo.delete()
    Documento.objects.filter(anexo=anexo).delete()  # Limpieza relacionada
    return redirect('admin_anexos')

#REPORTES DE DOCUMENTOS 

@user_passes_test(es_admin)
def reporte_general_pdf(request):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=50  # más margen inferior
    )

    # --------------------
    # ESTILOS Y COLORES
    # --------------------
    vino_rl = colors.HexColor('#7B1F26')
    dorado_rl = colors.HexColor('#d4af37')

    # Matplotlib (para gráficos)
    vino_hex = "#7B1F26"
    dorado_hex = "#d4af37"

    arial12 = ParagraphStyle(
        'Arial12', fontName='Helvetica', fontSize=12,
        leading=15, textColor=vino_rl
    )
    encabezado = ParagraphStyle(
        'Encabezado', fontName='Helvetica-Bold', fontSize=14,
        alignment=1, spaceAfter=10, textColor=vino_rl
    )
    titulo = ParagraphStyle(
        'Titulo', fontName='Helvetica-Bold', fontSize=16,
        alignment=1, spaceAfter=12, textColor=dorado_rl
    )
    sub_titulo = ParagraphStyle(
        'SubTitulo', fontName='Helvetica-Bold', fontSize=12,
        spaceAfter=6, textColor=vino_rl
    )
    observacion = ParagraphStyle(
        'Observacion', fontName='Helvetica', fontSize=10,
        textColor=colors.HexColor('#333333'), spaceAfter=10,
        leftIndent=10, rightIndent=10
    )

    elements = []
    ahora = datetime.now()
    fecha_str = ahora.strftime("%d de %B de %Y")

    # --------------------
    # PORTADA
    # --------------------
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", encabezado))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📄 Reporte Trimestral de Documentación Institucional", titulo))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", arial12))
    elements.append(Spacer(1, 20))

    # --------------------
    # DATOS GENERALES
    # --------------------
    entidades = Usuario.objects.filter(rol='usuario')
    documentos = Documento.objects.all()
    total_entidades = entidades.count()
    total_esperado = documentos.count()
    total_subidos = documentos.exclude(archivo='').count()
    total_validados = documentos.filter(estado='validado').count()
    total_rechazados = documentos.filter(estado='rechazado').count()
    total_pendientes = total_esperado - total_validados - total_rechazados
    porcentaje_global = (total_validados / total_esperado * 100) if total_esperado else 0

    # --------------------
    # RESUMEN EJECUTIVO
    # --------------------
    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Entidades registradas', total_entidades],
        [2, 'Documentos esperados', total_esperado],
        [3, 'Documentos subidos', total_subidos],
        [4, 'Documentos validados', total_validados],
        [5, 'Documentos rechazados', total_rechazados],
        [6, 'Documentos en proceso de revisión', total_pendientes],
        [7, 'Porcentaje global de validación', f"{porcentaje_global:.2f}%"]
    ]
    t_resumen = Table(resumen, hAlign='CENTER', colWidths=[30, 250, 120])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), vino_rl),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER')
    ]))
    elements.append(Paragraph("Resumen Ejecutivo", sub_titulo))
    elements.append(t_resumen)
    elements.append(Spacer(1, 20))

    # --------------------
    # AVANCE POR ENTIDAD
    # --------------------
    tabla_entidades = [['Entidad (Usuario)', 'Subidos', 'Validados', 'Rechazados', 'En proceso', '% Validados']]
    for ent in entidades:
        docs_ent = documentos.filter(usuario=ent)
        subidos = docs_ent.exclude(archivo='').count()
        validados = docs_ent.filter(estado='validado').count()
        rechazados = docs_ent.filter(estado='rechazado').count()
        en_proceso = docs_ent.count() - validados - rechazados
        pct = (validados / docs_ent.count() * 100) if docs_ent.count() else 0
        tabla_entidades.append([ent.username, subidos, validados, rechazados, en_proceso, f"{pct:.2f}%"])

    t_entidades = Table(tabla_entidades, hAlign='CENTER', repeatRows=1)
    t_entidades.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), vino_rl),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER')
    ]))
    elements.append(Paragraph("Avance por Entidad", sub_titulo))
    elements.append(t_entidades)
    elements.append(Spacer(1, 20))

    # --------------------
    # GRAFICOS (solo globales)
    # --------------------
    estados = ['Validados', 'Rechazados', 'En revisión']
    valores = [total_validados, total_rechazados, total_pendientes]

    # Gráfico de barras global
    plt.figure(figsize=(4,3))
    plt.bar(estados, valores, color=['green', 'red', 'orange'])
    plt.title("Distribución global de documentos")
    img_buf = BytesIO()
    plt.savefig(img_buf, format='png')
    img_buf.seek(0)
    elements.append(Image(img_buf, width=300, height=200))
    plt.close()

    # Gráfico circular (pie chart)
    plt.figure(figsize=(4,3))
    plt.pie(valores, labels=estados, autopct='%1.1f%%', colors=['green', 'red', 'orange'])
    plt.title("Porcentaje global de documentos")
    img_buf2 = BytesIO()
    plt.savefig(img_buf2, format='png')
    img_buf2.seek(0)
    elements.append(Image(img_buf2, width=300, height=200))
    plt.close()

    elements.append(Spacer(1, 20))

    # --------------------
    # OBSERVACIONES
    # --------------------
    observaciones = Documento.objects.exclude(observaciones__isnull=True).exclude(observaciones__exact='')
    for obs in observaciones:
        elements.append(Paragraph(
            f"{obs.usuario.username} - {obs.anexo.nombre}: {obs.observaciones}",
            observacion
        ))

    # --------------------
    # PIE DE PÁGINA
    # --------------------
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(vino_rl)
        canvas.drawString(30, 40, "Secretaría de las Mujeres del Estado de Zacatecas - Reporte Institucional")
        canvas.restoreState()

    pdf.build(elements, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_general_{slugify(fecha_str)}.pdf"'
    return response

@user_passes_test(es_admin)
def reporte_entidad_pdf(request, entidad_id):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=50
    )

    # --------------------
    # COLORES Y ESTILOS
    # --------------------
    vino_rl = colors.HexColor('#7B1F26')
    dorado_rl = colors.HexColor('#d4af37')

    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15, textColor=vino_rl)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10, textColor=vino_rl)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12, textColor=dorado_rl)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=12, spaceAfter=6, textColor=vino_rl)
    arial10 = ParagraphStyle('Arial10', fontName='Helvetica', fontSize=10, leading=12)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#333333'),
                                 spaceAfter=10, leftIndent=10, rightIndent=10)

    elements = []
    ahora = datetime.now()
    fecha_str = ahora.strftime("%d de %B de %Y")

    # --------------------
    # DATOS DE LA ENTIDAD
    # --------------------
    entidad = get_object_or_404(Usuario, id=entidad_id)
    nombre_entidad = entidad.get_full_name() or entidad.username
    docs = Documento.objects.filter(usuario=entidad)
    total_docs = docs.count()
    validados = docs.filter(estado='validado').count()
    rechazados = docs.filter(estado='rechazado').count()
    en_revision = docs.filter(estado='pendiente').count()  # 🔄 "pendiente" → "en proceso de revisión"
    porcentaje = (validados / total_docs * 100) if total_docs else 0

    # --------------------
    # PORTADA
    # --------------------
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", encabezado))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"📄 Reporte de la Entidad: {nombre_entidad}", titulo))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", arial12))
    elements.append(Spacer(1, 20))

    # --------------------
    # TABLA 1: Resumen ejecutivo
    # --------------------
    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Documentos esperados', total_docs],
        [2, 'Documentos validados', validados],
        [3, 'Documentos rechazados', rechazados],
        [4, 'Documentos en proceso de revisión', en_revision],
        [5, 'Avance (%)', f'{porcentaje:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30, 250, 100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),vino_rl),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
    ]))

    elements.append(Paragraph("📊 Resumen Ejecutivo de la Entidad", sub_titulo))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        f"Observación: La entidad {nombre_entidad} presenta un avance del {porcentaje:.1f}%. "
        f"Con {validados} documentos validados de un total de {total_docs}, "
        f"{'su desempeño es sobresaliente.' if porcentaje >= 80 else 'se encuentra en proceso, con áreas por mejorar.'}",
        observacion
    ))
    elements.append(Spacer(1, 15))

    # --------------------
    # GRÁFICO 1: Distribución por estado
    # --------------------
    estados = ['Validados','Rechazados','En proceso de revisión']
    valores = [validados, rechazados, en_revision]
    colores = ['#4CAF50','#FF6347','#FFD700']

    fig, ax = plt.subplots(figsize=(5,4))
    ax.pie(valores, labels=estados, autopct='%1.1f%%', colors=colores, startangle=90)
    ax.set_title('Distribución de Documentos por Estado')
    plt.tight_layout()
    img_buf = BytesIO()
    plt.savefig(img_buf, format='png')
    plt.close(fig)
    img_buf.seek(0)

    elements.append(Image(img_buf, width=300, height=200, hAlign='CENTER'))
    elements.append(Paragraph(
        f"Observación: Predominan los documentos {('validados' if validados>rechazados and validados>en_revision else 'rechazados' if rechazados>en_revision else 'en proceso de revisión')}, "
        f"lo que refleja la situación actual de la entidad.", observacion
    ))
    elements.append(Spacer(1,15))

    # --------------------
    # TABLA 2: Documentos por anexo
    # --------------------
    anexos = AnexoRequerido.objects.all()
    tabla_anexos_data = [['#','Anexo','Validados','Rechazados','En proceso de revisión']]
    for i, anexo in enumerate(anexos, start=1):
        docs_anexo = docs.filter(anexo=anexo)
        val = docs_anexo.filter(estado='validado').count()
        rec = docs_anexo.filter(estado='rechazado').count()
        proc = docs_anexo.filter(estado='pendiente').count()
        tabla_anexos_data.append([i, anexo.nombre, val, rec, proc])

    tabla_anexos = Table(tabla_anexos_data, hAlign='CENTER', colWidths=[30,200,70,70,100])
    tabla_anexos.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),vino_rl),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
    ]))

    elements.append(Paragraph("📋 Estado de Documentos por Anexo", sub_titulo))
    elements.append(tabla_anexos)
    elements.append(Spacer(1,15))

    # --------------------
    # TABLA 3: Anexos con más rechazos
    # --------------------
    rechazos_por_anexo = {a.nombre: docs.filter(anexo=a, estado='rechazado').count() for a in anexos}
    tabla_rechazos = [['#','Anexo','Rechazados']]
    for i, (anexo, cant) in enumerate(rechazos_por_anexo.items(), start=1):
        tabla_rechazos.append([i, anexo, cant])

    tabla_rechazos_t = Table(tabla_rechazos, hAlign='CENTER', colWidths=[30,250,100])
    tabla_rechazos_t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),vino_rl),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
    ]))

    max_rechazo = max(rechazos_por_anexo.values()) if rechazos_por_anexo else 0
    anexo_max = [k for k,v in rechazos_por_anexo.items() if v==max_rechazo][0] if max_rechazo else None

    elements.append(Paragraph("📋 Anexos con Mayor Número de Rechazos", sub_titulo))
    elements.append(tabla_rechazos_t)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        f"Observación: El anexo con más rechazos es '{anexo_max}' con {max_rechazo} documentos. "
        "Este punto debe recibir especial atención." if anexo_max else "Observación: No se registran rechazos en los anexos.",
        observacion
    ))
    elements.append(Spacer(1,15))

    # --------------------
    # PIE DE PÁGINA
    # --------------------
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(vino_rl)
        canvas.drawString(30, 40, "Secretaría de las Mujeres del Estado de Zacatecas - Reporte Institucional")
        canvas.restoreState()

    pdf.build(elements, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    nombre_archivo = f"reporte_entidad_{entidad.username}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

#ANEXOS 
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
    try:
        anexo = AnexoRequerido.objects.get(id=anexo_id)
        anexo.delete()
        messages.success(request, "El anexo fue eliminado correctamente.")
    except AnexoRequerido.DoesNotExist:
        messages.error(request, "El anexo no existe.")
    return redirect('admin_anexos')


@user_passes_test(es_admin)
def eliminar_todos_anexos(request):
    AnexoRequerido.objects.all().delete()
    messages.success(request, "Todos los anexos han sido eliminados.")
    return redirect('admin_anexos')

@user_passes_test(es_admin)
def limpiar_anexos_subidos(request):
    if request.method == 'POST':
        documentos = Documento.objects.all()
        archivos_limpiados = 0

        for doc in documentos:
            if doc.archivo:
                doc.archivo.delete(save=False)
                doc.archivo = None
                doc.estado = 'pendiente'
                doc.observaciones = ''
                doc.save()
                archivos_limpiados += 1

        if archivos_limpiados:
            messages.success(request, f"✅ Se han limpiado {archivos_limpiados} archivos subidos correctamente.")
        else:
            messages.info(request, "ℹ️ No había archivos para limpiar.")
        return redirect('admin_anexos')
    return redirect('admin_anexos')


@user_passes_test(es_admin)
def respaldar_anexos(request):
    if request.method == 'POST':
        documentos = Documento.objects.all()
        respaldados = 0

        for doc in documentos:
            if doc.archivo:
                # Evitar respaldar si ya existe un respaldo con mismo nombre y entidad
                nombre_archivo = doc.archivo.name.split('/')[-1]
                existe = AnexoHistorico.objects.filter(
                    entidad=doc.usuario,
                    anexo_requerido=doc.anexo,
                    archivo__endswith=nombre_archivo
                ).exists()

                if not existe:
                    # Crear copia física en histórico con nombre
                    contenido = ContentFile(doc.archivo.read(), name=nombre_archivo)
                    AnexoHistorico.objects.create(
                        entidad=doc.usuario,
                        anexo_requerido=doc.anexo,
                        archivo=contenido
                    )
                    respaldados += 1

        if respaldados:
            messages.success(request, f"✅ Se han respaldado {respaldados} archivos correctamente.")
        else:
            messages.info(request, "ℹ️ No había archivos nuevos para respaldar.")
        return redirect('admin_anexos')
    return redirect('admin_anexos')


# Generar reporte de anexos
@user_passes_test(es_admin)
def reporte_anexos_pdf(request):
    anexos = AnexoRequerido.objects.all()
    data = []

    for anexo in anexos:
        cumplidos = Documento.objects.filter(anexo=anexo, estado='validado').count()
        data.append({
            'nombre': anexo.nombre,
            'descripcion': anexo.descripcion or "—",
            'cumplieron': cumplidos,
        })

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    fecha_str = now().strftime("%d de %B de %Y")
    elements.append(Paragraph("📄 Reporte de Cumplimiento de Anexos", styles['Title']))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Tabla resumen
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

    # Gráfico
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

    pdf.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Reporte_Anexos_{fecha_str}.pdf"'
    return response

@user_passes_test(es_admin)
def vista_respaldo_anexos(request):
    respaldos = AnexoHistorico.objects.all().order_by('-fecha_subida')
    return render(request, 'core/respaldo_anexos.html', {'respaldos': respaldos})

@user_passes_test(es_admin)
def limpiar_respaldo(request):
    if request.method == 'POST':
        respaldos = AnexoHistorico.objects.all()
        count = respaldos.count()

        if count == 0:
            messages.info(request, "ℹ️ No hay respaldos para limpiar.")
            return redirect('vista_respaldo_anexos')

        # Eliminar archivos físicos si existen
        for r in respaldos:
            if r.archivo and default_storage.exists(r.archivo.name):
                default_storage.delete(r.archivo.name)

        # Eliminar registros de la tabla
        respaldos.delete()

        messages.success(request, f"✅ Se han eliminado {count} archivos y registros de respaldo correctamente.")
        return redirect('vista_respaldo_anexos')
    return redirect('vista_respaldo_anexos')


@user_passes_test(es_admin)
def descargar_respaldo_zip(request):
    respaldos = AnexoHistorico.objects.all()
    if not respaldos.exists():
        messages.info(request, "ℹ️ No hay archivos respaldados para descargar.")
        return redirect('vista_respaldo_anexos')

    buffer = BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for r in respaldos:
            if r.archivo and default_storage.exists(r.archivo.name):
                # Obtener nombre original del archivo
                nombre = f"{r.entidad.username}_{r.anexo_requerido.nombre}_{r.fecha_subida.strftime('%Y%m%d_%H%M%S')}"
                ext = r.archivo.name.split('.')[-1]
                nombre_archivo_zip = f"{nombre}.{ext}"

                # Abrir el archivo físico y escribirlo en el ZIP
                with r.archivo.open('rb') as f:
                    zip_file.writestr(nombre_archivo_zip, f.read())

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=respaldo_anexos.zip'
    return response

import random, string
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Usuario  # tu modelo de usuario
import random
import string
from django.core.mail import send_mail
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import Usuario  # asegúrate de importar tu modelo personalizado

def generar_contrasena(longitud=10):
    """Genera contraseña aleatoria provisional"""
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(longitud))

def olvido_contrasena(request):
    if request.method == "POST":
        correo = request.POST.get("correo")  # 👈 asegúrate que en el form el campo se llame 'correo'

        try:
            usuario = Usuario.objects.get(correo=correo)

            # Generar nueva contraseña provisional
            nueva_pass = generar_contrasena()
            usuario.set_password(nueva_pass)  # 👈 se guarda encriptada
            usuario.save()

            # Enviar correo
            mensaje = f"""Hola {usuario.nombre_responsable},

Tu nueva contraseña es: {nueva_pass}

Por favor, cambia tu contraseña después de iniciar sesión.
"""
            send_mail(
                subject="Recuperación de contraseña - SEMUJERES",
                message=mensaje,
                from_email="asemujeres@gmail.com",  # 👈 usa tu correo configurado en settings.py
                recipient_list=[usuario.correo],
                fail_silently=False,
            )

            messages.success(request, "Se envió una nueva contraseña a tu correo.")
            return redirect("login")

        except Usuario.DoesNotExist:
            messages.error(request, "El correo no está registrado.")

    return render(request, "core/olvido_contrasena.html")


from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render

@login_required
def cambiar_contrasena(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # 🔑 Para que no cierre sesión
            messages.success(request, "Tu contraseña se cambió correctamente.")
            return render(request, "core/cambiar_contrasena.html", {"form": PasswordChangeForm(user=request.user)})
        else:
            messages.error(request, "Por favor corrige los errores.")
    else:
        form = PasswordChangeForm(user=request.user)

    # Traducción de etiquetas al español
    form.fields['old_password'].label = "Contraseña actual"
    form.fields['new_password1'].label = "Nueva contraseña"
    form.fields['new_password2'].label = "Confirmar nueva contraseña"

    return render(request, "core/cambiar_contrasena.html", {"form": form})
