from flask import Blueprint, request, redirect, url_for, render_template, flash, session, jsonify, current_app
from flask_login import login_required, current_user
from extensions import mysql
import MySQLdb
from datetime import datetime
import json

notificaciones_bp = Blueprint('notificaciones', __name__)

@notificaciones_bp.route('/crear', methods=['POST'])
@login_required
def crear_notificacion():
    """Crea una nueva notificación"""
    try:
        # Obtener datos de la notificación
        destinatario_id = request.form.get('destinatario_id')
        tipo = request.form.get('tipo', 'mensaje')  # mensaje, reparacion, sistema
        titulo = request.form.get('titulo', 'Nueva notificación')
        mensaje = request.form.get('mensaje', '')
        url = request.form.get('url', '#')
        icono = request.form.get('icono', 'bell')
        
        # Validar datos
        if not destinatario_id or not mensaje:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400
        
        # Crear notificación en la base de datos
        cursor = mysql.connection.cursor()
        
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
        
        # Insertar notificación
        cursor.execute("""
            INSERT INTO notificaciones 
            (remitente_id, destinatario_id, tipo, titulo, mensaje, url, icono)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (current_user.id, destinatario_id, tipo, titulo, mensaje, url, icono))
        
        mysql.connection.commit()
        notificacion_id = cursor.lastrowid
        cursor.close()
        
        return jsonify({
            'success': True, 
            'message': 'Notificación creada correctamente',
            'notificacion_id': notificacion_id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al crear notificación: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@notificaciones_bp.route('/obtener')
@login_required
def obtener_notificaciones():
    """Obtiene las notificaciones del usuario actual"""
    try:
        # Obtener de la base de datos
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Verificar si existe la tabla
        cursor.execute("SHOW TABLES LIKE 'notificaciones'")
        if not cursor.fetchone():
            return jsonify({'success': True, 'notificaciones': []})
        
        # Obtener notificaciones
        cursor.execute("""
            SELECT n.*, 
                   CASE 
                       WHEN n.remitente_id = 0 THEN 'Sistema'
                       WHEN c.id IS NOT NULL THEN c.nombre
                       WHEN e.id IS NOT NULL THEN e.nombre
                       ELSE 'Usuario desconocido'
                   END as remitente_nombre
            FROM notificaciones n
            LEFT JOIN clientes c ON n.remitente_id = c.id
            LEFT JOIN empleados e ON n.remitente_id = e.id
            WHERE n.destinatario_id = %s
            ORDER BY n.fecha_creacion DESC
            LIMIT 10
        """, (current_user.id,))
        
        notificaciones = cursor.fetchall()
        
        # Formatear fechas
        for notificacion in notificaciones:
            notificacion['fecha_creacion'] = notificacion['fecha_creacion'].strftime('%d/%m/%Y %H:%M')
            if notificacion['fecha_lectura']:
                notificacion['fecha_lectura'] = notificacion['fecha_lectura'].strftime('%d/%m/%Y %H:%M')
        
        # Guardar en sesión para acceso rápido
        session['notificaciones'] = notificaciones
        session['notificaciones_total'] = len([n for n in notificaciones if not n['leida']])
        
        return jsonify({
            'success': True,
            'notificaciones': notificaciones,
            'total_no_leidas': session['notificaciones_total']
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener notificaciones: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@notificaciones_bp.route('/marcar-leida/<int:id>', methods=['POST'])
@login_required
def marcar_leida(id):
    """Marca una notificación como leída"""
    try:
        cursor = mysql.connection.cursor()
        
        # Verificar que la notificación pertenezca al usuario
        cursor.execute("""
            SELECT id FROM notificaciones 
            WHERE id = %s AND destinatario_id = %s
        """, (id, current_user.id))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Notificación no encontrada'}), 404
        
        # Marcar como leída
        cursor.execute("""
            UPDATE notificaciones 
            SET leida = TRUE, fecha_lectura = NOW()
            WHERE id = %s
        """, (id,))
        
        mysql.connection.commit()
        cursor.close()
        
        # Actualizar sesión
        if 'notificaciones' in session:
            notificaciones = session['notificaciones']
            for notificacion in notificaciones:
                if notificacion['id'] == id:
                    notificacion['leida'] = True
                    notificacion['fecha_lectura'] = datetime.now().strftime('%d/%m/%Y %H:%M')
            
            session['notificaciones'] = notificaciones
            session['notificaciones_total'] = len([n for n in notificaciones if not n['leida']])
        
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error al marcar notificación como leída: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@notificaciones_bp.route('/todas')
@login_required
def ver_todas():
    """Muestra todas las notificaciones del usuario"""
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Verificar si existe la tabla
        cursor.execute("SHOW TABLES LIKE 'notificaciones'")
        if not cursor.fetchone():
            return render_template('notificaciones/todas.html', notificaciones=[])
        
        # Obtener todas las notificaciones
        cursor.execute("""
            SELECT n.*, 
                   CASE 
                       WHEN n.remitente_id = 0 THEN 'Sistema'
                       WHEN c.id IS NOT NULL THEN c.nombre
                       WHEN e.id IS NOT NULL THEN e.nombre
                       ELSE 'Usuario desconocido'
                   END as remitente_nombre
            FROM notificaciones n
            LEFT JOIN clientes c ON n.remitente_id = c.id
            LEFT JOIN empleados e ON n.remitente_id = e.id
            WHERE n.destinatario_id = %s
            ORDER BY n.leida ASC, n.fecha_creacion DESC
        """, (current_user.id,))
        
        notificaciones = cursor.fetchall()
        
        # Formatear fechas
        for notificacion in notificaciones:
            notificacion['fecha_creacion'] = notificacion['fecha_creacion'].strftime('%d/%m/%Y %H:%M')
            if notificacion['fecha_lectura']:
                notificacion['fecha_lectura'] = notificacion['fecha_lectura'].strftime('%d/%m/%Y %H:%M')
        
        # Marcar todas como leídas
        cursor.execute("""
            UPDATE notificaciones
            SET leida = TRUE, fecha_lectura = NOW()
            WHERE destinatario_id = %s AND leida = FALSE
        """, (current_user.id,))
        
        mysql.connection.commit()
        cursor.close()
        
        # Actualizar sesión
        session['notificaciones'] = notificaciones[:10]
        session['notificaciones_total'] = 0
        
        return render_template('notificaciones/todas.html', notificaciones=notificaciones)
        
    except Exception as e:
        current_app.logger.error(f"Error al obtener todas las notificaciones: {e}")
        flash('Error al obtener las notificaciones', 'danger')
        return redirect(url_for('main.index'))

@notificaciones_bp.route('/enviar-tecnico', methods=['POST'])
@login_required
def enviar_a_tecnico():
    """Envía una notificación al técnico seleccionado"""
    try:
        # Obtener datos de la notificación
        tecnico_id = request.form.get('tecnico_id')
        tipo = request.form.get('tipo', 'admin_mensaje')
        titulo = request.form.get('titulo', 'Mensaje del administrador')
        mensaje = request.form.get('mensaje', '')
        url = request.form.get('url', '#')
        icono = request.form.get('icono', 'envelope')
        
        # Validar datos
        if not tecnico_id or not mensaje:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400
        
        # Crear notificación en la base de datos
        cursor = mysql.connection.cursor()
        
        # Verificar si existe la tabla notificaciones
        cursor.execute("SHOW TABLES LIKE 'notificaciones'")
        if not cursor.fetchone():
            # Crear tabla de notificaciones (usando la misma estructura)
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
        
        # Insertar notificación
        cursor.execute("""
            INSERT INTO notificaciones 
            (remitente_id, destinatario_id, tipo, titulo, mensaje, url, icono)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (current_user.id, tecnico_id, tipo, titulo, mensaje, url, icono))
        
        mysql.connection.commit()
        notificacion_id = cursor.lastrowid
        cursor.close()
        
        # Si la solicitud espera JSON, devolver respuesta JSON
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'success': True, 
                'message': 'Notificación enviada al técnico correctamente',
                'notificacion_id': notificacion_id
            })
        
        # En caso contrario, redirigir a la página anterior con un mensaje flash
        flash('Mensaje enviado al técnico correctamente', 'success')
        referer = request.headers.get('Referer')
        return redirect(referer if referer else url_for('admin.index'))
        
    except Exception as e:
        current_app.logger.error(f"Error al enviar notificación al técnico: {e}")
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': str(e)}), 500
        
        flash(f'Error al enviar mensaje: {str(e)}', 'danger')
        referer = request.headers.get('Referer')
        return redirect(referer if referer else url_for('admin.index'))

@notificaciones_bp.route('/enviar-admin', methods=['POST'])
@login_required
def enviar_a_admin():
    """Envía una notificación a los administradores"""
    try:
        # Obtener datos de la notificación
        tipo = request.form.get('tipo', 'tecnico_mensaje')
        titulo = request.form.get('titulo', 'Mensaje de técnico')
        mensaje = request.form.get('mensaje', '')
        url = request.form.get('url', '#')
        icono = request.form.get('icono', 'envelope')
        
        # Validar datos
        if not mensaje:
            return jsonify({'success': False, 'message': 'El mensaje es requerido'}), 400
        
        # Crear notificación en la base de datos
        cursor = mysql.connection.cursor()
        
        # Primero, obtener todos los usuarios administradores
        cursor.execute("""
            SELECT id FROM empleados WHERE es_admin = TRUE
        """)
        
        admins = cursor.fetchall()
        
        if not admins:
            return jsonify({'success': False, 'message': 'No hay administradores en el sistema'}), 404
        
        # Verificar si existe la tabla notificaciones
        cursor.execute("SHOW TABLES LIKE 'notificaciones'")
        if not cursor.fetchone():
            # Crear tabla de notificaciones (usando la misma estructura)
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
        
        # Insertar notificación para cada administrador
        notificacion_ids = []
        for admin in admins:
            cursor.execute("""
                INSERT INTO notificaciones 
                (remitente_id, destinatario_id, tipo, titulo, mensaje, url, icono)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (current_user.id, admin['id'], tipo, titulo, mensaje, url, icono))
            
            notificacion_ids.append(cursor.lastrowid)
        
        mysql.connection.commit()
        cursor.close()
        
        # Si la solicitud espera JSON, devolver respuesta JSON
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'success': True, 
                'message': 'Notificación enviada a los administradores correctamente',
                'notificacion_ids': notificacion_ids
            })
        
        # En caso contrario, redirigir a la página anterior con un mensaje flash
        flash('Mensaje enviado a los administradores correctamente', 'success')
        referer = request.headers.get('Referer')
        return redirect(referer if referer else url_for('reparaciones.por_tecnico'))
        
    except Exception as e:
        current_app.logger.error(f"Error al enviar notificación a los administradores: {e}")
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': str(e)}), 500
        
        flash(f'Error al enviar mensaje: {str(e)}', 'danger')
        referer = request.headers.get('Referer')
        return redirect(referer if referer else url_for('reparaciones.por_tecnico'))

@notificaciones_bp.route('/marcar-todas-leidas', methods=['POST'])
@login_required
def marcar_todas_leidas():
    """Marca todas las notificaciones del usuario como leídas"""
    try:
        cursor = mysql.connection.cursor()
        
        # Marcar todas las notificaciones del usuario como leídas
        cursor.execute("""
            UPDATE notificaciones 
            SET leida = TRUE, fecha_lectura = NOW()
            WHERE destinatario_id = %s AND leida = FALSE
        """, (current_user.id,))
        
        # Contar cuántas se actualizaron
        rows_affected = cursor.rowcount
        
        mysql.connection.commit()
        cursor.close()
        
        # Actualizar sesión
        if 'notificaciones' in session:
            notificaciones = session['notificaciones']
            for notificacion in notificaciones:
                notificacion['leida'] = True
                if not notificacion.get('fecha_lectura'):
                    notificacion['fecha_lectura'] = datetime.now().strftime('%d/%m/%Y %H:%M')
            
            session['notificaciones'] = notificaciones
            session['notificaciones_total'] = 0
        
        return jsonify({
            'success': True, 
            'message': f'{rows_affected} notificaciones marcadas como leídas'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error al marcar todas las notificaciones como leídas: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500 