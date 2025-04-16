from flask import Blueprint, jsonify, request, current_app
import pymysql
import os
import datetime
import uuid
from utils.db import get_db_connection
from utils.auth import token_required
from utils.pdf import generate_invoice_pdf

facturas_bp = Blueprint('facturas', __name__)

@facturas_bp.route('/generar', methods=['POST'])
@token_required
def generar_factura(usuario_actual):
    try:
        data = request.get_json()
        pedido_id = data.get('pedido_id')
        
        if not pedido_id:
            return jsonify({'error': 'ID de pedido es requerido'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verificar si el pedido existe y pertenece al usuario
        cursor.execute('''
            SELECT p.*, c.nombre, c.direccion, c.telefono, c.email, c.documento 
            FROM pedidos p 
            JOIN clientes c ON p.cliente_id = c.id
            WHERE p.id = %s AND c.id = %s
        ''', (pedido_id, usuario_actual['id']))
        pedido = cursor.fetchone()
        
        if not pedido:
            return jsonify({'error': 'Pedido no encontrado o no autorizado'}), 404
        
        # Verificar si ya existe una factura para este pedido
        cursor.execute('SELECT * FROM facturas WHERE pedido_id = %s', (pedido_id,))
        factura_existente = cursor.fetchone()
        
        if factura_existente:
            return jsonify({'mensaje': 'Ya existe una factura para este pedido', 'factura': factura_existente}), 200
        
        # Obtener detalles del pedido
        cursor.execute('''
            SELECT pd.*, p.nombre, p.precio 
            FROM pedido_detalles pd
            JOIN productos p ON pd.producto_id = p.id
            WHERE pd.pedido_id = %s
        ''', (pedido_id,))
        detalles = cursor.fetchall()
        
        if not detalles:
            return jsonify({'error': 'El pedido no tiene productos'}), 400
        
        # Generar número de factura único
        fecha_actual = datetime.datetime.now()
        numero_factura = f"FAC-{fecha_actual.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Calcular totales
        subtotal = sum(item['cantidad'] * item['precio'] for item in detalles)
        iva = subtotal * 0.19  # 19% IVA en Colombia
        total = subtotal + iva
        
        # Generar PDF de factura
        pdf_filename = f"factura_{numero_factura.replace('-', '_')}.pdf"
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'facturas', pdf_filename)
        
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        
        # Generar PDF
        generate_invoice_pdf(
            pdf_path, 
            numero_factura, 
            pedido, 
            detalles, 
            subtotal, 
            iva, 
            total,
            fecha_actual
        )
        
        # URL para descargar la factura
        url_descarga = f"/uploads/facturas/{pdf_filename}"
        
        # Insertar factura en la base de datos
        cursor.execute('''
            INSERT INTO facturas 
            (numero_factura, pedido_id, fecha_emision, fecha_vencimiento, subtotal, iva, total, estado, formato, url_descarga)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            numero_factura, 
            pedido_id, 
            fecha_actual, 
            fecha_actual + datetime.timedelta(days=30),  # 30 días para pagar
            subtotal,
            iva,
            total,
            'PENDIENTE',
            'PDF',
            url_descarga
        ))
        
        factura_id = cursor.lastrowid
        conn.commit()
        
        # Obtener la factura recién creada
        cursor.execute('SELECT * FROM facturas WHERE id = %s', (factura_id,))
        nueva_factura = cursor.fetchone()
        
        return jsonify({
            'mensaje': 'Factura generada exitosamente',
            'factura': nueva_factura
        }), 201
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Error al generar factura: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@facturas_bp.route('/listar', methods=['GET'])
@token_required
def listar_facturas(usuario_actual):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Obtener facturas del usuario
        cursor.execute('''
            SELECT f.*, p.numero_pedido
            FROM facturas f
            JOIN pedidos p ON f.pedido_id = p.id
            JOIN clientes c ON p.cliente_id = c.id
            WHERE c.id = %s
            ORDER BY f.fecha_emision DESC
        ''', (usuario_actual['id'],))
        
        facturas = cursor.fetchall()
        
        return jsonify({'facturas': facturas}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error al obtener facturas: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@facturas_bp.route('/<int:factura_id>', methods=['GET'])
@token_required
def obtener_factura(usuario_actual, factura_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verificar si la factura existe y pertenece al usuario
        cursor.execute('''
            SELECT f.*, p.numero_pedido
            FROM facturas f
            JOIN pedidos p ON f.pedido_id = p.id
            JOIN clientes c ON p.cliente_id = c.id
            WHERE f.id = %s AND c.id = %s
        ''', (factura_id, usuario_actual['id']))
        
        factura = cursor.fetchone()
        
        if not factura:
            return jsonify({'error': 'Factura no encontrada o no autorizada'}), 404
        
        # Obtener detalles del pedido asociado
        cursor.execute('''
            SELECT pd.*, pr.nombre, pr.precio 
            FROM pedido_detalles pd
            JOIN productos pr ON pd.producto_id = pr.id
            WHERE pd.pedido_id = %s
        ''', (factura['pedido_id'],))
        
        detalles = cursor.fetchall()
        
        # Complementar la información de la factura
        factura['detalles'] = detalles
        
        return jsonify({'factura': factura}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error al obtener factura: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@facturas_bp.route('/<int:factura_id>/estado', methods=['PUT'])
@token_required
def actualizar_estado_factura(usuario_actual, factura_id):
    try:
        data = request.get_json()
        nuevo_estado = data.get('estado')
        
        if not nuevo_estado:
            return jsonify({'error': 'El estado es requerido'}), 400
            
        estados_validos = ['PENDIENTE', 'PAGADA', 'ANULADA', 'VENCIDA']
        if nuevo_estado not in estados_validos:
            return jsonify({'error': f'Estado no válido. Debe ser uno de: {", ".join(estados_validos)}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verificar si la factura existe y pertenece al usuario (o es administrador)
        if usuario_actual['rol'] == 'admin':
            cursor.execute('SELECT * FROM facturas WHERE id = %s', (factura_id,))
        else:
            cursor.execute('''
                SELECT f.*
                FROM facturas f
                JOIN pedidos p ON f.pedido_id = p.id
                JOIN clientes c ON p.cliente_id = c.id
                WHERE f.id = %s AND c.id = %s
            ''', (factura_id, usuario_actual['id']))
        
        factura = cursor.fetchone()
        
        if not factura:
            return jsonify({'error': 'Factura no encontrada o no autorizada'}), 404
        
        # Actualizar estado
        cursor.execute('''
            UPDATE facturas SET estado = %s WHERE id = %s
        ''', (nuevo_estado, factura_id))
        
        conn.commit()
        
        return jsonify({'mensaje': 'Estado de factura actualizado correctamente'}), 200
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Error al actualizar estado de factura: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close() 