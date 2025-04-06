from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models.models import mysql
from routes.auth import admin_required
import re

clientes_bp = Blueprint('clientes', __name__)

@clientes_bp.route('/')
@login_required
def index():
    """Lista todos los clientes"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener parámetros de filtro y ordenamiento
    busqueda = request.args.get('busqueda', '')
    estado = request.args.get('estado', 'activos')
    tipo = request.args.get('tipo', 'todos')
    orden = request.args.get('orden', 'recientes')
    
    # Construir consulta SQL
    query = '''
        SELECT * FROM clientes
        WHERE 1=1
    '''
    params = []
    
    # Filtrar por búsqueda
    if busqueda:
        query += ' AND (nombre LIKE %s OR apellido LIKE %s OR email LIKE %s OR telefono LIKE %s)'
        term = f'%{busqueda}%'
        params.extend([term, term, term, term])
    
    # Filtrar por estado
    if estado == 'activos':
        query += ' AND activo = TRUE'
    elif estado == 'inactivos':
        query += ' AND activo = FALSE'
    
    # Filtrar por tipo de cliente
    if tipo != 'todos':
        query += ' AND tipo_cliente = %s'
        params.append(tipo)
    
    # Ordenar resultados
    if orden == 'recientes':
        query += ' ORDER BY fecha_registro DESC'
    elif orden == 'alfabetico':
        query += ' ORDER BY nombre ASC, apellido ASC'
    elif orden == 'ultima_compra':
        query += ' ORDER BY ultima_compra DESC NULLS LAST'
    
    # Ejecutar consulta
    cur = mysql.connection.cursor()
    cur.execute(query, params)
    clientes = cur.fetchall()
    cur.close()
    
    return render_template('clientes/lista.html', 
                          clientes=clientes,
                          busqueda=busqueda,
                          estado=estado,
                          tipo=tipo,
                          orden=orden)

@clientes_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    """Formulario para crear un nuevo cliente"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido', '')
        email = request.form.get('email', '')
        telefono = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')
        ciudad = request.form.get('ciudad', '')
        codigo_postal = request.form.get('codigo_postal', '')
        identificacion = request.form.get('identificacion', '')
        tipo_cliente = request.form.get('tipo_cliente', 'Regular')
        notas = request.form.get('notas', '')
        password = request.form.get('password', '')
        puede_comprar_online = 'puede_comprar_online' in request.form
        
        # Validaciones básicas
        if not nombre:
            flash('El nombre es obligatorio', 'warning')
            return render_template('clientes/formulario.html')
        
        # Validar email si se proporciona
        if email:
            # Verificar formato del email
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                flash('El formato del email no es válido', 'warning')
                return render_template('clientes/formulario.html')
            
            # Verificar si el email ya existe
            cur = mysql.connection.cursor()
            cur.execute('SELECT id FROM clientes WHERE email = %s', (email,))
            if cur.fetchone():
                flash('El email ya está registrado', 'warning')
                cur.close()
                return render_template('clientes/formulario.html')
            
            # Verificar si existe en empleados
            cur.execute('SELECT id FROM empleados WHERE email = %s', (email,))
            if cur.fetchone():
                flash('El email ya está registrado como empleado', 'warning')
                cur.close()
                return render_template('clientes/formulario.html')
            
            cur.close()
        
        try:
            cur = mysql.connection.cursor()
            
            # Hash de contraseña si se proporcionó
            from extensions import bcrypt
            hashed_password = None
            if password:
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            
            # Insertar cliente
            cur.execute('''
                INSERT INTO clientes 
                (nombre, apellido, email, telefono, direccion, ciudad, codigo_postal, 
                identificacion, tipo_cliente, notas, password, activo, fecha_registro, puede_comprar_online)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), %s)
            ''', (nombre, apellido, email, telefono, direccion, ciudad, codigo_postal, 
                 identificacion, tipo_cliente, notas, hashed_password, puede_comprar_online))
            
            mysql.connection.commit()
            nuevo_id = cur.lastrowid
            cur.close()
            
            flash('Cliente creado con éxito', 'success')
            return redirect(url_for('clientes.ver', cliente_id=nuevo_id))
            
        except Exception as e:
            flash(f'Error al crear el cliente: {str(e)}', 'danger')
            return render_template('clientes/formulario.html')
    
    return render_template('clientes/formulario.html', cliente=None)

@clientes_bp.route('/<int:cliente_id>')
@login_required
def ver(cliente_id):
    """Ver detalles de un cliente"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    cur = mysql.connection.cursor()
    
    # Obtener datos del cliente
    cur.execute('SELECT * FROM clientes WHERE id = %s', (cliente_id,))
    cliente = cur.fetchone()
    
    if not cliente:
        flash('Cliente no encontrado', 'warning')
        cur.close()
        return redirect(url_for('clientes.index'))
    
    # Obtener compras del cliente
    cur.execute('''
        SELECT v.*, COUNT(d.id) as total_items
        FROM ventas v
        LEFT JOIN detalles_venta d ON v.id = d.venta_id
        WHERE v.cliente_id = %s
        GROUP BY v.id
        ORDER BY v.fecha DESC
        LIMIT 10
    ''', (cliente_id,))
    compras = cur.fetchall()
    
    # Obtener reparaciones del cliente
    cur.execute('''
        SELECT r.*, e.nombre as tecnico_nombre
        FROM reparaciones r
        LEFT JOIN empleados e ON r.tecnico_id = e.id
        WHERE r.cliente_id = %s
        ORDER BY r.fecha_recepcion DESC
        LIMIT 10
    ''', (cliente_id,))
    reparaciones = cur.fetchall()
    
    # Calcular totales
    cur.execute('''
        SELECT 
            COUNT(v.id) AS total_compras,
            COALESCE(SUM(v.total), 0) AS total_gastado,
            COUNT(r.id) AS total_reparaciones
        FROM clientes c
        LEFT JOIN ventas v ON c.id = v.cliente_id
        LEFT JOIN reparaciones r ON c.id = r.cliente_id
        WHERE c.id = %s
    ''', (cliente_id,))
    estadisticas = cur.fetchone()
    
    cur.close()
    
    return render_template('clientes/ver.html', 
                          cliente=cliente, 
                          compras=compras,
                          reparaciones=reparaciones,
                          estadisticas=estadisticas)

@clientes_bp.route('/<int:cliente_id>/editar', methods=['GET', 'POST'])
@login_required
def editar(cliente_id):
    """Editar datos de un cliente"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener datos del cliente
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM clientes WHERE id = %s', (cliente_id,))
    cliente = cur.fetchone()
    cur.close()
    
    if not cliente:
        flash('Cliente no encontrado', 'warning')
        return redirect(url_for('clientes.index'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido', '')
        email = request.form.get('email', '')
        telefono = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')
        ciudad = request.form.get('ciudad', '')
        codigo_postal = request.form.get('codigo_postal', '')
        identificacion = request.form.get('identificacion', '')
        tipo_cliente = request.form.get('tipo_cliente', 'Regular')
        notas = request.form.get('notas', '')
        password = request.form.get('password', '')
        activo = 'activo' in request.form
        puede_comprar_online = 'puede_comprar_online' in request.form
        
        # Validaciones básicas
        if not nombre:
            flash('El nombre es obligatorio', 'warning')
            return render_template('clientes/formulario.html', cliente=cliente)
        
        # Validar email si se proporciona
        if email and email != cliente['email']:
            # Verificar formato del email
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                flash('El formato del email no es válido', 'warning')
                return render_template('clientes/formulario.html', cliente=cliente)
            
            # Verificar si el email ya existe
            cur = mysql.connection.cursor()
            cur.execute('SELECT id FROM clientes WHERE email = %s AND id != %s', (email, cliente_id))
            if cur.fetchone():
                flash('El email ya está registrado', 'warning')
                cur.close()
                return render_template('clientes/formulario.html', cliente=cliente)
            
            # Verificar si existe en empleados
            cur.execute('SELECT id FROM empleados WHERE email = %s', (email,))
            if cur.fetchone():
                flash('El email ya está registrado como empleado', 'warning')
                cur.close()
                return render_template('clientes/formulario.html', cliente=cliente)
            
            cur.close()
        
        try:
            cur = mysql.connection.cursor()
            
            # Crear consulta base
            query = '''
                UPDATE clientes 
                SET nombre = %s, apellido = %s, email = %s, telefono = %s, 
                    direccion = %s, ciudad = %s, codigo_postal = %s, 
                    identificacion = %s, tipo_cliente = %s, notas = %s, 
                    activo = %s, puede_comprar_online = %s
            '''
            params = [nombre, apellido, email, telefono, direccion, ciudad, 
                     codigo_postal, identificacion, tipo_cliente, notas, 
                     activo, puede_comprar_online]
            
            # Si se proporcionó una nueva contraseña, actualizarla
            if password:
                from extensions import bcrypt
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
                query += ", password = %s"
                params.append(hashed_password)
            
            # Completar consulta
            query += " WHERE id = %s"
            params.append(cliente_id)
            
            # Ejecutar actualización
            cur.execute(query, params)
            mysql.connection.commit()
            cur.close()
            
            flash('Cliente actualizado con éxito', 'success')
            return redirect(url_for('clientes.ver', cliente_id=cliente_id))
            
        except Exception as e:
            flash(f'Error al actualizar el cliente: {str(e)}', 'danger')
            return render_template('clientes/formulario.html', cliente=cliente)
    
    return render_template('clientes/formulario.html', cliente=cliente)

@clientes_bp.route('/<int:cliente_id>/cambiar_estado', methods=['POST'])
@login_required
def cambiar_estado(cliente_id):
    """Activar o desactivar un cliente"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT activo FROM clientes WHERE id = %s', (cliente_id,))
        cliente = cur.fetchone()
        
        if not cliente:
            cur.close()
            flash('Cliente no encontrado', 'warning')
            return redirect(url_for('clientes.index'))
        
        # Cambiar estado
        nuevo_estado = not cliente['activo']
        cur.execute('UPDATE clientes SET activo = %s WHERE id = %s', (nuevo_estado, cliente_id))
        mysql.connection.commit()
        cur.close()
        
        estado_texto = 'activado' if nuevo_estado else 'desactivado'
        flash(f'Cliente {estado_texto} con éxito', 'success')
        
    except Exception as e:
        flash(f'Error al cambiar estado del cliente: {str(e)}', 'danger')
    
    return redirect(url_for('clientes.ver', cliente_id=cliente_id))

@clientes_bp.route('/buscar', methods=['GET'])
@login_required
def buscar():
    """API para buscar clientes (usado en autocompletado)"""
    if not current_user.is_empleado:
        return jsonify([])
    
    term = request.args.get('term', '')
    if not term or len(term) < 2:
        return jsonify([])
    
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT id, nombre, apellido, email, telefono, identificacion
        FROM clientes
        WHERE (nombre LIKE %s OR apellido LIKE %s OR email LIKE %s OR 
               telefono LIKE %s OR identificacion LIKE %s) AND activo = TRUE
        LIMIT 10
    ''', [f'%{term}%'] * 5)
    clientes = cur.fetchall()
    cur.close()
    
    resultados = []
    for cliente in clientes:
        nombre_completo = f"{cliente['nombre']} {cliente['apellido']}" if cliente['apellido'] else cliente['nombre']
        resultados.append({
            'id': cliente['id'],
            'value': nombre_completo,
            'label': f"{nombre_completo} - {cliente['telefono'] or cliente['email']}",
            'nombre': cliente['nombre'],
            'apellido': cliente['apellido'],
            'email': cliente['email'],
            'telefono': cliente['telefono'],
            'identificacion': cliente['identificacion']
        })
    
    return jsonify(resultados) 