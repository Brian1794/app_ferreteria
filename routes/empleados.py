from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.models import mysql
from routes.auth import admin_required
from extensions import bcrypt
import MySQLdb

empleados_bp = Blueprint('empleados', __name__)

@empleados_bp.route('/')
@login_required
def index():
    """Lista todos los empleados"""
    if not current_user.is_empleado:
        flash('No tienes permisos para acceder a esta sección', 'danger')
        return redirect(url_for('main.index'))
    
    if not current_user.es_admin and not current_user.tiene_cargo('Gerente'):
        flash('No tienes permisos para acceder a esta sección', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener empleados con información de cargo
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT e.*, c.nombre as cargo_nombre
        FROM empleados e
        LEFT JOIN cargos c ON e.cargo_id = c.id
        ORDER BY e.nombre
    ''')
    empleados = cur.fetchall()
    cur.close()
    
    return render_template('empleados/lista.html', empleados=empleados)

@empleados_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo():
    """Crea un nuevo empleado"""
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        rol = request.form.get('rol')
        cargo_id = request.form.get('cargo_id')
        telefono = request.form.get('telefono', '')
        cedula = request.form.get('cedula', '')
        direccion = request.form.get('direccion', '')
        
        # Validaciones básicas
        if not all([nombre, email, password, rol]):
            flash('Todos los campos marcados con * son obligatorios', 'warning')
            return redirect(url_for('empleados.nuevo'))
        
        # Verificar si el email ya existe
        cur = mysql.connection.cursor()
        cur.execute('SELECT id FROM empleados WHERE email = %s', (email,))
        empleado_existente = cur.fetchone()
        
        # Verificar si el email existe en clientes
        cur.execute('SELECT id FROM clientes WHERE email = %s', (email,))
        cliente_existente = cur.fetchone()
        
        if empleado_existente or cliente_existente:
            flash('El email ya está registrado', 'warning')
            
            # Obtener lista de cargos para el formulario
            cur.execute('SELECT id, nombre FROM cargos ORDER BY nombre')
            cargos = cur.fetchall()
            cur.close()
            
            return render_template('empleados/formulario.html', 
                                  cargos=cargos, 
                                  empleado=None, 
                                  es_admin=True, 
                                  es_mismo_usuario=False)
        
        # Hashear contraseña
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        try:
            # Verificar si existen las columnas telefono, cedula y direccion
            columnas_existentes = []
            cur.execute("SHOW COLUMNS FROM empleados")
            for column in cur.fetchall():
                columnas_existentes.append(column[0])
            
            # Construir consulta SQL base
            query = "INSERT INTO empleados (nombre, email, password, rol, cargo_id"
            values = "%s, %s, %s, %s, %s"
            params = [nombre, email, hashed_password, rol, cargo_id]
            
            # Agregar columnas adicionales si existen
            if 'telefono' in columnas_existentes:
                query += ", telefono"
                values += ", %s"
                params.append(telefono)
                
            if 'cedula' in columnas_existentes:
                query += ", cedula"
                values += ", %s"
                params.append(cedula)
                
            if 'direccion' in columnas_existentes:
                query += ", direccion"
                values += ", %s"
                params.append(direccion)
            
            query += ", activo) VALUES (" + values + ", TRUE)"
            
            # Insertar nuevo empleado
            cur.execute(query, params)
            
            mysql.connection.commit()
            nuevo_id = cur.lastrowid
            cur.close()
            
            flash('Empleado creado con éxito', 'success')
            return redirect(url_for('empleados.ver', empleado_id=nuevo_id))
            
        except Exception as e:
            flash(f'Error al crear empleado: {str(e)}', 'danger')
            
            # Obtener lista de cargos para el formulario
            cur.execute('SELECT id, nombre FROM cargos ORDER BY nombre')
            cargos = cur.fetchall()
            cur.close()
            
            return render_template('empleados/formulario.html', 
                                  cargos=cargos, 
                                  empleado=None, 
                                  es_admin=True, 
                                  es_mismo_usuario=False)
    
    # Obtener lista de cargos para el formulario
    cur = mysql.connection.cursor()
    cur.execute('SELECT id, nombre FROM cargos ORDER BY nombre')
    cargos = cur.fetchall()
    cur.close()
    
    return render_template('empleados/formulario.html', 
                          cargos=cargos, 
                          empleado=None, 
                          es_admin=True, 
                          es_mismo_usuario=False)

@empleados_bp.route('/<int:empleado_id>')
@login_required
def ver(empleado_id):
    """Ver detalles de un empleado"""
    # Verificar permisos
    tiene_permiso = (current_user.es_admin or 
                    current_user.tiene_cargo('Gerente') or 
                    current_user.id == empleado_id)
    
    if not current_user.is_empleado or not tiene_permiso:
        flash('No tienes permisos para acceder a esta información', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener datos del empleado
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT e.*, c.nombre as cargo_nombre, c.descripcion as cargo_descripcion, c.permisos as permisos_json
        FROM empleados e
        LEFT JOIN cargos c ON e.cargo_id = c.id
        WHERE e.id = %s
    ''', (empleado_id,))
    empleado = cur.fetchone()
    
    if not empleado:
        flash('Empleado no encontrado', 'warning')
        return redirect(url_for('empleados.index'))
    
    # Obtener ventas realizadas por el empleado
    cur.execute('''
        SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as monto_total
        FROM ventas
        WHERE empleado_id = %s AND estado = 'Pagada'
    ''', (empleado_id,))
    stats_ventas = cur.fetchone()
    
    # Obtener reparaciones asignadas
    cur.execute('''
        SELECT COUNT(*) as total_reparaciones,
               COUNT(CASE WHEN estado NOT IN ('ENTREGADO', 'CANCELADO') THEN 1 END) as reparaciones_activas
        FROM reparaciones
        WHERE tecnico_id = %s
    ''', (empleado_id,))
    stats_reparaciones = cur.fetchone()
    
    cur.close()
    
    return render_template('empleados/ver.html', 
                          empleado=empleado, 
                          stats_ventas=stats_ventas,
                          stats_reparaciones=stats_reparaciones)

@empleados_bp.route('/<int:empleado_id>/editar', methods=['GET', 'POST'])
@login_required
def editar(empleado_id):
    """Editar datos de un empleado"""
    # Verificar permisos (solo admin, gerente, o el propio empleado)
    tiene_permiso = (current_user.es_admin or 
                    current_user.tiene_cargo('Gerente') or 
                    current_user.id == empleado_id)
    
    if not current_user.is_empleado or not tiene_permiso:
        flash('No tienes permisos para editar esta información', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener datos del empleado
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM empleados WHERE id = %s', (empleado_id,))
    empleado = cur.fetchone()
    
    if not empleado:
        flash('Empleado no encontrado', 'warning')
        return redirect(url_for('empleados.index'))
    
    # Solo administradores pueden cambiar roles y cargos
    es_admin = current_user.es_admin
    es_mismo_usuario = current_user.id == empleado_id
    
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password', '')  # Opcional
        telefono = request.form.get('telefono', '')
        cedula = request.form.get('cedula', '')
        direccion = request.form.get('direccion', '')
        
        # Campos que solo puede cambiar un administrador
        if es_admin:
            rol = request.form.get('rol')
            cargo_id = request.form.get('cargo_id')
            activo = 'activo' in request.form
        else:
            rol = empleado['rol']
            cargo_id = empleado['cargo_id']
            activo = empleado['activo']
        
        # Validaciones básicas
        if not nombre or not email:
            flash('Nombre y email son obligatorios', 'warning')
            
            # Obtener lista de cargos para el formulario
            cur.execute('SELECT id, nombre FROM cargos ORDER BY nombre')
            cargos = cur.fetchall()
            
            return render_template('empleados/formulario.html', 
                                  empleado=empleado, 
                                  cargos=cargos,
                                  es_admin=es_admin,
                                  es_mismo_usuario=es_mismo_usuario)
        
        # Verificar si el email ya existe en otro empleado
        if email != empleado['email']:
            cur.execute('SELECT id FROM empleados WHERE email = %s AND id != %s', (email, empleado_id))
            if cur.fetchone():
                flash('El email ya está registrado por otro empleado', 'warning')
                
                # Obtener lista de cargos para el formulario
                cur.execute('SELECT id, nombre FROM cargos ORDER BY nombre')
                cargos = cur.fetchall()
                
                return render_template('empleados/formulario.html', 
                                      empleado=empleado, 
                                      cargos=cargos,
                                      es_admin=es_admin,
                                      es_mismo_usuario=es_mismo_usuario)
            
            # Verificar si el email existe en clientes
            cur.execute('SELECT id FROM clientes WHERE email = %s', (email,))
            if cur.fetchone():
                flash('El email ya está registrado por un cliente', 'warning')
                
                # Obtener lista de cargos para el formulario
                cur.execute('SELECT id, nombre FROM cargos ORDER BY nombre')
                cargos = cur.fetchall()
                
                return render_template('empleados/formulario.html', 
                                      empleado=empleado, 
                                      cargos=cargos,
                                      es_admin=es_admin,
                                      es_mismo_usuario=es_mismo_usuario)
        
        try:
            # Verificar si existen las columnas telefono, cedula y direccion
            columnas_existentes = []
            cur.execute("SHOW COLUMNS FROM empleados")
            for column in cur.fetchall():
                columnas_existentes.append(column[0])
            
            # Construir consulta SQL base
            query = "UPDATE empleados SET nombre = %s, email = %s"
            params = [nombre, email]
            
            # Agregar columnas adicionales si existen
            if 'telefono' in columnas_existentes:
                query += ", telefono = %s"
                params.append(telefono)
                
            if 'cedula' in columnas_existentes:
                query += ", cedula = %s"
                params.append(cedula)
                
            if 'direccion' in columnas_existentes:
                query += ", direccion = %s"
                params.append(direccion)
            
            # Agregar cambio de contraseña si se proporcionó
            if password:
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                query += ", password = %s"
                params.append(hashed_password)
            
            # Agregar campos que solo puede cambiar un administrador
            if es_admin:
                query += ", rol = %s, cargo_id = %s, activo = %s"
                params.extend([rol, cargo_id, activo])
            
            # Completar consulta
            query += " WHERE id = %s"
            params.append(empleado_id)
            
            # Ejecutar actualización
            cur.execute(query, params)
            mysql.connection.commit()
            
            flash('Empleado actualizado con éxito', 'success')
            return redirect(url_for('empleados.ver', empleado_id=empleado_id))
            
        except Exception as e:
            flash(f'Error al actualizar empleado: {str(e)}', 'danger')
        
        finally:
            cur.close()
    
    # Obtener lista de cargos para el formulario
    cur = mysql.connection.cursor()
    cur.execute('SELECT id, nombre FROM cargos ORDER BY nombre')
    cargos = cur.fetchall()
    cur.close()
    
    return render_template('empleados/formulario.html', 
                          empleado=empleado, 
                          cargos=cargos,
                          es_admin=es_admin,
                          es_mismo_usuario=es_mismo_usuario)

@empleados_bp.route('/<int:empleado_id>/cambiar_estado', methods=['POST'])
@login_required
@admin_required
def cambiar_estado(empleado_id):
    """Activar o desactivar un empleado"""
    try:
        # No permitir desactivar el propio usuario
        if current_user.id == empleado_id:
            flash('No puedes desactivar tu propia cuenta', 'warning')
            return redirect(url_for('empleados.ver', empleado_id=empleado_id))
        
        cur = mysql.connection.cursor()
        cur.execute('SELECT activo FROM empleados WHERE id = %s', (empleado_id,))
        empleado = cur.fetchone()
        
        if not empleado:
            flash('Empleado no encontrado', 'warning')
            return redirect(url_for('empleados.index'))
        
        # Cambiar estado
        nuevo_estado = not empleado['activo']
        cur.execute('UPDATE empleados SET activo = %s WHERE id = %s', (nuevo_estado, empleado_id))
        mysql.connection.commit()
        cur.close()
        
        estado_texto = 'activado' if nuevo_estado else 'desactivado'
        flash(f'Empleado {estado_texto} con éxito', 'success')
        
    except Exception as e:
        flash(f'Error al cambiar estado: {str(e)}', 'danger')
    
    return redirect(url_for('empleados.ver', empleado_id=empleado_id))

@empleados_bp.route('/mi_perfil')
@login_required
def mi_perfil():
    """Muestra el perfil del empleado actualmente logueado"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener datos del empleado
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT e.*, c.nombre as nombre_cargo, c.descripcion as cargo_descripcion
        FROM empleados e
        LEFT JOIN cargos c ON e.cargo_id = c.id
        WHERE e.id = %s
    ''', (current_user.id,))
    empleado = cursor.fetchone()
    
    if not empleado:
        flash('Error al cargar datos del empleado', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Obtener estadísticas
    # Ventas realizadas
    cursor.execute('''
        SELECT COUNT(*) as total_ventas, COALESCE(SUM(total), 0) as monto_total
        FROM ventas
        WHERE empleado_id = %s AND estado = 'Pagada'
    ''', (current_user.id,))
    stats_ventas = cursor.fetchone()
    
    # Reparaciones asignadas (si es técnico)
    cursor.execute('''
        SELECT COUNT(*) as total_reparaciones,
               COUNT(CASE WHEN estado NOT IN ('ENTREGADO', 'CANCELADO') THEN 1 END) as reparaciones_activas
        FROM reparaciones
        WHERE tecnico_id = %s
    ''', (current_user.id,))
    stats_reparaciones = cursor.fetchone()
    
    cursor.close()
    
    return render_template('empleados/perfil.html', 
                          empleado=empleado,
                          stats_ventas=stats_ventas,
                          stats_reparaciones=stats_reparaciones)

@empleados_bp.route('/debug-usuario')
@login_required
def debug_usuario():
    """Ruta para depurar los datos del usuario actual"""
    try:
        from flask import jsonify
        # Información general del usuario
        user_info = {
            'id': current_user.id,
            'nombre': current_user.nombre,
            'email': current_user.email,
            'es_admin': current_user.es_admin,
            'es_cliente': current_user.es_cliente,
            'cargo_id': current_user.cargo_id,
            'cargo_nombre': current_user.cargo_nombre
        }
        
        # Verificaciones de roles
        role_checks = {
            'es_tecnico': current_user.es_tecnico() if hasattr(current_user, 'es_tecnico') else None,
            'es_vendedor': current_user.es_vendedor() if hasattr(current_user, 'es_vendedor') else None,
            'es_almacenista': current_user.es_almacenista() if hasattr(current_user, 'es_almacenista') else None,
            'is_empleado': current_user.is_empleado if hasattr(current_user, 'is_empleado') else None
        }
        
        # Obtener cargo de la base de datos para verificar
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT c.nombre FROM empleados e JOIN cargos c ON e.cargo_id = c.id WHERE e.id = %s", (current_user.id,))
        cargo_db = cursor.fetchone()
        cursor.close()
        
        result = {
            'user_info': user_info,
            'role_checks': role_checks,
            'cargo_from_db': cargo_db
        }
        
        return render_template('empleados/debug_usuario.html', user_data=result)
    except Exception as e:
        return f"Error al depurar usuario: {str(e)}"

@empleados_bp.route('/<int:empleado_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar(empleado_id):
    """Eliminar un empleado"""
    try:
        # No permitir eliminar el propio usuario
        if current_user.id == empleado_id:
            flash('No puedes eliminar tu propia cuenta', 'warning')
            return redirect(url_for('empleados.ver', empleado_id=empleado_id))
        
        cur = mysql.connection.cursor()
        
        # Verificar si el empleado existe
        cur.execute('SELECT id, nombre FROM empleados WHERE id = %s', (empleado_id,))
        empleado = cur.fetchone()
        
        if not empleado:
            flash('Empleado no encontrado', 'warning')
            return redirect(url_for('empleados.index'))
        
        nombre_empleado = empleado['nombre']
        
        # Eliminar el empleado
        cur.execute('DELETE FROM empleados WHERE id = %s', (empleado_id,))
        mysql.connection.commit()
        cur.close()
        
        flash(f'Empleado "{nombre_empleado}" eliminado con éxito', 'success')
        
    except Exception as e:
        flash(f'Error al eliminar empleado: {str(e)}', 'danger')
    
    return redirect(url_for('empleados.index')) 