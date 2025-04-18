from flask import Blueprint, request, jsonify, redirect, url_for
import pymysql
import os
import random
import string
import uuid
from datetime import datetime
import json
from app.db import get_db_connection
import requests
from dotenv import load_dotenv
import secrets
from flask_jwt_extended import jwt_required, get_jwt_identity

load_dotenv()

pagos_pse_bp = Blueprint('pagos_pse', __name__, url_prefix='/api/pagos/pse')

# Configuración de PSE (estos valores deberían estar en variables de entorno)
PSE_URL = os.getenv('PSE_URL', 'https://api.pagoseguro.com/pse')
PSE_PUBLIC_KEY = os.getenv('PSE_PUBLIC_KEY', 'test_key_public')
PSE_PRIVATE_KEY = os.getenv('PSE_PRIVATE_KEY', 'test_key_private')

# Estado de pago
ESTADO_PENDIENTE = 'pendiente'
ESTADO_COMPLETADO = 'completado'
ESTADO_RECHAZADO = 'rechazado'
ESTADO_ERROR = 'error'

# Configuración de PSE (debe estar en variables de entorno)
PSE_API_URL = os.getenv('PSE_API_URL')
PSE_API_KEY = os.getenv('PSE_API_KEY')
PSE_MERCHANT_ID = os.getenv('PSE_MERCHANT_ID')

@pagos_pse_bp.route('/bancos', methods=['GET'])
@jwt_required()
def listar_bancos():
    """
    Lista todos los bancos disponibles para pagos PSE
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Consultar los bancos disponibles
        cursor.execute("""
            SELECT id, nombre, codigo_banco, estado, logo_url 
            FROM bancos_pse 
            WHERE estado = 'activo'
            ORDER BY nombre
        """)
        
        bancos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not bancos:
            return jsonify({'exito': False, 'mensaje': 'No hay bancos disponibles'}), 404
            
        return jsonify({
            'exito': True,
            'bancos': bancos
        })
        
    except Exception as e:
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@pagos_pse_bp.route('/iniciar', methods=['POST'])
@jwt_required()
def iniciar_pago():
    """
    Inicia un proceso de pago PSE
    Requiere:
    - factura_id: ID de la factura a pagar
    - banco_id: ID del banco seleccionado
    - tipo_persona: Natural (N) o Jurídica (J)
    - tipo_documento: CC, CE, NIT, etc.
    - documento: Número de documento
    - nombre: Nombre del pagador
    - apellido: Apellido del pagador
    - email: Email del pagador
    - telefono: Teléfono del pagador
    """
    try:
        usuario_id = get_jwt_identity()
        data = request.json
        
        # Validar campos requeridos
        campos_requeridos = [
            'factura_id', 'banco_id', 'tipo_persona', 
            'tipo_documento', 'documento', 'nombre', 
            'apellido', 'email', 'celular'
        ]
        
        for campo in campos_requeridos:
            if campo not in data or not data[campo]:
                return jsonify({'exito': False, 'mensaje': f'Falta el campo {campo}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verificar que la factura existe y está pendiente
        cursor.execute("""
            SELECT id, total, estado, referencia
            FROM facturas
            WHERE id = %s AND usuario_id = %s
        """, (data['factura_id'], usuario_id))
        
        factura = cursor.fetchone()
        
        if not factura:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'La factura no existe'}), 404
            
        if factura['estado'] != 'pendiente':
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'La factura no está en estado pendiente'}), 400
        
        # Verificar que el banco existe y está activo
        cursor.execute("""
            SELECT id, nombre, codigo_banco, estado
            FROM bancos_pse
            WHERE id = %s AND estado = 'activo'
        """, (data['banco_id'],))
        
        banco = cursor.fetchone()
        
        if not banco:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'El banco seleccionado no existe'}), 404
            
        if banco['estado'] != 'activo':
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'El banco seleccionado no está disponible'}), 400
        
        # Generar referencia única de pago
        referencia = f"PSE-{factura['referencia']}-{str(uuid.uuid4())[:8]}"
        
        # Generar ID de transacción PSE simulado
        pse_id = 'PSE-' + str(uuid.uuid4())[:8]
        
        # Registrar el intento de pago
        now = datetime.datetime.now()
        
        cursor.execute("""
            INSERT INTO pagos (
                factura_id, usuario_id, metodo_pago, referencia, 
                estado, monto, banco_id, banco_nombre, transaction_id,
                fecha_creacion, datos_adicionales
            ) VALUES (%s, %s, 'pse', %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['factura_id'],
            usuario_id,
            referencia,
            ESTADO_PENDIENTE,
            factura['total'],
            banco['id'],
            banco['nombre'],
            pse_id,
            datetime.datetime.now(),
            # Guardar todos los datos adicionales como JSON
            str(data)
        ))
        
        conn.commit()
        pago_id = cursor.lastrowid
        
        # Simular redirección al banco
        url_redireccion = f"https://secure.pse.com.co/pse/?ref={referencia}&bank={banco['id']}"
        
        cursor.close()
        conn.close()
        
        # Preparar datos para enviar a PSE
        pse_data = {
            'merchant_id': PSE_MERCHANT_ID,
            'transaction_id': pse_id,
            'reference': referencia,
            'description': f"Pago factura {factura['referencia']}",
            'amount': float(factura['total']),
            'currency': 'COP',
            'bank_code': banco['codigo_banco'],
            'customer': {
                'document_type': data['tipo_documento'],
                'document': data['documento'],
                'name': data['nombre'],
                'last_name': data['apellido'],
                'email': data['email'],
                'phone': data['celular'],
                'person_type': data['tipo_persona']  # 'N' para persona natural, 'J' para jurídica
            },
            'redirect_url': f"{request.host_url.rstrip('/')}/api/pagos/pse/respuesta",
            'callback_url': f"{request.host_url.rstrip('/')}/api/pagos/pse/callback"
        }
        
        # Realizar solicitud a PSE
        # Aquí se simula la respuesta, en producción se enviaría a la API real
        pse_response = {
            'success': True,
            'transaction_id': pse_id,
            'payment_url': f"https://pse-test.com/payments/{pse_id}"
        }
        
        # Actualizar registro con la URL de pago
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pagos
            SET payment_url = %s
            WHERE id = %s
        """, (pse_response['payment_url'], pago_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'exito': True,
            'pago_id': pago_id,
            'referencia': referencia,
            'pse_id': pse_id,
            'monto': float(factura['total']),
            'banco': banco['nombre'],
            'url_redireccion': url_redireccion,
            'payment_url': pse_response['payment_url']
        })
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
            if 'cursor' in locals() and cursor:
                cursor.close()
            conn.close()
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@pagos_pse_bp.route('/verificar/<int:pago_id>', methods=['GET'])
@jwt_required()
def verificar_pago(pago_id):
    """
    Verifica el estado de un pago PSE
    """
    try:
        usuario_id = get_jwt_identity()
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Obtener el pago
        cursor.execute("""
            SELECT p.*, f.referencia as factura_referencia, b.nombre as banco_nombre
            FROM pagos p
            JOIN facturas f ON p.factura_id = f.id
            LEFT JOIN bancos_pse b ON p.banco_id = b.id
            WHERE p.id = %s AND p.usuario_id = %s
        """, (pago_id, usuario_id))
        
        pago = cursor.fetchone()
        
        if not pago:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'Pago no encontrado'}), 404
        
        # Si el pago aún está pendiente, consultar estado real
        # En este caso simulamos una actualización aleatoria del estado
        if pago['estado'] == ESTADO_PENDIENTE:
            # Simular consulta a PSE
            # En producción, aquí se haría la llamada real a la API de PSE
            estados_posibles = [ESTADO_PENDIENTE, ESTADO_COMPLETADO, ESTADO_RECHAZADO]
            nuevo_estado = random.choice(estados_posibles)
            
            # Actualizar solo si el estado cambió
            if nuevo_estado != ESTADO_PENDIENTE:
                cursor.execute("""
                    UPDATE pagos_pse
                    SET estado = %s, fecha_actualizacion = %s
                    WHERE id = %s
                """, (nuevo_estado, datetime.datetime.now(), pago_id))
                
                # Si el pago se completó, actualizar la factura
                if nuevo_estado == ESTADO_COMPLETADO:
                    cursor.execute("""
                        UPDATE facturas
                        SET estado = 'pagada', metodo_pago = 'pse', fecha_pago = %s
                        WHERE id = %s
                    """, (datetime.datetime.now(), pago['factura_id']))
                    
                    # Registrar en la tabla de pagos
                    cursor.execute("""
                        INSERT INTO pagos (
                            factura_id, metodo, monto, fecha, referencia, observaciones
                        ) 
                        SELECT factura_id, 'pse', monto, %s, referencia, 'Pago PSE'
                        FROM pagos_pse
                        WHERE id = %s
                    """, (datetime.datetime.now(), pago_id))
                
                conn.commit()
                pago['estado'] = nuevo_estado
                pago['fecha_actualizacion'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'exito': True,
            'pago': pago
        })
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
            if 'cursor' in locals() and cursor:
                cursor.close()
            conn.close()
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@pagos_pse_bp.route('/respuesta', methods=['GET'])
def respuesta_pago():
    """
    Maneja la respuesta de PSE después de intentar un pago
    """
    try:
        # Obtener parámetros de respuesta de PSE
        referencia = request.args.get('ref')
        estado = request.args.get('estado')
        
        if not referencia or not estado:
            return jsonify({'exito': False, 'mensaje': 'Parámetros incompletos'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Buscar el pago por referencia
        cursor.execute("""
            SELECT id, factura_id, estado
            FROM pagos_pse
            WHERE referencia = %s
        """, (referencia,))
        
        pago = cursor.fetchone()
        
        if not pago:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'Pago no encontrado'}), 404
        
        # Actualizar el estado según la respuesta de PSE
        nuevo_estado = ESTADO_PENDIENTE
        if estado == 'OK':
            nuevo_estado = ESTADO_COMPLETADO
        elif estado == 'FAILED':
            nuevo_estado = ESTADO_RECHAZADO
        elif estado == 'ERROR':
            nuevo_estado = ESTADO_ERROR
        
        # Si el estado cambió, actualizar en la base de datos
        if nuevo_estado != pago['estado']:
            cursor.execute("""
                UPDATE pagos_pse
                SET estado = %s, fecha_actualizacion = %s
                WHERE id = %s
            """, (nuevo_estado, datetime.datetime.now(), pago['id']))
            
            # Si el pago se completó, actualizar la factura
            if nuevo_estado == ESTADO_COMPLETADO:
                cursor.execute("""
                    UPDATE facturas
                    SET estado = 'pagada', metodo_pago = 'pse', fecha_pago = %s
                    WHERE id = %s
                """, (datetime.datetime.now(), pago['factura_id']))
                
                # Registrar en la tabla de pagos
                cursor.execute("""
                    INSERT INTO pagos (
                        factura_id, metodo, monto, fecha, referencia, observaciones
                    ) 
                    SELECT factura_id, 'pse', monto, %s, referencia, 'Pago PSE'
                    FROM pagos_pse
                    WHERE id = %s
                """, (datetime.datetime.now(), pago['id']))
            
            conn.commit()
        
        cursor.close()
        conn.close()
        
        # Redirigir al usuario según el resultado
        if nuevo_estado == ESTADO_COMPLETADO:
            return redirect(url_for('facturas.detalle_factura', factura_id=pago['factura_id']))
        else:
            # En caso de error o rechazo, redirigir a una página de error
            return redirect(url_for('pagos.error_pago', pago_id=pago['id']))
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
            if 'cursor' in locals() and cursor:
                cursor.close()
            conn.close()
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@pagos_pse_bp.route('/historial/<int:factura_id>', methods=['GET'])
def historial_pagos(factura_id):
    """
    Obtiene el historial de intentos de pago PSE para una factura
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT p.*, b.nombre as banco_nombre
            FROM pagos_pse p
            JOIN bancos_pse b ON p.banco_id = b.id
            WHERE p.factura_id = %s
            ORDER BY p.fecha_creacion DESC
        """, (factura_id,))
        
        pagos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Formatear los resultados
        resultado = []
        for pago in pagos:
            resultado.append({
                'id': pago['id'],
                'referencia': pago['referencia'],
                'pse_id': pago['pse_id'],
                'estado': pago['estado'],
                'monto': float(pago['monto']),
                'banco': pago['banco_nombre'],
                'fecha_creacion': pago['fecha_creacion'].isoformat(),
                'fecha_actualizacion': pago['fecha_actualizacion'].isoformat()
            })
        
        return jsonify({
            'exito': True,
            'factura_id': factura_id,
            'pagos': resultado
        })
        
    except Exception as e:
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@pagos_pse_bp.route('/confirmar', methods=['POST'])
@jwt_required()
def confirmar_pago():
    """
    Confirma si el usuario desea continuar con el pago PSE
    """
    try:
        data = request.get_json()
        if not data or 'pago_id' not in data:
            return jsonify({'exito': False, 'mensaje': 'Falta el ID del pago'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Verificar que el pago existe y está pendiente
        cursor.execute("""
            SELECT p.id, p.estado, p.monto, f.referencia 
            FROM pagos_pse p
            JOIN facturas f ON p.factura_id = f.id
            WHERE p.id = %s AND p.estado = 'pendiente'
        """, (data['pago_id'],))
        
        pago = cursor.fetchone()
        
        if not pago:
            cursor.close()
            conn.close()
            return jsonify({'exito': False, 'mensaje': 'Pago no encontrado o no está pendiente'}), 404
            
        return jsonify({
            'exito': True,
            'mensaje': '¿Desea continuar con el pago?',
            'datos_pago': {
                'id': pago['id'],
                'monto': float(pago['monto']),
                'referencia': pago['referencia']
            }
        })
        
    except Exception as e:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
        return jsonify({'exito': False, 'mensaje': str(e)}), 500

@pagos_pse_bp.route('/verificar-continuar', methods=['POST'])
@jwt_required()
def verificar_continuar():
    """
    Verifica si el usuario desea continuar con el proceso de pago
    Retorna:
    - confirmación del usuario para continuar
    """
    try:
        data = request.json
        if not data or 'continuar' not in data:
            return jsonify({
                'exito': False,
                'mensaje': 'Se requiere la confirmación para continuar'
            }), 400
            
        if data['continuar']:
            return jsonify({
                'exito': True,
                'mensaje': 'Usuario confirmó continuar con el proceso',
                'continuar': True
            })
        else:
            return jsonify({
                'exito': True,
                'mensaje': 'Usuario decidió no continuar con el proceso',
                'continuar': False
            })
            
    except Exception as e:
        return jsonify({
            'exito': False,
            'mensaje': f'Error al procesar la verificación: {str(e)}'
        }), 500