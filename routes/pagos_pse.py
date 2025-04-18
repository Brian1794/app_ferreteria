from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from models.carrito import Pedido
from extensions import mysql
import time
import random
import pymysql
import uuid
import datetime
import requests

# Definir una función simple para reemplazar token_required
def token_required(f):
    """Decorador simplificado que simula autenticación por token para las rutas de API"""
    def decorated(*args, **kwargs):
        # Aquí solo pasamos un usuario simulado 
        usuario_actual = {'id': 1, 'rol': 'admin'}
        return f(usuario_actual, *args, **kwargs)
    return decorated

pagos_pse_bp = Blueprint('pagos_pse', __name__, url_prefix='/pagos/pse')

@pagos_pse_bp.route('/iniciar', methods=['GET', 'POST'])
@login_required
def iniciar():
    """Inicia el proceso de pago con PSE"""
    if request.method == 'POST':
        # Obtener parámetros del formulario
        factura_id = request.form.get('pedido_id')
        banco_id = request.form.get('banco_pse')
        tipo_persona = request.form.get('tipo_persona')
        tipo_documento = request.form.get('tipo_documento')
        numero_documento = request.form.get('numero_documento')
        email = request.form.get('email', current_user.email)
        celular = request.form.get('celular_pse', '')
        
        # Validar parámetros
        if not all([factura_id, banco_id, tipo_persona, tipo_documento, numero_documento]):
            flash('Faltan datos necesarios para procesar el pago con PSE', 'danger')
            return redirect(url_for('carrito.pago', pedido_id=factura_id))
        
        cursor = mysql.connection.cursor()
        
        try:
            # Verificar que el pedido exista y pertenezca al usuario
            cursor.execute("""
                SELECT p.*, c.nombre, c.email 
                FROM pedidos p
                JOIN clientes c ON p.cliente_id = c.id
                WHERE p.id = %s AND p.cliente_id = %s
            """, (factura_id, current_user.id))
            pedido = cursor.fetchone()
            
            if not pedido:
                flash('Pedido no encontrado o no autorizado', 'danger')
                return redirect(url_for('carrito.mis_pedidos'))
            
            # Obtener nombre del banco
            banco_nombre = obtener_nombre_banco(banco_id)
            
            # Crear registro en pagos_pse
            referencia = f"PSE-{factura_id}-{int(time.time())}"
            fecha_actual = datetime.datetime.now()
            
            cursor.execute("""
                INSERT INTO pagos_pse (
                    pedido_id, referencia_pago, banco_id, banco_nombre,
                    estado, monto, fecha_creacion, tipo_persona,
                    tipo_documento, numero_documento, email, celular
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                factura_id,
                referencia,
                banco_id,
                banco_nombre,
                'PENDIENTE',
                float(pedido[6]),  # total del pedido
                fecha_actual,
                tipo_persona,
                tipo_documento,
                numero_documento,
                email,
                celular
            ))
            mysql.connection.commit()
            
            # Almacenar información del pago en la sesión
            session['pse_payment'] = {
                'factura_id': factura_id,
                'banco_id': banco_id,
                'referencia': referencia,
                'monto': float(pedido[6]),
                'banco': banco_nombre,
                'tipo_persona': tipo_persona,
                'numero_documento': numero_documento,
                'fecha': fecha_actual.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Renderizar la plantilla de redirección
            return render_template('pagos/pse_redireccion.html',
                                banco=banco_nombre,
                                pedido=pedido,
                                pago_info=session['pse_payment'])
                                
        except Exception as e:
            print(f"Error al crear registro de pago PSE: {e}")
            mysql.connection.rollback()
            flash('Error al procesar el pago. Por favor intenta nuevamente.', 'danger')
            return redirect(url_for('carrito.pago', pedido_id=factura_id))
        finally:
            cursor.close()
            
    # Si es GET, redirigir a la página de pago
    return redirect(url_for('carrito.pago'))

@pagos_pse_bp.route('/procesar', methods=['POST'])
@login_required
def procesar():
    """Simula el procesamiento del pago después de la redirección del banco"""
    # Verificar que exista información de pago en la sesión
    if 'pse_payment' not in session:
        flash('No se encontró información de pago', 'danger')
        return redirect(url_for('carrito.mis_pedidos'))
    
    pago_info = session['pse_payment']
    factura_id = pago_info['factura_id']
    referencia = pago_info.get('referencia', f"PSE-{factura_id}-{int(time.time())}")
    
    try:
        # Simular procesamiento del pago (esto tomaría unos segundos en un entorno real)
        time.sleep(2)
        
        # Simular resultado (90% éxito)
        exito = random.random() < 0.9
        
        cursor = mysql.connection.cursor()
        
        if exito:
            # Actualizar estado del pago
            cursor.execute("""
                UPDATE pagos_pse
                SET estado = 'APROBADA', fecha_procesado = %s
                WHERE referencia_pago = %s
            """, (datetime.datetime.now(), referencia))
            
            # Actualizar estado del pedido
            cursor.execute("""
                UPDATE pedidos
                SET estado = 'PAGADO', fecha_pago = %s
                WHERE id = %s
            """, (datetime.datetime.now(), factura_id))
            
            mysql.connection.commit()
            
            # Limpiar sesión y redireccionar a confirmación
            session.pop('pse_payment', None)
            flash('¡Pago procesado exitosamente!', 'success')
            return redirect(url_for('pagos.confirmacion', 
                                  referencia=referencia,
                                  estado='aprobado'))
        else:
            # Actualizar estado a rechazado
            cursor.execute("""
                UPDATE pagos_pse
                SET estado = 'RECHAZADA', fecha_procesado = %s
                WHERE referencia_pago = %s
            """, (datetime.datetime.now(), referencia))
            
            mysql.connection.commit()
            
            # Limpiar sesión y redireccionar a página de error
            session.pop('pse_payment', None)
            flash('El pago no pudo ser procesado. Por favor, intente nuevamente.', 'warning')
            return redirect(url_for('pagos.error', 
                                  referencia=referencia,
                                  estado='rechazado'))
            
    except Exception as e:
        print(f"Error al procesar pago PSE: {e}")
        if 'cursor' in locals() and cursor:
            mysql.connection.rollback()
            cursor.close()
        session.pop('pse_payment', None)
        flash('Error al procesar el pago. Por favor, intente nuevamente.', 'danger')
        return redirect(url_for('carrito.pago', pedido_id=factura_id))
        
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()

@pagos_pse_bp.route('/cancelar')
@login_required
def cancelar():
    """Cancela el proceso de pago con PSE"""
    # Verificar que exista información de pago en la sesión
    if 'pse_payment' in session:
        factura_id = session['pse_payment']['factura_id']
        session.pop('pse_payment', None)
        flash('Pago cancelado por el usuario', 'warning')
        return redirect(url_for('carrito.pago', pedido_id=factura_id, status='failure'))
    else:
        flash('No se encontró información de pago', 'danger')
        return redirect(url_for('carrito.mis_pedidos'))

# Funciones auxiliares
def obtener_nombre_banco(banco_id):
    """Obtiene el nombre del banco según su ID"""
    bancos = {
        '1': 'Bancolombia',
        '2': 'Banco de Bogotá',
        '3': 'Davivienda',
        '4': 'BBVA Colombia',
        '5': 'Banco de Occidente',
        '6': 'Banco Popular',
        '7': 'Banco AV Villas',
        '8': 'Banco Caja Social',
        '9': 'Scotiabank Colpatria',
        '10': 'Itaú',
        '11': 'Banco Agrario de Colombia',
        '12': 'Banco Falabella',
        '13': 'Banco Pichincha',
        '14': 'Banco Finandina',
        '15': 'Banco Cooperativo Coopcentral',
        '16': 'Banco GNB Sudameris',
        '17': 'Banco Serfinanza',
        '18': 'Bancamía',
        '19': 'Banco W',
        '20': 'Banco ProCredit',
        '21': 'Banco Mundo Mujer',
        '22': 'Banco Multibank',
        '23': 'Bancoldex',
        '24': 'Confiar Cooperativa Financiera',
        '25': 'Coofinep Cooperativa Financiera',
        '26': 'Cotrafa Cooperativa Financiera',
        '27': 'Daviplata',
        '28': 'Nequi'
    }
    return bancos.get(banco_id, 'Banco Desconocido')

def generar_factura(pedido_id):
    """Simula la generación de una factura electrónica"""
    # Aquí iría la lógica para generar la factura y enviarla por correo
    # Por ahora, solo registramos en la base de datos que se generó
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            UPDATE pedidos 
            SET factura_generada = 1, fecha_factura = NOW()
            WHERE id = %s
        """, (pedido_id,))
        mysql.connection.commit()
    except Exception as e:
        print(f"Error al registrar generación de factura: {e}")
    finally:
        cursor.close()
    
    return True

@pagos_pse_bp.route('/retorno/<referencia_pago>', methods=['GET'])
def retorno_pago_pse(referencia_pago):
    try:
        # Obtener el estado del pago desde la API de PSE
        # Esto es un ejemplo, en producción se consultaría la API real
        
        """
        respuesta_api = requests.get(
            f'https://api.pse.com.co/consultar-transaccion?referencia={referencia_pago}'
        )
        
        estado_transaccion = respuesta_api.json().get('estado')
        """
        
        # Para fines de demostración, simulamos una respuesta exitosa
        estado_transaccion = request.args.get('estado', 'RECHAZADA')
        if 'approved' in request.args:
            estado_transaccion = 'APROBADA'
            
        cursor = mysql.connection.cursor(pymysql.cursors.DictCursor)
        
        # Buscar el pago por referencia
        cursor.execute('SELECT * FROM pagos_pse WHERE referencia_pago = %s', (referencia_pago,))
        pago = cursor.fetchone()
        
        if not pago:
            cursor.close()
            return jsonify({'error': 'Pago no encontrado'}), 404
            
        # Actualizar el estado del pago
        cursor.execute('''
            UPDATE pagos_pse 
            SET estado = %s, fecha_procesado = %s 
            WHERE referencia_pago = %s
        ''', (estado_transaccion, datetime.datetime.now(), referencia_pago))
        
        # Si el pago fue exitoso, actualizar el estado de la factura
        if estado_transaccion == 'APROBADA':
            cursor.execute('''
                UPDATE facturas SET estado = 'PAGADA' WHERE id = %s
            ''', (pago['factura_id'],))
            
        mysql.connection.commit()
        
        # Redireccionar al usuario a la página de resultado
        cursor.close()
        return redirect(url_for('pagos.resultado_pago', 
                               referencia=referencia_pago, 
                               estado=estado_transaccion))
        
    except Exception as e:
        if 'cursor' in locals() and cursor:
            mysql.connection.rollback()
            cursor.close()
        return jsonify({'error': f'Error al procesar retorno PSE: {str(e)}'}), 500

@pagos_pse_bp.route('/bancos', methods=['GET'])
def listar_bancos_pse():
    try:
        cursor = mysql.connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute('SELECT * FROM bancos_pse WHERE activo = 1 ORDER BY nombre')
        bancos = cursor.fetchall()
        
        cursor.close()
        return jsonify({'bancos': bancos}), 200
        
    except Exception as e:
        if 'cursor' in locals() and cursor:
            cursor.close()
        return jsonify({'error': f'Error al obtener bancos PSE: {str(e)}'}), 500

@pagos_pse_bp.route('/consultar/<referencia_pago>', methods=['GET'])
@token_required
def consultar_estado_pago(usuario_actual, referencia_pago):
    try:
        cursor = mysql.connection.cursor(pymysql.cursors.DictCursor)
        
        # Buscar el pago por referencia y verificar que pertenezca al usuario
        if usuario_actual['rol'] == 'admin':
            cursor.execute('SELECT * FROM pagos_pse WHERE referencia_pago = %s', (referencia_pago,))
        else:
            cursor.execute('''
                SELECT pse.*
                FROM pagos_pse pse
                JOIN pedidos p ON pse.pedido_id = p.id
                JOIN clientes c ON p.cliente_id = c.id
                WHERE pse.referencia_pago = %s AND c.id = %s
            ''', (referencia_pago, usuario_actual['id']))
            
        pago = cursor.fetchone()
        cursor.close()
        
        if not pago:
            return jsonify({'error': 'Pago no encontrado o no autorizado'}), 404
            
        # En un sistema real, aquí se consultaría la API de PSE para verificar
        # el estado actual de la transacción
        
        return jsonify({'pago': pago}), 200
        
    except Exception as e:
        if 'cursor' in locals() and cursor:
            cursor.close()
        return jsonify({'error': f'Error al consultar pago PSE: {str(e)}'}), 500

@pagos_pse_bp.route('/confirmacion/<referencia>', methods=['GET'])
@login_required
def confirmacion(referencia):
    """Muestra la página de confirmación del pago"""
    try:
        cursor = mysql.connection.cursor(pymysql.cursors.DictCursor)
        
        # Obtener información del pago
        cursor.execute("""
            SELECT p.*, ped.total as monto
            FROM pagos_pse p
            JOIN pedidos ped ON p.pedido_id = ped.id
            WHERE p.referencia_pago = %s
        """, (referencia,))
        
        pago = cursor.fetchone()
        
        if not pago:
            flash('No se encontró el pago referenciado', 'danger')
            return redirect(url_for('carrito.mis_pedidos'))
            
        return render_template('pagos/confirmacion.html',
                             pago=pago,
                             referencia=referencia)
                             
    except Exception as e:
        print(f"Error al mostrar confirmación: {e}")
        flash('Error al procesar la confirmación', 'danger')
        return redirect(url_for('carrito.mis_pedidos'))
        
    finally:
        if 'cursor' in locals():
            cursor.close()

@pagos_pse_bp.route('/error/<referencia>', methods=['GET'])
@login_required
def error(referencia):
    """Muestra la página de error del pago"""
    try:
        cursor = mysql.connection.cursor(pymysql.cursors.DictCursor)
        
        # Obtener información del pago
        cursor.execute("""
            SELECT p.*, ped.total as monto
            FROM pagos_pse p
            JOIN pedidos ped ON p.pedido_id = ped.id
            WHERE p.referencia_pago = %s
        """, (referencia,))
        
        pago = cursor.fetchone()
        
        if not pago:
            flash('No se encontró el pago referenciado', 'danger')
            return redirect(url_for('carrito.mis_pedidos'))
            
        return render_template('pagos/error.html',
                             pago=pago,
                             referencia=referencia)
                             
    except Exception as e:
        print(f"Error al mostrar página de error: {e}")
        flash('Error al procesar la confirmación', 'danger')
        return redirect(url_for('carrito.mis_pedidos'))
        
    finally:
        if 'cursor' in locals():
            cursor.close()

@pagos_pse_bp.route('/confirmar', methods=['POST'])
def confirmar_pago():
    pago_id = request.json.get('pago_id')
    if not pago_id:
        return jsonify({'error': 'Se requiere el ID del pago'}), 400
        
    cursor = mysql.connection.cursor(pymysql.cursors.DictCursor)
    cursor.execute('SELECT * FROM pagos_pse WHERE id = %s AND estado = "PENDIENTE"', (pago_id,))
    pago = cursor.fetchone()
    
    if not pago:
        return jsonify({'error': 'Pago no encontrado o no está pendiente'}), 404
        
    return jsonify({
        'message': '¿Desea continuar con la transacción?',
        'pago_id': pago_id,
        'monto': pago['monto'],
        'referencia': pago['referencia']
    })