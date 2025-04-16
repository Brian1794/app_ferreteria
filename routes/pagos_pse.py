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

@pagos_pse_bp.route('/iniciar')
@login_required
def iniciar():
    """Inicia el proceso de pago con PSE"""
    # Obtener parámetros
    factura_id = request.args.get('factura_id')
    banco_id = request.args.get('banco_id')
    tipo_persona = request.args.get('tipo_persona')
    tipo_documento = request.args.get('tipo_documento')
    numero_documento = request.args.get('numero_documento')
    email = request.args.get('email')
    celular = request.args.get('celular_pse', '')
    
    # Validar parámetros
    if not all([factura_id, banco_id, tipo_persona, tipo_documento, numero_documento, email]):
        flash('Faltan datos necesarios para procesar el pago con PSE', 'danger')
        return redirect(url_for('carrito.pago', pedido_id=factura_id))
    
    # Verificar que el pedido exista y pertenezca al usuario
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.*, c.nombre, c.email 
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.id = %s AND p.cliente_id = %s
    """, (factura_id, current_user.id))
    pedido = cursor.fetchone()
    cursor.close()
    
    if not pedido:
        flash('Pedido no encontrado o no autorizado', 'danger')
        return redirect(url_for('carrito.mis_pedidos'))
    
    # Obtener nombre del banco
    banco_nombre = obtener_nombre_banco(banco_id)
    
    # Guardar información del pago en sesión
    session['pse_payment'] = {
        'factura_id': factura_id,
        'banco_id': banco_id,
        'banco_nombre': banco_nombre,
        'tipo_persona': tipo_persona,
        'tipo_documento': tipo_documento,
        'numero_documento': numero_documento,
        'email': email,
        'celular': celular,
        'monto': pedido['total'] if isinstance(pedido, dict) else pedido[6],
        'fecha': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Crear una transacción de pago en la base de datos
    cursor = mysql.connection.cursor()
    
    # Generar referencia única
    referencia = f"PSE-{factura_id}-{int(time.time())}"
    
    # Agregar la referencia al objeto de sesión antes de cualquier operación de base de datos
    session['pse_payment']['referencia'] = referencia
    
    try:
        # Crear tablas si no existen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagos_pse (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pedido_id INT NOT NULL,
                referencia_pago VARCHAR(50) NOT NULL,
                banco_id VARCHAR(10) NOT NULL,
                banco_nombre VARCHAR(100) NOT NULL,
                estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
                monto DECIMAL(10,2) NOT NULL,
                fecha_creacion DATETIME NOT NULL,
                fecha_procesado DATETIME NULL,
                tipo_persona VARCHAR(10) NOT NULL,
                tipo_documento VARCHAR(20) NOT NULL,
                numero_documento VARCHAR(30) NOT NULL,
                email VARCHAR(100) NOT NULL,
                celular VARCHAR(20) NULL,
                UNIQUE(referencia_pago)
            )
        """)
        
        # Registrar el intento de pago
        cursor.execute("""
            INSERT INTO pagos_pse 
            (pedido_id, referencia_pago, banco_id, banco_nombre, monto, fecha_creacion, 
             tipo_persona, tipo_documento, numero_documento, email, celular)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            factura_id,
            referencia,
            banco_id,
            banco_nombre,
            float(session['pse_payment']['monto']),
            datetime.datetime.now(),
            tipo_persona,
            tipo_documento,
            numero_documento,
            email,
            celular
        ))
        mysql.connection.commit()
        
    except Exception as e:
        print(f"Error al crear registro de pago PSE: {e}")
        mysql.connection.rollback()
    finally:
        cursor.close()
    
    # Redirigir a la página específica según el banco
    if banco_id == '28':  # Nequi
        return render_template('pagos/nequi_redireccion.html', 
                              pedido=pedido,
                              pago_info=session['pse_payment'])
    elif banco_id == '27':  # Daviplata
        return render_template('pagos/daviplata_redireccion.html',
                              pedido=pedido, 
                              pago_info=session['pse_payment'])
    else:  # PSE estándar
        return render_template('pagos/pse_redireccion.html', 
                              banco=banco_nombre,
                              pedido=pedido,
                              pago_info=session['pse_payment'])

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
    banco_id = pago_info['banco_id']
    referencia = pago_info.get('referencia', f"PSE-{factura_id}-{int(time.time())}")
    
    # Simular un resultado aleatorio (90% éxito, 10% fallo)
    exito = random.random() < 0.9
    
    if exito:
        # Actualizar estado del pago en la base de datos
        Pedido.actualizar_estado_pago(factura_id, 'pse', referencia, 'PAGADO')
        
        # Actualizar registro en la tabla pagos_pse
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                UPDATE pagos_pse
                SET estado = 'APROBADA', fecha_procesado = %s
                WHERE referencia_pago = %s
            """, (datetime.datetime.now(), referencia))
            mysql.connection.commit()
        except Exception as e:
            print(f"Error al actualizar estado de pago PSE: {e}")
        finally:
            cursor.close()
        
        # Generar factura (implementación simulada)
        generar_factura(factura_id)
        
        # Mensaje de éxito
        flash('¡Pago exitoso! La factura ha sido enviada a tu correo electrónico.', 'success')
        
        # Limpiar datos de sesión
        session.pop('pse_payment', None)
        
        # Redirigir a página de confirmación
        return redirect(url_for('carrito.confirmacion', pedido_id=factura_id))
    else:
        # Actualizar registro en la tabla pagos_pse
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                UPDATE pagos_pse
                SET estado = 'RECHAZADA', fecha_procesado = %s
                WHERE referencia_pago = %s
            """, (datetime.datetime.now(), referencia))
            mysql.connection.commit()
        except Exception as e:
            print(f"Error al actualizar estado de pago PSE: {e}")
        finally:
            cursor.close()
        
        # Mensaje de error
        flash('El pago no pudo ser procesado. Por favor, intenta nuevamente.', 'danger')
        
        # Limpiar datos de sesión
        session.pop('pse_payment', None)
        
        # Redirigir a página de pago
        return redirect(url_for('carrito.pago', pedido_id=factura_id, status='failure'))

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