from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from models.models import mysql
import json

tienda_bp = Blueprint('tienda', __name__)

@tienda_bp.route('/')
def index():
    """Página principal de la tienda online"""
    # Obtener productos destacados
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.activo = TRUE AND p.destacado = TRUE
        ORDER BY p.id DESC
        LIMIT 8
    ''')
    productos_destacados = cur.fetchall()
    
    # Obtener categorías
    cur.execute('SELECT * FROM categorias WHERE activa = TRUE')
    categorias = cur.fetchall()
    
    # Obtener configuración de la tienda
    cur.execute("SELECT * FROM configuracion WHERE grupo = 'tienda_online'")
    config = {row['nombre']: row['valor'] for row in cur.fetchall()}
    cur.close()
    
    return render_template('tienda/index.html', 
                          productos=productos_destacados, 
                          categorias=categorias,
                          config=config)

@tienda_bp.route('/productos')
def productos():
    """Listado de productos de la tienda"""
    categoria_id = request.args.get('categoria', None)
    busqueda = request.args.get('busqueda', '')
    
    cur = mysql.connection.cursor()
    
    # Construir consulta base
    query = '''
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.activo = TRUE
    '''
    params = []
    
    # Filtrar por categoría si se proporciona
    if categoria_id and categoria_id.isdigit():
        query += ' AND p.categoria_id = %s'
        params.append(int(categoria_id))
    
    # Filtrar por búsqueda si se proporciona
    if busqueda:
        query += ' AND (p.nombre LIKE %s OR p.descripcion LIKE %s)'
        params.extend([f'%{busqueda}%', f'%{busqueda}%'])
    
    query += ' ORDER BY p.id DESC'
    
    cur.execute(query, params)
    productos = cur.fetchall()
    
    # Obtener categorías para el menú lateral
    cur.execute('SELECT * FROM categorias WHERE activa = TRUE')
    categorias = cur.fetchall()
    cur.close()
    
    return render_template('tienda/productos.html', 
                          productos=productos, 
                          categorias=categorias,
                          busqueda=busqueda,
                          categoria_id=categoria_id)

@tienda_bp.route('/producto/<int:producto_id>')
def ver_producto(producto_id):
    """Página de detalle de un producto"""
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.id = %s AND p.activo = TRUE
    ''', (producto_id,))
    producto = cur.fetchone()
    
    if not producto:
        flash('Producto no encontrado', 'warning')
        return redirect(url_for('tienda.productos'))
    
    # Productos relacionados (misma categoría)
    cur.execute('''
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.categoria_id = %s AND p.id != %s AND p.activo = TRUE
        LIMIT 4
    ''', (producto.get('categoria_id'), producto_id))
    productos_relacionados = cur.fetchall()
    cur.close()
    
    return render_template('tienda/producto.html', 
                          producto=producto, 
                          relacionados=productos_relacionados)

@tienda_bp.route('/carrito')
def carrito():
    """Página de carrito de compras"""
    # Si el usuario no está autenticado, usamos un carrito de sesión
    if not current_user.is_authenticated or not current_user.es_cliente:
        carrito_items = session.get('carrito', [])
        producto_ids = [item['producto_id'] for item in carrito_items]
        
        if not producto_ids:
            return render_template('tienda/carrito.html', items=[], total=0)
        
        # Obtener información de los productos
        cur = mysql.connection.cursor()
        placeholders = ','.join(['%s'] * len(producto_ids))
        cur.execute(f'SELECT * FROM productos WHERE id IN ({placeholders}) AND activo = TRUE', 
                   producto_ids)
        productos = {producto['id']: producto for producto in cur.fetchall()}
        cur.close()
        
        # Calcular total y armar lista de items para la vista
        items = []
        total = 0
        
        for item in carrito_items:
            producto_id = item['producto_id']
            cantidad = item['cantidad']
            
            if producto_id in productos:
                producto = productos[producto_id]
                subtotal = producto['precio_venta'] * cantidad
                total += subtotal
                
                items.append({
                    'id': producto_id,
                    'nombre': producto['nombre'],
                    'precio': producto['precio_venta'],
                    'cantidad': cantidad,
                    'subtotal': subtotal,
                    'imagen': producto['imagen']
                })
        
        return render_template('tienda/carrito.html', items=items, total=total)
    else:
        # Usuario autenticado, usamos carrito de base de datos
        cliente_id = current_user.id
        
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT c.*, p.nombre, p.precio_venta, p.imagen
            FROM carrito c
            JOIN productos p ON c.producto_id = p.id
            WHERE c.cliente_id = %s
        ''', (cliente_id,))
        carrito_items = cur.fetchall()
        
        total = sum(item['precio_venta'] * item['cantidad'] for item in carrito_items)
        cur.close()
        
        return render_template('tienda/carrito.html', items=carrito_items, total=total)

@tienda_bp.route('/agregar_carrito', methods=['POST'])
def agregar_carrito():
    """Agregar producto al carrito"""
    producto_id = request.form.get('producto_id', type=int)
    cantidad = request.form.get('cantidad', 1, type=int)
    
    if not producto_id or cantidad < 1:
        flash('Datos inválidos', 'warning')
        return redirect(url_for('tienda.productos'))
    
    # Verificar que el producto existe y está activo
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM productos WHERE id = %s AND activo = TRUE', (producto_id,))
    producto = cur.fetchone()
    cur.close()
    
    if not producto:
        flash('Producto no disponible', 'warning')
        return redirect(url_for('tienda.productos'))
    
    # Si el usuario no está autenticado, usar carrito de sesión
    if not current_user.is_authenticated or not current_user.es_cliente:
        carrito = session.get('carrito', [])
        
        # Verificar si el producto ya está en el carrito
        for item in carrito:
            if item['producto_id'] == producto_id:
                item['cantidad'] += cantidad
                session['carrito'] = carrito
                flash('Producto actualizado en el carrito', 'success')
                return redirect(url_for('tienda.carrito'))
        
        # Agregar nuevo producto al carrito
        carrito.append({
            'producto_id': producto_id,
            'cantidad': cantidad
        })
        
        session['carrito'] = carrito
        flash('Producto agregado al carrito', 'success')
        return redirect(url_for('tienda.carrito'))
    else:
        # Usuario autenticado, usar carrito de base de datos
        cliente_id = current_user.id
        
        try:
            cur = mysql.connection.cursor()
            
            # Verificar si el producto ya está en el carrito
            cur.execute('SELECT * FROM carrito WHERE cliente_id = %s AND producto_id = %s', 
                       (cliente_id, producto_id))
            item_existente = cur.fetchone()
            
            if item_existente:
                # Actualizar cantidad
                nueva_cantidad = item_existente['cantidad'] + cantidad
                cur.execute('UPDATE carrito SET cantidad = %s WHERE id = %s', 
                           (nueva_cantidad, item_existente['id']))
                flash('Producto actualizado en el carrito', 'success')
            else:
                # Insertar nuevo item en el carrito
                cur.execute('INSERT INTO carrito (cliente_id, producto_id, cantidad) VALUES (%s, %s, %s)', 
                           (cliente_id, producto_id, cantidad))
                flash('Producto agregado al carrito', 'success')
            
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('tienda.carrito'))
        
        except Exception as e:
            flash(f'Error al agregar producto al carrito: {str(e)}', 'danger')
            return redirect(url_for('tienda.productos'))

@tienda_bp.route('/eliminar_carrito/<int:item_id>', methods=['POST'])
def eliminar_carrito(item_id):
    """Eliminar producto del carrito"""
    # Si el usuario no está autenticado, eliminar del carrito de sesión
    if not current_user.is_authenticated or not current_user.es_cliente:
        carrito = session.get('carrito', [])
        
        if item_id < len(carrito):
            carrito.pop(item_id)
            session['carrito'] = carrito
            flash('Producto eliminado del carrito', 'success')
        
        return redirect(url_for('tienda.carrito'))
    else:
        # Usuario autenticado, eliminar del carrito en la base de datos
        try:
            cur = mysql.connection.cursor()
            cur.execute('DELETE FROM carrito WHERE id = %s AND cliente_id = %s', 
                       (item_id, current_user.id))
            mysql.connection.commit()
            cur.close()
            
            flash('Producto eliminado del carrito', 'success')
        except Exception as e:
            flash(f'Error al eliminar producto del carrito: {str(e)}', 'danger')
        
        return redirect(url_for('tienda.carrito'))

@tienda_bp.route('/mi_cuenta')
@login_required
def mi_cuenta():
    """Página de cuenta de cliente"""
    # Redirigir a la función mi_cuenta del blueprint main
    return redirect(url_for('main.mi_cuenta'))

@tienda_bp.route('/reparacion/<int:reparacion_id>')
@login_required
def ver_reparacion(reparacion_id):
    """Ver detalle de una reparación"""
    if not current_user.es_cliente:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    cliente_id = current_user.id
    
    # Obtener datos de la reparación
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT r.*, t.nombre as tecnico_nombre, e.nombre as recibido_por_nombre
        FROM reparaciones r
        LEFT JOIN empleados t ON r.tecnico_id = t.id
        LEFT JOIN empleados e ON r.recibido_por = e.id
        WHERE r.id = %s AND r.cliente_id = %s
    ''', (reparacion_id, cliente_id))
    reparacion = cur.fetchone()
    
    if not reparacion:
        flash('Reparación no encontrada o no tienes permiso para verla', 'warning')
        return redirect(url_for('tienda.mi_cuenta'))
    
    # Obtener repuestos utilizados
    cur.execute('''
        SELECT rr.*, p.nombre as producto_nombre
        FROM reparaciones_repuestos rr
        LEFT JOIN productos p ON rr.producto_id = p.id
        WHERE rr.reparacion_id = %s
    ''', (reparacion_id,))
    repuestos = cur.fetchall()
    
    # Obtener seguimiento
    cur.execute('''
        SELECT s.*, e.nombre as empleado_nombre
        FROM seguimiento_reparaciones s
        LEFT JOIN empleados e ON s.empleado_id = e.id
        WHERE s.reparacion_id = %s
        ORDER BY s.fecha ASC
    ''', (reparacion_id,))
    seguimiento = cur.fetchall()
    cur.close()
    
    return render_template('tienda/reparacion.html',
                          reparacion=reparacion,
                          repuestos=repuestos,
                          seguimiento=seguimiento)

@tienda_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Proceso de checkout/pago"""
    if not current_user.es_cliente:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    cliente_id = current_user.id
    
    # Si es POST, procesar la compra
    if request.method == 'POST':
        direccion = request.form.get('direccion')
        ciudad = request.form.get('ciudad')
        codigo_postal = request.form.get('codigo_postal')
        metodo_pago = request.form.get('metodo_pago')
        
        if not all([direccion, ciudad, codigo_postal, metodo_pago]):
            flash('Por favor completa todos los campos', 'warning')
            return redirect(url_for('tienda.checkout'))
        
        # Obtener productos en el carrito
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT c.*, p.precio_venta, p.stock
            FROM carrito c
            JOIN productos p ON c.producto_id = p.id
            WHERE c.cliente_id = %s
        ''', (cliente_id,))
        items = cur.fetchall()
        
        if not items:
            flash('Tu carrito está vacío', 'warning')
            return redirect(url_for('tienda.carrito'))
        
        # Verificar stock disponible
        for item in items:
            if item['cantidad'] > item['stock']:
                flash(f'No hay suficiente stock para el producto: {item["nombre"]}', 'danger')
                return redirect(url_for('tienda.carrito'))
        
        # Calcular totales
        subtotal = sum(item['precio_venta'] * item['cantidad'] for item in items)
        
        # Obtener configuración de envío
        cur.execute("SELECT * FROM configuracion WHERE grupo = 'tienda_online'")
        config = {row['nombre']: row['valor'] for row in cur.fetchall()}
        
        # Calcular costo de envío
        costo_envio = 0
        envio_gratis_desde = float(config.get('envio_gratis_desde', 0))
        if subtotal < envio_gratis_desde:
            costo_envio = float(config.get('costo_envio_default', 0))
        
        total = subtotal + costo_envio
        
        try:
            # Crear venta
            direccion_completa = f"{direccion}, {ciudad}, CP {codigo_postal}"
            cur.execute('''
                INSERT INTO ventas 
                (cliente_id, total, metodo_pago, estado, tipo, direccion_envio, costo_envio, estado_envio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (cliente_id, total, metodo_pago, 'Pendiente', 'Online', direccion_completa, costo_envio, 'Pendiente'))
            
            # Obtener ID de la venta
            venta_id = cur.lastrowid
            
            # Crear detalles de venta y actualizar stock
            for item in items:
                producto_id = item['producto_id']
                cantidad = item['cantidad']
                precio = item['precio_venta']
                subtotal = precio * cantidad
                
                # Insertar detalle
                cur.execute('''
                    INSERT INTO detalles_venta 
                    (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (venta_id, producto_id, cantidad, precio, subtotal))
                
                # Actualizar stock
                cur.execute('UPDATE productos SET stock = stock - %s WHERE id = %s', 
                           (cantidad, producto_id))
            
            # Vaciar carrito
            cur.execute('DELETE FROM carrito WHERE cliente_id = %s', (cliente_id,))
            
            # Actualizar última compra del cliente
            cur.execute('UPDATE clientes SET ultima_compra = NOW() WHERE id = %s', (cliente_id,))
            
            mysql.connection.commit()
            
            flash('¡Compra realizada con éxito! Pronto nos comunicaremos para coordinar la entrega.', 'success')
            return redirect(url_for('tienda.compra_exitosa', venta_id=venta_id))
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al procesar la compra: {str(e)}', 'danger')
            return redirect(url_for('tienda.carrito'))
        finally:
            cur.close()
    
    # Obtener datos del cliente para pre-llenar el formulario
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM clientes WHERE id = %s', (cliente_id,))
    cliente = cur.fetchone()
    
    # Obtener productos en el carrito
    cur.execute('''
        SELECT c.*, p.nombre, p.precio_venta, p.imagen, p.stock
        FROM carrito c
        JOIN productos p ON c.producto_id = p.id
        WHERE c.cliente_id = %s
    ''', (cliente_id,))
    items = cur.fetchall()
    
    if not items:
        flash('Tu carrito está vacío', 'warning')
        return redirect(url_for('tienda.carrito'))
    
    # Calcular totales
    subtotal = sum(item['precio_venta'] * item['cantidad'] for item in items)
    
    # Obtener configuración de envío
    cur.execute("SELECT * FROM configuracion WHERE grupo = 'tienda_online'")
    config = {row['nombre']: row['valor'] for row in cur.fetchall()}
    cur.close()
    
    # Calcular costo de envío
    costo_envio = 0
    envio_gratis_desde = float(config.get('envio_gratis_desde', 0))
    if subtotal < envio_gratis_desde:
        costo_envio = float(config.get('costo_envio_default', 0))
    
    total = subtotal + costo_envio
    
    return render_template('tienda/checkout.html',
                          cliente=cliente,
                          items=items,
                          subtotal=subtotal,
                          costo_envio=costo_envio,
                          total=total,
                          config=config)

@tienda_bp.route('/mis-compras')
@login_required
def mis_compras():
    """Muestra el historial de compras del cliente"""
    if not current_user.es_cliente:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    cliente_id = current_user.id
    
    # Obtener todas las compras del cliente
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT * FROM ventas 
        WHERE cliente_id = %s
        ORDER BY fecha DESC
    ''', (cliente_id,))
    compras = cur.fetchall()
    cur.close()
    
    return render_template('tienda/mis_compras.html', compras=compras)

@tienda_bp.route('/compra_exitosa/<int:venta_id>')
@login_required
def compra_exitosa(venta_id):
    """Página de confirmación de compra exitosa"""
    if not current_user.es_cliente:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('main.index'))
    
    cliente_id = current_user.id
    
    # Obtener datos de la venta
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT * FROM ventas 
        WHERE id = %s AND cliente_id = %s
    ''', (venta_id, cliente_id))
    venta = cur.fetchone()
    
    if not venta:
        flash('Venta no encontrada', 'warning')
        return redirect(url_for('tienda.mis_compras'))
    
    # Intentar obtener detalles si la tabla existe
    detalles = []
    try:
        cur.execute('''
            SELECT d.*, p.nombre
            FROM detalles_venta d
            JOIN productos p ON d.producto_id = p.id
            WHERE d.venta_id = %s
        ''', (venta_id,))
        detalles = cur.fetchall()
    except:
        # Si hay error (tabla no existe), dejamos detalles como lista vacía
        pass
    
    cur.close()
    
    return render_template('tienda/compra_exitosa.html',
                          venta=venta,
                          detalles=detalles)

@tienda_bp.route('/crear-datos-prueba')
def crear_datos_prueba():
    """Crea datos de prueba para las funciones del perfil de cliente"""
    try:
        cur = mysql.connection.cursor()
        
        # Crear un cliente de prueba
        cur.execute("SELECT * FROM clientes WHERE email = 'cliente@test.com'")
        cliente = cur.fetchone()
        
        if not cliente:
            # Crear cliente de prueba
            cur.execute('''
                INSERT INTO clientes (nombre, email, password, direccion, telefono, activo)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', ('Cliente de Prueba', 'cliente@test.com', 'password123', 'Dirección de prueba', '555-123-4567', True))
            cliente_id = cur.lastrowid
            flash('Cliente de prueba creado correctamente', 'success')
        else:
            cliente_id = cliente['id'] if isinstance(cliente, dict) else cliente[0]
            flash('El cliente de prueba ya existe', 'info')
        
        # Crear algunas ventas de prueba
        estados = ['COMPLETADA', 'PENDIENTE', 'CANCELADA']
        for i in range(5):
            estado = estados[i % 3]
            total = (i + 1) * 100
            
            cur.execute('''
                INSERT INTO ventas (cliente_id, fecha, total, estado, observaciones)
                VALUES (%s, DATE_SUB(NOW(), INTERVAL %s DAY), %s, %s, %s)
            ''', (cliente_id, i*3, total, estado, f'Venta de prueba #{i+1}'))
            
            venta_id = cur.lastrowid
            
            # Crear algunos detalles de venta
            for j in range(2):
                cur.execute('''
                    INSERT INTO detalles_venta (venta_id, cantidad, precio_unitario, subtotal)
                    VALUES (%s, %s, %s, %s)
                ''', (venta_id, j+1, 50*(j+1), 50*(j+1)*(j+1)))
        
        # Crear algunas reparaciones de prueba
        estados_rep = ['RECIBIDO', 'DIAGNOSTICO', 'REPARACION', 'LISTO', 'ENTREGADO']
        for i in range(5):
            estado = estados_rep[i % 5]
            
            cur.execute('''
                INSERT INTO reparaciones (cliente_id, descripcion, electrodomestico, 
                                        estado, fecha_recepcion)
                VALUES (%s, %s, %s, %s, DATE_SUB(NOW(), INTERVAL %s DAY))
            ''', (cliente_id, f'Reparación de prueba #{i+1}', 
                f'Electrodoméstico {i+1}', estado, i*5))
            
        mysql.connection.commit()
        flash('Datos de prueba creados correctamente. Usa cliente@test.com / password123 para ingresar', 'success')
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al crear datos de prueba: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('main.index')) 