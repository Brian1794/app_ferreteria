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
            (reparacion_id, descripcion, usuario_id, fecha)
            VALUES (%s, %s, %s, NOW())
        """, (id, f"Repuesto agregado: {repuesto_descripcion} (Cantidad: {cantidad}, Subtotal: ${subtotal})", current_user.id))
        
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
            (reparacion_id, descripcion, usuario_id, fecha)
            VALUES (%s, %s, %s, NOW())
        """, (id, f"Repuesto eliminado: {descripcion}", current_user.id))
        
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

@reparaciones_bp.route('/por-tecnico')
@login_required
def por_tecnico():
    """Muestra las reparaciones asignadas al técnico actual"""
    if not hasattr(current_user, 'cargo_id'):
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Verificar si el usuario es técnico
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
    
    # Obtener reparaciones asignadas al técnico
    cursor = get_dict_cursor()
    cursor.execute('''
        SELECT r.*, c.nombre as cliente_nombre,
               DATE_FORMAT(r.fecha_recepcion, '%d/%m/%Y') as fecha_recepcion,
               DATE_FORMAT(r.fecha_entrega_estimada, '%d/%m/%Y') as fecha_entrega_estimada
        FROM reparaciones r
        LEFT JOIN clientes c ON r.cliente_id = c.id
        WHERE r.tecnico_id = %s AND r.estado NOT IN ('ENTREGADO', 'CANCELADO')
        ORDER BY 
            CASE 
                WHEN r.estado = 'LISTO' THEN 1
                WHEN r.estado = 'REPARACION' THEN 2
                WHEN r.estado = 'DIAGNOSTICO' THEN 3
                WHEN r.estado = 'RECIBIDO' THEN 4
                WHEN r.estado = 'ESPERA_REPUESTOS' THEN 5
                ELSE 6
            END,
            r.fecha_entrega_estimada ASC
    ''', (current_user.id,))
    reparaciones = cursor.fetchall()
    cursor.close()
    
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
    
    return render_template('reparaciones/por_tecnico.html', reparaciones=reparaciones)

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