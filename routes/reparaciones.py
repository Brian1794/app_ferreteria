from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from models.models import mysql
from models.whatsapp import WhatsAppManager
from datetime import datetime
import MySQLdb
from extensions import get_dict_cursor, retry_on_connection_error
import functools
import logging
import time
import traceback
from functools import wraps
from forms import ReparacionForm  # Adjusted import to match project structure

# Configurar logging
logger = logging.getLogger(__name__)

reparaciones_bp = Blueprint('reparaciones', __name__)

# Función para obtener conexión a la base de datos
def get_db_connection():
    return mysql.connection

# Función para obtener un cursor de diccionario
def get_dict_cursor():
    return mysql.connection.cursor(MySQLdb.cursors.DictCursor)

def empleado_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or hasattr(current_user, 'es_cliente') and current_user.es_cliente:
            flash('Esta sección es solo para personal de la ferretería', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@reparaciones_bp.route('/')
def index():
    """Página principal de servicio de reparaciones accesible para todos los usuarios"""
    return render_template('reparaciones/index.html')

@reparaciones_bp.route('/admin/lista')
@login_required
@empleado_required
@retry_on_connection_error()
def listar():
    """Muestra todas las reparaciones"""
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT r.id, r.descripcion, c.nombre as cliente, r.estado,
                   DATE_FORMAT(r.fecha_recepcion, '%d/%m/%Y') as fecha_recepcion,
                   DATE_FORMAT(r.fecha_entrega_estimada, '%d/%m/%Y') as fecha_entrega_estimada,
                   e.nombre as tecnico
            FROM reparaciones r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            LEFT JOIN empleados e ON r.tecnico_id = e.id
            ORDER BY r.fecha_recepcion DESC
        """)
        reparaciones = cursor.fetchall()
        return render_template('reparaciones/lista.html', reparaciones=reparaciones)
    finally:
        cursor.close()

@reparaciones_bp.route('/pendientes')
@login_required
@empleado_required
def pendientes():
    """Muestra las reparaciones pendientes"""
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT r.id, r.descripcion, c.nombre as cliente, r.estado,
               DATE_FORMAT(r.fecha_recepcion, '%d/%m/%Y') as fecha_recepcion,
               DATE_FORMAT(r.fecha_entrega_estimada, '%d/%m/%Y') as fecha_entrega_estimada,
               e.nombre as tecnico
        FROM reparaciones r
        LEFT JOIN clientes c ON r.cliente_id = c.id
        LEFT JOIN empleados e ON r.tecnico_id = e.id
        WHERE r.estado NOT IN ('ENTREGADO', 'CANCELADO')
        ORDER BY r.fecha_recepcion DESC
    """)
    reparaciones = cursor.fetchall()
    cursor.close()
    
    return render_template('reparaciones/lista.html', 
                           reparaciones=reparaciones, 
                           titulo="Reparaciones Pendientes", 
                           solo_pendientes=True)

@reparaciones_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
@empleado_required
def nueva():
    """Crea una nueva reparación"""
    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id')
        descripcion = request.form.get('descripcion')
        electrodomestico = request.form.get('electrodomestico')
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        problema = request.form.get('problema')
        fecha_entrega_estimada = request.form.get('fecha_entrega_estimada')
        
        # Validaciones básicas
        if not descripcion or not electrodomestico or not problema:
            flash('Los campos descripción, electrodoméstico y problema son obligatorios', 'danger')
            return redirect(url_for('reparaciones.nueva'))
        
        cursor = mysql.connection.cursor()
        try:
            # Insertamos la reparación
            cursor.execute("""
                INSERT INTO reparaciones 
                (cliente_id, descripcion, electrodomestico, marca, modelo, problema, fecha_entrega_estimada, estado, recepcionista_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'RECIBIDO', %s)
            """, (cliente_id, descripcion, electrodomestico, marca, modelo, problema, fecha_entrega_estimada, current_user.id))
            
            reparacion_id = cursor.lastrowid
            mysql.connection.commit()
            
            # Registrar en el historial
            cursor.execute("""
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado_nuevo, descripcion, usuario_id, fecha)
                VALUES (%s, %s, %s, %s, NOW())
            """, (reparacion_id, "RECIBIDO", "Reparación registrada", current_user.id))
            mysql.connection.commit()
            
            # Enviamos notificación por WhatsApp si está configurado
            cursor.execute("SELECT valor FROM configuracion WHERE grupo = 'whatsapp_automaticos' AND nombre = 'notificar_reparaciones'")
            config = cursor.fetchone()
            
            if config and config[0] == 'si':
                try:
                    WhatsAppManager.notificar_estado_reparacion(reparacion_id)
                except Exception as e:
                    # Capturamos la excepción pero no interrumpimos el flujo
                    print(f"Error al enviar WhatsApp: {str(e)}")
            
            flash('Reparación registrada con éxito', 'success')
            return redirect(url_for('reparaciones.ver', id=reparacion_id))
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al registrar la reparación: {str(e)}', 'danger')
        finally:
            cursor.close()
    
    # Obtenemos los clientes para el selector
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, nombre, telefono FROM clientes ORDER BY nombre")
    clientes = cursor.fetchall()
    
    # Obtener técnicos disponibles
    cursor.execute("""
        SELECT e.id, e.nombre 
        FROM empleados e
        INNER JOIN cargos c ON e.cargo_id = c.id
        WHERE c.nombre = 'Técnico' AND e.activo = TRUE
        ORDER BY e.nombre
    """)
    tecnicos = cursor.fetchall()
    cursor.close()
    
    return render_template('reparaciones/nueva.html', clientes=clientes, tecnicos=tecnicos)

@reparaciones_bp.route('/ver/<int:id>', methods=['GET'])
@login_required
def ver(id):
    # Obtener detalles de la reparación
    cursor = get_dict_cursor()
    cursor.execute('''
        SELECT r.*, c.nombre as cliente_nombre, e.nombre as tecnico_nombre
        FROM reparaciones r
        LEFT JOIN clientes c ON r.cliente_id = c.id
        LEFT JOIN empleados e ON r.tecnico_id = e.id
        WHERE r.id = %s
    ''', (id,))
    reparacion = cursor.fetchone()
    
    if not reparacion:
        flash('Reparación no encontrada', 'danger')
        return redirect(url_for('reparaciones.admin'))
    
    # Verificar permiso: solo el cliente dueño o empleados pueden ver detalles
    if hasattr(current_user, 'es_cliente') and current_user.es_cliente:
        if current_user.id != reparacion['cliente_id']:
            flash('No tienes permiso para ver esta reparación', 'danger')
            return redirect(url_for('reparaciones.mis_reparaciones'))
    
    # Obtener historial de la reparación
    cursor.execute('''
        SELECT h.*, e.nombre as usuario_nombre
        FROM historial_reparaciones h
        LEFT JOIN empleados e ON h.usuario_id = e.id
        WHERE h.reparacion_id = %s
        ORDER BY h.fecha DESC
    ''', (id,))
    historial = cursor.fetchall()
    
    # Obtener repuestos utilizados
    cursor.execute('''
        SELECT rr.*, p.nombre as producto_nombre
        FROM reparaciones_repuestos rr
        LEFT JOIN productos p ON rr.producto_id = p.id
        WHERE rr.reparacion_id = %s
    ''', (id,))
    repuestos = cursor.fetchall()
    
    # Obtener técnicos disponibles
    cursor.execute('''
        SELECT e.id, e.nombre 
        FROM empleados e
        INNER JOIN cargos c ON e.cargo_id = c.id
        WHERE c.nombre = 'Técnico' AND e.activo = TRUE
        ORDER BY e.nombre
    ''')
    tecnicos = cursor.fetchall()
    
    # Mapeo de estados para mostrar texto amigable
    estados_texto = {
        'RECIBIDO': 'Recibido',
        'DIAGNOSTICO': 'En diagnóstico',
        'REPARACION': 'En reparación',
        'ESPERA_REPUESTOS': 'Esperando repuestos',
        'LISTO': 'Listo para entrega',
        'ENTREGADO': 'Entregado',
        'CANCELADO': 'Cancelado'
    }
    
    reparacion['estado_texto'] = estados_texto.get(reparacion['estado'], reparacion['estado'])
    
    return render_template('reparaciones/detalle.html', 
                          reparacion=reparacion,
                          historial=historial,
                          repuestos=repuestos,
                          tecnicos=tecnicos,
                          estados=estados_texto)

@reparaciones_bp.route('/<int:id>/editar', methods=['POST'])
@login_required
@empleado_required
def editar(id):
    """Actualiza los datos de una reparación"""
    diagnostico = request.form.get('diagnostico')
    estado = request.form.get('estado')
    tecnico_id = request.form.get('tecnico_id')
    fecha_entrega_estimada = request.form.get('fecha_entrega_estimada')
    notas = request.form.get('notas')
    costo_estimado = request.form.get('costo_estimado', '0')
    costo_final = request.form.get('costo_final', '0')
    
    # Convertir campos numéricos
    try:
        costo_estimado = float(costo_estimado) if costo_estimado else 0
        costo_final = float(costo_final) if costo_final else 0
    except ValueError:
        flash('Los costos deben ser valores numéricos', 'danger')
        return redirect(url_for('reparaciones.ver', id=id))
    
    cursor = mysql.connection.cursor()
    
    try:
        # Guardar el estado anterior para verificar cambios
        cursor.execute("SELECT estado FROM reparaciones WHERE id = %s", (id,))
        estado_anterior = cursor.fetchone()[0]
        
        # Actualizamos la reparación
        cursor.execute("""
            UPDATE reparaciones SET
            diagnostico = %s,
            estado = %s,
            tecnico_id = %s,
            fecha_entrega_estimada = %s,
            notas = %s,
            costo_estimado = %s,
            costo_final = %s,
            fecha_entrega = CASE WHEN %s = 'ENTREGADO' AND estado != 'ENTREGADO' THEN CURDATE() ELSE fecha_entrega END
            WHERE id = %s
        """, (diagnostico, estado, tecnico_id, fecha_entrega_estimada, notas, 
              costo_estimado, costo_final, estado, id))
        
        mysql.connection.commit()
        
        # Si cambió el estado, registrar en historial
        if estado != estado_anterior:
            cursor.execute("""
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado_anterior, estado_nuevo, descripcion, usuario_id, fecha)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (id, estado_anterior, estado, f"Cambio de estado: {estado_anterior} → {estado}", current_user.id))
            mysql.connection.commit()
            
            # Enviar notificación por WhatsApp
            cursor.execute("SELECT valor FROM configuracion WHERE grupo = 'whatsapp_automaticos' AND nombre = 'notificar_reparaciones'")
            config = cursor.fetchone()
            
            if config and config[0] == 'si':
                try:
                    WhatsAppManager.notificar_estado_reparacion(id)
                except Exception as e:
                    # Capturamos la excepción pero no interrumpimos el flujo
                    print(f"Error al enviar WhatsApp: {str(e)}")
        
        flash('Reparación actualizada con éxito', 'success')
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al actualizar la reparación: {str(e)}', 'danger')
    finally:
        cursor.close()
    
    return redirect(url_for('reparaciones.ver', id=id))

@reparaciones_bp.route('/<int:id>/agregar_repuesto', methods=['POST'])
@login_required
@empleado_required
def agregar_repuesto(id):
    """Agrega un repuesto a la reparación"""
    producto_id = request.form.get('producto_id')
    repuesto_descripcion = request.form.get('repuesto_descripcion')
    cantidad = request.form.get('cantidad', '1')
    precio_unitario = request.form.get('precio_unitario', '0')
    
    # Validaciones básicas
    if not repuesto_descripcion:
        flash('La descripción del repuesto es obligatoria', 'danger')
        return redirect(url_for('reparaciones.ver', id=id))
    
    # Convertir campos numéricos
    try:
        cantidad = int(cantidad) if cantidad else 1
        precio_unitario = float(precio_unitario) if precio_unitario else 0
        subtotal = cantidad * precio_unitario
    except ValueError:
        flash('La cantidad y el precio deben ser valores numéricos', 'danger')
        return redirect(url_for('reparaciones.ver', id=id))
    
    cursor = mysql.connection.cursor()
    
    try:
        # Obtener el estado actual de la reparación
        cursor.execute("SELECT estado FROM reparaciones WHERE id = %s", (id,))
        estado_actual = cursor.fetchone()[0]
        
        # Insertamos el repuesto
        cursor.execute("""
            INSERT INTO reparaciones_repuestos
            (reparacion_id, producto_id, repuesto_descripcion, cantidad, precio_unitario, subtotal)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id, producto_id if producto_id else None, repuesto_descripcion, 
              cantidad, precio_unitario, subtotal))
        
        # Si es un producto del inventario, actualizamos el stock
        if producto_id:
            cursor.execute("""
                UPDATE productos
                SET stock = stock - %s
                WHERE id = %s
            """, (cantidad, producto_id))
        
        # Actualizamos el costo final sumando el nuevo repuesto
        cursor.execute("""
            UPDATE reparaciones
            SET costo_final = IFNULL(costo_final, 0) + %s
            WHERE id = %s
        """, (subtotal, id))
        
        # Registrar en historial
        cursor.execute("""
            INSERT INTO historial_reparaciones 
            (reparacion_id, estado, fecha, tecnico_id, comentario) 
            VALUES (%s, %s, NOW(), %s, %s)
        """, (id, estado_actual, current_user.id, 
              f"Repuesto agregado: {repuesto_descripcion} (Cantidad: {cantidad}, Subtotal: ${subtotal})"))
        
        mysql.connection.commit()
        flash('Repuesto agregado con éxito', 'success')
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al agregar el repuesto: {str(e)}', 'danger')
    finally:
        cursor.close()
    
    return redirect(url_for('reparaciones.ver', id=id))

@reparaciones_bp.route('/<int:id>/eliminar_repuesto/<int:repuesto_id>', methods=['POST'])
@login_required
@empleado_required
def eliminar_repuesto(id, repuesto_id):
    """Elimina un repuesto de la reparación"""
    cursor = mysql.connection.cursor()
    
    try:
        # Obtener el estado actual de la reparación
        cursor.execute("SELECT estado FROM reparaciones WHERE id = %s", (id,))
        estado_actual = cursor.fetchone()[0]
        
        # Obtener datos del repuesto
        cursor.execute("""
            SELECT producto_id, cantidad, subtotal, repuesto_descripcion
            FROM reparaciones_repuestos
            WHERE id = %s AND reparacion_id = %s
        """, (repuesto_id, id))
        repuesto = cursor.fetchone()
        
        if not repuesto:
            flash('Repuesto no encontrado', 'danger')
            return redirect(url_for('reparaciones.ver', id=id))
        
        producto_id, cantidad, subtotal, descripcion = repuesto
        
        # Si era un producto del inventario, devolvemos al stock
        if producto_id:
            cursor.execute("""
                UPDATE productos
                SET stock = stock + %s
                WHERE id = %s
            """, (cantidad, producto_id))
        
        # Eliminamos el repuesto
        cursor.execute("DELETE FROM reparaciones_repuestos WHERE id = %s", (repuesto_id,))
        
        # Actualizamos el costo final restando el repuesto eliminado
        cursor.execute("""
            UPDATE reparaciones
            SET costo_final = GREATEST(0, IFNULL(costo_final, 0) - %s)
            WHERE id = %s
        """, (subtotal, id))
        
        # Registrar en historial
        cursor.execute("""
            INSERT INTO historial_reparaciones 
            (reparacion_id, estado, fecha, tecnico_id, comentario) 
            VALUES (%s, %s, NOW(), %s, %s)
        """, (id, estado_actual, current_user.id, f"Repuesto eliminado: {descripcion}"))
        
        mysql.connection.commit()
        flash('Repuesto eliminado con éxito', 'success')
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al eliminar el repuesto: {str(e)}', 'danger')
    finally:
        cursor.close()
    
    return redirect(url_for('reparaciones.ver', id=id))

@reparaciones_bp.route('/productos/buscar')
@login_required
@empleado_required
def buscar_productos():
    """API para buscar productos para repuestos"""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return {'items': []}
    
    cursor = get_dict_cursor()
    cursor.execute("""
        SELECT id, nombre, precio_venta, stock
        FROM productos
        WHERE (nombre LIKE %s OR codigo_barras LIKE %s) AND activo = TRUE
        LIMIT 10
    """, (f'%{query}%', f'%{query}%'))
    productos = cursor.fetchall()
    cursor.close()
    
    return {'items': [
        {
            'id': producto['id'],
            'text': f"{producto['nombre']} (${producto['precio_venta']} - Stock: {producto['stock']})",
            'precio': float(producto['precio_venta'])
        } 
        for producto in productos
    ]}

@reparaciones_bp.route('/mis-reparaciones')
@login_required
@retry_on_connection_error()
def mis_reparaciones():
    if not hasattr(current_user, 'es_cliente') or not current_user.es_cliente:
        flash('Esta página es solo para clientes', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Obtener las reparaciones del cliente actual
    cursor = None
    try:
        cursor = get_dict_cursor()
        cursor.execute('''
            SELECT r.id, r.electrodomestico, r.marca, r.modelo, r.problema, r.estado,
                   r.fecha_recepcion, r.fecha_entrega_estimada, 
                   e.nombre as tecnico_nombre
            FROM reparaciones r
            LEFT JOIN empleados e ON r.tecnico_id = e.id
            WHERE r.cliente_id = %s
            ORDER BY r.fecha_recepcion DESC
        ''', (current_user.id,))
        reparaciones = cursor.fetchall()
        
        # Formatear fechas para mostrar
        for reparacion in reparaciones:
            if reparacion['fecha_recepcion']:
                reparacion['fecha_recepcion_fmt'] = reparacion['fecha_recepcion'].strftime('%d/%m/%Y')
            else:
                reparacion['fecha_recepcion_fmt'] = 'No disponible'
                
            if reparacion['fecha_entrega_estimada']:
                reparacion['fecha_entrega_estimada_fmt'] = reparacion['fecha_entrega_estimada'].strftime('%d/%m/%Y')
            else:
                reparacion['fecha_entrega_estimada_fmt'] = 'Por determinar'
        
        # Mapeo de estados para mostrar texto amigable
        estados_texto = {
            'RECIBIDO': 'Recibido',
            'DIAGNOSTICO': 'En diagnóstico',
            'REPARACION': 'En reparación',
            'ESPERA_REPUESTOS': 'Esperando repuestos',
            'LISTO': 'Listo para entrega',
            'ENTREGADO': 'Entregado',
            'CANCELADO': 'Cancelado'
        }
        
        # Agregar el texto amigable a cada reparación
        for reparacion in reparaciones:
            reparacion['estado_texto'] = estados_texto.get(reparacion['estado'], reparacion['estado'])
        
        return render_template('reparaciones/mis_reparaciones.html', reparaciones=reparaciones)
    except Exception as e:
        logger.error(f"Error al obtener reparaciones: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Error al obtener reparaciones. Por favor, contacte al soporte técnico.', 'danger')
        return render_template('reparaciones/mis_reparaciones.html', reparaciones=[])
    finally:
        if cursor:
            cursor.close()

@reparaciones_bp.route('/solicitud', methods=['GET', 'POST'])
@retry_on_connection_error()
def solicitud():
    """Página de solicitud de reparación"""
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            nombre = request.form.get('nombre', '')
            email = request.form.get('email', '')
            telefono = request.form.get('telefono', '')
            direccion = request.form.get('direccion', '')
            electrodomestico = request.form.get('electrodomestico', '')
            marca = request.form.get('marca', '')
            modelo = request.form.get('modelo', '')
            problema = request.form.get('problema', '')
            
            # Validar campos requeridos
            if not nombre or not email or not telefono or not electrodomestico or not problema:
                flash('Por favor complete todos los campos obligatorios.', 'danger')
                return render_template('reparaciones/solicitud.html')
            
            # Iniciar conexión a la base de datos
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Verificar si el cliente existe por email
            cursor.execute('SELECT * FROM clientes WHERE email = %s', (email,))
            cliente = cursor.fetchone()
            
            # Si el cliente no existe, lo creamos
            if cliente is None:
                cursor.execute(
                    'INSERT INTO clientes (nombre, email, telefono, direccion) VALUES (%s, %s, %s, %s)',
                    (nombre, email, telefono, direccion)
                )
                mysql.connection.commit()
                
                # Obtener el ID del cliente recién creado
                cursor.execute('SELECT * FROM clientes WHERE email = %s', (email,))
                cliente = cursor.fetchone()
            
            # Determinar el ID del cliente
            cliente_id = cliente['id']
            
            # Verificar si la tabla reparaciones tiene todos los campos necesarios
            try:
                # Intentar insertar con los campos básicos
                cursor.execute(
                    '''INSERT INTO reparaciones 
                       (cliente_id, electrodomestico, marca, modelo, problema, estado, fecha_recepcion, descripcion) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                    (cliente_id, electrodomestico, marca, modelo, problema, 'RECIBIDO', datetime.now(), 
                     f"Solicitud web enviada por {nombre} - {email}")
                )
            except Exception as e:
                logger.error(f"Error en primera inserción: {str(e)}")
                # Si falla, intentar con menos campos
                cursor.execute(
                    '''INSERT INTO reparaciones 
                       (cliente_id, electrodomestico, marca, modelo, estado, fecha_recepcion) 
                       VALUES (%s, %s, %s, %s, %s, %s)''',
                    (cliente_id, electrodomestico, marca, modelo, 'RECIBIDO', datetime.now())
                )
            
            # Obtener el ID de la reparación recién creada
            reparacion_id = cursor.lastrowid
            
            # Intentar registrar en el historial
            try:
                cursor.execute(
                    '''INSERT INTO historial_reparaciones 
                       (reparacion_id, estado_nuevo, descripcion, fecha) 
                       VALUES (%s, %s, %s, %s)''',
                    (reparacion_id, 'RECIBIDO', f"Solicitud web recibida - {problema}", datetime.now())
                )
            except Exception as hist_error:
                logger.error(f"Error al registrar historial: {str(hist_error)}")
                # No interrumpimos el flujo si falla el historial
            
            mysql.connection.commit()
            cursor.close()
            
            # Mostrar mensaje de éxito
            flash('¡Solicitud de reparación enviada con éxito! Nos pondremos en contacto contigo pronto.', 'success')
            
            # Redireccionar a la página de confirmación
            return redirect(url_for('reparaciones.confirmacion'))
            
        except Exception as e:
            # Registrar el error detalladamente
            logger.error(f"Error al procesar solicitud de reparación: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Mostrar mensaje de error
            flash('Ha ocurrido un error al procesar tu solicitud. Por favor, inténtalo de nuevo más tarde.', 'danger')
            
            return render_template('reparaciones/solicitud.html')
    
    return render_template('reparaciones/solicitud.html')

@reparaciones_bp.route('/confirmacion')
def confirmacion():
    """Página de confirmación de solicitud"""
    return render_template('reparaciones/confirmacion.html')

@reparaciones_bp.route('/admin')
@login_required
@empleado_required
@retry_on_connection_error()
def admin():
    """Panel de administración de reparaciones"""
    # Verificar si el usuario tiene permisos adecuados
    if not hasattr(current_user, 'es_admin') or not current_user.es_admin:
        flash('No tienes permisos para acceder a esta sección.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Obtener lista de todas las reparaciones
        cursor = get_dict_cursor()
        
        # Añadir log para depuración
        logger.info("Consultando reparaciones para panel de administración")
        
        cursor.execute('''
            SELECT r.id, r.electrodomestico, r.marca, r.modelo, r.problema, r.estado,
                   r.fecha_recepcion, r.fecha_entrega_estimada, r.cliente_id,
                   c.nombre as nombre_cliente, c.email as email_cliente, c.telefono as telefono_cliente 
            FROM reparaciones r 
            JOIN clientes c ON r.cliente_id = c.id 
            ORDER BY r.fecha_recepcion DESC
        ''')
        
        reparaciones = cursor.fetchall()
        logger.info(f"Se encontraron {len(reparaciones)} reparaciones")
        
        # Formatear fechas para mostrar
        for reparacion in reparaciones:
            # Log de depuración para ver los valores reales
            logger.debug(f"Reparación {reparacion['id']}: estado = '{reparacion['estado']}'")
            
            if reparacion['fecha_recepcion']:
                reparacion['fecha_recepcion_fmt'] = reparacion['fecha_recepcion'].strftime('%d/%m/%Y')
            else:
                reparacion['fecha_recepcion_fmt'] = 'No disponible'
                
            if reparacion['fecha_entrega_estimada']:
                reparacion['fecha_entrega_estimada_fmt'] = reparacion['fecha_entrega_estimada'].strftime('%d/%m/%Y')
            else:
                reparacion['fecha_entrega_estimada_fmt'] = 'Por determinar'
        
        cursor.close()
        
        # Mapeo de estados ampliado para cubrir posibles variaciones
        estados_texto = {
            'RECIBIDO': 'Recibido',
            'DIAGNOSTICO': 'En diagnóstico',
            'REPARACION': 'En reparación',
            'ESPERA_REPUESTOS': 'Esperando repuestos',
            'LISTO': 'Listo para entrega',
            'ENTREGADO': 'Entregado',
            'CANCELADO': 'Cancelado',
            # Versiones en minúscula por si acaso
            'recibido': 'Recibido',
            'diagnostico': 'En diagnóstico',
            'reparacion': 'En reparación',
            'espera_repuestos': 'Esperando repuestos',
            'listo': 'Listo para entrega',
            'entregado': 'Entregado',
            'cancelado': 'Cancelado',
            # Versiones con espacios por si acaso
            'en_revision': 'En Revisión',
            'en revision': 'En Revisión',
            'en_reparacion': 'En Reparación',
            'en reparacion': 'En Reparación',
            'pendiente': 'Pendiente',
            'presupuesto': 'Presupuesto',
            'completada': 'Completada'
        }
        
        # Agregar el texto amigable a cada reparación
        for reparacion in reparaciones:
            estado_original = reparacion['estado']
            reparacion['estado_texto'] = estados_texto.get(estado_original, estado_original)
            
            # No modificar el valor original del estado
            # reparacion['estado'] = reparacion['estado'].lower() if reparacion['estado'] else ''
        
        return render_template('reparaciones/admin.html', reparaciones=reparaciones)
    
    except Exception as e:
        # Registrar el error
        logger.error(f"Error al cargar panel admin de reparaciones: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Mostrar mensaje de error
        flash('Ha ocurrido un error al cargar el panel de administración. Por favor, inténtalo de nuevo más tarde.', 'danger')
        
        return redirect(url_for('main.index'))

@reparaciones_bp.route('/actualizar/<int:id>', methods=['POST'])
@login_required
@retry_on_connection_error()
def actualizar_reparacion(id):
    """Actualizar estado de una reparación"""
    # Verificar si el usuario tiene permisos adecuados
    if not hasattr(current_user, 'es_admin') and not current_user.es_admin:
        flash('No tienes permisos para realizar esta acción.', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Obtener nuevo estado
        nuevo_estado = request.form.get('estado')
        comentario = request.form.get('comentario', '')
        
        if not nuevo_estado:
            flash('El estado es requerido.', 'danger')
            return redirect(url_for('reparaciones.admin'))
        
        # Actualizar estado de la reparación
        cursor = mysql.connection.cursor()
        
        # Primero registrar en el historial
        cursor.execute(
            'INSERT INTO historial_reparaciones (reparacion_id, estado_anterior, estado_nuevo, comentario, fecha_cambio, usuario_id) ' +
            'SELECT %s, estado, %s, %s, %s, %s FROM reparaciones WHERE id = %s',
            (id, nuevo_estado, comentario, datetime.now(), current_user.id, id)
        )
        
        # Luego actualizar el estado actual
        cursor.execute(
            'UPDATE reparaciones SET estado = %s, fecha_actualizacion = %s WHERE id = %s',
            (nuevo_estado, datetime.now(), id)
        )
        
        mysql.connection.commit()
        cursor.close()
        
        flash('Estado de reparación actualizado con éxito.', 'success')
        
    except Exception as e:
        # Registrar el error
        logger.error(f"Error al actualizar reparación: {str(e)}")
        
        # Mostrar mensaje de error
        flash('Ha ocurrido un error al actualizar la reparación. Por favor, inténtalo de nuevo más tarde.', 'danger')
    
    return redirect(url_for('reparaciones.admin'))

@reparaciones_bp.route('/tecnico/reparaciones', methods=['GET'])
@login_required
def por_tecnico():
    # Verificar que es un técnico
    if not hasattr(current_user, 'cargo_id') or current_user.cargo_nombre != 'Técnico':
        flash('No tienes permiso para acceder a esta página', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtener reparaciones asignadas al técnico
    cursor.execute('''
        SELECT r.*, 
            c.nombre as cliente_nombre, 
            c.telefono as cliente_telefono,
            e.nombre as tecnico_nombre,
            CASE 
                WHEN r.estado = 'RECIBIDO' THEN 'Recibido'
                WHEN r.estado = 'DIAGNOSTICO' THEN 'En diagnóstico'
                WHEN r.estado = 'ESPERA_REPUESTOS' THEN 'Esperando repuestos'
                WHEN r.estado = 'REPARACION' THEN 'En reparación'
                WHEN r.estado = 'LISTO' THEN 'Listo para entregar'
                WHEN r.estado = 'ENTREGADO' THEN 'Entregado'
                WHEN r.estado = 'CANCELADO' THEN 'Cancelado'
                ELSE r.estado
            END as estado_texto
        FROM reparaciones r
        LEFT JOIN clientes c ON r.cliente_id = c.id
        LEFT JOIN empleados e ON r.tecnico_id = e.id
        WHERE r.tecnico_id = ?
        ORDER BY 
            CASE 
                WHEN r.estado = 'RECIBIDO' THEN 1
                WHEN r.estado = 'DIAGNOSTICO' THEN 2
                WHEN r.estado = 'ESPERA_REPUESTOS' THEN 3
                WHEN r.estado = 'REPARACION' THEN 4
                WHEN r.estado = 'LISTO' THEN 5
                WHEN r.estado = 'ENTREGADO' THEN 6
                WHEN r.estado = 'CANCELADO' THEN 7
                ELSE 8
            END,
            r.fecha_recepcion DESC
    ''', (current_user.id,))
    reparaciones = cursor.fetchall()
    
    # Estadísticas del técnico
    # Total de reparaciones asignadas
    cursor.execute('''
        SELECT COUNT(*) as total FROM reparaciones
        WHERE tecnico_id = ?
    ''', (current_user.id,))
    result = cursor.fetchone()
    reparaciones_totales = result['total'] if result else 0
    
    # Reparaciones en progreso
    cursor.execute('''
        SELECT COUNT(*) as total FROM reparaciones
        WHERE tecnico_id = ? AND estado IN ('DIAGNOSTICO', 'REPARACION', 'ESPERA_REPUESTOS')
    ''', (current_user.id,))
    result = cursor.fetchone()
    reparaciones_progreso = result['total'] if result else 0
    
    # Reparaciones completadas
    cursor.execute('''
        SELECT COUNT(*) as total FROM reparaciones
        WHERE tecnico_id = ? AND estado IN ('LISTO', 'ENTREGADO')
    ''', (current_user.id,))
    result = cursor.fetchone()
    reparaciones_completadas = result['total'] if result else 0
    
    # Cálculo de eficiencia (% de reparaciones completadas)
    eficiencia = 'N/A'
    if reparaciones_totales > 0:
        eficiencia = f"{(reparaciones_completadas / reparaciones_totales) * 100:.0f}%"
    
    conn.close()
    
    return render_template('reparaciones/reparaciones_tecnico.html', 
        reparaciones=reparaciones,
        reparaciones_totales=reparaciones_totales,
        reparaciones_progreso=reparaciones_progreso,
        reparaciones_completadas=reparaciones_completadas,
        eficiencia=eficiencia
    )

def crear_reparacion():
    """Procesar el formulario de nueva reparación"""
    try:
        form = ReparacionForm()
        if form.validate_on_submit():
            # Crear una nueva reparación
            estado = 'Recibido'
            
            # Obtener datos del formulario
            fecha_recepcion = datetime.now()
            cliente_id = form.cliente_id.data
            electrodomestico = form.electrodomestico.data
            marca = form.marca.data
            modelo = form.modelo.data
            num_serie = form.num_serie.data
            problema = form.problema.data
            descripcion = form.descripcion.data
            
            # Insertar en la base de datos
            cursor = mysql.connection.cursor()
            sql = """
                INSERT INTO reparaciones 
                (cliente_id, electrodomestico, marca, modelo, num_serie, problema, descripcion, estado, fecha_recepcion) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (cliente_id, electrodomestico, marca, modelo, num_serie, problema, descripcion, estado, fecha_recepcion))
            reparacion_id = cursor.lastrowid
            
            # Registro en historial
            sql_historial = """
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado, fecha, comentario) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql_historial, (reparacion_id, estado, fecha_recepcion, "Recepción inicial del equipo"))
            
            mysql.connection.commit()
            cursor.close()
            
            flash('Solicitud de reparación registrada correctamente', 'success')
            return redirect(url_for('reparaciones.admin'))
        else:
            # Si hay errores en el formulario
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en {field}: {error}', 'error')
            
        # Si es GET o hay errores en el formulario
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT id, nombre, apellido FROM clientes ORDER BY nombre')
        clientes = cursor.fetchall()
        cursor.close()
        
        return render_template('reparaciones/nueva.html', form=form, clientes=clientes)
    
    except Exception as e:
        current_app.logger.error(f"Error al crear reparación: {str(e)}")
        flash('Ocurrió un error al procesar la solicitud', 'error')
        return redirect(url_for('reparaciones.admin'))

@reparaciones_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_reparacion_tecnico(id):
    if not current_user.es_tecnico:
        flash('No tienes permiso para editar reparaciones.', 'danger')
        return redirect(url_for('reparaciones.lista'))

    # Lógica para editar la reparación
    # Obtener detalles de la reparación
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM reparaciones WHERE id = %s', (id,))
    reparacion = cursor.fetchone()

    if request.method == 'POST':
        # Actualizar detalles de la reparación
        estado = request.form.get('estado')
        precio = request.form.get('precio')
        cursor.execute('UPDATE reparaciones SET estado = %s, precio = %s WHERE id = %s', (estado, precio, id))
        mysql.connection.commit()
        flash('Reparación actualizada con éxito', 'success')
        return redirect(url_for('reparaciones.lista'))

    return render_template('reparaciones/editar.html', reparacion=reparacion)

@reparaciones_bp.route('/actualizar-estado/<int:id>', methods=['GET', 'POST'])
@login_required
def actualizar_estado(id):
    """Permite al técnico actualizar el estado de una reparación"""
    # Verificar si el usuario es técnico
    if not hasattr(current_user, 'cargo_id'):
        flash('Acceso denegado: No se encontró información del cargo.', 'danger')
        return redirect(url_for('main.index'))
    
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT c.nombre FROM cargos c
        INNER JOIN empleados e ON c.id = e.cargo_id
        WHERE e.id = %s
    """, (current_user.id,))
    result = cursor.fetchone()
    
    if not result:
        flash('No se encontró información del cargo en la base de datos', 'danger')
        return redirect(url_for('main.dashboard'))
    
    print(f"Resultado de la consulta del cargo: {result}")
    
    if result[0] != 'Técnico':
        flash('Esta página es solo para técnicos', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Obtener la reparación
    cursor = get_dict_cursor()
    cursor.execute('''
        SELECT r.*, c.nombre as cliente_nombre,
               r.electrodomestico as tipo_aparato,
               r.problema as descripcion_problema,
               r.diagnostico
        FROM reparaciones r
        LEFT JOIN clientes c ON r.cliente_id = c.id
        WHERE r.id = %s AND r.tecnico_id = %s
    ''', (id, current_user.id))
    reparacion = cursor.fetchone()
    
    if not reparacion:
        flash('Reparación no encontrada o no asignada a ti', 'danger')
        return redirect(url_for('reparaciones.por_tecnico'))
    
    # Mapeo de estados para mostrar texto amigable
    estados_texto = {
        'RECIBIDO': 'Recibido',
        'DIAGNOSTICO': 'En diagnóstico',
        'REPARACION': 'En reparación',
        'ESPERA_REPUESTOS': 'Esperando repuestos',
        'LISTO': 'Listo para entrega',
        'ENTREGADO': 'Entregado',
        'CANCELADO': 'Cancelado'
    }
    
    # Obtener estados posibles basados en el estado actual
    estados_siguiente = {
        'RECIBIDO': ['DIAGNOSTICO', 'CANCELADO'],
        'DIAGNOSTICO': ['REPARACION', 'ESPERA_REPUESTOS', 'LISTO', 'CANCELADO'],
        'REPARACION': ['ESPERA_REPUESTOS', 'LISTO', 'CANCELADO'],
        'ESPERA_REPUESTOS': ['REPARACION', 'LISTO', 'CANCELADO'],
        'LISTO': ['ENTREGADO']
    }
    
    # Procesar actualización de estado si es POST
    if request.method == 'POST':
        # Obtener datos del formulario
        nuevo_estado = request.form.get('estado')
        diagnostico = request.form.get('diagnostico', '')
        comentario = request.form.get('comentario', '')
        
        # Validar que el nuevo estado sea válido
        estados_permitidos = estados_siguiente.get(reparacion['estado'], [])
        
        if nuevo_estado not in estados_permitidos:
            flash(f'El estado {nuevo_estado} no es válido para esta reparación', 'danger')
            return redirect(url_for('reparaciones.actualizar_estado', id=id))
        
        try:
            # Actualizar estado de la reparación
            cursor.execute('''
                UPDATE reparaciones 
                SET estado = %s, 
                    diagnostico = COALESCE(%s, diagnostico),
                    fecha_actualizacion = NOW()
                WHERE id = %s
            ''', (nuevo_estado, diagnostico if diagnostico else None, id))
            
            # Registrar en el historial
            cursor.execute('''
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado, fecha, tecnico_id, comentario) 
                VALUES (%s, %s, NOW(), %s, %s)
            ''', (id, nuevo_estado, current_user.id, comentario))
            
            mysql.connection.commit()
            
            # Notificar al cliente si el estado es LISTO
            if nuevo_estado == 'LISTO':
                try:
                    # Obtener datos del cliente
                    cursor.execute('''
                        SELECT c.nombre, c.telefono, r.electrodomestico
                        FROM reparaciones r
                        JOIN clientes c ON r.cliente_id = c.id
                        WHERE r.id = %s
                    ''', (id,))
                    cliente_datos = cursor.fetchone()
                    
                    if cliente_datos and cliente_datos['telefono']:
                        # Si existe la función de WhatsApp, enviar notificación
                        if 'whatsapp_bp' in current_app.blueprints:
                            from routes.whatsapp import enviar_mensaje_whatsapp
                            mensaje = f"Hola {cliente_datos['nombre']}, tu reparación del {cliente_datos['electrodomestico']} está lista para recoger. Por favor, pasa por nuestra tienda. ¡Gracias!"
                            try:
                                enviar_mensaje_whatsapp(cliente_datos['telefono'], mensaje)
                                print(f"Mensaje WhatsApp enviado a {cliente_datos['telefono']}")
                            except Exception as e:
                                print(f"Error al enviar WhatsApp: {e}")
                except Exception as e:
                    print(f"Error al notificar cliente: {e}")
            
            flash(f'Estado actualizado a {estados_texto.get(nuevo_estado, nuevo_estado)}', 'success')
            return redirect(url_for('reparaciones.por_tecnico'))
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al actualizar estado: {e}', 'danger')
            print(f"Error en actualización de estado: {e}")
            return redirect(url_for('reparaciones.actualizar_estado', id=id))
    
    # Preparar lista de estados para la vista
    estados_disponibles = []
    for estado in estados_siguiente.get(reparacion['estado'], []):
        estados_disponibles.append({
            'valor': estado,
            'texto': estados_texto.get(estado, estado)
        })
    
    # Renderizar la plantilla con los datos
    return render_template('reparaciones/actualizar_estado.html', 
                           reparacion=reparacion,
                           estado_actual=estados_texto.get(reparacion['estado'], reparacion['estado']),
                           estados=estados_disponibles)

@reparaciones_bp.route('/actualizar-diagnostico/<int:id>', methods=['POST'])
@login_required
def actualizar_diagnostico(id):
    """Permite al técnico actualizar el diagnóstico y datos de la reparación"""
    # Verificar si el usuario es técnico
    if not hasattr(current_user, 'cargo_id'):
        flash('Acceso denegado: No se encontró información del cargo.', 'danger')
        return redirect(url_for('main.index'))
    
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT c.nombre FROM cargos c
        INNER JOIN empleados e ON c.id = e.cargo_id
        WHERE e.id = %s
    """, (current_user.id,))
    result = cursor.fetchone()
    
    if not result or result[0] != 'Técnico':
        flash('Esta página es solo para técnicos', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Obtener datos del formulario
    diagnostico = request.form.get('diagnostico', '')
    estado = request.form.get('estado', '')
    fecha_entrega_estimada = request.form.get('fecha_entrega_estimada', None)
    costo_estimado = request.form.get('costo_estimado', 0)
    costo_final = request.form.get('costo_final', 0)
    notas = request.form.get('notas', '')
    
    try:
        # Convertir a valores numéricos
        if costo_estimado:
            costo_estimado = float(costo_estimado)
        else:
            costo_estimado = 0
            
        if costo_final:
            costo_final = float(costo_final)
        else:
            costo_final = 0
            
        # Obtener el estado actual para el historial
        cursor = get_dict_cursor()
        cursor.execute("SELECT estado FROM reparaciones WHERE id = %s", (id,))
        reparacion = cursor.fetchone()
        
        if not reparacion:
            flash('Reparación no encontrada', 'danger')
            return redirect(url_for('reparaciones.por_tecnico'))
        
        estado_anterior = reparacion['estado']
        
        # Actualizar la reparación
        cursor.execute("""
            UPDATE reparaciones 
            SET diagnostico = %s, 
                estado = %s, 
                fecha_entrega_estimada = %s,
                costo_estimado = %s,
                costo_final = %s,
                notas = %s,
                fecha_actualizacion = NOW()
            WHERE id = %s
        """, (diagnostico, estado, fecha_entrega_estimada, costo_estimado, costo_final, notas, id))
        
        # Si cambió el estado, registrar en el historial
        if estado != estado_anterior:
            cursor.execute("""
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado, fecha, tecnico_id, comentario) 
                VALUES (%s, %s, NOW(), %s, %s)
            """, (id, estado, current_user.id, f"Actualización de diagnóstico y cambio de estado a {estado}"))
        else:
            # Si solo se actualizó el diagnóstico
            cursor.execute("""
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado, fecha, tecnico_id, comentario) 
                VALUES (%s, %s, NOW(), %s, %s)
            """, (id, estado, current_user.id, "Actualización de diagnóstico"))
        
        mysql.connection.commit()
        flash('Diagnóstico actualizado correctamente', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al actualizar diagnóstico: {e}', 'danger')
        print(f"Error en actualización de diagnóstico: {e}")
    
    return redirect(url_for('reparaciones.ver', id=id))

@reparaciones_bp.route('/enviar-mensaje/<int:id>', methods=['POST'])
@login_required
def enviar_mensaje(id):
    """Envía un mensaje por WhatsApp al cliente sobre el estado de la reparación"""
    # Verificar permisos
    if not hasattr(current_user, 'cargo_id'):
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener datos de la reparación y el cliente
    cursor = get_dict_cursor()
    cursor.execute("""
        SELECT r.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
        FROM reparaciones r
        JOIN clientes c ON r.cliente_id = c.id
        WHERE r.id = %s
    """, (id,))
    reparacion = cursor.fetchone()
    
    if not reparacion:
        flash('Reparación no encontrada', 'danger')
        return redirect(url_for('reparaciones.por_tecnico'))
    
    # Verificar que haya un número de teléfono
    if not reparacion['cliente_telefono']:
        flash('El cliente no tiene un número de teléfono registrado', 'danger')
        return redirect(url_for('reparaciones.ver', id=id))
    
    # Obtener tipo de mensaje y texto
    tipo_mensaje = request.form.get('tipo_mensaje', 'actualizacion')
    mensaje_final = ""
    
    if tipo_mensaje == 'personalizado':
        mensaje_final = request.form.get('mensaje_personalizado', '')
    else:
        # Construir mensaje según el tipo
        if tipo_mensaje == 'actualizacion':
            mensaje_final = f"Hola {reparacion['cliente_nombre']}, le informamos que su {reparacion['electrodomestico']} " \
                           f"está en estado {reparacion['estado']}. Gracias por confiar en nosotros."
        elif tipo_mensaje == 'presupuesto':
            mensaje_final = f"Hola {reparacion['cliente_nombre']}, hemos diagnosticado su {reparacion['electrodomestico']}. " \
                           f"El presupuesto estimado es de ${reparacion['costo_estimado'] or '0'}. " \
                           f"Por favor, confírmenos si desea proceder con la reparación."
        elif tipo_mensaje == 'listo':
            mensaje_final = f"Hola {reparacion['cliente_nombre']}, su {reparacion['electrodomestico']} " \
                           f"ya está reparado y listo para recoger. El costo final es de ${reparacion['costo_final'] or '0'}. " \
                           f"Le esperamos en nuestra tienda. ¡Gracias por su confianza!"
    
    try:
        # Verificar si el servicio de WhatsApp está configurado
        if 'whatsapp_bp' in current_app.blueprints:
            from routes.whatsapp import enviar_mensaje_whatsapp
            
            # Intentar enviar el mensaje
            resultado = enviar_mensaje_whatsapp(reparacion['cliente_telefono'], mensaje_final)
            
            # Registrar el mensaje en la base de datos
            cursor.execute("""
                INSERT INTO whatsapp_mensajes 
                (telefono, mensaje, tipo_mensaje, objeto_tipo, objeto_id, fecha_envio) 
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (reparacion['cliente_telefono'], mensaje_final, tipo_mensaje, 'reparacion', id))
            
            # Registrar en el historial
            cursor.execute("""
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado, fecha, tecnico_id, comentario) 
                VALUES (%s, %s, NOW(), %s, %s)
            """, (id, reparacion['estado'], current_user.id, f"Mensaje enviado al cliente: {tipo_mensaje}"))
            
            mysql.connection.commit()
            flash('Mensaje enviado con éxito', 'success')
        else:
            flash('El sistema de WhatsApp no está configurado', 'warning')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al enviar mensaje: {e}', 'danger')
        print(f"Error al enviar mensaje WhatsApp: {e}")
    
    return redirect(url_for('reparaciones.ver', id=id))

@reparaciones_bp.route('/detalle/<int:id>', methods=['GET'])
@login_required
def detalle(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtener información de la reparación
    cursor.execute('''
        SELECT r.*, 
            c.nombre as cliente_nombre, 
            c.telefono as cliente_telefono,
            e.nombre as tecnico_nombre
        FROM reparaciones r
        LEFT JOIN clientes c ON r.cliente_id = c.id
        LEFT JOIN empleados e ON r.tecnico_id = e.id
        WHERE r.id = ?
    ''', (id,))
    reparacion = cursor.fetchone()
    
    if not reparacion:
        conn.close()
        flash('Reparación no encontrada', 'error')
        return redirect(url_for('reparaciones.lista'))
    
    # Verificar permisos
    if current_user.es_cliente and current_user.id != reparacion['cliente_id']:
        conn.close()
        flash('No tienes permiso para ver esta reparación', 'error')
        return redirect(url_for('reparaciones.mis_reparaciones'))
    
    # Obtener historial
    cursor.execute('''
        SELECT * FROM historial_reparaciones
        WHERE reparacion_id = ?
        ORDER BY fecha DESC
    ''', (id,))
    historial = cursor.fetchall()
    
    # Obtener repuestos
    cursor.execute('''
        SELECT rr.*, p.nombre as producto_nombre
        FROM reparaciones_repuestos rr
        LEFT JOIN productos p ON rr.producto_id = p.id
        WHERE rr.reparacion_id = ?
    ''', (id,))
    repuestos = cursor.fetchall()
    
    # Obtener mensajes
    cursor.execute('''
        SELECT * FROM whatsapp_mensajes
        WHERE reparacion_id = ?
        ORDER BY fecha DESC
    ''', (id,))
    mensajes = cursor.fetchall()
    
    # Obtener lista de técnicos para asignación
    cursor.execute('''
        SELECT id, nombre FROM empleados 
        WHERE cargo_id = (SELECT id FROM cargos WHERE nombre = 'Técnico')
    ''')
    tecnicos = cursor.fetchall()
    
    # Si el usuario es técnico, obtener estadísticas
    reparaciones_totales = 0
    reparaciones_progreso = 0
    reparaciones_completadas = 0
    eficiencia = 'N/A'
    
    if hasattr(current_user, 'cargo_id') and current_user.cargo_nombre == 'Técnico':
        # Total de reparaciones asignadas al técnico
        cursor.execute('''
            SELECT COUNT(*) as total FROM reparaciones
            WHERE tecnico_id = ?
        ''', (current_user.id,))
        result = cursor.fetchone()
        reparaciones_totales = result['total'] if result else 0
        
        # Reparaciones en progreso
        cursor.execute('''
            SELECT COUNT(*) as total FROM reparaciones
            WHERE tecnico_id = ? AND estado IN ('DIAGNOSTICO', 'REPARACION', 'ESPERA_REPUESTOS')
        ''', (current_user.id,))
        result = cursor.fetchone()
        reparaciones_progreso = result['total'] if result else 0
        
        # Reparaciones completadas
        cursor.execute('''
            SELECT COUNT(*) as total FROM reparaciones
            WHERE tecnico_id = ? AND estado IN ('LISTO', 'ENTREGADO')
        ''', (current_user.id,))
        result = cursor.fetchone()
        reparaciones_completadas = result['total'] if result else 0
        
        # Cálculo de eficiencia (% de reparaciones completadas)
        if reparaciones_totales > 0:
            eficiencia = f"{(reparaciones_completadas / reparaciones_totales) * 100:.0f}%"
    
    conn.close()
    
    # Estados disponibles para la reparación
    estados = {
        'RECIBIDO': 'Recibido',
        'DIAGNOSTICO': 'En diagnóstico',
        'ESPERA_REPUESTOS': 'Esperando repuestos',
        'REPARACION': 'En reparación',
        'LISTO': 'Listo para entregar',
        'ENTREGADO': 'Entregado',
        'CANCELADO': 'Cancelado'
    }
    
    return render_template('reparaciones/detalle.html', 
        reparacion=reparacion,
        historial=historial,
        repuestos=repuestos,
        mensajes=mensajes,
        tecnicos=tecnicos,
        estados=estados,
        reparaciones_totales=reparaciones_totales,
        reparaciones_progreso=reparaciones_progreso,
        reparaciones_completadas=reparaciones_completadas,
        eficiencia=eficiencia
    ) 