from flask import Blueprint, request, jsonify, render_template, send_file
import pymysql
from app.config.db import get_connection
from app.utils.auth import token_required
import datetime
import uuid
import os
from fpdf import FPDF
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask_jwt_extended import jwt_required, get_jwt_identity

load_dotenv()

facturas_bp = Blueprint('facturas', __name__)

# Estados de factura
ESTADO_PENDIENTE = 'pendiente'
ESTADO_PAGADA = 'pagada'
ESTADO_CANCELADA = 'cancelada'
ESTADO_ANULADA = 'anulada'

@facturas_bp.route('/', methods=['GET'])
@jwt_required()
def listar_facturas():
    """Obtiene la lista de facturas del usuario autenticado"""
    try:
        usuario_id = get_jwt_identity()
        
        # Parámetros opcionales de filtrado
        estado = request.args.get('estado')
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Construir la consulta base
        query = """
        SELECT f.id, f.referencia, f.cliente_id, c.nombre as cliente_nombre, 
               f.total, f.estado, f.fecha_creacion, f.fecha_pago
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.id
        WHERE f.usuario_id = %s
        """
        params = [usuario_id]
        
        # Agregar filtros si existen
        if estado:
            query += " AND f.estado = %s"
            params.append(estado)
            
        if fecha_inicio:
            query += " AND f.fecha_creacion >= %s"
            params.append(fecha_inicio)
            
        if fecha_fin:
            query += " AND f.fecha_creacion <= %s"
            params.append(fecha_fin)
            
        query += " ORDER BY f.fecha_creacion DESC"
        
        cursor.execute(query, params)
        facturas = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Formatear las fechas para JSON
        for factura in facturas:
            if factura['fecha_creacion']:
                factura['fecha_creacion'] = factura['fecha_creacion'].isoformat()
            if factura['fecha_pago']:
                factura['fecha_pago'] = factura['fecha_pago'].isoformat()
        
        return jsonify({
            'exito': True,
            'facturas': facturas
        })
        
    except Exception as e:
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@facturas_bp.route('/<int:factura_id>', methods=['GET'])
@jwt_required()
def detalle_factura(factura_id):
    """Obtiene el detalle de una factura específica"""
    try:
        usuario_id = get_jwt_identity()
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Obtener datos de la factura
        cursor.execute("""
        SELECT f.*, c.nombre as cliente_nombre, c.email as cliente_email,
               c.direccion as cliente_direccion, c.telefono as cliente_telefono
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.id
        WHERE f.id = %s AND f.usuario_id = %s
        """, (factura_id, usuario_id))
        
        factura = cursor.fetchone()
        if not factura:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'Factura no encontrada'}), 404
        
        # Obtener los items de la factura
        cursor.execute("""
        SELECT i.*, p.nombre as producto_nombre, p.codigo as producto_codigo
        FROM items_factura i
        JOIN productos p ON i.producto_id = p.id
        WHERE i.factura_id = %s
        """, (factura_id,))
        
        items = cursor.fetchall()
        
        # Obtener el historial de pagos si existe
        cursor.execute("""
        SELECT * FROM pagos WHERE factura_id = %s
        """, (factura_id,))
        
        pagos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Formatear las fechas para JSON
        if factura['fecha_creacion']:
            factura['fecha_creacion'] = factura['fecha_creacion'].isoformat()
        if factura['fecha_pago']:
            factura['fecha_pago'] = factura['fecha_pago'].isoformat()
        if factura['fecha_vencimiento']:
            factura['fecha_vencimiento'] = factura['fecha_vencimiento'].isoformat()
            
        for pago in pagos:
            if pago['fecha_pago']:
                pago['fecha_pago'] = pago['fecha_pago'].isoformat()
        
        # Construir respuesta
        respuesta = {
            'exito': True,
            'factura': factura,
            'items': items,
            'pagos': pagos
        }
        
        return jsonify(respuesta)
        
    except Exception as e:
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@facturas_bp.route('/', methods=['POST'])
@jwt_required()
def crear_factura():
    """Crea una nueva factura con sus items"""
    try:
        usuario_id = get_jwt_identity()
        datos = request.json
        
        # Validar datos requeridos
        if not 'cliente_id' in datos:
            return jsonify({'exito': False, 'mensaje': 'ID de cliente es requerido'}), 400
            
        if not 'items' in datos or not datos['items']:
            return jsonify({'exito': False, 'mensaje': 'La factura debe tener al menos un item'}), 400
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que el cliente existe
        cursor.execute("SELECT id FROM clientes WHERE id = %s AND usuario_id = %s", 
                      (datos['cliente_id'], usuario_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'Cliente no encontrado'}), 404
        
        # Generar referencia única para la factura
        referencia = 'FACT-' + str(uuid.uuid4())[:8]
        
        # Calcular fecha de vencimiento (30 días por defecto)
        dias_vencimiento = datos.get('dias_vencimiento', 30)
        fecha_actual = datetime.datetime.now()
        fecha_vencimiento = fecha_actual + datetime.timedelta(days=dias_vencimiento)
        
        # Iniciar transacción
        conn.begin()
        
        try:
            # Crear la factura
            cursor.execute("""
            INSERT INTO facturas (
                usuario_id, cliente_id, referencia, subtotal, impuestos, total,
                estado, metodo_pago, notas, fecha_creacion, fecha_vencimiento
            ) VALUES (%s, %s, %s, 0, 0, 0, 'pendiente', %s, %s, %s, %s)
            """, (
                usuario_id,
                datos['cliente_id'],
                referencia,
                datos.get('metodo_pago', None),
                datos.get('notas', None),
                fecha_actual,
                fecha_vencimiento
            ))
            
            factura_id = cursor.lastrowid
            
            # Variables para calcular totales
            subtotal = 0
            impuestos = 0
            
            # Insertar los items
            for item in datos['items']:
                # Validar datos del item
                if not 'producto_id' in item or not 'cantidad' in item or not 'precio' in item:
                    raise ValueError('Datos incorrectos en un item de la factura')
                
                # Verificar que el producto existe
                cursor.execute("SELECT id, precio, impuesto FROM productos WHERE id = %s", (item['producto_id'],))
                producto = cursor.fetchone()
                
                if not producto:
                    raise ValueError(f"Producto con ID {item['producto_id']} no encontrado")
                
                # Usar el precio proporcionado o el precio del producto
                precio = item.get('precio', producto['precio'])
                
                # Calcular impuesto
                tasa_impuesto = item.get('impuesto', producto['impuesto'])
                importe = precio * item['cantidad']
                impuesto_item = importe * (tasa_impuesto / 100)
                
                # Actualizar totales
                subtotal += importe
                impuestos += impuesto_item
                
                # Insertar el item
                cursor.execute("""
                INSERT INTO items_factura (
                    factura_id, producto_id, cantidad, precio, impuesto, 
                    importe, impuesto_importe
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    factura_id,
                    item['producto_id'],
                    item['cantidad'],
                    precio,
                    tasa_impuesto,
                    importe,
                    impuesto_item
                ))
            
            # Actualizar totales en la factura
            total = subtotal + impuestos
            cursor.execute("""
            UPDATE facturas 
            SET subtotal = %s, impuestos = %s, total = %s
            WHERE id = %s
            """, (subtotal, impuestos, total, factura_id))
            
            # Confirmar transacción
            conn.commit()
            
            # Obtener la factura creada
            cursor.execute("""
            SELECT * FROM facturas WHERE id = %s
            """, (factura_id,))
            
            factura = cursor.fetchone()
            
            # Formatear fechas
            if factura['fecha_creacion']:
                factura['fecha_creacion'] = factura['fecha_creacion'].isoformat()
            if factura['fecha_vencimiento']:
                factura['fecha_vencimiento'] = factura['fecha_vencimiento'].isoformat()
            
            cursor.close()
            conn.close()
            
            return jsonify({
                'exito': True,
                'mensaje': 'Factura creada correctamente',
                'factura': factura
            })
            
        except Exception as e:
            conn.rollback()
            raise e
            
    except Exception as e:
        if 'conn' in locals() and conn:
            if 'cursor' in locals() and cursor:
                cursor.close()
            conn.close()
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@facturas_bp.route('/<int:factura_id>', methods=['DELETE'])
@jwt_required()
def anular_factura(factura_id):
    """Anula una factura existente"""
    try:
        usuario_id = get_jwt_identity()
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que la factura existe y pertenece al usuario
        cursor.execute("""
        SELECT id, estado 
        FROM facturas 
        WHERE id = %s AND usuario_id = %s
        """, (factura_id, usuario_id))
        
        factura = cursor.fetchone()
        if not factura:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'Factura no encontrada'}), 404
        
        # Verificar que la factura no esté pagada
        if factura['estado'] == 'pagada':
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'No se puede anular una factura pagada'}), 400
        
        # Actualizar estado de la factura
        cursor.execute("""
        UPDATE facturas 
        SET estado = 'anulada', fecha_actualizacion = %s
        WHERE id = %s
        """, (datetime.datetime.now(), factura_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'exito': True,
            'mensaje': 'Factura anulada correctamente'
        })
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
            if 'cursor' in locals() and cursor:
                cursor.close()
            conn.close()
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@facturas_bp.route('/pdf/<int:factura_id>', methods=['GET'])
@jwt_required()
def generar_pdf(factura_id):
    """Genera un PDF de la factura"""
    try:
        usuario_id = get_jwt_identity()
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que la factura existe y pertenece al usuario
        cursor.execute("""
        SELECT f.*, c.nombre as cliente_nombre, c.email as cliente_email,
               c.direccion as cliente_direccion, c.telefono as cliente_telefono,
               u.nombre as usuario_nombre, u.empresa as empresa_nombre,
               u.direccion as empresa_direccion, u.telefono as empresa_telefono
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.id
        JOIN usuarios u ON f.usuario_id = u.id
        WHERE f.id = %s AND f.usuario_id = %s
        """, (factura_id, usuario_id))
        
        factura = cursor.fetchone()
        if not factura:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'Factura no encontrada'}), 404
        
        # Obtener los items de la factura
        cursor.execute("""
        SELECT i.*, p.nombre as producto_nombre, p.codigo as producto_codigo
        FROM items_factura i
        JOIN productos p ON i.producto_id = p.id
        WHERE i.factura_id = %s
        """, (factura_id,))
        
        items = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Generar HTML para renderizar el PDF
        return render_template(
            'facturas/factura_pdf.html',
            factura=factura,
            items=items
        )
        
    except Exception as e:
        if 'conn' in locals() and conn:
            if 'cursor' in locals() and cursor:
                cursor.close()
            conn.close()
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@facturas_bp.route('/generar', methods=['POST'])
@token_required
def generar_factura(usuario_actual):
    """Genera una nueva factura a partir de un pedido"""
    try:
        data = request.get_json()
        pedido_id = data.get('pedido_id')
        
        if not pedido_id:
            return jsonify({"error": "Se requiere ID del pedido"}), 400
        
        connection = get_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Verificar si el pedido existe y está aprobado
        cursor.execute("""
            SELECT p.*, c.nombre, c.apellido, c.documento, c.email, c.direccion, c.telefono
            FROM pedidos p
            JOIN clientes c ON p.cliente_id = c.id
            WHERE p.id = %s AND p.estado = 'APROBADO'
        """, (pedido_id,))
        
        pedido = cursor.fetchone()
        
        if not pedido:
            return jsonify({"error": "Pedido no encontrado o no está aprobado"}), 404
        
        # Verificar si ya existe una factura para este pedido
        cursor.execute("SELECT id FROM facturas WHERE pedido_id = %s", (pedido_id,))
        factura_existente = cursor.fetchone()
        
        if factura_existente:
            return jsonify({"error": "Ya existe una factura para este pedido"}), 400
        
        # Obtener detalles del pedido
        cursor.execute("""
            SELECT d.*, p.nombre, p.precio
            FROM detalle_pedidos d
            JOIN productos p ON d.producto_id = p.id
            WHERE d.pedido_id = %s
        """, (pedido_id,))
        
        detalles = cursor.fetchall()
        
        if not detalles:
            return jsonify({"error": "No hay detalles para este pedido"}), 400
        
        # Generar número de factura único
        fecha_actual = datetime.now()
        numero_factura = f"FV-{fecha_actual.strftime('%Y%m')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Calcular valores
        subtotal = sum(item['cantidad'] * item['precio'] for item in detalles)
        iva = subtotal * 0.19  # 19% IVA
        total = subtotal + iva
        
        # Fecha de vencimiento: 30 días después
        fecha_vencimiento = fecha_actual + timedelta(days=30)
        
        # Insertar factura en la base de datos
        cursor.execute("""
            INSERT INTO facturas (
                pedido_id, numero_factura, fecha_emision, fecha_vencimiento,
                subtotal, iva, total, estado
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDIENTE')
        """, (
            pedido_id, numero_factura, fecha_actual, fecha_vencimiento,
            subtotal, iva, total
        ))
        
        connection.commit()
        factura_id = cursor.lastrowid
        
        # Generar PDF
        ruta_pdf = generar_pdf_factura(factura_id, pedido, detalles, 
                                      numero_factura, fecha_actual, 
                                      fecha_vencimiento, subtotal, iva, total)
        
        # Actualizar ruta del PDF
        cursor.execute("UPDATE facturas SET ruta_pdf = %s WHERE id = %s", 
                       (ruta_pdf, factura_id))
        connection.commit()
        
        return jsonify({
            "mensaje": "Factura generada correctamente",
            "factura_id": factura_id,
            "numero_factura": numero_factura,
            "ruta_pdf": ruta_pdf
        }), 201
        
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@facturas_bp.route('/listar', methods=['GET'])
@token_required
def listar_facturas(usuario_actual):
    """Lista todas las facturas o filtra por cliente, pedido o estado"""
    try:
        connection = get_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Parámetros de filtrado opcionales
        pedido_id = request.args.get('pedido_id')
        cliente_id = request.args.get('cliente_id')
        estado = request.args.get('estado')
        
        # Construir la consulta base
        query = """
            SELECT f.*, p.cliente_id, c.nombre, c.apellido, c.documento
            FROM facturas f
            JOIN pedidos p ON f.pedido_id = p.id
            JOIN clientes c ON p.cliente_id = c.id
            WHERE 1=1
        """
        params = []
        
        # Añadir filtros si existen
        if pedido_id:
            query += " AND f.pedido_id = %s"
            params.append(pedido_id)
        
        if cliente_id:
            query += " AND p.cliente_id = %s"
            params.append(cliente_id)
        
        if estado:
            query += " AND f.estado = %s"
            params.append(estado)
        
        # Ordenar por fecha de emisión descendente
        query += " ORDER BY f.fecha_emision DESC"
        
        cursor.execute(query, params)
        facturas = cursor.fetchall()
        
        # Formatear fechas para JSON
        for factura in facturas:
            factura['fecha_emision'] = factura['fecha_emision'].isoformat()
            factura['fecha_vencimiento'] = factura['fecha_vencimiento'].isoformat()
        
        return jsonify({"facturas": facturas}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@facturas_bp.route('/<int:factura_id>', methods=['GET'])
@token_required
def obtener_factura(usuario_actual, factura_id):
    """Obtiene los detalles de una factura específica"""
    try:
        connection = get_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Obtener detalles de la factura
        cursor.execute("""
            SELECT f.*, p.cliente_id, p.numero_pedido, p.fecha_pedido,
                   c.nombre, c.apellido, c.documento, c.email, c.direccion, c.telefono
            FROM facturas f
            JOIN pedidos p ON f.pedido_id = p.id
            JOIN clientes c ON p.cliente_id = c.id
            WHERE f.id = %s
        """, (factura_id,))
        
        factura = cursor.fetchone()
        
        if not factura:
            return jsonify({"error": "Factura no encontrada"}), 404
        
        # Obtener detalles de los productos
        cursor.execute("""
            SELECT dp.*, pr.nombre, pr.precio, pr.codigo
            FROM detalle_pedidos dp
            JOIN productos pr ON dp.producto_id = pr.id
            WHERE dp.pedido_id = %s
        """, (factura['pedido_id'],))
        
        detalles = cursor.fetchall()
        
        # Formatear fechas para JSON
        factura['fecha_emision'] = factura['fecha_emision'].isoformat()
        factura['fecha_vencimiento'] = factura['fecha_vencimiento'].isoformat()
        factura['fecha_pedido'] = factura['fecha_pedido'].isoformat()
        
        # Añadir detalles a la respuesta
        factura['detalles'] = detalles
        
        return jsonify({"factura": factura}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@facturas_bp.route('/pdf/<int:factura_id>', methods=['GET'])
@token_required
def descargar_pdf(usuario_actual, factura_id):
    """Descarga el PDF de una factura"""
    try:
        connection = get_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Obtener ruta del PDF
        cursor.execute("SELECT ruta_pdf FROM facturas WHERE id = %s", (factura_id,))
        factura = cursor.fetchone()
        
        if not factura or not factura['ruta_pdf']:
            return jsonify({"error": "PDF de factura no encontrado"}), 404
        
        # Verificar que el archivo existe
        ruta_completa = os.path.join(os.getcwd(), factura['ruta_pdf'].lstrip('/'))
        if not os.path.exists(ruta_completa):
            return jsonify({"error": "El archivo PDF no existe en el servidor"}), 404
        
        return send_file(ruta_completa, as_attachment=True)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@facturas_bp.route('/actualizar/<int:factura_id>', methods=['PATCH'])
@token_required
def actualizar_factura(usuario_actual, factura_id):
    """Actualiza el estado de una factura"""
    try:
        data = request.get_json()
        nuevo_estado = data.get('estado')
        observaciones = data.get('observaciones', '')
        
        if not nuevo_estado:
            return jsonify({"error": "Se requiere el estado de la factura"}), 400
            
        if nuevo_estado not in ['PENDIENTE', 'PAGADA', 'ANULADA']:
            return jsonify({"error": "Estado no válido"}), 400
        
        connection = get_connection()
        cursor = connection.cursor()
        
        # Actualizar estado de la factura
        cursor.execute("""
            UPDATE facturas 
            SET estado = %s, observaciones = %s
            WHERE id = %s
        """, (nuevo_estado, observaciones, factura_id))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Factura no encontrada"}), 404
            
        connection.commit()
        
        return jsonify({
            "mensaje": "Estado de factura actualizado correctamente",
            "factura_id": factura_id,
            "nuevo_estado": nuevo_estado
        }), 200
        
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def generar_pdf_factura(factura_id, pedido, detalles, numero_factura, 
                        fecha_emision, fecha_vencimiento, subtotal, iva, total):
    """Genera el PDF de la factura y devuelve la ruta"""
    # Crear directorio de facturas si no existe
    directorio = os.path.join(os.getcwd(), 'static', 'facturas')
    if not os.path.exists(directorio):
        os.makedirs(directorio)
    
    # Nombre del archivo
    nombre_archivo = f"factura_{factura_id}.pdf"
    ruta_archivo = os.path.join(directorio, nombre_archivo)
    
    # Crear PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Título y encabezado
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(190, 10, 'FACTURA DE VENTA', 0, 1, 'C')
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(190, 10, f"No. {numero_factura}", 0, 1, 'C')
    
    # Información de la empresa
    pdf.set_font('Arial', '', 10)
    pdf.cell(190, 10, 'FERRETERÍA ACME S.A.S', 0, 1)
    pdf.cell(190, 5, 'NIT: 901.345.678-9', 0, 1)
    pdf.cell(190, 5, 'Dirección: Calle Principal #123, Bogotá, Colombia', 0, 1)
    pdf.cell(190, 5, 'Teléfono: (601) 123-4567', 0, 1)
    pdf.cell(190, 5, 'Email: facturacion@ferreteria-acme.com', 0, 1)
    
    # Separador
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # Información del cliente
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(190, 7, 'DATOS DEL CLIENTE', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(50, 5, 'Nombre:', 0, 0)
    pdf.cell(140, 5, f"{pedido['nombre']} {pedido['apellido']}", 0, 1)
    pdf.cell(50, 5, 'Documento:', 0, 0)
    pdf.cell(140, 5, pedido['documento'], 0, 1)
    pdf.cell(50, 5, 'Dirección:', 0, 0)
    pdf.cell(140, 5, pedido['direccion'], 0, 1)
    pdf.cell(50, 5, 'Teléfono:', 0, 0)
    pdf.cell(140, 5, pedido['telefono'], 0, 1)
    pdf.cell(50, 5, 'Email:', 0, 0)
    pdf.cell(140, 5, pedido['email'], 0, 1)
    
    # Información de la factura
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(190, 7, 'DATOS DE LA FACTURA', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(50, 5, 'Fecha de emisión:', 0, 0)
    pdf.cell(140, 5, fecha_emision.strftime('%d/%m/%Y'), 0, 1)
    pdf.cell(50, 5, 'Fecha de vencimiento:', 0, 0)
    pdf.cell(140, 5, fecha_vencimiento.strftime('%d/%m/%Y'), 0, 1)
    pdf.cell(50, 5, 'No. Pedido:', 0, 0)
    pdf.cell(140, 5, str(pedido['numero_pedido']), 0, 1)
    
    # Separador
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # Tabla de productos
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(15, 7, 'Cant.', 1, 0, 'C')
    pdf.cell(95, 7, 'Descripción', 1, 0, 'C')
    pdf.cell(30, 7, 'Precio Unit.', 1, 0, 'C')
    pdf.cell(30, 7, 'Subtotal', 1, 1, 'C')
    
    pdf.set_font('Arial', '', 9)
    for item in detalles:
        subtotal_item = item['cantidad'] * item['precio']
        pdf.cell(15, 6, str(item['cantidad']), 1, 0, 'C')
        pdf.cell(95, 6, item['nombre'], 1, 0, 'L')
        pdf.cell(30, 6, f"${item['precio']:,.2f}", 1, 0, 'R')
        pdf.cell(30, 6, f"${subtotal_item:,.2f}", 1, 1, 'R')
    
    # Totales
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(140, 6, 'Subtotal:', 0, 0, 'R')
    pdf.cell(40, 6, f"${subtotal:,.2f}", 0, 1, 'R')
    pdf.cell(140, 6, 'IVA (19%):', 0, 0, 'R')
    pdf.cell(40, 6, f"${iva:,.2f}", 0, 1, 'R')
    pdf.cell(140, 6, 'TOTAL:', 0, 0, 'R')
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 6, f"${total:,.2f}", 0, 1, 'R')
    
    # Pie de página
    pdf.ln(10)
    pdf.set_font('Arial', '', 9)
    pdf.cell(190, 5, 'Esta factura es un título valor según el Código de Comercio', 0, 1, 'C')
    pdf.cell(190, 5, 'Gracias por su compra', 0, 1, 'C')
    
    # Guardar PDF
    pdf.output(ruta_archivo)
    
    # Devolver ruta relativa para guardar en BD
    return f"/static/facturas/{nombre_archivo}" 