# --------------------
# Python Estándar
# --------------------
import os
import random
import string
import zipfile
from datetime import datetime
from io import BytesIO

# --------------------
# Django - Vistas, autenticación y utilidades
# --------------------
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail, BadHeaderError
from django.db.utils import IntegrityError
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify

# --------------------
# Librerías de Terceros (ReportLab, Matplotlib, Pandas)
# --------------------
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
)
from reportlab.platypus import Image as RLImage

# Ajuste de Matplotlib (necesario si se usa en entornos sin GUI)
matplotlib.use('Agg') 

# --------------------
# Modelos y Formularios del Proyecto (Locales)
# --------------------
from .forms import (
    CrearUsuarioForm, 
    EditarUsuarioForm, 
    AnexoForm, 
    EditarPerfilAdminForm, 
)
from .models import (
    Documento, 
    Usuario, 
    AnexoRequerido, 
    AnexoHistorico,
)


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
def admin_revision_documentacion(request, entidad_id=None):
    entidades = Usuario.objects.filter(rol='usuario')
    entidad_seleccionada = None
    documentos = Documento.objects.none()

    if entidad_id:
        entidad_seleccionada = get_object_or_404(Usuario, id=entidad_id)

        # Asegura que existan los documentos
        for anexo in AnexoRequerido.objects.all():
            Documento.objects.get_or_create(usuario=entidad_seleccionada, anexo=anexo)

        documentos = Documento.objects.filter(usuario=entidad_seleccionada)

        if request.method == 'POST':
            # ... (código para guardar cambios) ...
            for doc in documentos:
                estado = request.POST.get(f'estado_{doc.id}')
                observaciones = request.POST.get(f'observaciones_{doc.id}')
                if estado:
                    doc.estado = estado
                doc.observaciones = observaciones
                doc.save()

            # 🟢 AÑADIR MENSAJE DE ÉXITO ANTES DE REDIRIGIR
            messages.success(request, 'Cambios de documentación guardados correctamente.')
            
            return redirect('admin_revision_documentacion_entidad', entidad_id=entidad_id)

    # Calcular porcentaje seguro
    total = documentos.count()
    if total > 0:
        validados = documentos.filter(estado='validado').count()
        porcentaje_validados = round((validados / total) * 100, 2)
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
            
            try:
                usuario.save()
                messages.success(request, 'Usuario creado con éxito.')
                return redirect('admin_crear_usuario')
            
            # 📌 CAMBIO CLAVE 1: Manejar el error de unicidad (correo ya existe)
            except IntegrityError:
                messages.error(request, 'El correo electrónico ya está registrado. Por favor, use uno diferente.')
                # Renderizamos la página con el formulario lleno para que el admin no pierda datos
                return render(request, 'core/admin_crear_usuario.html', {'form': form})
            
        else:
            # Si la validación del formulario falla por otras razones (e.g., contraseñas no coinciden)
            # Renderizamos para mostrar los errores específicos del formulario
            pass 
    else:
        form = CrearUsuarioForm()
    
    return render(request, 'core/admin_crear_usuario.html', {'form': form})

from django.shortcuts import render, redirect  # <-- Asegúrate de tener 'redirect'
from django.contrib import messages            # <-- Importar messages
from django.contrib.auth.decorators import login_required
# ... tus importaciones de modelos (Documento, AnexoRequerido, etc.)

@login_required
def usuario_dashboard(request):
    # 🔹 Asegurar que el usuario tenga documentos creados
    for anexo in AnexoRequerido.objects.all():
        Documento.objects.get_or_create(usuario=request.user, anexo=anexo)

    documentos = Documento.objects.filter(usuario=request.user)

    if request.method == 'POST':
        archivos_guardados = False  # Bandera para controlar si se subió algo

        for doc in documentos:
            # Buscamos si viene un archivo para este documento específico
            archivo = request.FILES.get(f'documento_{doc.id}')
            
            if archivo:
                doc.archivo = archivo
                
                # Opcional: Si el documento fue rechazado antes, al subir uno nuevo
                # podrías querer regresarlo a estado 'pendiente' automáticamente:
                if doc.estado == 'rechazado':
                     doc.estado = 'pendiente'
                
                doc.save()
                archivos_guardados = True  # ¡Se guardó al menos uno!

        # Si se guardó al menos un archivo, mandamos el mensaje y recargamos
        if archivos_guardados:
            messages.success(request, '¡Documentos subidos exitosamente!')
            return redirect('usuario_dashboard') # Redirige a la misma URL para limpiar el formulario

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
def admin_eliminar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuario eliminado correctamente.')
        return redirect('admin_gestion_usuarios')
    
    # En caso de acceso por GET (opcional, puede redirigir o lanzar error)
    return redirect('admin_gestion_usuaarios')

@user_passes_test(es_admin)
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    if request.method == 'POST':
        form = EditarUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('admin_gestion_usuarios')
    else:
        form = EditarUsuarioForm(instance=usuario)

    return render(request, 'core/admin_editar_usuario.html', {'form': form, 'usuario': usuario})



@user_passes_test(es_admin)
def admin_perfil(request):
    usuario = request.user

    if request.method == 'POST':
        form = EditarPerfilAdminForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu perfil fue actualizado correctamente.')
            return redirect('admin_perfil')
        else:
            messages.error(request, 'Revisa los campos e inténtalo de nuevo.')
    else:
        form = EditarPerfilAdminForm(instance=usuario)

    return render(request, 'core/admin_perfil.html', {
        'form': form,
        'usuario': usuario,
    })



@user_passes_test(es_admin)
def cambiar_contrasena_admin(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # mantiene la sesión
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('admin_perfil')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'core/cambiar_contrasena_admin.html', {
        'form': form
    })

# --- Verificación de rol admin
def es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.rol == 'admin')

# --- Función para sincronizar anexos con todos los usuarios
def sincronizar_documentos_por_usuario():
    usuarios = Usuario.objects.all()
    anexos = AnexoRequerido.objects.all()

    for usuario in usuarios:
        for anexo in anexos:
            Documento.objects.get_or_create(
                usuario=usuario,
                anexo=anexo,
                defaults={
                    "estado": "pendiente",
                    "observaciones": ""
                }
            )

import io
import matplotlib.pyplot as plt
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.utils.text import slugify

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Model imports (Asegúrate de importar tus modelos)
from .models import AnexoRequerido, Documento, Usuario  # Ajusta según tu estructura

@user_passes_test(lambda u: u.is_superuser) # O tu función es_admin
def reporte_general_pdf(request):
    anexos = AnexoRequerido.objects.all()
    documentos = Documento.objects.all()

    # 1. Validaciones previas
    if not anexos.exists():
        messages.warning(request, "No hay anexos disponibles para generar el reporte.")
        return redirect('admin_dashboard') # Ajusta tu redirect

    # 2. Configuración de Colores Institucionales
    # Guinda oficial aproximado y Dorado
    COLOR_VINO = colors.HexColor('#691C32') 
    COLOR_DORADO = colors.HexColor('#BC955C')
    COLOR_GRIS_TXT = colors.HexColor('#404040')
    
    # Colores para Matplotlib (hex strings)
    HEX_VINO = '#691C32'
    HEX_DORADO = '#BC955C'
    HEX_GRIS = '#9E9E9E'

    buffer = io.BytesIO()
    
    # 3. Configuración del Documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=60, bottomMargin=50
    )

    # 4. Estilos de Texto
    styles = getSampleStyleSheet()
    
    style_titulo = ParagraphStyle(
        'TituloPersonalizado',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=COLOR_VINO,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    style_subtitulo = ParagraphStyle(
        'SubTituloPersonalizado',
        parent=styles['Heading2'],
        fontName='Helvetica',
        fontSize=12,
        textColor=COLOR_DORADO,
        alignment=TA_CENTER,
        spaceAfter=20
    )

    style_header_tabla = ParagraphStyle(
        'HeaderTabla',
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.white,
        alignment=TA_CENTER
    )

    style_celda = ParagraphStyle(
        'CeldaTabla',
        fontName='Helvetica',
        fontSize=9,
        textColor=COLOR_GRIS_TXT,
        alignment=TA_CENTER,
        leading=11  # Espaciado entre líneas
    )
    
    # Estilo especial para celdas de texto largo (alineado a la izquierda)
    style_celda_left = ParagraphStyle(
        'CeldaTablaLeft',
        parent=style_celda,
        alignment=TA_LEFT
    )

    elements = []
    
    # --- CONTENIDO ---

    # Título Principal
    elements.append(Paragraph("Secretaría de las Mujeres", style_titulo))
    elements.append(Paragraph("Reporte Ejecutivo de Cumplimiento Documental", style_subtitulo))
    
    ahora = datetime.now()
    fecha_str = ahora.strftime("%d/%m/%Y a las %H:%M hrs")
    elements.append(Paragraph(f"<b>Fecha de corte:</b> {fecha_str}", style_celda))
    elements.append(Spacer(1, 20))

    # --- CALCULOS CORREGIDOS (General) ---
    entidades = Usuario.objects.filter(rol='usuario') 
    total_entidades = entidades.count()
    
    # 1. Documentos esperados
    # OJO: Si tu sistema crea los registros vacíos desde el inicio, usa:
    total_esperado = documentos.count()
    # SI NO crea registros vacíos (solo se crean al subir), lo "esperado" sería:
    # total_esperado = total_entidades * AnexoRequerido.objects.count()

    # 2. Contamos directamente por estatus (Más seguro)
    total_validados = documentos.filter(estado='validado').count()
    total_rechazados = documentos.filter(estado='rechazado').count()
    
    # IMPORTANTE: Usa el nombre exacto de tu estatus en la BD ('pendiente', 'en_revision', etc.)
    total_en_revision = documentos.filter(estado='pendiente').count()
    
    # 3. Total subidos (los que ya tienen archivo)
    total_subidos = documentos.exclude(archivo='').count()
    
    # 4. Porcentaje
    if total_esperado > 0:
        porcentaje_global = (total_validados / total_esperado) * 100
    else:
        porcentaje_global = 0

    # --- TABLA RESUMEN EJECUTIVO ---
    # Usamos Paragraph dentro de la tabla para mejor formato
    data_resumen = [
        [Paragraph('Indicador', style_header_tabla), Paragraph('Valor', style_header_tabla)],
        ['Total de Entidades', total_entidades],
        ['Documentos Esperados (Total)', total_esperado],
        ['Documentos Cargados', total_subidos],
        ['Documentos Validados', total_validados],
        ['Documentos con Observaciones', total_rechazados],
        ['Pendientes de Revisión', total_en_revision],
        ['% Avance Global', f"{porcentaje_global:.1f}%"]
    ]

    t_resumen = Table(data_resumen, colWidths=[300, 100])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_VINO), # Encabezado Guinda
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke), # Fila final gris claro
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), # Fila final negrita
    ]))
    
    elements.append(t_resumen)
    elements.append(Spacer(1, 25))

    # --- GRAFICOS (Matplotlib Limpio) ---
    # Preparamos datos
    labels = ['Validados', 'Con Observaciones', 'En Revisión', 'Faltantes']
    # Faltantes = Esperados - Subidos
    total_faltantes = total_esperado - total_subidos
    sizes = [total_validados, total_rechazados, total_en_revision, total_faltantes]
    colors_pie = [HEX_DORADO, '#D32F2F', '#FFA000', '#E0E0E0'] # Dorado, Rojo, Ambar, Gris claro

    # Filtrar datos con valor 0 para que no salgan en el gráfico
    final_labels = []
    final_sizes = []
    final_colors = []
    for l, s, c in zip(labels, sizes, colors_pie):
        if s > 0:
            final_labels.append(l)
            final_sizes.append(s)
            final_colors.append(c)

    if final_sizes:
        plt.figure(figsize=(6, 3)) # Ancho, Alto (pulgadas)
        # Donut Chart (más moderno que el Pie normal)
        plt.pie(final_sizes, labels=final_labels, colors=final_colors, autopct='%1.1f%%', 
                startangle=140, pctdistance=0.85, textprops={'fontsize': 8})
        
        # Círculo blanco al centro para hacer la "Dona"
        centre_circle = plt.Circle((0,0),0.70,fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
        plt.title('Estatus Documental Global', fontsize=10, color=HEX_VINO, fontweight='bold')
        plt.axis('equal')
        plt.tight_layout()

        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png', dpi=100)
        plt.close()
        img_buf.seek(0)
        elements.append(Image(img_buf, width=400, height=200))
        elements.append(Spacer(1, 20))


    # --- TABLA DETALLADA POR ENTIDAD ---
    elements.append(Paragraph("Desglose por Entidad", ParagraphStyle('h3', parent=styles['Normal'], fontSize=14, textColor=COLOR_VINO, spaceAfter=10)))

    # Encabezados
    data_entidades = [[
        Paragraph('Entidad', style_header_tabla),
        Paragraph('Cargados', style_header_tabla),
        Paragraph('Validados', style_header_tabla),
        Paragraph('Obs.', style_header_tabla),
        Paragraph('Avance', style_header_tabla)
    ]]

    for ent in entidades:
        docs_ent = documentos.filter(usuario=ent)
        cargados = docs_ent.exclude(archivo='').count()
        validados = docs_ent.filter(estado='validado').count()
        rechazados = docs_ent.filter(estado='rechazado').count()
        
        esperados_ent = docs_ent.count()
        pct = (validados / esperados_ent * 100) if esperados_ent > 0 else 0
        
        # Color del texto de avance según porcentaje
        color_avance = "black"
        if pct == 100: color_avance = "green"
        elif pct < 50: color_avance = "red"

        # IMPORTANTE: Usamos Paragraph(ent.username) para que si el nombre es largo, se ajuste y no rompa la tabla
        row = [
            Paragraph(ent.username, style_celda_left), # Alineado izquierda
            Paragraph(str(cargados), style_celda),
            Paragraph(str(validados), style_celda),
            Paragraph(str(rechazados), style_celda),
            Paragraph(f"<font color={color_avance}>{pct:.0f}%</font>", style_celda)
        ]
        data_entidades.append(row)

    # Definimos anchos fijos para forzar el ajuste de texto
    col_widths = [200, 60, 60, 60, 60] 
    
    t_entidades = Table(data_entidades, colWidths=col_widths, repeatRows=1)
    t_entidades.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_VINO),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), # Centrado vertical
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke]), # Filas acebradas
    ]))

    elements.append(t_entidades)

    # 5. Función para construir el PDF
    doc.build(elements, onFirstPage=draw_footer_header, onLaterPages=draw_footer_header)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"Reporte_Semujer_{slugify(fecha_str)}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# --- Función auxiliar para Encabezado y Pie de Página ---
def draw_footer_header(canvas, doc):
    canvas.saveState()
    
    # Colores
    VINO = colors.HexColor('#691C32')
    
    # --- ENCABEZADO ---
    # Línea superior decorativa
    canvas.setStrokeColor(VINO)
    canvas.setLineWidth(3)
    canvas.line(30, letter[1] - 40, letter[0] - 30, letter[1] - 40)
    
    # Texto pequeño arriba
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(colors.gray)
    canvas.drawString(40, letter[1] - 30, "PLATAFORMA INTEGRAL DE GESTIÓN DOCUMENTAL")

    # --- PIE DE PÁGINA ---
    canvas.setLineWidth(1)
    canvas.line(30, 50, letter[0] - 30, 50) # Línea abajo
    
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.gray)
    canvas.drawString(30, 35, "Secretaría de las Mujeres del Estado de Zacatecas")
    
    # Número de página
    page_num = canvas.getPageNumber()
    canvas.drawRightString(letter[0] - 40, 35, f"Pág. {page_num}")
    
    canvas.restoreState()


import io
import matplotlib.pyplot as plt
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.utils.text import slugify

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Importa tus modelos aquí (asegúrate que los nombres sean correctos)
from .models import AnexoRequerido, Documento, Usuario 

@user_passes_test(lambda u: u.is_superuser) # O tu test 'es_admin'
def reporte_entidad_pdf(request, entidad_id):
    
    # --- 1. Definimos la función auxiliar DENTRO para evitar NameError ---
    def draw_footer_header_entidad(canvas, doc):
        canvas.saveState()
        VINO = colors.HexColor('#691C32')
        
        # Header (Línea y Texto)
        canvas.setStrokeColor(VINO)
        canvas.setLineWidth(3)
        canvas.line(40, letter[1] - 40, letter[0] - 40, letter[1] - 40)
        
        canvas.setFont('Helvetica-Bold', 8)
        canvas.setFillColor(colors.gray)
        canvas.drawString(40, letter[1] - 30, "PLATAFORMA INTEGRAL DE GESTIÓN DOCUMENTAL")

        # Footer (Línea, Texto y Paginado)
        canvas.setLineWidth(1)
        canvas.line(40, 50, letter[0] - 40, 50)
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.gray)
        canvas.drawString(40, 35, "Secretaría de las Mujeres del Estado de Zacatecas")
        
        page_num = canvas.getPageNumber()
        canvas.drawRightString(letter[0] - 40, 35, f"Pág. {page_num}")
        
        canvas.restoreState()

    # --- 2. Inicia la lógica de la vista ---
    entidad = get_object_or_404(Usuario, id=entidad_id)
    
    # Configuración de Colores
    COLOR_VINO = colors.HexColor('#691C32') 
    COLOR_DORADO = colors.HexColor('#BC955C')
    COLOR_GRIS_TXT = colors.HexColor('#404040')
    HEX_DORADO = '#BC955C'
    HEX_VINO = '#691C32'

    buffer = io.BytesIO()
    
    # IMPORTANTE: Usamos la variable 'pdf' para el objeto del reporte
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=60, bottomMargin=50
    )

    styles = getSampleStyleSheet()
    
    # Estilos Personalizados
    style_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, textColor=COLOR_VINO, alignment=TA_CENTER, spaceAfter=5)
    style_subtitulo = ParagraphStyle('SubTitulo', parent=styles['Heading2'], fontName='Helvetica', fontSize=12, textColor=COLOR_DORADO, alignment=TA_CENTER, spaceAfter=15)
    style_header_tabla = ParagraphStyle('HeaderTabla', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white, alignment=TA_CENTER)
    style_celda = ParagraphStyle('CeldaTabla', fontName='Helvetica', fontSize=9, textColor=COLOR_GRIS_TXT, alignment=TA_CENTER, leading=11)
    
    # Estilo clave para que el nombre del anexo no se corte
    style_celda_left = ParagraphStyle('CeldaTablaLeft', parent=style_celda, alignment=TA_LEFT)

    elements = []
    
    # --- CONTENIDO ---
    elements.append(Paragraph("Secretaría de las Mujeres", style_titulo))
    elements.append(Paragraph(f"Reporte Individual: {entidad.username}", style_subtitulo))
    
    ahora = datetime.now()
    fecha_str = ahora.strftime("%d/%m/%Y")
    elements.append(Paragraph(f"<b>Fecha de emisión:</b> {fecha_str}", style_celda))
    elements.append(Spacer(1, 20))

    # --- CÁLCULOS ---
    anexos_requeridos = AnexoRequerido.objects.all()
    docs_entidad = Documento.objects.filter(usuario=entidad)
    
    total_esperados = anexos_requeridos.count()
    
    # Contamos DIRECTAMENTE de la base de datos para evitar números negativos
    # Asegúrate de que 'pendiente' es como se llama tu estatus en el modelo.
    # Si se llama 'en_revision', cambia 'pendiente' por 'en_revision'.
    en_revision = docs_entidad.filter(estado='pendiente').count() 
    validados = docs_entidad.filter(estado='validado').count()
    rechazados = docs_entidad.filter(estado='rechazado').count()
    
    # Total subidos es la suma real de lo que tienes (o usa exclude(archivo='') )
    total_subidos = docs_entidad.exclude(archivo='').count()
    
    # Faltantes
    faltantes = total_esperados - total_subidos
    if faltantes < 0: faltantes = 0
    
    avance_pct = (validados / total_esperados * 100) if total_esperados > 0 else 0

    # --- TABLA RESUMEN ---
    data_resumen = [
        [Paragraph('Indicador', style_header_tabla), Paragraph('Valor', style_header_tabla)],
        ['Documentos Requeridos', total_esperados],
        ['Documentos Cargados', total_subidos],
        ['Documentos Validados', validados],
        ['Con Observaciones', rechazados],
        ['En Proceso de Revisión', en_revision],
        ['Pendientes de Carga', faltantes],
        ['% Cumplimiento Validado', f"{avance_pct:.1f}%"]
    ]

    t_resumen = Table(data_resumen, colWidths=[250, 100])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_VINO),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(t_resumen)
    elements.append(Spacer(1, 20))

    # --- GRÁFICO (Dona) ---
    labels = ['Validados', 'Observaciones', 'En Revisión', 'Faltantes']
    sizes = [validados, rechazados, en_revision, faltantes]
    colors_pie = [HEX_DORADO, '#D32F2F', '#FFA000', '#E0E0E0']

    f_labels, f_sizes, f_colors = [], [], []
    for l, s, c in zip(labels, sizes, colors_pie):
        if s > 0:
            f_labels.append(l)
            f_sizes.append(s)
            f_colors.append(c)

    if f_sizes:
        plt.figure(figsize=(6, 3))
        plt.pie(f_sizes, labels=f_labels, colors=f_colors, autopct='%1.1f%%', 
                startangle=140, pctdistance=0.85, textprops={'fontsize': 8})
        plt.gca().add_artist(plt.Circle((0,0),0.70,fc='white'))
        plt.title('Estado Actual de la Documentación', fontsize=10, color=HEX_VINO, fontweight='bold')
        plt.axis('equal')
        plt.tight_layout()

        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png', dpi=100)
        plt.close()
        img_buf.seek(0)
        elements.append(Image(img_buf, width=400, height=200))
        elements.append(Spacer(1, 20))

    # --- TABLA DETALLE ---
    elements.append(Paragraph("Desglose por Anexo", ParagraphStyle('h3', parent=styles['Normal'], fontSize=14, textColor=COLOR_VINO, spaceAfter=10)))

    data_detalle = [[
        Paragraph('#', style_header_tabla),
        Paragraph('Nombre del Anexo', style_header_tabla),
        Paragraph('Estatus', style_header_tabla)
    ]]

    for idx, anexo in enumerate(anexos_requeridos, start=1):
        # Usamos 'doc_obj' para no confundir con variables externas
        doc_obj = docs_entidad.filter(anexo=anexo).first()
        estado_texto = "Pendiente de Carga"
        color_texto = "grey"
        
        if doc_obj:
            if doc_obj.archivo:
                if doc_obj.estado == 'validado':
                    estado_texto = "VALIDADO"
                    color_texto = "green"
                elif doc_obj.estado == 'rechazado':
                    estado_texto = "CON OBSERVACIONES"
                    color_texto = "red"
                else:
                    estado_texto = "En Revisión"
                    color_texto = "#FF8F00"
            else:
                estado_texto = "Sin Archivo"
                color_texto = "grey"

        row = [
            str(idx),
            # Paragraph permite que el texto largo baje de línea
            Paragraph(anexo.nombre, style_celda_left), 
            Paragraph(f"<font color={color_texto}><b>{estado_texto}</b></font>", style_celda)
        ]
        data_detalle.append(row)

    col_widths = [30, 280, 130]
    t_detalle = Table(data_detalle, colWidths=col_widths, repeatRows=1)
    t_detalle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_VINO),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
    ]))

    elements.append(t_detalle)

    # --- GENERAR PDF ---
    # Usamos 'pdf.build' y pasamos la función interna draw_footer_header_entidad
    pdf.build(elements, onFirstPage=draw_footer_header_entidad, onLaterPages=draw_footer_header_entidad)

    buffer.seek(0)
    filename = f"Reporte_{entidad.username}_{slugify(fecha_str)}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
    


# --- Vista principal de administración de anexos
@user_passes_test(es_admin)
def admin_anexos(request):
    anexos = AnexoRequerido.objects.all().order_by('nombre')

    if request.method == 'POST':
        form = AnexoForm(request.POST)
        if form.is_valid():
            form.save()
            sincronizar_documentos_por_usuario()  # 🔥 sincronización total
            messages.success(request, "El documento requerido fue agregado correctamente.")
            return redirect('admin_anexos')  # evita reenvíos dobles
        else:
            messages.error(request, "Ocurrió un error al guardar el documento.")
    else:
        form = AnexoForm()

    return render(request, 'core/admin_anexos.html', {
        'anexos': anexos,
        'form': form,
    })


# --- Eliminar un anexo
@user_passes_test(es_admin)
def eliminar_anexo(request, anexo_id):
    try:
        anexo = AnexoRequerido.objects.get(id=anexo_id)
        anexo.delete()
        messages.success(request, "El anexo fue eliminado correctamente.")
    except AnexoRequerido.DoesNotExist:
        messages.error(request, "El anexo no existe.")
    return redirect('admin_anexos')

# --- Eliminar todos los anexos
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
            messages.success(request, f"Se han limpiado {archivos_limpiados} archivos subidos correctamente.")
        else:
            messages.info(request, "No había archivos para limpiar.")
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
            messages.success(request, f"Se han respaldado {respaldados} archivos correctamente.")
        else:
            messages.info(request, "No había archivos nuevos para respaldar.")
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
    # CORRECCIÓN: Usamos 'entidad' y 'anexo_requerido' según tu modelo real
    respaldos = AnexoHistorico.objects.select_related('entidad', 'anexo_requerido').all().order_by('entidad__username', '-fecha_subida')

    # Sacar años únicos
    fechas = AnexoHistorico.objects.values_list('fecha_subida', flat=True)
    years = sorted(
        {str(f.year) for f in fechas if f is not None},
        reverse=True
    )

    # Filtro por año
    raw_year = request.GET.get('year', '')
    year_selected = ''

    if raw_year and raw_year.isdigit():
        respaldos = respaldos.filter(fecha_subida__year=int(raw_year))
        year_selected = raw_year

    return render(
        request,
        'core/respaldo_anexos.html',
        {
            'respaldos': respaldos,
            'years': years,
            'year_selected': year_selected,
        }
    )

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

from django.utils.text import slugify  # Importante para limpiar nombres de carpetas
# Asegúrate de tener los otros imports: io, zipfile, HttpResponse, etc.

@user_passes_test(es_admin)
def descargar_respaldo_zip(request):
    # 1. OPTIMIZACIÓN: Usamos select_related para que no haga mil consultas
    respaldos = AnexoHistorico.objects.select_related('entidad', 'anexo_requerido').all()

    if not respaldos.exists():
        messages.info(request, "ℹ️ No hay archivos respaldados para descargar.")
        return redirect('vista_respaldo_anexos')

    buffer = BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for r in respaldos:
            # Verificamos que el archivo exista físicamente
            if r.archivo and default_storage.exists(r.archivo.name):
                
                # 2. LIMPIEZA DE NOMBRES (Slugify)
                # Esto evita errores si la entidad tiene espacios o acentos (ej: "Secretaría A" -> "secretaria-a")
                nombre_carpeta = slugify(r.entidad.username)
                nombre_anexo = slugify(r.anexo_requerido.nombre)
                fecha_str = r.fecha_subida.strftime('%Y%m%d_%H%M')
                
                # Obtener extensión original (pdf, docx, etc)
                ext = r.archivo.name.split('.')[-1]

                # 3. ESTRUCTURA DE CARPETAS
                # Formato: NombreEntidad / NombreAnexo_Fecha.pdf
                # La barra "/" le indica al ZIP que cree una carpeta
                ruta_en_zip = f"{nombre_carpeta}/{nombre_anexo}_{fecha_str}.{ext}"

                try:
                    with r.archivo.open('rb') as f:
                        zip_file.writestr(ruta_en_zip, f.read())
                except Exception as e:
                    # Si falla un archivo, continuamos con los demás pero lo imprimimos en consola
                    print(f"Error al comprimir archivo {r.id}: {e}")

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/zip')
    # Le ponemos fecha al nombre del ZIP global
    fecha_hoy = datetime.now().strftime('%d-%m-%Y')
    response['Content-Disposition'] = f'attachment; filename=Respaldo_Documental_{fecha_hoy}.zip'
    return response

# 🔑 Función para generar contraseñas aleatorias
def generar_contrasena(longitud=10):
    """Genera una contraseña aleatoria provisional"""
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(longitud))

# 📌 Recuperación de contraseña por correo
def olvido_contrasena(request):
    if request.method == "POST":
        correo = request.POST.get("correo")  # 👈 en tu form el input debe llamarse 'correo'

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
                from_email="asemujeres@gmail.com",  # ⚠️ cámbialo por el correo configurado en settings.py
                recipient_list=[usuario.correo],
                fail_silently=False,
            )

            messages.success(request, "Se envió una nueva contraseña a tu correo.")
            return render(request, "core/olvido_contrasena.html")

        except Usuario.DoesNotExist:
            messages.error(request, " El correo no está registrado.")

    return render(request, "core/olvido_contrasena.html")

# 📌 Cambio de contraseña dentro del sistema
@login_required
def cambiar_contrasena(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # 🔑 Mantener sesión activa
            messages.success(request, "✅ Tu contraseña se cambió correctamente.")
            return render(request, "core/cambiar_contrasena.html", {"form": PasswordChangeForm(user=request.user)})
        else:
            messages.error(request, "❌ Corrige los errores del formulario.")
    else:
        form = PasswordChangeForm(user=request.user)

    # Traducción de etiquetas al español
    form.fields['old_password'].label = "Contraseña actual"
    form.fields['new_password1'].label = "Nueva contraseña"
    form.fields['new_password2'].label = "Confirmar nueva contraseña"

    return render(request, "core/cambiar_contrasena.html", {"form": form})
