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

# --------------------
# Modelos y formularios del proyecto
# --------------------
from .models import Documento, Usuario, AnexoRequerido, AnexoHistorico
from .forms import CrearUsuarioForm, EditarUsuarioForm, AnexoForm

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


    anexo = get_object_or_404(AnexoRequerido, id=anexo_id)
    anexo.delete()
    Documento.objects.filter(anexo=anexo).delete()  # Limpieza relacionada
    return redirect('admin_anexos')

#REPORTES DE DOCUMENTOS 

@user_passes_test(es_admin)
def reporte_general_pdf(request):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # --------------------
    # ESTILOS
    # --------------------
    arial12 = ParagraphStyle('Arial12', fontName='Helvetica', fontSize=12, leading=15)
    arial10 = ParagraphStyle('Arial10', fontName='Helvetica', fontSize=10, leading=12)
    encabezado = ParagraphStyle('Encabezado', fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=10)
    titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=16, alignment=1, spaceAfter=12)
    sub_titulo = ParagraphStyle('SubTitulo', fontName='Helvetica-Bold', fontSize=12, spaceAfter=6)
    observacion = ParagraphStyle('Observacion', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#333333'), spaceAfter=10, leftIndent=10, rightIndent=10)

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
        [6, 'Documentos pendientes', total_pendientes],
        [7, 'Porcentaje global de validación', f"{porcentaje_global:.2f}%"]
    ]
    t_resumen = Table(resumen, hAlign='LEFT', colWidths=[30, 200, 100])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#d3d3d3')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ]))
    elements.append(Paragraph("Resumen Ejecutivo", sub_titulo))
    elements.append(t_resumen)
    elements.append(Spacer(1, 20))

    # --------------------
    # AVANCE POR ENTIDAD
    # --------------------
    tabla_entidades = [['Entidad', 'Subidos', 'Validados', 'Rechazados', 'Pendientes', '% Validados']]
    for ent in entidades:
        docs_ent = documentos.filter(usuario=ent)
        subidos = docs_ent.exclude(archivo='').count()
        validados = docs_ent.filter(estado='validado').count()
        rechazados = docs_ent.filter(estado='rechazado').count()
        pendientes = docs_ent.count() - validados - rechazados
        pct = (validados / docs_ent.count() * 100) if docs_ent.count() else 0
        tabla_entidades.append([ent.entidad, subidos, validados, rechazados, pendientes, f"{pct:.2f}%"])

    t_entidades = Table(tabla_entidades, hAlign='LEFT', repeatRows=1)
    t_entidades.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#d3d3d3')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ]))
    elements.append(Paragraph("Avance por Entidad", sub_titulo))
    elements.append(t_entidades)
    elements.append(Spacer(1, 20))

    # --------------------
    # ANEXOS MÁS RECHAZADOS
    # --------------------
    anexos = AnexoRequerido.objects.all()
    tabla_anexos = [['Anexo', 'Veces rechazado']]
    for a in anexos:
        count_rech = Documento.objects.filter(anexo=a, estado='rechazado').count()
        tabla_anexos.append([a.nombre, count_rech])
    t_anexos = Table(tabla_anexos, hAlign='LEFT', repeatRows=1)
    t_anexos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#d3d3d3')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ]))
    elements.append(Paragraph("Anexos más rechazados", sub_titulo))
    elements.append(t_anexos)
    elements.append(Spacer(1, 20))

    # --------------------
    # OBSERVACIONES
    # --------------------
    observaciones = Documento.objects.exclude(observaciones__isnull=True).exclude(observaciones__exact='')
    for obs in observaciones:
        elements.append(Paragraph(f"{obs.usuario.entidad} - {obs.anexo.nombre}: {obs.observaciones}", observacion))

    # --------------------
    # PIE DE PÁGINA
    # --------------------
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawString(30, 15, "Secretaría de las Mujeres del Estado de Zacatecas - Reporte Institucional")
        canvas.restoreState()

    pdf.build(elements, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_general_{slugify(fecha_str)}.pdf"'
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
                # Evitar respaldar si ya existe en histórico
                existe = AnexoHistorico.objects.filter(
                    entidad=doc.usuario,
                    anexo_requerido=doc.anexo,
                    archivo=doc.archivo
                ).exists()
                if not existe:
                    AnexoHistorico.objects.create(
                        entidad=doc.usuario,
                        anexo_requerido=doc.anexo,
                        archivo=doc.archivo
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

        # Eliminar registros de la base
        respaldos.delete()

        messages.success(request, f"✅ Se han eliminado {count} archivos respaldados correctamente.")
        return redirect('vista_respaldo_anexos')
    return redirect('vista_respaldo_anexos')


@user_passes_test(es_admin)
def descargar_respaldo_zip(request):
    respaldos = AnexoHistorico.objects.all()
    if not respaldos.exists():
        messages.info(request, "ℹ️ No hay archivos respaldados para descargar.")
        return redirect('vista_respaldo_anexos')

    # Crear buffer en memoria
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for r in respaldos:
            if r.archivo and default_storage.exists(r.archivo.name):
                nombre = f"{r.entidad.username}_{r.anexo_requerido.nombre}_{r.fecha_subida.strftime('%Y%m%d_%H%M%S')}"
                ext = r.archivo.name.split('.')[-1]
                nombre_archivo_zip = f"{nombre}.{ext}"

                with default_storage.open(r.archivo.name, 'rb') as f:
                    zip_file.writestr(nombre_archivo_zip, f.read())

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=respaldo_anexos.zip'
    return response


#Recuperción de contraseña

def olvido_contrasena(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()  # Quitamos espacios

        if not email:
            # Validación si no ingresa correo
            messages.error(request, "Por favor, ingresa un correo válido.")
            return redirect("olvido_contrasena")

        # Aquí mandas un correo al administrador avisando
        send_mail(
            subject="Solicitud de recuperación de contraseña",
            message=f"El usuario con correo {email} solicitó recuperar su contraseña.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=["tu_correo_admin@gmail.com"],  # <-- cambia por el correo del admin
            fail_silently=False,
        )
        
        # Mensaje de éxito
        messages.success(request, "Se ha enviado tu solicitud al administrador.")
        return redirect("olvido_contrasena")  # o a otra página que quieras

    return render(request, "core/olvido_contrasena.html")



#Recuperción de contraseña

def olvido_contrasena(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()  # Quitamos espacios

        if not email:
            # Validación si no ingresa correo
            messages.error(request, "Por favor, ingresa un correo válido.")
            return redirect("olvido_contrasena")

        # Aquí mandas un correo al administrador avisando
        send_mail(
            subject="Solicitud de recuperación de contraseña",
            message=f"El usuario con correo {email} solicitó recuperar su contraseña.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=["tu_correo_admin@gmail.com"],  # <-- cambia por el correo del admin
            fail_silently=False,
        )
        
        # Mensaje de éxito
        messages.success(request, "Se ha enviado tu solicitud al administrador.")
        return redirect("olvido_contrasena")  # o a otra página que quieras

    return render(request, "core/olvido_contrasena.html")