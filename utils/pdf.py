"""
Utilidades para la generación de PDFs
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import locale

def generate_invoice_pdf(output_path, numero_factura, pedido, detalles, subtotal, iva, total, fecha_emision):
    """
    Genera un PDF de factura
    """
    # Configurar locale para formato de moneda
    locale.setlocale(locale.LC_ALL, 'es_CO.UTF-8')
    
    # Crear el documento
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    styles.add(ParagraphStyle(
        name='Center',
        parent=styles['Heading1'],
        alignment=1,
    ))
    
    # Título
    elements.append(Paragraph('FACTURA DE VENTA', styles['Center']))
    elements.append(Spacer(1, 12))
    
    # Información de la factura
    elements.append(Paragraph(f'Factura No: {numero_factura}', styles['Normal']))
    elements.append(Paragraph(f'Fecha: {fecha_emision.strftime("%d/%m/%Y")}', styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Información del cliente
    elements.append(Paragraph('DATOS DEL CLIENTE', styles['Heading2']))
    elements.append(Paragraph(f'Nombre: {pedido["nombre"]}', styles['Normal']))
    elements.append(Paragraph(f'Documento: {pedido["documento"]}', styles['Normal']))
    elements.append(Paragraph(f'Dirección: {pedido["direccion"]}', styles['Normal']))
    elements.append(Paragraph(f'Teléfono: {pedido["telefono"]}', styles['Normal']))
    elements.append(Paragraph(f'Email: {pedido["email"]}', styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Tabla de productos
    data = [['Producto', 'Cantidad', 'Precio Unit.', 'Total']]
    for item in detalles:
        data.append([
            item['nombre'],
            str(item['cantidad']),
            locale.currency(item['precio'], grouping=True),
            locale.currency(item['cantidad'] * item['precio'], grouping=True)
        ])
    
    # Agregar totales
    data.extend([
        ['', '', 'Subtotal', locale.currency(subtotal, grouping=True)],
        ['', '', 'IVA (19%)', locale.currency(iva, grouping=True)],
        ['', '', 'Total', locale.currency(total, grouping=True)]
    ])
    
    # Estilo de la tabla
    table_style = TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -4), 1, colors.black),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (2, -3), (-1, -1), 'Helvetica-Bold'),
    ])
    
    table = Table(data)
    table.setStyle(table_style)
    elements.append(table)
    
    # Construir el PDF
    doc.build(elements)