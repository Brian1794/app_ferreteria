from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify, abort
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

# Definir el decorador admin_required
def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_admin:
            flash('Esta sección es solo para administradores', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@reparaciones_bp.route('/')
def index():
    """Página principal de servicio de reparaciones accesible para todos los usuarios"""
    try:
        # Verificar la conexión a la base de datos
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        
        return render_template('reparaciones/index.html')
    except Exception as e:
        logger.error(f"Error al cargar la página de reparaciones: {str(e)}")
        flash("Error al cargar la página. Por favor, inténtelo de nuevo más tarde.", "error")
        return redirect(url_for('main.index'))

@reparaciones_bp.before_request
def before_request():
    """Se ejecuta antes de cada solicitud al blueprint de reparaciones"""
    try:
        # Verificar la conexión a la base de datos
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
    except Exception as e:
        logger.error(f"Error de conexión a la base de datos en reparaciones: {str(e)}")
        flash("Error de conexión. Por favor, inténtelo de nuevo más tarde.", "error")
        return redirect(url_for('main.index'))

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

@reparaciones_bp.route('/ver/<int:id>', methods=['GET', 'POST'])
@login_required
def ver(id):
    """Ver detalles de una reparación y permitir comunicación con el cliente"""
    try:
        if not id:
            flash('ID de reparación no válido', 'danger')
            return redirect(url_for('reparaciones.admin_dashboard'))
            
        # Obtener detalles de la reparación
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Consultar la reparación con manejo de errores
        try:
            cursor.execute("""
                SELECT r.*, 
                       c.nombre as nombre_cliente, c.telefono as telefono_cliente, c.email as email_cliente, c.id as cliente_id,
                       e.nombre as nombre_tecnico, e.id as tecnico_id
                FROM reparaciones r
                LEFT JOIN clientes c ON r.cliente_id = c.id
                LEFT JOIN empleados e ON r.tecnico_id = e.id
                WHERE r.id = %s
            """, (id,))
            
            reparacion = cursor.fetchone()
            
            if not reparacion:
                flash('Reparación no encontrada', 'danger')
                return redirect(url_for('reparaciones.admin_dashboard'))
        except Exception as db_error:
            print(f"Error al consultar la reparación: {db_error}")
            flash('Error al cargar los datos de la reparación', 'danger')
            return redirect(url_for('reparaciones.admin_dashboard'))
        
        # Verificar permisos - Solo el técnico asignado o administradores
        is_admin = hasattr(current_user, 'es_admin') and current_user.es_admin
        is_tecnico = hasattr(current_user, 'cargo_nombre') and current_user.cargo_nombre == 'Técnico'
        is_cliente = hasattr(current_user, 'es_cliente') and current_user.es_cliente
        
        if not is_admin and not is_tecnico and not is_cliente:
            flash('No tienes permiso para ver esta reparación', 'danger')
            return redirect(url_for('reparaciones.admin_dashboard'))
        
        # Si es cliente, verificar que sea el dueño de la reparación
        if is_cliente and reparacion['cliente_id'] != current_user.id:
            flash('No tienes permiso para ver esta reparación', 'danger')
            return redirect(url_for('reparaciones.mis_reparaciones'))
        
        # Si es técnico, verificar que sea el asignado (a menos que sea administrador)
        if is_tecnico and not is_admin and reparacion['tecnico_id'] and reparacion['tecnico_id'] != current_user.id:
            flash('No estás asignado a esta reparación', 'danger')
            return redirect(url_for('reparaciones.por_tecnico'))
        
        # Mapeo de estados a colores
        estados_colores = {
            'RECIBIDO': 'ffc107',     # Amarillo
            'DIAGNOSTICO': '17a2b8',  # Azul claro
            'REPARACION': '007bff',   # Azul
            'ESPERA_REPUESTOS': '6c757d', # Gris
            'LISTO': '28a745',        # Verde
            'ENTREGADO': '343a40',    # Negro
            'CANCELADO': 'dc3545'     # Rojo
        }
        
        # Mapeo de estados a nombres amigables
        estados_nombres = {
            'RECIBIDO': 'Recibido',
            'DIAGNOSTICO': 'En diagnóstico',
            'REPARACION': 'En reparación',
            'ESPERA_REPUESTOS': 'Esperando repuestos',
            'LISTO': 'Listo para entregar',
            'ENTREGADO': 'Entregado',
            'CANCELADO': 'Cancelado'
        }
        
        # Asignar valores por defecto si no existen
        reparacion = reparacion or {}
        
        # Agregar color y nombre amigable a la reparación
        estado = reparacion.get('estado', 'RECIBIDO')
        reparacion['estado_color'] = estados_colores.get(estado, 'ffc107')
        reparacion['estado_nombre'] = estados_nombres.get(estado, 'Pendiente')
        
        # Obtener historial de mensajes (comunicación entre técnico y cliente)
        mensajes = []
        try:
            cursor.execute("""
                SELECT m.*, 
                       CASE 
                           WHEN m.remitente_tipo = 'cliente' THEN c.nombre
                           WHEN m.remitente_tipo = 'tecnico' THEN e.nombre
                           ELSE 'Sistema'
                       END as remitente_nombre
                FROM mensajes_reparacion m
                LEFT JOIN clientes c ON m.remitente_id = c.id AND m.remitente_tipo = 'cliente'
                LEFT JOIN empleados e ON m.remitente_id = e.id AND m.remitente_tipo = 'tecnico'
                WHERE m.reparacion_id = %s
                ORDER BY m.fecha_creacion ASC
            """, (id,))
            
            mensajes = cursor.fetchall() or []
        except Exception as msg_error:
            print(f"Error al cargar mensajes: {msg_error}")
            # No bloqueamos la carga de la página por errores en los mensajes
            mensajes = []
        
        # Procesar mensaje si se envió uno
        if request.method == 'POST':
            mensaje = request.form.get('mensaje', '').strip()
            
            if mensaje:
                # Verificar si existe la tabla mensajes_reparacion
                cursor.execute("SHOW TABLES LIKE 'mensajes_reparacion'")
                if not cursor.fetchone():
                    # Crear tabla de mensajes
                    cursor.execute("""
                        CREATE TABLE mensajes_reparacion (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            reparacion_id INT NOT NULL,
                            remitente_id INT NOT NULL,
                            remitente_tipo VARCHAR(10) NOT NULL,
                            mensaje TEXT NOT NULL,
                            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    mysql.connection.commit()
                
                # Determinar tipo de remitente
                remitente_tipo = 'cliente' if current_user.es_cliente else 'tecnico'
                
                # Insertar mensaje
                cursor.execute("""
                    INSERT INTO mensajes_reparacion 
                    (reparacion_id, remitente_id, remitente_tipo, mensaje)
                    VALUES (%s, %s, %s, %s)
                """, (id, current_user.id, remitente_tipo, mensaje))
                
                mysql.connection.commit()
                
                # Crear notificación para el destinatario
                if remitente_tipo == 'tecnico' and reparacion['cliente_id']:
                    # Enviar notificación al cliente
                    try:
                        # Verificar si existe la tabla notificaciones
                        cursor.execute("SHOW TABLES LIKE 'notificaciones'")
                        if not cursor.fetchone():
                            # Crear tabla de notificaciones
                            cursor.execute("""
                                CREATE TABLE notificaciones (
                                    id INT AUTO_INCREMENT PRIMARY KEY,
                                    remitente_id INT NOT NULL,
                                    destinatario_id INT NOT NULL,
                                    tipo VARCHAR(20) NOT NULL,
                                    titulo VARCHAR(255) NOT NULL,
                                    mensaje TEXT NOT NULL,
                                    url VARCHAR(255) DEFAULT '#',
                                    icono VARCHAR(50) DEFAULT 'bell',
                                    leida BOOLEAN DEFAULT FALSE,
                                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    fecha_lectura TIMESTAMP NULL
                                )
                            """)
                            mysql.connection.commit()
                        
                        # Insertar notificación para el cliente
                        titulo = f"Mensaje del técnico sobre tu reparación #{id}"
                        url = url_for('reparaciones.ver', id=id)
                        
                        cursor.execute("""
                            INSERT INTO notificaciones 
                            (remitente_id, destinatario_id, tipo, titulo, mensaje, url, icono)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (current_user.id, reparacion['cliente_id'], 'mensaje', titulo, mensaje, url, 'comment'))
                        
                        mysql.connection.commit()
                    except Exception as e:
                        print(f"Error al crear notificación: {e}")
                
                elif remitente_tipo == 'cliente' and reparacion['tecnico_id']:
                    # Enviar notificación al técnico
                    try:
                        # Verificar si existe la tabla notificaciones
                        cursor.execute("SHOW TABLES LIKE 'notificaciones'")
                        if not cursor.fetchone():
                            # Crear tabla de notificaciones
                            cursor.execute("""
                                CREATE TABLE notificaciones (
                                    id INT AUTO_INCREMENT PRIMARY KEY,
                                    remitente_id INT NOT NULL,
                                    destinatario_id INT NOT NULL,
                                    tipo VARCHAR(20) NOT NULL,
                                    titulo VARCHAR(255) NOT NULL,
                                    mensaje TEXT NOT NULL,
                                    url VARCHAR(255) DEFAULT '#',
                                    icono VARCHAR(50) DEFAULT 'bell',
                                    leida BOOLEAN DEFAULT FALSE,
                                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    fecha_lectura TIMESTAMP NULL
                                )
                            """)
                            mysql.connection.commit()
                        
                        # Insertar notificación para el técnico
                        titulo = f"Mensaje del cliente sobre la reparación #{id}"
                        url = url_for('reparaciones.ver', id=id)
                        
                        cursor.execute("""
                            INSERT INTO notificaciones 
                            (remitente_id, destinatario_id, tipo, titulo, mensaje, url, icono)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (current_user.id, reparacion['tecnico_id'], 'mensaje', titulo, mensaje, url, 'comment'))
                        
                        mysql.connection.commit()
                    except Exception as e:
                        print(f"Error al crear notificación: {e}")
                
                # Recargar mensajes
                cursor.execute("""
                    SELECT m.*, 
                        CASE 
                            WHEN m.remitente_tipo = 'cliente' THEN c.nombre
                            WHEN m.remitente_tipo = 'tecnico' THEN CONCAT(e.nombre, ' ', COALESCE(e.apellido, ''))
                            ELSE 'Sistema'
                        END as remitente_nombre
                    FROM mensajes_reparacion m
                    LEFT JOIN clientes c ON m.remitente_id = c.id AND m.remitente_tipo = 'cliente'
                    LEFT JOIN empleados e ON m.remitente_id = e.id AND m.remitente_tipo = 'tecnico'
                    WHERE m.reparacion_id = %s
                    ORDER BY m.fecha_creacion ASC
                """, (id,))
                
                mensajes = cursor.fetchall()
                
                flash('Mensaje enviado correctamente', 'success')
        
        cursor.close()
        
        # Lista de posibles estados para el técnico
        estados = {
            'RECIBIDO': 'Recibido',
            'DIAGNOSTICO': 'En diagnóstico',
            'REPARACION': 'En reparación',
            'ESPERA_REPUESTOS': 'Esperando repuestos',
            'LISTO': 'Listo para entregar',
            'ENTREGADO': 'Entregado',
            'CANCELADO': 'Cancelado'
        }
        
        return render_template(
            'reparaciones/ver.html', 
            reparacion=reparacion, 
            mensajes=mensajes,
            estados=estados,
            es_tecnico=(hasattr(current_user, 'cargo_nombre') and current_user.cargo_nombre == 'Técnico'),
            es_cliente=current_user.es_cliente
        )
        
    except Exception as e:
        print(f"Error al ver reparación: {e}")
        flash('Error al cargar los detalles de la reparación', 'danger')
        return redirect(url_for('main.dashboard'))

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
def mis_reparaciones():
    """Muestra las reparaciones asignadas al técnico actual"""
    try:
        # Obtener el filtro de la URL
        filtro = request.args.get('filtro', 'todos')
        
        # Verificar si el usuario actual es un técnico
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT e.id FROM empleados e 
            JOIN cargos c ON e.cargo_id = c.id 
            WHERE e.id = %s AND c.nombre = 'Técnico'
        """, (current_user.id,))
        
        if not cursor.fetchone():
            flash('No tienes permisos para acceder a esta sección', 'danger')
            return redirect(url_for('main.index'))
        
        # Preparar la consulta base
        query = """
            SELECT r.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM reparaciones r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            WHERE r.tecnico_id = %s
        """
        
        # Aplicar filtro si es necesario
        params = [current_user.id]
        if filtro != 'todos':
            query += " AND r.estado = %s"
            params.append(filtro.upper())
        
        # Agregar ordenamiento
        query += """
            ORDER BY 
                CASE r.estado
                    WHEN 'RECIBIDO' THEN 1
                    WHEN 'DIAGNOSTICO' THEN 2
                    WHEN 'REPARACION' THEN 3
                    WHEN 'LISTO' THEN 4
                    WHEN 'ENTREGADO' THEN 5
                    ELSE 6
                END,
                r.fecha_recepcion DESC
        """
        
        cursor.execute(query, tuple(params))
        reparaciones = cursor.fetchall()
        
        # Obtener estadísticas
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN estado = 'RECIBIDO' THEN 1 END) as recibido,
                COUNT(CASE WHEN estado = 'DIAGNOSTICO' THEN 1 END) as diagnostico,
                COUNT(CASE WHEN estado = 'REPARACION' THEN 1 END) as reparacion,
                COUNT(CASE WHEN estado = 'LISTO' THEN 1 END) as listo
            FROM reparaciones
            WHERE tecnico_id = %s
        """, (current_user.id,))
        
        stats = cursor.fetchone()
        
        # Mapeo de estados a colores (en lugar de usar la tabla estados_reparacion)
        estados_colores = {
            'RECIBIDO': 'ffc107',     # Amarillo
            'DIAGNOSTICO': '17a2b8',  # Azul claro
            'REPARACION': '007bff',   # Azul
            'ESPERA_REPUESTOS': '6c757d', # Gris
            'LISTO': '28a745',        # Verde
            'ENTREGADO': '343a40',    # Negro
            'CANCELADO': 'dc3545'     # Rojo
        }
        
        # Mapeo de estados a nombres amigables
        estados_nombres = {
            'RECIBIDO': 'Recibido',
            'DIAGNOSTICO': 'En diagnóstico',
            'REPARACION': 'En reparación',
            'ESPERA_REPUESTOS': 'Esperando repuestos',
            'LISTO': 'Listo para entregar',
            'ENTREGADO': 'Entregado',
            'CANCELADO': 'Cancelado'
        }
        
        # Agregar color y nombre amigable a cada reparación
        for reparacion in reparaciones:
            estado = reparacion.get('estado', 'RECIBIDO')
            reparacion['estado_color'] = estados_colores.get(estado, 'ffc107')
            reparacion['estado_nombre'] = estados_nombres.get(estado, 'Pendiente')
        
        cursor.close()
        
        # Si no hay estadísticas disponibles, crear un diccionario por defecto
        if not stats:
            stats = {
                'total': 0,
                'recibido': 0,
                'diagnostico': 0,
                'reparacion': 0,
                'listo': 0
            }
        
        # Calcular eficiencia (porcentaje de reparaciones completadas)
        if stats['total'] > 0:
            # Contar reparaciones completadas (LISTO + ENTREGADO)
            cursor.execute("""
                SELECT COUNT(*) as completadas 
                FROM reparaciones 
                WHERE tecnico_id = %s AND (estado = 'LISTO' OR estado = 'ENTREGADO')
            """, (current_user.id,))
            completadas = cursor.fetchone()['completadas']
            stats['eficiencia'] = round((completadas / stats['total']) * 100)
        else:
            stats['eficiencia'] = 0
        
        return render_template('reparaciones/tecnico_reparaciones.html',
                              reparaciones=reparaciones,
                              stats=stats)
    except Exception as e:
        flash(f'Error al cargar tus reparaciones: {str(e)}', 'danger')
        return redirect(url_for('main.index'))

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

@reparaciones_bp.route('/tecnico/reparaciones')
def por_tecnico():
    """Muestra las reparaciones asignadas al técnico actual"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para acceder a esta página', 'warning')
        return redirect(url_for('auth.login_empleado'))
    
    # Verificar si el usuario es un técnico
    if not hasattr(current_user, 'cargo_nombre') or current_user.cargo_nombre != 'Técnico':
        flash('Esta página es solo para técnicos', 'warning')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Obtener el ID del técnico actual
        tecnico_id = current_user.id
        
        # Conexión a la base de datos y cursor
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Consultar las reparaciones asignadas al técnico
        query = """
            SELECT r.*, c.nombre as nombre_cliente, c.telefono as telefono_cliente,
                   COALESCE(c.direccion, '') as direccion_cliente
            FROM reparaciones r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            WHERE r.tecnico_id = %s
            ORDER BY r.fecha_recepcion DESC
        """
        
        cursor.execute(query, (tecnico_id,))
        reparaciones = cursor.fetchall()
        
        # Mapeo de estados a colores (en lugar de usar la tabla estados_reparacion)
        estados_colores = {
            'RECIBIDO': 'ffc107',     # Amarillo
            'DIAGNOSTICO': '17a2b8',  # Azul claro
            'REPARACION': '007bff',   # Azul
            'ESPERA_REPUESTOS': '6c757d', # Gris
            'LISTO': '28a745',        # Verde
            'ENTREGADO': '343a40',    # Negro
            'CANCELADO': 'dc3545'     # Rojo
        }
        
        # Mapeo de estados a nombres amigables
        estados_nombres = {
            'RECIBIDO': 'Recibido',
            'DIAGNOSTICO': 'En diagnóstico',
            'REPARACION': 'En reparación',
            'ESPERA_REPUESTOS': 'Esperando repuestos',
            'LISTO': 'Listo para entregar',
            'ENTREGADO': 'Entregado',
            'CANCELADO': 'Cancelado'
        }
        
        # Agregar color y nombre amigable a cada reparación
        for reparacion in reparaciones:
            estado = reparacion.get('estado', 'RECIBIDO')
            reparacion['estado_color'] = estados_colores.get(estado, 'ffc107')
            reparacion['estado_nombre'] = estados_nombres.get(estado, 'Pendiente')
        
        cursor.close()
        return render_template('reparaciones/por_tecnico.html', reparaciones=reparaciones)
    
    except MySQLdb.Error as e:
        # Manejar errores específicos de MySQL
        error_msg = f"Error de base de datos: {str(e)}"
        current_app.logger.error(error_msg)
        flash(error_msg, 'danger')
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        # Manejar otros errores inesperados
        error_msg = f"Error inesperado: {str(e)}"
        current_app.logger.error(error_msg)
        flash(error_msg, 'danger')
        return redirect(url_for('main.dashboard'))

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
        return redirect(url_for('reparaciones.listar'))

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
        return redirect(url_for('reparaciones.listar'))

    return render_template('reparaciones/editar.html', reparacion=reparacion)

@reparaciones_bp.route('/actualizar-estado/<int:id>', methods=['POST'])
@login_required
def actualizar_estado(id):
    """Actualiza el estado de una reparación por parte del técnico"""
    if request.method == 'POST':
        nuevo_estado = request.form.get('estado')
        diagnostico = request.form.get('diagnostico', '')
        notas = request.form.get('notas', '')
        notificar_cliente = request.form.get('notificar_cliente') == 'on'
        
        # Estados válidos
        estados_validos = ['RECIBIDO', 'DIAGNOSTICO', 'REPARACION', 'ESPERA_REPUESTOS', 'LISTO', 'ENTREGADO', 'CANCELADO']
        
        if nuevo_estado not in estados_validos:
            flash('Estado no válido', 'danger')
            return redirect(url_for('reparaciones.mis_reparaciones'))
        
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Verificar que la reparación exista y esté asignada al técnico
            cursor.execute("""
                SELECT id, estado, cliente_id FROM reparaciones 
                WHERE id = %s AND tecnico_id = %s
            """, (id, current_user.id))
            
            reparacion = cursor.fetchone()
            
            if not reparacion:
                flash('Reparación no encontrada o no está asignada a ti', 'danger')
                return redirect(url_for('reparaciones.mis_reparaciones'))
            
            estado_anterior = reparacion['estado']
            
            # Actualizar el estado
            cursor.execute("""
                UPDATE reparaciones 
                SET estado = %s, 
                    diagnostico = CASE WHEN %s != '' THEN %s ELSE diagnostico END,
                    notas = CONCAT(IFNULL(notas, ''), '\n', %s),
                    fecha_actualizacion = NOW()
                WHERE id = %s
            """, (nuevo_estado, diagnostico, diagnostico, f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {nuevo_estado}: {notas}", id))
            
            # Registrar en historial
            cursor.execute("""
                INSERT INTO historial_reparaciones 
                (reparacion_id, estado_anterior, estado_nuevo, descripcion, usuario_id, fecha)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (id, estado_anterior, nuevo_estado, notas, current_user.id))
            
            mysql.connection.commit()
            
            # Crear notificación para el cliente
            if notificar_cliente and reparacion['cliente_id']:
                try:
                    estados_texto = {
                        'RECIBIDO': 'recibida para revisión',
                        'DIAGNOSTICO': 'en diagnóstico',
                        'REPARACION': 'en proceso de reparación',
                        'ESPERA_REPUESTOS': 'esperando repuestos',
                        'LISTO': 'lista para retirar',
                        'ENTREGADO': 'entregada',
                        'CANCELADO': 'cancelada'
                    }
                    
                    # Verificar si existe la tabla notificaciones
                    cursor.execute("SHOW TABLES LIKE 'notificaciones'")
                    if not cursor.fetchone():
                        cursor.execute("""
                            CREATE TABLE notificaciones (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                remitente_id INT NOT NULL,
                                destinatario_id INT NOT NULL,
                                tipo VARCHAR(20) NOT NULL,
                                titulo VARCHAR(255) NOT NULL,
                                mensaje TEXT NOT NULL,
                                url VARCHAR(255) DEFAULT '#',
                                icono VARCHAR(50) DEFAULT 'bell',
                                leida BOOLEAN DEFAULT FALSE,
                                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                fecha_lectura TIMESTAMP NULL
                            )
                        """)
                    
                    cursor.execute("""
                        INSERT INTO notificaciones 
                        (remitente_id, destinatario_id, tipo, titulo, mensaje, leida, fecha_creacion, url, icono) 
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s)
                    """, (
                        current_user.id,
                        reparacion['cliente_id'],
                        'reparacion',
                        'Actualización de reparación', 
                        f"Tu reparación #{id} ahora está {estados_texto.get(nuevo_estado, nuevo_estado.lower())}. {diagnostico if diagnostico else ''}",
                        False,
                        url_for('reparaciones.ver', id=id),
                        'tools'
                    ))
                    mysql.connection.commit()
                except Exception as notif_error:
                    print(f"Error al crear notificación para cliente: {notif_error}")
            
            flash(f'Estado actualizado a {nuevo_estado}', 'success')
            cursor.close()
            
        except Exception as e:
            flash(f'Error al actualizar estado: {str(e)}', 'danger')
    
    return redirect(url_for('reparaciones.ver', id=id))

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
    if not hasattr(current_user, 'cargo_id') and not current_user.es_cliente:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener datos de la reparación y el cliente
    cursor = get_dict_cursor()
    cursor.execute("""
        SELECT r.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono, 
               e.id as tecnico_id, e.nombre as tecnico_nombre
        FROM reparaciones r
        JOIN clientes c ON r.cliente_id = c.id
        LEFT JOIN empleados e ON r.tecnico_id = e.id
        WHERE r.id = %s
    """, (id,))
    reparacion = cursor.fetchone()
    
    if not reparacion:
        flash('Reparación no encontrada', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener el mensaje
    mensaje = request.form.get('mensaje', '')
    
    if not mensaje:
        flash('Debe ingresar un mensaje', 'warning')
        return redirect(url_for('reparaciones.ver', id=id))
    
    # Determinar el tipo de remitente y destinatario
    if current_user.es_cliente:
        remitente_tipo = 'cliente'
        remitente_id = current_user.id
        destinatario_tipo = 'tecnico'
        destinatario_id = reparacion['tecnico_id']
        remitente_nombre = current_user.nombre
    else:
        remitente_tipo = 'tecnico'
        remitente_id = current_user.id
        destinatario_tipo = 'cliente'
        destinatario_id = reparacion['cliente_id']
        remitente_nombre = current_user.nombre
    
    # Guardar mensaje en la base de datos
    try:
        # Verificar si existe la tabla de mensajes
        cursor.execute("SHOW TABLES LIKE 'mensajes_reparacion'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE mensajes_reparacion (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    reparacion_id INT NOT NULL,
                    remitente_id INT NOT NULL,
                    remitente_tipo VARCHAR(20) NOT NULL,
                    remitente_nombre VARCHAR(100) NOT NULL,
                    destinatario_id INT NOT NULL,
                    destinatario_tipo VARCHAR(20) NOT NULL,
                    mensaje TEXT NOT NULL,
                    leido BOOLEAN DEFAULT FALSE,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX (reparacion_id),
                    INDEX (remitente_id),
                    INDEX (destinatario_id)
                )
            """)
            
        # Insertar mensaje
        cursor.execute("""
            INSERT INTO mensajes_reparacion 
            (reparacion_id, remitente_id, remitente_tipo, remitente_nombre, destinatario_id, destinatario_tipo, mensaje)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (id, remitente_id, remitente_tipo, remitente_nombre, destinatario_id, destinatario_tipo, mensaje))
        
        # Crear notificación para el destinatario
        if destinatario_id:
            try:
                # Verificar si existe la tabla notificaciones
                cursor.execute("SHOW TABLES LIKE 'notificaciones'")
                if not cursor.fetchone():
                    cursor.execute("""
                        CREATE TABLE notificaciones (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            remitente_id INT NOT NULL,
                            destinatario_id INT NOT NULL,
                            tipo VARCHAR(20) NOT NULL,
                            titulo VARCHAR(255) NOT NULL,
                            mensaje TEXT NOT NULL,
                            url VARCHAR(255) DEFAULT '#',
                            icono VARCHAR(50) DEFAULT 'bell',
                            leida BOOLEAN DEFAULT FALSE,
                            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            fecha_lectura TIMESTAMP NULL
                        )
                    """)
                
                # Crear notificación
                titulo = f"Nuevo mensaje sobre reparación #{id}"
                notif_mensaje = f"{remitente_nombre}: {mensaje[:50]}..." if len(mensaje) > 50 else f"{remitente_nombre}: {mensaje}"
                url = url_for('reparaciones.ver', id=id)
                icono = "comments"
                
                cursor.execute("""
                    INSERT INTO notificaciones 
                    (remitente_id, destinatario_id, tipo, titulo, mensaje, url, icono)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (remitente_id, destinatario_id, 'mensaje', titulo, notif_mensaje, url, icono))
                
            except Exception as notif_error:
                print(f"Error al crear notificación: {notif_error}")
        
        mysql.connection.commit()
        cursor.close()
        
        flash('Mensaje enviado correctamente', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al enviar mensaje: {e}', 'danger')
    
    return redirect(url_for('reparaciones.ver', id=id))

@reparaciones_bp.route('/detalle/<int:id>', methods=['GET'])
@login_required
def detalle(id):
    """Ver detalles de una reparación"""
    try:
        # Usar SQLite como capa de abstracción
        import sqlite3
        
        # Conectar a la base de datos
        conn = sqlite3.connect('app_ferreteria.db')
        conn.row_factory = sqlite3.Row
        
        # Obtener la reparación
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, c.nombre as cliente_nombre
            FROM reparaciones r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            WHERE r.id = ?
        """, (id,))
        
        reparacion = cursor.fetchone()
        
        if not reparacion:
            flash('Reparación no encontrada', 'warning')
            return redirect(url_for('reparaciones.listar'))
        
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

    except Exception as e:
        flash(f'Error al cargar detalles de la reparación: {str(e)}', 'danger')
        return redirect(url_for('reparaciones.listar'))

@reparaciones_bp.route('/admin-dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Dashboard de administración de reparaciones"""
    try:
        # Obtener datos para las estadísticas
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Total de reparaciones
        cur.execute("SELECT COUNT(*) as total FROM reparaciones")
        total_reparaciones = cur.fetchone()['total']
        
        # Estadísticas por estado
        estados = [
            {'estado': 'recibido', 'nombre': 'Por Revisar'},
            {'estado': 'diagnostico', 'nombre': 'En Diagnóstico'},
            {'estado': 'reparacion', 'nombre': 'En Reparación'},
            {'estado': 'listo', 'nombre': 'Listos para Entrega'},
            {'estado': 'entregado', 'nombre': 'Entregados'}
        ]
        
        # Reparaciones en recibido
        cur.execute("SELECT COUNT(*) as recibido FROM reparaciones WHERE estado = 'RECIBIDO'")
        recibido = cur.fetchone()['recibido']
        
        # Reparaciones en diagnóstico
        cur.execute("SELECT COUNT(*) as diagnostico FROM reparaciones WHERE estado = 'DIAGNOSTICO'")
        diagnostico = cur.fetchone()['diagnostico']
        
        # Reparaciones en reparación
        cur.execute("SELECT COUNT(*) as reparacion FROM reparaciones WHERE estado = 'REPARACION'")
        reparacion = cur.fetchone()['reparacion']
        
        # Reparaciones listas
        cur.execute("SELECT COUNT(*) as listo FROM reparaciones WHERE estado = 'LISTO'")
        listo = cur.fetchone()['listo']
        
        # Reparaciones entregadas
        cur.execute("SELECT COUNT(*) as entregado FROM reparaciones WHERE estado = 'ENTREGADO'")
        entregado = cur.fetchone()['entregado']
        
        # Obtener reparaciones recientes
        cur.execute('''
            SELECT r.id, r.estado, r.fecha_recepcion, r.electrodomestico as dispositivo, 
                   c.nombre as cliente_nombre, t.nombre as tecnico_nombre, r.tecnico_id
            FROM reparaciones r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            LEFT JOIN empleados t ON r.tecnico_id = t.id
            ORDER BY r.fecha_recepcion DESC
            LIMIT 10
        ''')
        reparaciones = cur.fetchall()
        
        # Obtener técnicos disponibles
        cur.execute('''
            SELECT e.id, e.nombre, e.foto_perfil,
                   COUNT(CASE WHEN r.estado IN ('RECIBIDO', 'DIAGNOSTICO', 'REPARACION', 'LISTO') THEN 1 END) as reparaciones_activas,
                   COUNT(CASE WHEN r.estado = 'ENTREGADO' THEN 1 END) as reparaciones_completadas
            FROM empleados e
            LEFT JOIN cargos c ON e.cargo_id = c.id
            LEFT JOIN reparaciones r ON e.id = r.tecnico_id
            WHERE c.nombre = 'Técnico' AND e.activo = TRUE
            GROUP BY e.id
            ORDER BY reparaciones_activas DESC
        ''')
        tecnicos = cur.fetchall()
        
        # Calcular porcentaje de reparaciones completadas para cada técnico
        for tecnico in tecnicos:
            total_asignadas = tecnico['reparaciones_activas'] + tecnico['reparaciones_completadas']
            if total_asignadas > 0:
                tecnico['porcentaje_completadas'] = int((tecnico['reparaciones_completadas'] / total_asignadas) * 100)
            else:
                tecnico['porcentaje_completadas'] = 0
        
        # Estadísticas para las tarjetas
        estadisticas = [
            {'estado': 'recibido', 'cantidad': recibido},
            {'estado': 'diagnostico', 'cantidad': diagnostico},
            {'estado': 'progreso', 'cantidad': reparacion},
            {'estado': 'listo', 'cantidad': listo}
        ]
        
        cur.close()
        
        return render_template('reparaciones/admin_dashboard.html',
                             total_reparaciones=total_reparaciones,
                             recibido=recibido,
                             diagnostico=diagnostico,
                             reparacion=reparacion,
                             listo=listo,
                             entregado=entregado,
                             reparaciones=reparaciones,
                             tecnicos=tecnicos,
                             estados=estadisticas)
    except Exception as e:
        flash(f'Error al cargar el dashboard: {str(e)}', 'danger')
        return redirect(url_for('main.index'))

@reparaciones_bp.route('/<int:reparacion_id>/asignar-tecnico', methods=['POST'])
@login_required
@admin_required
def asignar_tecnico(reparacion_id):
    """Asignar un técnico a una reparación"""
    if request.method == 'POST':
        tecnico_id = request.form.get('tecnico_id', '')
        
        try:
            cur = mysql.connection.cursor()
            
            # Verificar si la reparación existe
            cur.execute("SELECT id, estado FROM reparaciones WHERE id = %s", (reparacion_id,))
            reparacion = cur.fetchone()
            
            if not reparacion:
                flash('Reparación no encontrada', 'danger')
                return redirect(url_for('reparaciones.admin_dashboard'))
            
            # Si el técnico_id está vacío, es para quitar la asignación
            if not tecnico_id:
                cur.execute("""
                    UPDATE reparaciones 
                    SET tecnico_id = NULL
                    WHERE id = %s
                """, (reparacion_id,))
                mysql.connection.commit()
                flash('Técnico desasignado con éxito', 'success')
            else:
                # Verificar si el técnico existe
                cur.execute("""
                    SELECT e.id FROM empleados e 
                    JOIN cargos c ON e.cargo_id = c.id 
                    WHERE e.id = %s AND c.nombre = 'Técnico'
                """, (tecnico_id,))
                
                if not cur.fetchone():
                    flash('Técnico no válido', 'danger')
                    return redirect(url_for('reparaciones.admin_dashboard'))
                
                # Asignar el técnico a la reparación
                cur.execute("""
                    UPDATE reparaciones 
                    SET tecnico_id = %s
                    WHERE id = %s
                """, (tecnico_id, reparacion_id))
                
                mysql.connection.commit()
                
                # Crear notificación para el técnico
                try:
                    # Obtener información de la reparación para la notificación
                    cur.execute("""
                        SELECT r.id, r.electrodomestico, c.nombre as cliente_nombre
                        FROM reparaciones r
                        LEFT JOIN clientes c ON r.cliente_id = c.id
                        WHERE r.id = %s
                    """, (reparacion_id,))
                    
                    reparacion_info = cur.fetchone()
                    
                    # Crear la notificación
                    if reparacion_info:
                        cur.execute("""
                            INSERT INTO notificaciones 
                            (usuario_id, es_tecnico, tipo, titulo, mensaje, leido, fecha, url) 
                            VALUES (%s, TRUE, 'reparacion', 'Nueva reparación asignada', 
                                   %s, FALSE, NOW(), %s)
                        """, (
                            tecnico_id,
                            f"Se te ha asignado la reparación #{reparacion_id} - {reparacion_info['electrodomestico']} de {reparacion_info['cliente_nombre']}",
                            f"/reparaciones/{reparacion_id}"
                        ))
                        mysql.connection.commit()
                except Exception as notif_error:
                    # Si falla la notificación, solo registramos el error pero continuamos
                    print(f"Error al crear notificación: {notif_error}")
                
                flash('Técnico asignado con éxito', 'success')
            
            cur.close()
            
        except Exception as e:
            flash(f'Error al asignar técnico: {str(e)}', 'danger')
    
    # Redirigir de vuelta al dashboard o a la vista detallada
    referer = request.headers.get('Referer')
    if referer and 'reparaciones/ver' in referer:
        return redirect(referer)
    else:
        return redirect(url_for('reparaciones.admin_dashboard')) 

@reparaciones_bp.route('/cliente/mis-reparaciones')
@login_required
def mis_reparaciones_cliente():
    """Muestra las reparaciones del cliente actual"""
    try:
        # Verificar si el usuario actual es un cliente
        if not hasattr(current_user, 'es_cliente') or not current_user.es_cliente:
            flash('No tienes permisos para acceder a esta sección', 'danger')
            return redirect(url_for('main.index'))
        
        # Obtener las reparaciones del cliente
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = """
            SELECT r.*, 
                   e.nombre as tecnico_nombre,
                   CASE 
                     WHEN r.estado = 'RECIBIDO' THEN 'ffc107'
                     WHEN r.estado = 'DIAGNOSTICO' THEN '17a2b8'
                     WHEN r.estado = 'REPARACION' THEN '007bff'
                     WHEN r.estado = 'ESPERA_REPUESTOS' THEN '6c757d'
                     WHEN r.estado = 'LISTO' THEN '28a745'
                     WHEN r.estado = 'ENTREGADO' THEN '343a40'
                     WHEN r.estado = 'CANCELADO' THEN 'dc3545'
                     ELSE 'ffc107'
                   END as estado_color,
                   CASE 
                     WHEN r.estado = 'RECIBIDO' THEN 'Recibido'
                     WHEN r.estado = 'DIAGNOSTICO' THEN 'En diagnóstico'
                     WHEN r.estado = 'REPARACION' THEN 'En reparación'
                     WHEN r.estado = 'ESPERA_REPUESTOS' THEN 'Esperando repuestos'
                     WHEN r.estado = 'LISTO' THEN 'Listo para entregar'
                     WHEN r.estado = 'ENTREGADO' THEN 'Entregado'
                     WHEN r.estado = 'CANCELADO' THEN 'Cancelado'
                     ELSE 'Pendiente'
                   END as estado_nombre
            FROM reparaciones r
            LEFT JOIN empleados e ON r.tecnico_id = e.id
            WHERE r.cliente_id = %s
            ORDER BY 
                CASE r.estado
                    WHEN 'RECIBIDO' THEN 1
                    WHEN 'DIAGNOSTICO' THEN 2
                    WHEN 'REPARACION' THEN 3
                    WHEN 'ESPERA_REPUESTOS' THEN 4
                    WHEN 'LISTO' THEN 5
                    WHEN 'ENTREGADO' THEN 6
                    WHEN 'CANCELADO' THEN 7
                    ELSE 8
                END,
                r.fecha_recepcion DESC
        """
        
        cursor.execute(query, (current_user.id,))
        reparaciones = cursor.fetchall()
        
        # Obtener contadores de estados
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN estado = 'RECIBIDO' THEN 1 END) as recibido,
                COUNT(CASE WHEN estado = 'DIAGNOSTICO' THEN 1 END) as diagnostico,
                COUNT(CASE WHEN estado = 'REPARACION' THEN 1 END) as reparacion,
                COUNT(CASE WHEN estado = 'ESPERA_REPUESTOS' THEN 1 END) as espera_repuestos,
                COUNT(CASE WHEN estado = 'LISTO' THEN 1 END) as listo,
                COUNT(CASE WHEN estado = 'ENTREGADO' THEN 1 END) as entregado,
                COUNT(CASE WHEN estado = 'CANCELADO' THEN 1 END) as cancelado
            FROM reparaciones
            WHERE cliente_id = %s
        """, (current_user.id,))
        
        stats = cursor.fetchone()
        cursor.close()
        
        # Si no hay estadísticas disponibles, crear un diccionario por defecto
        if not stats:
            stats = {
                'total': 0,
                'recibido': 0,
                'diagnostico': 0,
                'reparacion': 0,
                'espera_repuestos': 0,
                'listo': 0,
                'entregado': 0,
                'cancelado': 0
            }
        
        return render_template('reparaciones/cliente_reparaciones.html',
                              reparaciones=reparaciones,
                              stats=stats)
    except Exception as e:
        flash(f'Error al cargar tus reparaciones: {str(e)}', 'danger')
        return redirect(url_for('main.index'))

@reparaciones_bp.route('/api/check-reparacion/<int:reparacion_id>')
@login_required
def check_reparacion(reparacion_id):
    """API endpoint para verificar si una reparación existe y el usuario tiene permisos"""
    try:
        # Obtener la reparación
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT r.id, r.cliente_id, r.tecnico_id
            FROM reparaciones r
            WHERE r.id = %s
        """, (reparacion_id,))
        
        reparacion = cursor.fetchone()
        cursor.close()
        
        # Verificar si existe
        if not reparacion:
            return jsonify({'exists': False, 'message': 'Reparación no encontrada'})
        
        # Verificar permisos
        is_admin = hasattr(current_user, 'es_admin') and current_user.es_admin
        is_tecnico = hasattr(current_user, 'cargo_nombre') and current_user.cargo_nombre == 'Técnico'
        is_cliente = hasattr(current_user, 'es_cliente') and current_user.es_cliente
        
        # Administradores siempre tienen acceso
        if is_admin:
            return jsonify({'exists': True})
            
        # Si es cliente, verificar que sea el dueño
        if is_cliente and reparacion['cliente_id'] == current_user.id:
            return jsonify({'exists': True})
            
        # Si es técnico, verificar que esté asignado
        if is_tecnico and reparacion['tecnico_id'] == current_user.id:
            return jsonify({'exists': True})
            
        # Cualquier otro empleado con acceso
        if not is_cliente and not is_tecnico:
            return jsonify({'exists': True})
            
        # Por defecto, no tiene permisos
        return jsonify({'exists': False, 'message': 'No tienes permisos para ver esta reparación'})
        
    except Exception as e:
        print(f"Error al verificar reparación: {e}")
        # En caso de error, devolvemos True para que la navegación continúe normalmente
        # y el error se maneje en la vista principal
        return jsonify({'exists': True, 'error': str(e)})