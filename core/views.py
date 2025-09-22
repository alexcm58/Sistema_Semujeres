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
from reportlab.platypus import KeepTogether


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
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Estilos
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    arial10 = ParagraphStyle('Arial10', fontName='Helvetica', fontSize=10, leading=12)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=12, spaceAfter=6)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)

    elements = []

    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
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
    # Tabla resumen general
    # --------------------
    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Entidades registradas', total_entidades],
        [2, 'Documentos esperados', total_esperado],
        [3, 'Documentos subidos', total_subidos],
        [4, 'Documentos validados', total_validados],
        [5, 'Documentos rechazados', total_rechazados],
        [6, 'Documentos pendientes', total_pendientes],
        [7, 'Porcentaje de avance (validado)', f'{porcentaje_global:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30,200,100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTSIZE',(0,0),(-1,-1),10)
    ]))
    elements.append(KeepTogether([
        Paragraph("📊 Resumen Ejecutivo:", sub_titulo),
        tabla_resumen,
        Paragraph("Tabla 1: Resumen general de documentos y entidades", arial10)
    ]))
    elements.append(Spacer(1, 10))

    # --------------------
    # Gráfico 1: Distribución por estado
    # --------------------
    fig_estado, ax_estado = plt.subplots(figsize=(6,4))
    estados = ['Validados', 'Rechazados', 'Pendientes']
    valores = [total_validados, total_rechazados, total_pendientes]
    colores = ['#4CAF50','#FF6347','#FFD700']
    ax_estado.pie(valores, labels=estados, autopct='%1.1f%%', colors=colores, startangle=90)
    ax_estado.set_title('Distribución de Documentos por Estado')
    plt.tight_layout()
    img_buf_estado = BytesIO()
    plt.savefig(img_buf_estado, format='png')
    plt.close(fig_estado)
    img_buf_estado.seek(0)

    elements.append(KeepTogether([
        Paragraph("Gráfico 1: Distribución de documentos por estado", arial10),
        Image(img_buf_estado, width=400, height=250),
        Paragraph("Observación: Se puede ver que la mayoría de los documentos se encuentran en estado validado, aunque aún hay pendientes y algunos rechazados.", observacion)
    ]))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla: Anexos por estado
    # --------------------
    anexos = AnexoRequerido.objects.all()
    tabla_anexos_data = [['#','Anexo','Validados','Rechazados','Pendientes']]
    for i, anexo in enumerate(anexos, start=1):
        docs_anexo = Documento.objects.filter(anexo=anexo)
        validados = docs_anexo.filter(estado='validado').count()
        rechazados = docs_anexo.filter(estado='rechazado').count()
        pendientes = docs_anexo.filter(estado='pendiente').count()
        tabla_anexos_data.append([i, anexo.nombre, validados, rechazados, pendientes])
    tabla_anexos = Table(tabla_anexos_data, hAlign='CENTER', colWidths=[30,200,60,60,60])
    tabla_anexos.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))

    elementos_anexos = [Paragraph("📋 Anexos por Estado:", sub_titulo), tabla_anexos, Paragraph("Tabla 2: Estado de documentos por anexo", arial10)]
    # Observaciones por anexo
    for anexo in anexos:
        docs_anexo = Documento.objects.filter(anexo=anexo)
        total = docs_anexo.count()
        validados = docs_anexo.filter(estado='validado').count()
        rechazados = docs_anexo.filter(estado='rechazado').count()
        pendientes = docs_anexo.filter(estado='pendiente').count()
        elementos_anexos.append(Paragraph(
            f"Anexo '{anexo.nombre}': {validados}/{total} validados, {rechazados} rechazados, {pendientes} pendientes.", observacion
        ))

    elements.append(KeepTogether(elementos_anexos))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla: Avance por entidad
    # --------------------
    data_entidades = [['#','Entidad','Subidos','Validados','Rechazados','Pendientes','Avance %']]
    porcentajes = {}
    entidad_obs_text = []
    for i, entidad in enumerate(entidades, start=1):
        docs = Documento.objects.filter(usuario=entidad)
        total = docs.count()
        subidos = docs.exclude(archivo='').count()
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        pendientes = total - validados - rechazados
        porcentaje = (validados / total * 100) if total else 0
        nombre = entidad.get_full_name() or entidad.username
        data_entidades.append([i,nombre,subidos,validados,rechazados,pendientes,f'{porcentaje:.1f}%'])
        porcentajes[nombre] = porcentaje
        entidad_obs_text.append(
            f"Entidad '{nombre}': {validados}/{total} validados ({porcentaje:.1f}%), {rechazados} rechazados, {pendientes} pendientes."
        )

    tabla_entidades = Table(data_entidades, hAlign='CENTER', repeatRows=1, colWidths=[30,120,50,50,50,50,50])
    style_ent = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9)
    ])
    for i in range(1,len(data_entidades)):
        pct = float(data_entidades[i][6].replace('%',''))
        if pct>=80: bg=colors.lightgreen
        elif pct>=50: bg=colors.lightyellow
        else: bg=colors.pink
        style_ent.add('BACKGROUND',(0,i),(-1,i),bg)
    tabla_entidades.setStyle(style_ent)
    elementos_entidades = [Paragraph("📋 Avance por Entidad:", sub_titulo), tabla_entidades, Paragraph("Tabla 3: Avance de documentos por entidad", arial10)]
    for obs in entidad_obs_text:
        elementos_entidades.append(Paragraph(obs, observacion))

    elements.append(KeepTogether(elementos_entidades))
    elements.append(Spacer(1,10))

    # --------------------
    # Gráfico barras: % validados por entidad
    # --------------------
    fig_bar, ax_bar = plt.subplots(figsize=(8,4))
    ax_bar.bar(porcentajes.keys(), porcentajes.values(), color='#7B1F26')
    ax_bar.set_ylabel('% Validados')
    ax_bar.set_title('Porcentaje de Documentos Validados por Entidad')
    ax_bar.set_ylim(0,100)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf_bar = BytesIO()
    plt.savefig(buf_bar, format='png')
    plt.close(fig_bar)
    buf_bar.seek(0)

    elements.append(KeepTogether([
        Paragraph("Gráfico 2: Porcentaje de documentos validados por entidad", arial10),
        Image(buf_bar, width=500, height=250),
        Paragraph("Observación: Permite identificar visualmente la entidad con mayor y menor avance.", observacion)
    ]))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla anexos más rechazados
    # --------------------
    tabla_anexos_rech = [['#','Anexo','Rechazados']]
    anexo_rechazados = {}
    for i, anexo in enumerate(anexos, start=1):
        count = Documento.objects.filter(anexo=anexo, estado='rechazado').count()
        tabla_anexos_rech.append([i, anexo.nombre, count])
        anexo_rechazados[anexo.nombre] = count
    tabla_anexos_rech_tabla = Table(tabla_anexos_rech, hAlign='CENTER', colWidths=[30,200,60])
    tabla_anexos_rech_tabla.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    elementos_anex_rech = [
        Paragraph("📋 Anexos más Rechazados:", sub_titulo),
        tabla_anexos_rech_tabla,
        Paragraph("Tabla 4: Anexos con mayor número de documentos rechazados", arial10)
    ]
    if anexo_rechazados:
        max_rech = max(anexo_rechazados.values())
        max_anexo = [k for k,v in anexo_rechazados.items() if v==max_rech][0]
        elementos_anex_rech.append(Paragraph(f"Observación: El anexo '{max_anexo}' presenta el mayor número de rechazos ({max_rech}).", observacion))
    elements.append(KeepTogether(elementos_anex_rech))
    elements.append(Spacer(1,10))

    # --------------------
    # Pie de página
    # --------------------
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de Seguimiento del Modelo para la Igualdad entre Mujeres y Hombres del Estado de Zacatecas.",
        ParagraphStyle('Pie', fontName='Helvetica', fontSize=10, alignment=1, textColor=colors.grey)
    )
    elements.append(Spacer(1,20))
    elements.append(pie)

    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"reporte_trimestral_{slugify(nombre_mes)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Estilos
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    arial10 = ParagraphStyle('Arial10', fontName='Helvetica', fontSize=10, leading=12)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=12, spaceAfter=6)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)

    elements = []

    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
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
    # Tabla resumen general
    # --------------------
    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Entidades registradas', total_entidades],
        [2, 'Documentos esperados', total_esperado],
        [3, 'Documentos subidos', total_subidos],
        [4, 'Documentos validados', total_validados],
        [5, 'Documentos rechazados', total_rechazados],
        [6, 'Documentos pendientes', total_pendientes],
        [7, 'Porcentaje de avance (validado)', f'{porcentaje_global:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30,200,100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTSIZE',(0,0),(-1,-1),10)
    ]))
    elements.append(Paragraph("📊 Resumen Ejecutivo:", sub_titulo))
    elements.append(tabla_resumen)
    elements.append(Paragraph("Tabla 1: Resumen general de documentos y entidades", arial10))
    elements.append(Spacer(1, 10))

    # --------------------
    # Gráfico 1: Distribución por estado
    # --------------------
    fig_estado, ax_estado = plt.subplots(figsize=(6,4))
    estados = ['Validados', 'Rechazados', 'Pendientes']
    valores = [total_validados, total_rechazados, total_pendientes]
    colores = ['#4CAF50','#FF6347','#FFD700']
    ax_estado.pie(valores, labels=estados, autopct='%1.1f%%', colors=colores, startangle=90)
    ax_estado.set_title('Distribución de Documentos por Estado')
    plt.tight_layout()
    img_buf_estado = BytesIO()
    plt.savefig(img_buf_estado, format='png')
    plt.close(fig_estado)
    img_buf_estado.seek(0)
    elements.append(Image(img_buf_estado, width=400, height=250))
    elements.append(Paragraph("Observación: Se puede ver que la mayoría de los documentos se encuentran en estado validado, aunque aún hay pendientes y algunos rechazados.", observacion))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla: Anexos por estado
    # --------------------
    anexos = AnexoRequerido.objects.all()
    tabla_anexos_data = [['#','Anexo','Validados','Rechazados','Pendientes']]
    for i, anexo in enumerate(anexos, start=1):
        docs_anexo = Documento.objects.filter(anexo=anexo)
        validados = docs_anexo.filter(estado='validado').count()
        rechazados = docs_anexo.filter(estado='rechazado').count()
        pendientes = docs_anexo.filter(estado='pendiente').count()
        tabla_anexos_data.append([i, anexo.nombre, validados, rechazados, pendientes])
    tabla_anexos = Table(tabla_anexos_data, hAlign='CENTER', colWidths=[30,200,60,60,60])
    tabla_anexos.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    elements.append(Paragraph("📋 Anexos por Estado:", sub_titulo))
    elements.append(tabla_anexos)
    elements.append(Paragraph("Tabla 2: Estado de documentos por anexo", arial10))

    # Observaciones específicas por anexo
    for anexo in anexos:
        docs_anexo = Documento.objects.filter(anexo=anexo)
        total = docs_anexo.count()
        validados = docs_anexo.filter(estado='validado').count()
        rechazados = docs_anexo.filter(estado='rechazado').count()
        pendientes = docs_anexo.filter(estado='pendiente').count()
        elements.append(Paragraph(
            f"Anexo '{anexo.nombre}': {validados}/{total} validados, {rechazados} rechazados, {pendientes} pendientes.", observacion
        ))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla: Avance por entidad
    # --------------------
    data_entidades = [['#','Entidad','Subidos','Validados','Rechazados','Pendientes','Avance %']]
    porcentajes = {}
    entidad_obs_text = []
    for i, entidad in enumerate(entidades, start=1):
        docs = Documento.objects.filter(usuario=entidad)
        total = docs.count()
        subidos = docs.exclude(archivo='').count()
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        pendientes = total - validados - rechazados
        porcentaje = (validados / total * 100) if total else 0
        nombre = entidad.get_full_name() or entidad.username
        data_entidades.append([i,nombre,subidos,validados,rechazados,pendientes,f'{porcentaje:.1f}%'])
        porcentajes[nombre] = porcentaje
        entidad_obs_text.append(
            f"Entidad '{nombre}': {validados}/{total} validados ({porcentaje:.1f}%), {rechazados} rechazados, {pendientes} pendientes."
        )

    tabla_entidades = Table(data_entidades, hAlign='CENTER', repeatRows=1, colWidths=[30,120,50,50,50,50,50])
    style_ent = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9)
    ])
    for i in range(1,len(data_entidades)):
        pct = float(data_entidades[i][6].replace('%',''))
        if pct>=80: bg=colors.lightgreen
        elif pct>=50: bg=colors.lightyellow
        else: bg=colors.pink
        style_ent.add('BACKGROUND',(0,i),(-1,i),bg)
    tabla_entidades.setStyle(style_ent)
    elements.append(Paragraph("📋 Avance por Entidad:", sub_titulo))
    elements.append(tabla_entidades)
    elements.append(Paragraph("Tabla 3: Avance de documentos por entidad", arial10))
    
    # Observaciones específicas por entidad
    for obs in entidad_obs_text:
        elements.append(Paragraph(obs, observacion))
    elements.append(Spacer(1,10))

    # --------------------
    # Gráfico: % validados por entidad
    # --------------------
    fig_bar, ax_bar = plt.subplots(figsize=(8,4))
    ax_bar.bar(porcentajes.keys(), porcentajes.values(), color='#7B1F26')
    ax_bar.set_ylabel('% Validados')
    ax_bar.set_title('Porcentaje de Documentos Validados por Entidad')
    ax_bar.set_ylim(0,100)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf_bar = BytesIO()
    plt.savefig(buf_bar, format='png')
    plt.close(fig_bar)
    buf_bar.seek(0)
    elements.append(Image(buf_bar, width=500, height=250))
    elements.append(Paragraph("Observación: Permite identificar visualmente la entidad con mayor y menor avance.", observacion))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla anexos más rechazados
    # --------------------
    tabla_anexos_rech = [['#','Anexo','Rechazados']]
    anexo_rechazados = {}
    for i, anexo in enumerate(anexos, start=1):
        count = Documento.objects.filter(anexo=anexo, estado='rechazado').count()
        tabla_anexos_rech.append([i, anexo.nombre, count])
        anexo_rechazados[anexo.nombre] = count
    tabla_anexos_rech_tabla = Table(tabla_anexos_rech, hAlign='CENTER', colWidths=[30,200,60])
    tabla_anexos_rech_tabla.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    elements.append(Paragraph("📋 Anexos más Rechazados:", sub_titulo))
    elements.append(tabla_anexos_rech_tabla)
    elements.append(Paragraph("Tabla 4: Anexos con mayor número de documentos rechazados", arial10))

    # Observación concreta
    if anexo_rechazados:
        max_rech = max(anexo_rechazados.values())
        max_anexo = [k for k,v in anexo_rechazados.items() if v==max_rech][0]
        elements.append(Paragraph(f"Observación: El anexo '{max_anexo}' presenta el mayor número de rechazos ({max_rech}).", observacion))
        elements.append(Spacer(1,10))

    # --------------------
    # Pie de página
    # --------------------
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de Seguimiento del Modelo para la Igualdad entre Mujeres y Hombres del Estado de Zacatecas.",
        ParagraphStyle('Pie', fontName='Helvetica', fontSize=10, alignment=1, textColor=colors.grey)
    )
    elements.append(Spacer(1,20))
    elements.append(pie)

    # --------------------
    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"reporte_trimestral_{slugify(nombre_mes)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Estilos
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=14, spaceAfter=8)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=12, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)

    elements = []

    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
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
    # Tabla resumen general
    # --------------------
    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Entidades registradas', total_entidades],
        [2, 'Documentos esperados', total_esperado],
        [3, 'Documentos subidos', total_subidos],
        [4, 'Documentos validados', total_validados],
        [5, 'Documentos rechazados', total_rechazados],
        [6, 'Documentos pendientes', total_pendientes],
        [7, 'Porcentaje de avance (validado)', f'{porcentaje_global:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30, 200, 100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTSIZE',(0,0),(-1,-1),12)
    ]))
    elements.append(Paragraph("📊 Resumen Ejecutivo:", sub_titulo))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 10))

    # --------------------
    # Gráfico 1: Distribución por estado
    # --------------------
    fig_estado, ax_estado = plt.subplots(figsize=(6,4))
    estados = ['Validados', 'Rechazados', 'Pendientes']
    valores = [total_validados, total_rechazados, total_pendientes]
    colores = ['#4CAF50','#FF6347','#FFD700']
    ax_estado.pie(valores, labels=estados, autopct='%1.1f%%', colors=colores, startangle=90)
    ax_estado.set_title('Distribución de Documentos por Estado')
    plt.tight_layout()
    img_buf_estado = BytesIO()
    plt.savefig(img_buf_estado, format='png')
    plt.close(fig_estado)
    img_buf_estado.seek(0)
    elements.append(Image(img_buf_estado, width=400, height=250))
    elements.append(Paragraph("Observación: Este gráfico muestra la proporción de documentos validados, rechazados y pendientes, facilitando identificar el cumplimiento general.", observacion))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla: Anexos por estado
    # --------------------
    anexos = AnexoRequerido.objects.all()
    tabla_anexos_data = [['#','Anexo','Validados','Rechazados','Pendientes']]
    for i, anexo in enumerate(anexos, start=1):
        docs_anexo = Documento.objects.filter(anexo=anexo)
        validados = docs_anexo.filter(estado='validado').count()
        rechazados = docs_anexo.filter(estado='rechazado').count()
        pendientes = docs_anexo.filter(estado='pendiente').count()
        tabla_anexos_data.append([i, anexo.nombre, validados, rechazados, pendientes])
    tabla_anexos = Table(tabla_anexos_data, hAlign='CENTER', colWidths=[30,200,60,60,60])
    tabla_anexos.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),12),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    elements.append(Paragraph("📋 Anexos por Estado:", sub_titulo))
    elements.append(tabla_anexos)
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla y gráfico por entidad
    # --------------------
    data_entidades = [['#','Entidad','Subidos','Validados','Rechazados','Pendientes','Avance %']]
    porcentajes = {}
    entidad_obs_text = []
    for i, entidad in enumerate(entidades, start=1):
        docs = Documento.objects.filter(usuario=entidad)
        total = docs.count()
        subidos = docs.exclude(archivo='').count()
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        pendientes = total - validados - rechazados
        porcentaje = (validados / total * 100) if total else 0
        nombre = entidad.get_full_name() or entidad.username
        data_entidades.append([i,nombre,subidos,validados,rechazados,pendientes,f'{porcentaje:.1f}%'])
        porcentajes[nombre] = porcentaje
        entidad_obs_text.append(f"Entidad '{nombre}': {validados}/{total} validados ({porcentaje:.1f}%), {rechazados} rechazados, {pendientes} pendientes.")

    tabla_entidades = Table(data_entidades, hAlign='CENTER', repeatRows=1, colWidths=[30,120,60,60,60,60,60])
    style_ent = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),12)
    ])
    for i in range(1,len(data_entidades)):
        pct = float(data_entidades[i][6].replace('%',''))
        if pct>=80: bg=colors.lightgreen
        elif pct>=50: bg=colors.lightyellow
        else: bg=colors.pink
        style_ent.add('BACKGROUND',(0,i),(-1,i),bg)
    tabla_entidades.setStyle(style_ent)
    elements.append(Paragraph("📋 Avance por Entidad:", sub_titulo))
    elements.append(tabla_entidades)
    elements.append(Spacer(1,10))

    # --------------------
    # Gráfico: % validados por entidad
    # --------------------
    fig_bar, ax_bar = plt.subplots(figsize=(8,4))
    ax_bar.bar(porcentajes.keys(), porcentajes.values(), color='#7B1F26')
    ax_bar.set_ylabel('% Validados')
    ax_bar.set_title('Porcentaje de Documentos Validados por Entidad')
    ax_bar.set_ylim(0,100)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf_bar = BytesIO()
    plt.savefig(buf_bar, format='png')
    plt.close(fig_bar)
    buf_bar.seek(0)
    elements.append(Image(buf_bar, width=500, height=250))
    elements.append(Paragraph("Observación: Identifica visualmente la entidad con mayor y menor avance.", observacion))
    elements.append(Spacer(1,10))

    # --------------------
    # Tabla de anexos más rechazados
    # --------------------
    tabla_anexos_rech = [['#','Anexo','Rechazados']]
    anexo_rechazados = {}
    for i, anexo in enumerate(anexos, start=1):
        count = Documento.objects.filter(anexo=anexo, estado='rechazado').count()
        tabla_anexos_rech.append([i, anexo.nombre, count])
        anexo_rechazados[anexo.nombre] = count
    tabla_anexos_rech_tabla = Table(tabla_anexos_rech, hAlign='CENTER', colWidths=[30,200,60])
    tabla_anexos_rech_tabla.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),12),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    elements.append(Paragraph("📋 Anexos más Rechazados:", sub_titulo))
    elements.append(tabla_anexos_rech_tabla)
    elements.append(Spacer(1,5))
    if anexo_rechazados:
        max_rech = max(anexo_rechazados.values())
        max_anexo = [k for k,v in anexo_rechazados.items() if v==max_rech][0]
        elements.append(Paragraph(f"Observación: El anexo '{max_anexo}' presenta el mayor número de rechazos ({max_rech}).", observacion))
        elements.append(Spacer(1,10))

    # --------------------
    # Pie de página
    # --------------------
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de Seguimiento del Modelo para la Igualdad entre Mujeres y Hombres del Estado de Zacatecas.",
        ParagraphStyle('Pie', fontName='Helvetica', fontSize=10, alignment=1, textColor=colors.grey)
    )
    elements.append(Spacer(1,20))
    elements.append(pie)

    # --------------------
    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"reporte_trimestral_{slugify(nombre_mes)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Estilos
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=14, spaceAfter=8)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=12, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)

    elements = []

    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
    fecha_str = ahora.strftime("%d de %B de %Y")

    # PORTADA
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", encabezado))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📄 Reporte Trimestral de Documentación Institucional", titulo))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", arial12))
    elements.append(Spacer(1, 20))

    # DATOS GENERALES
    entidades = Usuario.objects.filter(rol='usuario')
    documentos = Documento.objects.all()
    total_entidades = entidades.count()
    total_esperado = documentos.count()
    total_subidos = documentos.exclude(archivo='').count()
    total_validados = documentos.filter(estado='validado').count()
    total_rechazados = documentos.filter(estado='rechazado').count()
    porcentaje_global = (total_validados / total_esperado * 100) if total_esperado else 0

    # Tabla resumen general
    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Entidades registradas', total_entidades],
        [2, 'Documentos esperados', total_esperado],
        [3, 'Documentos subidos', total_subidos],
        [4, 'Documentos validados', total_validados],
        [5, 'Documentos rechazados', total_rechazados],
        [6, 'Porcentaje de avance (validado)', f'{porcentaje_global:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30, 200, 100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTSIZE',(0,0),(-1,-1),12)
    ]))
    elements.append(Paragraph("📊 Resumen Ejecutivo:", sub_titulo))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 10))

    # Observaciones dinámicas generales
    # Entidad con mayor y menor cumplimiento
    max_entidad, min_entidad = None, None
    max_pct, min_pct = -1, 101
    entidad_obs_text = []
    for entidad in entidades:
        docs = Documento.objects.filter(usuario=entidad)
        total_docs = docs.count()
        validados = docs.filter(estado='validado').count()
        porcentaje = (validados/total_docs*100) if total_docs else 0
        if porcentaje > max_pct:
            max_pct = porcentaje
            max_entidad = entidad.get_full_name() or entidad.username
        if porcentaje < min_pct:
            min_pct = porcentaje
            min_entidad = entidad.get_full_name() or entidad.username
        entidad_obs_text.append(f"Entidad '{entidad.get_full_name() or entidad.username}': {validados}/{total_docs} documentos validados ({porcentaje:.1f}%), {docs.filter(estado='rechazado').count()} rechazados.")

    elements.append(Paragraph(f"La entidad con mayor cumplimiento es '{max_entidad}' ({max_pct:.1f}%) y la que menos '{min_entidad}' ({min_pct:.1f}%).", observacion))
    elements.append(Spacer(1, 5))
    # Observaciones por entidad
    elements.append(Paragraph("Observaciones por entidad:", sub_titulo))
    for obs in entidad_obs_text:
        elements.append(Paragraph(obs, observacion))
    elements.append(Spacer(1, 10))

    # TABLA POR ENTIDAD
    data = [['#', 'Entidad', 'Subidos', 'Validados', 'Rechazados', 'Esperados', 'Avance %']]
    porcentajes = {}
    for i, entidad in enumerate(entidades, start=1):
        docs = Documento.objects.filter(usuario=entidad)
        total = docs.count()
        subidos = docs.exclude(archivo='').count()
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        porcentaje = (validados / total * 100) if total else 0
        nombre = entidad.get_full_name() or entidad.username
        data.append([i, nombre, subidos, validados, rechazados, total, f'{porcentaje:.1f}%'])
        porcentajes[nombre] = porcentaje

    tabla_entidades = Table(data, hAlign='CENTER', repeatRows=1, colWidths=[30,120,60,60,60,60,60])
    style = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),12)
    ])
    for i in range(1,len(data)):
        pct = float(data[i][6].replace('%',''))
        if pct >= 80: bg_color=colors.lightgreen
        elif pct >=50: bg_color=colors.lightyellow
        else: bg_color=colors.pink
        style.add('BACKGROUND',(0,i),(-1,i),bg_color)
    tabla_entidades.setStyle(style)
    elements.append(Paragraph("📋 Avance por Entidad:", sub_titulo))
    elements.append(tabla_entidades)
    elements.append(Spacer(1,10))

    # ------------------------
    # Gráfico 1: % validados por entidad
    # ------------------------
    fig1, ax1 = plt.subplots(figsize=(8,4))
    ax1.bar(porcentajes.keys(), porcentajes.values(), color='#7B1F26')
    ax1.set_ylabel('% Validados')
    ax1.set_title('Porcentaje de Documentos Validados por Entidad')
    ax1.set_ylim(0,100)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    img_buf1 = BytesIO()
    plt.savefig(img_buf1, format='png')
    plt.close(fig1)
    img_buf1.seek(0)
    elements.append(Image(img_buf1, width=500, height=250))
    elements.append(Paragraph("Observación: Este gráfico permite identificar visualmente qué entidades tienen mejor desempeño en la entrega y validación de documentos.", observacion))
    elements.append(Spacer(1,10))

    # ------------------------
    # Gráfico 2: Anexos más rechazados
    # ------------------------
    anexos = AnexoRequerido.objects.all()
    anexo_labels, anexo_rechazados = [], []
    for anexo in anexos:
        count_rechazados = Documento.objects.filter(anexo=anexo, estado='rechazado').count()
        if count_rechazados>0:
            anexo_labels.append(anexo.nombre)
            anexo_rechazados.append(count_rechazados)
    if anexo_labels:
        fig2, ax2 = plt.subplots(figsize=(8,4))
        ax2.bar(anexo_labels, anexo_rechazados, color='tomato')
        ax2.set_ylabel('Cantidad Rechazada')
        ax2.set_title('Anexos con Más Rechazos')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        img_buf2 = BytesIO()
        plt.savefig(img_buf2, format='png')
        plt.close(fig2)
        img_buf2.seek(0)
        elements.append(Image(img_buf2, width=500, height=250))
        # Observación específica sobre anexos
        max_rechazo = max(anexo_rechazados)
        idx_max = anexo_rechazados.index(max_rechazo)
        elements.append(Paragraph(f"Observación: El anexo '{anexo_labels[idx_max]}' presenta el mayor número de rechazos ({max_rechazo}). Requiere atención prioritaria.", observacion))
        elements.append(Spacer(1,10))

    # Pie de página
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de Seguimiento del Modelo para la Igualdad entre Mujeres y Hombres del Estado de Zacatecas.",
        ParagraphStyle('Pie', fontName='Helvetica', fontSize=10, alignment=1, textColor=colors.grey)
    )
    elements.append(Spacer(1,20))
    elements.append(pie)

    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"reporte_trimestral_{slugify(nombre_mes)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    # Estilos
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=14, spaceAfter=8)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=12, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)
    
    elements = []

    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
    fecha_str = ahora.strftime("%d de %B de %Y")

    # Portada
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", encabezado))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📄 Reporte Trimestral de Documentación Institucional", titulo))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", arial12))
    elements.append(Spacer(1, 20))

    # Datos generales
    entidades = Usuario.objects.filter(rol='usuario')
    total_entidades = entidades.count()
    total_esperado = Documento.objects.count()
    total_subidos = Documento.objects.exclude(archivo='').count()
    total_validados = Documento.objects.filter(estado='validado').count()
    total_rechazados = Documento.objects.filter(estado='rechazado').count()
    porcentaje_global = (total_validados / total_esperado * 100) if total_esperado else 0

    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Entidades registradas', total_entidades],
        [2, 'Documentos esperados', total_esperado],
        [3, 'Documentos subidos', total_subidos],
        [4, 'Documentos validados', total_validados],
        [5, 'Documentos rechazados', total_rechazados],
        [6, 'Porcentaje de avance (validado)', f'{porcentaje_global:.1f}%']
    ]

    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30, 200, 100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12)
    ]))
    elements.append(Paragraph("📊 Resumen Ejecutivo:", sub_titulo))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 10))

    # Observación específica general
    elementos_observacion = []
    if entidades.exists():
        # Mejor y peor desempeño
        max_val = 0
        min_val = 100
        max_entidad = ""
        min_entidad = ""
        for entidad in entidades:
            docs = Documento.objects.filter(usuario=entidad)
            total_docs = docs.count()
            validados = docs.filter(estado='validado').count()
            porcentaje = (validados / total_docs * 100) if total_docs else 0
            if porcentaje > max_val:
                max_val = porcentaje
                max_entidad = entidad.get_full_name() or entidad.username
            if porcentaje < min_val:
                min_val = porcentaje
                min_entidad = entidad.get_full_name() or entidad.username

        elementos_observacion.append(
            f"El avance general es del {porcentaje_global:.1f}%. "
            f"La entidad con mayor cumplimiento es '{max_entidad}' con {max_val:.1f}% de documentos validados, "
            f"mientras que la entidad con menor cumplimiento es '{min_entidad}' con {min_val:.1f}%."
        )

        if total_rechazados > 0:
            elementos_observacion.append(
                f"Se identificaron {total_rechazados} documentos rechazados, los cuales requieren revisión prioritaria."
            )
        else:
            elementos_observacion.append("No se registraron documentos rechazados en este periodo.")

    elements.append(Paragraph("Observación:", sub_titulo))
    for obs in elementos_observacion:
        elements.append(Paragraph(obs, observacion))
    elements.append(Spacer(1, 15))

    # Tabla por entidad (igual que antes)
    data = [['#', 'Entidad', 'Subidos', 'Validados', 'Rechazados', 'Esperados', 'Avance %']]
    porcentajes = {}
    for i, entidad in enumerate(entidades, start=1):
        docs = Documento.objects.filter(usuario=entidad)
        total = docs.count()
        subidos = docs.exclude(archivo='').count()
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        porcentaje = (validados / total * 100) if total else 0
        nombre = entidad.get_full_name() or entidad.username
        data.append([i, nombre, subidos, validados, rechazados, total, f'{porcentaje:.1f}%'])
        porcentajes[nombre] = porcentaje

    tabla_entidades = Table(data, hAlign='CENTER', repeatRows=1, colWidths=[30, 120, 60, 60, 60, 60, 60])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 12)
    ])
    for i in range(1, len(data)):
        porcentaje = float(data[i][6].replace('%', ''))
        if porcentaje >= 80:
            bg_color = colors.lightgreen
        elif porcentaje >= 50:
            bg_color = colors.lightyellow
        else:
            bg_color = colors.pink
        style.add('BACKGROUND', (0, i), (-1, i), bg_color)
    tabla_entidades.setStyle(style)

    elements.append(Paragraph("📋 Avance por Entidad:", sub_titulo))
    elements.append(tabla_entidades)
    elements.append(Spacer(1, 10))

    # Observaciones dinámicas por entidad
    for i, entidad in enumerate(entidades, start=1):
        docs = Documento.objects.filter(usuario=entidad)
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        total_docs = docs.count()
        porcentaje = (validados / total_docs * 100) if total_docs else 0
        obs_text = f"Entidad '{entidad.get_full_name() or entidad.username}': {validados} documentos validados de {total_docs} ({porcentaje:.1f}%), con {rechazados} documentos rechazados."
        elements.append(Paragraph(obs_text, observacion))

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    # Estilos
    styles = getSampleStyleSheet()
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=14, spaceAfter=8)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=12, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)
    
    elements = []

    # Fecha
    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
    fecha_str = ahora.strftime("%d de %B de %Y")

    # 📄 PORTADA
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", encabezado))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📄 Reporte Trimestral de Documentación Institucional", titulo))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", arial12))
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
        ['#', 'Indicador', 'Valor'],
        [1, 'Entidades registradas', total_entidades],
        [2, 'Documentos esperados', total_esperado],
        [3, 'Documentos subidos', total_subidos],
        [4, 'Documentos validados', total_validados],
        [5, 'Documentos rechazados', total_rechazados],
        [6, 'Porcentaje de avance (validado)', f'{porcentaje_global:.1f}%']
    ]

    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30, 200, 100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12)
    ]))
    elements.append(Paragraph("📊 Resumen Ejecutivo:", sub_titulo))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph(
        "Observación: Se puede observar que el porcentaje global de documentos validados permite identificar qué tan cumplidas están las entidades con respecto a la documentación esperada.",
        observacion
    ))

    # 📋 TABLA POR ENTIDAD
    data = [['#', 'Entidad', 'Subidos', 'Validados', 'Rechazados', 'Esperados', 'Avance %']]
    porcentajes = {}
    for i, entidad in enumerate(entidades, start=1):
        docs = Documento.objects.filter(usuario=entidad)
        total = docs.count()
        subidos = docs.exclude(archivo='').count()
        validados = docs.filter(estado='validado').count()
        rechazados = docs.filter(estado='rechazado').count()
        porcentaje = (validados / total * 100) if total else 0
        nombre = entidad.get_full_name() if hasattr(entidad, 'get_full_name') and entidad.get_full_name() else entidad.username
        data.append([i, nombre, subidos, validados, rechazados, total, f'{porcentaje:.1f}%'])
        porcentajes[nombre] = porcentaje

    tabla_entidades = Table(data, hAlign='CENTER', repeatRows=1, colWidths=[30, 120, 60, 60, 60, 60, 60])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7B1F26')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 12)
    ])
    for i in range(1, len(data)):
        porcentaje = float(data[i][6].replace('%', ''))
        if porcentaje >= 80:
            bg_color = colors.lightgreen
        elif porcentaje >= 50:
            bg_color = colors.lightyellow
        else:
            bg_color = colors.pink
        style.add('BACKGROUND', (0, i), (-1, i), bg_color)
    tabla_entidades.setStyle(style)

    elements.append(Paragraph("📋 Avance por Entidad (con base en validados):", sub_titulo))
    elements.append(tabla_entidades)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "Observación: Esta tabla permite identificar cuáles entidades tienen mayor cumplimiento en la entrega y validación de documentos, resaltando con colores los niveles de avance.",
        observacion
    ))

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
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(
        "Observación: El gráfico permite visualizar de manera rápida qué entidades presentan mayor porcentaje de documentos validados.",
        observacion
    ))

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
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            "Observación: Este gráfico permite identificar qué anexos son más problemáticos y requieren atención para mejorar el cumplimiento.",
            observacion
        ))

    # 🖊️ PIE
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de \"Seguimiento Secretaría de las Mujeres - Gestión y Revisión de Documentación\" Estado de Zacatecas.",
        ParagraphStyle('pie', fontSize=9, alignment=1, textColor=colors.grey)
    )
    elements.append(Spacer(1, 20))
    elements.append(pie)

    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"Reporte_General_Trimestral_{slugify(nombre_mes)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

@user_passes_test(es_admin)
def reporte_entidad_pdf(request, entidad_id):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Estilos
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    arial10 = ParagraphStyle('Arial10', fontName='Helvetica', fontSize=10, leading=12)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=12, spaceAfter=6)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)

    elements = []
    ahora = datetime.now()
    fecha_str = ahora.strftime("%d de %B de %Y")

    # Obtener entidad
    entidad = get_object_or_404(Usuario, id=entidad_id)
    nombre_entidad = entidad.get_full_name() or entidad.username
    docs = Documento.objects.filter(usuario=entidad)
    total_docs = docs.count()
    validados = docs.filter(estado='validado').count()
    rechazados = docs.filter(estado='rechazado').count()
    pendientes = docs.filter(estado='pendiente').count()
    porcentaje = (validados / total_docs * 100) if total_docs else 0

    # --------------------
    # PORTADA
    # --------------------
    elements.append(Paragraph("Secretaría de las Mujeres del Estado de Zacatecas", titulo))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"📄 Reporte de la Entidad: {nombre_entidad}", titulo))
    elements.append(Paragraph(f"Fecha de generación: {fecha_str}", arial12))
    elements.append(Spacer(1, 30))

    # --------------------
    # TABLA 1: Resumen ejecutivo
    # --------------------
    resumen = [
        ['#', 'Indicador', 'Valor'],
        [1, 'Documentos esperados', total_docs],
        [2, 'Documentos validados', validados],
        [3, 'Documentos rechazados', rechazados],
        [4, 'Documentos pendientes', pendientes],
        [5, 'Avance (%)', f'{porcentaje:.1f}%']
    ]
    tabla_resumen = Table(resumen, hAlign='CENTER', colWidths=[30,200,100])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTSIZE',(0,0),(-1,-1),10)
    ]))

    elements.append(KeepTogether([
        Paragraph("📊 Resumen Ejecutivo de la Entidad", sub_titulo),
        tabla_resumen,
        Paragraph("Tabla 1: Resumen general de la entidad", arial10),
        Paragraph(f"Observación: La entidad {nombre_entidad} presenta un avance del {porcentaje:.1f}%. "
                  f"Con {validados} documentos validados de un total de {total_docs}, "
                  f"{'su desempeño es sobresaliente.' if porcentaje >= 80 else 'se encuentra en proceso, con áreas por mejorar.'}", observacion)
    ]))
    elements.append(Spacer(1, 15))

    # --------------------
    # GRÁFICO 1: Distribución por estado
    # --------------------
    fig, ax = plt.subplots(figsize=(6,4))
    estados = ['Validados','Rechazados','Pendientes']
    valores = [validados, rechazados, pendientes]
    colores = ['#4CAF50','#FF6347','#FFD700']
    ax.pie(valores, labels=estados, autopct='%1.1f%%', colors=colores, startangle=90)
    ax.set_title('Distribución de Documentos por Estado')
    plt.tight_layout()
    img_buf = BytesIO()
    plt.savefig(img_buf, format='png')
    plt.close(fig)
    img_buf.seek(0)

    elements.append(KeepTogether([
        Paragraph("Gráfico 1: Distribución de documentos de la entidad", arial10),
        Image(img_buf, width=400, height=250),
        Paragraph(f"Observación: Predominan los documentos {('validados' if validados>rechazados and validados>pendientes else 'rechazados' if rechazados>pendientes else 'pendientes')}, "
                  f"lo que refleja la situación actual de la entidad.", observacion)
    ]))
    elements.append(Spacer(1,15))

    # --------------------
    # TABLA 2: Documentos por anexo
    # --------------------
    anexos = AnexoRequerido.objects.all()
    tabla_anexos_data = [['#','Anexo','Validados','Rechazados','Pendientes']]
    for i, anexo in enumerate(anexos, start=1):
        docs_anexo = docs.filter(anexo=anexo)
        val = docs_anexo.filter(estado='validado').count()
        rec = docs_anexo.filter(estado='rechazado').count()
        pen = docs_anexo.filter(estado='pendiente').count()
        tabla_anexos_data.append([i, anexo.nombre, val, rec, pen])

    tabla_anexos = Table(tabla_anexos_data, hAlign='CENTER', colWidths=[30,200,60,60,60])
    tabla_anexos.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))

    elements.append(KeepTogether([
        Paragraph("📋 Estado de Documentos por Anexo", sub_titulo),
        tabla_anexos,
        Paragraph("Tabla 2: Avance de documentos por anexo", arial10)
    ]))
    elements.append(Spacer(1,15))

    # --------------------
    # GRÁFICO 2: Documentos validados por anexo
    # --------------------
    anexos_nombres = [a.nombre for a in anexos]
    val_por_anexo = [docs.filter(anexo=a, estado='validado').count() for a in anexos]
    fig2, ax2 = plt.subplots(figsize=(8,4))
    ax2.bar(anexos_nombres, val_por_anexo, color='#7B1F26')
    ax2.set_title("Documentos Validados por Anexo")
    ax2.set_ylabel("Cantidad")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf2 = BytesIO()
    plt.savefig(buf2, format='png')
    plt.close(fig2)
    buf2.seek(0)

    elements.append(KeepTogether([
        Paragraph("Gráfico 2: Documentos validados por anexo", arial10),
        Image(buf2, width=500, height=250),
        Paragraph("Observación: Se destacan los anexos con mayor número de documentos validados. "
                  "Esto permite identificar los temas en los que la entidad ha mostrado mayor avance.", observacion)
    ]))
    elements.append(Spacer(1,15))

    # --------------------
    # TABLA 3: Anexos con más rechazos
    # --------------------
    rechazos_por_anexo = {a.nombre: docs.filter(anexo=a, estado='rechazado').count() for a in anexos}
    tabla_rechazos = [['#','Anexo','Rechazados']]
    for i, (anexo, cant) in enumerate(rechazos_por_anexo.items(), start=1):
        tabla_rechazos.append([i, anexo, cant])

    tabla_rechazos_t = Table(tabla_rechazos, hAlign='CENTER', colWidths=[30,200,60])
    tabla_rechazos_t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#7B1F26')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTSIZE',(0,0),(-1,-1),9),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')
    ]))

    max_rechazo = max(rechazos_por_anexo.values()) if rechazos_por_anexo else 0
    anexo_max = [k for k,v in rechazos_por_anexo.items() if v==max_rechazo][0] if max_rechazo else None

    elements.append(KeepTogether([
        Paragraph("📋 Anexos con Mayor Número de Rechazos", sub_titulo),
        tabla_rechazos_t,
        Paragraph("Tabla 3: Número de documentos rechazados por anexo", arial10),
        Paragraph(f"Observación: El anexo con más rechazos es '{anexo_max}' con {max_rechazo} documentos. "
                  "Este punto debe recibir especial atención.", observacion) if anexo_max else Paragraph("Observación: No se registran rechazos en los anexos.", observacion)
    ]))
    elements.append(Spacer(1,15))

    # --------------------
    # Pie de página
    # --------------------
    pie = Paragraph(
        "Este reporte ha sido generado automáticamente por el Sistema de \"Seguimiento Secretaría de las Mujeres - Gestión y Revisión de Documentación\" Estado de Zacatecas.",
        ParagraphStyle('pie', fontSize=9, alignment=1, textColor=colors.grey)
    )
    elements.append(Spacer(1,20))
    elements.append(pie)

    pdf.build(elements)
    buffer.seek(0)
    nombre_archivo = f"reporte_entidad_{(entidad)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response

@user_passes_test(es_admin)
def eliminar_todos_anexos(request):
    AnexoRequerido.objects.all().delete()
    messages.success(request, "Todos los anexos han sido eliminados.")
    return redirect('admin_anexos')



# Opción 1: Solo limpiar
@user_passes_test(es_admin)
def limpiar_anexos_subidos(request):
    anexos = AnexoUsuario.objects.all()
    for anexo in anexos:
        if anexo.archivo:
            anexo.archivo.delete(save=False)  # elimina el archivo físico
            anexo.archivo = None
            anexo.estado = 'pendiente'
            anexo.observaciones = ''
            anexo.save()
    messages.success(request, "Los archivos subidos han sido limpiados para el nuevo trimestre.")
    return redirect('admin_anexos')


# Opción 2: Respaldar y limpiar
@user_passes_test(es_admin)
def respaldar_y_limpiar_anexos(request):
    trimestre_actual = f"{now().year}-Q{((now().month-1)//3)+1}"
    anexos = AnexoUsuario.objects.all()

    for anexo in anexos:
        if anexo.archivo:
            # Guardar en histórico
            AnexoHistorico.objects.create(
                entidad=anexo.entidad,
                anexo_requerido=anexo.anexo_requerido,
                archivo=anexo.archivo,
                trimestre=trimestre_actual
            )
            # Limpiar en el registro actual
            anexo.archivo = None
            anexo.estado = 'pendiente'
            anexo.observaciones = ''
            anexo.save()
    messages.success(request, "Los archivos fueron respaldados y limpiados para el nuevo trimestre.")
    return redirect('admin_anexos')



@user_passes_test(es_admin)
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

    ahora = datetime.now()
    nombre_mes = ahora.strftime("%B").capitalize()
    fecha_str = ahora.strftime("%d de %B de %Y")

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
    nombre_archivo = f"Reporte_Anexos_{slugify(nombre_mes)}_{ahora.year}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response
@user_passes_test(es_admin)
def vista_respaldo_anexos(request):
    respaldos = AnexoHistorico.objects.all().order_by('-trimestre')
    return render(request, 'core/respaldo_anexos.html', {'respaldos': respaldos})


@user_passes_test(lambda u: u.is_superuser)  # o tu función es_admin
def respaldar_y_limpiar_anexos(request):
    trimestre_actual = f"{now().year}-Q{((now().month-1)//3)+1}"
    anexos = Documento.objects.all()

    for anexo in anexos:
        if anexo.archivo:
            # Guardar en histórico
            AnexoHistorico.objects.create(
                entidad=anexo.usuario,
                anexo_requerido=anexo.anexo,
                archivo=anexo.archivo,
                trimestre=trimestre_actual
            )
            # Limpiar en el registro actual
            anexo.archivo = None
            anexo.estado = 'pendiente'
            anexo.observaciones = ''
            anexo.save()
    messages.success(request, "Los archivos fueron respaldados y limpiados para el nuevo trimestre.")
    return redirect('admin_anexos')

