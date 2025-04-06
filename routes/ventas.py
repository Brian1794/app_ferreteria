from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models.models import mysql
from datetime import datetime
import json

ventas_bp = Blueprint('ventas', __name__)

@ventas_bp.route('/')
@login_required
def index():
    """Lista de ventas realizadas"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Parámetros de filtro
    estado = request.args.get('estado', 'todas')
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    cliente = request.args.get('cliente', '')
    
    # Construir consulta SQL
    query = '''
        SELECT v.*, c.nombre as cliente_nombre, c.apellido as cliente_apellido,
               e.nombre as vendedor_nombre
        FROM ventas v
        LEFT JOIN clientes c ON v.cliente_id = c.id
        LEFT JOIN empleados e ON v.empleado_id = e.id
        WHERE 1=1
    '''
    params = []
    
    # Aplicar filtros
    if estado != 'todas':
        query += ' AND v.estado = %s'
        params.append(estado)
    
    if desde:
        query += ' AND DATE(v.fecha) >= %s'
        params.append(desde)
    
    if hasta:
        query += ' AND DATE(v.fecha) <= %s'
        params.append(hasta)
    
    if cliente:
        query += ' AND (c.nombre LIKE %s OR c.apellido LIKE %s)'
        params.extend([f'%{cliente}%', f'%{cliente}%'])
    
    query += ' ORDER BY v.fecha DESC'
    
    # Ejecutar consulta
    cur = mysql.connection.cursor()
    cur.execute(query, params)
    ventas = cur.fetchall()
    cur.close()
    
    return render_template('ventas/lista.html',
                          ventas=ventas,
                          estado=estado,
                          desde=desde,
                          hasta=hasta,
                          cliente=cliente)

@ventas_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def nueva():
    """Crear una nueva venta"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        cliente_id = request.form.get('cliente_id')
        metodo_pago = request.form.get('metodo_pago')
        descuento = request.form.get('descuento', 0)
        notas = request.form.get('notas', '')
        productos_json = request.form.get('productos_json', '[]')
        
        # Validaciones básicas
        if not cliente_id or not metodo_pago:
            flash('Cliente y método de pago son obligatorios', 'warning')
            return redirect(url_for('ventas.nueva'))
        
        try:
            productos = json.loads(productos_json)
            
            if not productos:
                flash('Debe agregar al menos un producto', 'warning')
                return redirect(url_for('ventas.nueva'))
            
            # Verificar stock disponible
            cur = mysql.connection.cursor()
            for producto in productos:
                producto_id = producto.get('id')
                cantidad = producto.get('cantidad', 0)
                
                cur.execute('SELECT stock FROM productos WHERE id = %s', (producto_id,))
                result = cur.fetchone()
                
                if not result or result['stock'] < cantidad:
                    cur.close()
                    flash(f'Stock insuficiente para el producto ID {producto_id}', 'danger')
                    return redirect(url_for('ventas.nueva'))
            
            # Calcular total
            total = sum(float(p.get('subtotal', 0)) for p in productos)
            
            # Aplicar descuento
            if descuento:
                descuento = float(descuento)
                total -= descuento
            
            # Crear venta
            cur.execute('''
                INSERT INTO ventas 
                (cliente_id, fecha, total, descuento, metodo_pago, estado, empleado_id, notas)
                VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s)
            ''', (cliente_id, total, descuento, metodo_pago, 'Pagada', current_user.id, notas))
            
            venta_id = cur.lastrowid
            
            # Crear detalles de venta y actualizar stock
            for producto in productos:
                producto_id = producto.get('id')
                cantidad = producto.get('cantidad', 0)
                precio = producto.get('precio', 0)
                subtotal = producto.get('subtotal', 0)
                
                # Insertar detalle
                cur.execute('''
                    INSERT INTO detalles_venta 
                    (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (venta_id, producto_id, cantidad, precio, subtotal))
                
                # Actualizar stock
                cur.execute('UPDATE productos SET stock = stock - %s WHERE id = %s', 
                           (cantidad, producto_id))
            
            # Actualizar última compra del cliente
            cur.execute('UPDATE clientes SET ultima_compra = NOW() WHERE id = %s', (cliente_id,))
            
            mysql.connection.commit()
            cur.close()
            
            flash('Venta registrada con éxito', 'success')
            return redirect(url_for('ventas.ver', venta_id=venta_id))
            
        except Exception as e:
            flash(f'Error al registrar venta: {str(e)}', 'danger')
            return redirect(url_for('ventas.nueva'))
    
    # Cargar datos para el formulario
    cur = mysql.connection.cursor()
    
    # Cargar métodos de pago
    metodos_pago = ['Efectivo', 'Tarjeta', 'Transferencia', 'Mixto', 'Crédito']
    
    cur.close()
    
    return render_template('ventas/formulario.html',
                          metodos_pago=metodos_pago)

@ventas_bp.route('/<int:venta_id>')
@login_required
def ver(venta_id):
    """Ver detalles de una venta"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener datos de la venta
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT v.*, c.nombre as cliente_nombre, c.apellido as cliente_apellido, 
               c.telefono as cliente_telefono, c.email as cliente_email,
               e.nombre as vendedor_nombre
        FROM ventas v
        LEFT JOIN clientes c ON v.cliente_id = c.id
        LEFT JOIN empleados e ON v.empleado_id = e.id
        WHERE v.id = %s
    ''', (venta_id,))
    venta = cur.fetchone()
    
    if not venta:
        flash('Venta no encontrada', 'warning')
        return redirect(url_for('ventas.index'))
    
    # Obtener detalles de la venta
    cur.execute('''
        SELECT d.*, p.nombre as producto_nombre, p.codigo_barras, p.imagen
        FROM detalles_venta d
        JOIN productos p ON d.producto_id = p.id
        WHERE d.venta_id = %s
    ''', (venta_id,))
    detalles = cur.fetchall()
    cur.close()
    
    return render_template('ventas/ver.html',
                          venta=venta,
                          detalles=detalles)

@ventas_bp.route('/<int:venta_id>/cambiar_estado', methods=['POST'])
@login_required
def cambiar_estado(venta_id):
    """Cambiar el estado de una venta"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    nuevo_estado = request.form.get('estado')
    
    if not nuevo_estado:
        flash('Estado no especificado', 'warning')
        return redirect(url_for('ventas.ver', venta_id=venta_id))
    
    try:
        cur = mysql.connection.cursor()
        
        # Obtener estado actual para comparar
        cur.execute('SELECT estado FROM ventas WHERE id = %s', (venta_id,))
        venta = cur.fetchone()
        
        if not venta:
            flash('Venta no encontrada', 'warning')
            return redirect(url_for('ventas.index'))
        
        estado_anterior = venta['estado']
        
        # Si se cancela una venta, restaurar el stock
        if nuevo_estado == 'Cancelada' and estado_anterior != 'Cancelada':
            cur.execute('''
                SELECT producto_id, cantidad 
                FROM detalles_venta 
                WHERE venta_id = %s
            ''', (venta_id,))
            detalles = cur.fetchall()
            
            for detalle in detalles:
                cur.execute('''
                    UPDATE productos 
                    SET stock = stock + %s 
                    WHERE id = %s
                ''', (detalle['cantidad'], detalle['producto_id']))
        
        # Si se reactiva una venta cancelada, reducir stock nuevamente
        elif estado_anterior == 'Cancelada' and nuevo_estado != 'Cancelada':
            cur.execute('''
                SELECT producto_id, cantidad 
                FROM detalles_venta 
                WHERE venta_id = %s
            ''', (venta_id,))
            detalles = cur.fetchall()
            
            for detalle in detalles:
                cur.execute('''
                    UPDATE productos 
                    SET stock = stock - %s 
                    WHERE id = %s
                ''', (detalle['cantidad'], detalle['producto_id']))
        
        # Actualizar estado
        cur.execute('UPDATE ventas SET estado = %s WHERE id = %s', (nuevo_estado, venta_id))
        mysql.connection.commit()
        cur.close()
        
        flash(f'Estado de venta actualizado a {nuevo_estado}', 'success')
        
    except Exception as e:
        flash(f'Error al cambiar estado: {str(e)}', 'danger')
    
    return redirect(url_for('ventas.ver', venta_id=venta_id))

@ventas_bp.route('/buscar_productos')
@login_required
def buscar_productos():
    """API para buscar productos (usado en el formulario de venta)"""
    if not current_user.is_empleado:
        return jsonify([])
    
    term = request.args.get('term', '')
    if not term or len(term) < 2:
        return jsonify([])
    
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT id, nombre, codigo_barras, precio_venta, stock, imagen
        FROM productos
        WHERE (nombre LIKE %s OR codigo_barras LIKE %s) AND activo = TRUE AND stock > 0
        LIMIT 10
    ''', [f'%{term}%', f'%{term}%'])
    productos = cur.fetchall()
    cur.close()
    
    resultados = []
    for producto in productos:
        resultados.append({
            'id': producto['id'],
            'label': f"{producto['nombre']} - ${producto['precio_venta']} ({producto['stock']} en stock)",
            'value': producto['nombre'],
            'nombre': producto['nombre'],
            'precio': float(producto['precio_venta']),
            'stock': producto['stock'],
            'codigo': producto['codigo_barras'],
            'imagen': producto['imagen']
        })
    
    return jsonify(resultados)

@ventas_bp.route('/buscar_clientes')
@login_required
def buscar_clientes():
    """API para buscar clientes (usado en el formulario de venta)"""
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

@ventas_bp.route('/reportes')
@login_required
def reportes():
    """Reportes de ventas"""
    if not current_user.is_empleado:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    # Parámetros de filtro
    tipo_reporte = request.args.get('tipo', 'diario')
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    
    # Construir consulta SQL según el tipo de reporte
    if tipo_reporte == 'diario':
        query = '''
            SELECT DATE(fecha) as fecha, COUNT(*) as total_ventas, SUM(total) as monto_total
            FROM ventas
            WHERE estado = 'Pagada'
        '''
        group_by = 'DATE(fecha)'
        
    elif tipo_reporte == 'mensual':
        query = '''
            SELECT YEAR(fecha) as anio, MONTH(fecha) as mes, 
                   COUNT(*) as total_ventas, SUM(total) as monto_total
            FROM ventas
            WHERE estado = 'Pagada'
        '''
        group_by = 'YEAR(fecha), MONTH(fecha)'
        
    elif tipo_reporte == 'productos':
        query = '''
            SELECT p.nombre, SUM(d.cantidad) as total_vendido, 
                   SUM(d.subtotal) as monto_total
            FROM detalles_venta d
            JOIN productos p ON d.producto_id = p.id
            JOIN ventas v ON d.venta_id = v.id
            WHERE v.estado = 'Pagada'
        '''
        group_by = 'p.id'
        
    elif tipo_reporte == 'vendedores':
        query = '''
            SELECT e.nombre, COUNT(v.id) as total_ventas, 
                   SUM(v.total) as monto_total
            FROM ventas v
            JOIN empleados e ON v.empleado_id = e.id
            WHERE v.estado = 'Pagada'
        '''
        group_by = 'e.id'
        
    else:  # clientes
        query = '''
            SELECT c.nombre, c.apellido, COUNT(v.id) as total_compras, 
                   SUM(v.total) as monto_total
            FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            WHERE v.estado = 'Pagada'
        '''
        group_by = 'c.id'
    
    # Aplicar filtros de fecha
    params = []
    if desde:
        query += ' AND DATE(v.fecha) >= %s'
        params.append(desde)
    
    if hasta:
        query += ' AND DATE(v.fecha) <= %s'
        params.append(hasta)
    
    # Completar consulta
    query += f' GROUP BY {group_by} ORDER BY monto_total DESC'
    
    # Ejecutar consulta
    cur = mysql.connection.cursor()
    cur.execute(query, params)
    resultados = cur.fetchall()
    cur.close()
    
    return render_template('ventas/reportes.html',
                          tipo_reporte=tipo_reporte,
                          desde=desde,
                          hasta=hasta,
                          resultados=resultados) 