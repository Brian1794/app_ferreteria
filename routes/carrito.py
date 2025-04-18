from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models.carrito import Carrito, Pedido
from extensions import mysql
from database import get_cursor, ejecutar_consulta, close_connection
import json
from flask_wtf.csrf import CSRFProtect
import time
from contextlib import contextmanager

carrito_bp = Blueprint('carrito', __name__)

# Exceptuar validación CSRF para todas las rutas de carrito - se manejará a nivel de aplicación
# No es necesario el decorador @csrf_exempt ya que se desactivó a nivel global

@carrito_bp.route('/')
@login_required
def ver_carrito():
    """Muestra el contenido del carrito del usuario"""
    if not current_user.is_authenticated or not hasattr(current_user, 'id'):
        flash('Debe iniciar sesión para ver su carrito', 'warning')
        return redirect(url_for('auth.login'))
    
    # Obtener los items del carrito
    items = Carrito.obtener_items(current_user.id)
    total = Carrito.obtener_total(current_user.id)
    
    if not items:
        flash('Tu carrito está vacío. ¡Agrega algunos productos!', 'info')
    
    return render_template('cart/view.html', 
                           items=items, 
                           total=total)

@carrito_bp.route('/agregar', methods=['POST'])
def agregar_al_carrito():
    """Agrega un producto al carrito"""
    # Si es Ajax, no se requiere verificación CSRF
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Debe iniciar sesión'})
    
    try:
        # Obtener datos de la solicitud
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Si no hay datos JSON, intentar obtener de form-data o params
        if not data:
            producto_id = request.form.get('producto_id') or request.args.get('producto_id')
            cantidad = request.form.get('cantidad') or request.args.get('cantidad', 1)
            
            if not producto_id:
                return jsonify({'success': False, 'message': 'ID de producto no proporcionado'})
                
            data = {
                'producto_id': producto_id,
                'cantidad': cantidad
            }
        
        # Imprimir datos recibidos para depuración
        print(f"Datos para agregar al carrito: {data}")
        
        # Convertir a enteros con manejo de errores
        try:
            producto_id = int(data.get('producto_id'))
            cantidad = int(data.get('cantidad', 1))
        except (ValueError, TypeError) as e:
            print(f"Error al convertir datos: {str(e)}, datos: {data}")
            return jsonify({'success': False, 'message': f'Datos de producto inválidos: {str(e)}'})
        
        # Validar que la cantidad sea positiva
        if cantidad <= 0:
            return jsonify({'success': False, 'message': 'La cantidad debe ser mayor a 0'})
        
        # Verificar stock disponible
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT stock, nombre, imagen FROM productos WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()
        
        if not producto:
            cursor.close()
            return jsonify({'success': False, 'message': f'Producto con ID {producto_id} no encontrado'})
        
        # Obtener información del producto con manejo seguro
        try:
            if isinstance(producto, dict):
                stock = int(producto.get('stock', 0) or 0)  # Manejar None como 0
                nombre = producto.get('nombre', 'Producto')
                imagen = producto.get('imagen', '')
            else:
                stock = int(producto[0] or 0)  # Manejar None como 0
                nombre = producto[1] if len(producto) > 1 else 'Producto'
                imagen = producto[2] if len(producto) > 2 else ''
                
            print(f"Stock del producto {nombre}: {stock}")
            
            if cantidad > stock:
                cursor.close()
                return jsonify({
                    'success': False, 
                    'message': f'No hay suficiente stock disponible. Máximo: {stock}'
                })
        except Exception as e:
            cursor.close()
            print(f"Error al procesar información del producto: {str(e)}")
            return jsonify({'success': False, 'message': f'Error al procesar el producto: {str(e)}'})
        
        # Agregar al carrito
        try:
            resultado = Carrito.agregar_producto(current_user.id, producto_id, cantidad)
            if not resultado:
                cursor.close()
                return jsonify({'success': False, 'message': 'Error al agregar al carrito'})
        except Exception as e:
            cursor.close()
            print(f"Error en Carrito.agregar_producto: {str(e)}")
            return jsonify({'success': False, 'message': f'Error al agregar producto: {str(e)}'})
        
        # Obtener conteo actualizado
        try:
            total_items = Carrito.contar_items(current_user.id)
        except Exception as e:
            print(f"Error al contar items: {str(e)}")
            total_items = 0
            
        cursor.close()
        
        return jsonify({
            'success': True, 
            'message': f'{nombre} agregado al carrito ({cantidad} unidad(es))',
            'total_items': total_items,
            'product_name': nombre,
            'product_image': imagen,
            'quantity': cantidad
        })
        
    except Exception as e:
        # Registrar el error para depuración
        print(f"Error al agregar al carrito: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@carrito_bp.route('/actualizar', methods=['POST'])
@login_required
def actualizar_carrito():
    """Actualiza la cantidad de un producto en el carrito"""
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Debe iniciar sesión'})
    
    try:
        data = request.get_json()
        producto_id = int(data.get('producto_id'))
        cantidad = int(data.get('cantidad', 1))
        
        # Validar que la cantidad sea positiva
        if cantidad <= 0:
            # Si es cero o negativa, eliminar del carrito
            Carrito.eliminar_producto(current_user.id, producto_id)
            mensaje = 'Producto eliminado del carrito'
        else:
            # Verificar stock disponible
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT stock FROM productos WHERE id = %s", (producto_id,))
            producto = cursor.fetchone()
            cursor.close()
            
            if not producto:
                return jsonify({'success': False, 'message': 'Producto no encontrado'})
            
            stock = producto['stock'] if isinstance(producto, dict) else producto[0]
            
            if cantidad > stock:
                return jsonify({
                    'success': False, 
                    'message': f'No hay suficiente stock disponible. Máximo: {stock}'
                })
            
            # Actualizar cantidad
            Carrito.actualizar_cantidad(current_user.id, producto_id, cantidad)
            mensaje = 'Carrito actualizado'
        
        # Obtener datos actualizados
        items = Carrito.obtener_items(current_user.id)
        total = Carrito.obtener_total(current_user.id)
        total_items = Carrito.contar_items(current_user.id)
        
        return jsonify({
            'success': True, 
            'message': mensaje,
            'total': total,
            'total_items': total_items,
            'items': items
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@carrito_bp.route('/eliminar/<int:producto_id>', methods=['POST'])
@login_required
def eliminar_del_carrito(producto_id):
    """Elimina un producto del carrito"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión', 'warning')
        return redirect(url_for('auth.login'))
    
    Carrito.eliminar_producto(current_user.id, producto_id)
    flash('Producto eliminado del carrito', 'success')
    
    return redirect(url_for('carrito.ver_carrito'))

@carrito_bp.route('/vaciar', methods=['POST'])
@login_required
def vaciar_carrito():
    """Elimina todos los productos del carrito"""
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Debe iniciar sesión'})
    
    try:
        Carrito.vaciar_carrito(current_user.id)
        return jsonify({
            'success': True, 
            'message': 'Carrito vaciado correctamente',
            'total': 0,
            'num_items': 0
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@carrito_bp.route('/checkout')
@login_required
def checkout():
    """Muestra la página de finalización de compra"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para completar la compra', 'warning')
        return redirect(url_for('auth.login'))
    
    try:
        # Obtener los items del carrito
        items = Carrito.obtener_items(current_user.id)
        
        if not items:
            flash('Su carrito está vacío', 'warning')
            return redirect(url_for('carrito.ver_carrito'))
        
        total = Carrito.obtener_total(current_user.id)
        
        # Obtener información del cliente y total de pedidos usando una sola conexión
        with get_cursor(dictionary=True) as cursor:
            # Obtener información del cliente
            cursor.execute("""
                SELECT c.*, COUNT(p.id) as total_pedidos 
                FROM clientes c 
                LEFT JOIN pedidos p ON c.id = p.cliente_id 
                WHERE c.id = %s 
                GROUP BY c.id
            """, (current_user.id,))
            cliente = cursor.fetchone()
            
            if not cliente:
                flash('No se encontró información del cliente', 'danger')
                return redirect(url_for('main.index'))
        
        return render_template('carrito/checkout.html', 
                             items=items, 
                             total=total,
                             cliente=cliente)
                             
    except Exception as e:
        flash(f'Error al cargar la página de checkout: {str(e)}', 'danger')
        return redirect(url_for('carrito.ver_carrito'))

@carrito_bp.route('/procesar-pedido', methods=['POST'])
@login_required
def procesar_pedido():
    """Procesa un nuevo pedido"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para completar la compra', 'warning')
        return redirect(url_for('auth.login'))
    
    # Verificar que el carrito no esté vacío
    items = Carrito.obtener_items(current_user.id)
    if not items:
        flash('Tu carrito está vacío. No se puede procesar el pedido.', 'warning')
        return redirect(url_for('productos.catalogo'))
    
    # Obtener información del cliente
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id = %s", (current_user.id,))
    cliente = cursor.fetchone()
    
    if not cliente:
        flash('No se encontró información del cliente', 'danger')
        cursor.close()
        return redirect(url_for('carrito.checkout'))
    
    # Obtener datos del formulario
    telefono = request.form.get('telefono', '')
    direccion = request.form.get('direccion', '')
    identificacion = request.form.get('identificacion', '')
    guardar_datos = 'guardar_datos' in request.form
    notas = request.form.get('notas', '')
    
    # Verificar si los datos son válidos
    if not telefono or not direccion:
        flash('Por favor ingrese dirección y teléfono para continuar', 'warning')
        cursor.close()
        return redirect(url_for('carrito.checkout'))
    
    # Si se marcó la opción de guardar datos, actualizarlos en el perfil
    if guardar_datos:
        try:
            # Actualizar perfil del cliente
            cursor.execute("""
                UPDATE clientes 
                SET telefono = %s, direccion = %s, identificacion = %s
                WHERE id = %s
            """, (telefono, direccion, identificacion, current_user.id))
            mysql.connection.commit()
        except Exception as e:
            print(f"Error al actualizar perfil: {e}")
    
    # Crear datos de envío con la información proporcionada
    datos_envio = {
        'direccion': direccion,
        'telefono': telefono,
        'identificacion': identificacion,
        'notas': notas
    }
    
    # Verificar stock antes de crear el pedido
    for item in items:
        cursor.execute("SELECT stock FROM productos WHERE id = %s", (item['producto_id'],))
        producto = cursor.fetchone()
        stock_actual = producto['stock'] if isinstance(producto, dict) else producto[0]
        
        if item['cantidad'] > stock_actual:
            flash(f'No hay suficiente stock para {item["nombre"]}. Stock disponible: {stock_actual}', 'danger')
            cursor.close()
            return redirect(url_for('carrito.checkout'))
    
    # Crear pedido
    exito, resultado = Pedido.crear_desde_carrito(current_user.id, datos_envio)
    
    if not exito:
        flash(f'Error al procesar el pedido: {resultado}', 'danger')
        cursor.close()
        return redirect(url_for('carrito.checkout'))
    
    # Guardar ID del pedido para la página de pago
    session['pedido_id'] = resultado
    
    cursor.close()
    return redirect(url_for('carrito.pago', pedido_id=resultado))

@carrito_bp.route('/pago/<int:pedido_id>')
@login_required
def pago(pedido_id):
    """Muestra la página de pago para un pedido"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para procesar el pago', 'warning')
        return redirect(url_for('auth.login'))
    
    # Verificar que el pedido pertenece al usuario actual
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.*, c.nombre, c.email 
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.id = %s AND p.cliente_id = %s
    """, (pedido_id, current_user.id))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Pedido no encontrado o no autorizado', 'danger')
        cursor.close()
        return redirect(url_for('carrito.mis_pedidos'))
    
    # Verificar que el pedido no esté ya pagado
    if pedido.get('estado', '') == 'PAGADO':
        flash('Este pedido ya ha sido pagado', 'warning')
        cursor.close()
        return redirect(url_for('carrito.confirmacion', pedido_id=pedido_id))
    
    # Obtener detalles del pedido
    cursor.execute("""
        SELECT pd.*, p.nombre, p.imagen
        FROM pedido_detalles pd
        JOIN productos p ON pd.producto_id = p.id
        WHERE pd.pedido_id = %s
    """, (pedido_id,))
    detalles = cursor.fetchall()
    cursor.close()
    
    # Definir pasarelas de pago disponibles
    pasarelas_disponibles = ['paypal', 'mercadopago', 'stripe', 'pse']
    
    return render_template('carrito/pago.html', 
                           pedido=pedido, 
                           detalles=detalles,
                           pasarelas_disponibles=pasarelas_disponibles)

@carrito_bp.route('/procesar-pago/<int:pedido_id>', methods=['POST'])
@login_required
def procesar_pago(pedido_id):
    """Procesa el pago de un pedido"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para procesar el pago', 'warning')
        return redirect(url_for('auth.login'))
    
    # Verificar que el pedido pertenece al usuario actual
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.*, c.nombre, c.email 
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.id = %s AND p.cliente_id = %s
    """, (pedido_id, current_user.id))
    pedido = cursor.fetchone()
    cursor.close()
    
    if not pedido:
        flash('Pedido no encontrado o no autorizado', 'danger')
        return redirect(url_for('carrito.mis_pedidos'))
    
    # Verificar que el pedido no esté ya pagado
    if pedido.get('estado', '') == 'PAGADO':
        flash('Este pedido ya ha sido pagado', 'warning')
        return redirect(url_for('carrito.confirmacion', pedido_id=pedido_id))
    
    # Obtener datos del formulario
    metodo_pago = request.form.get('metodo_pago')
    referencia = request.form.get('referencia', '')
    
    # Validar método de pago
    metodos_validos = ['efectivo', 'transferencia', 'oxxo', 'paypal', 'google_pay', 'pse', 'mercadopago']
    if metodo_pago not in metodos_validos:
        flash('Método de pago no válido', 'danger')
        return redirect(url_for('carrito.pago', pedido_id=pedido_id))
    
    # Procesar según el método de pago
    if metodo_pago == 'efectivo':
        # Para pago en efectivo, solo actualizamos el estado
        estado = 'PENDIENTE'
        mensaje = 'Pago en efectivo registrado. Deberás pagar al recoger el pedido.'
    elif metodo_pago == 'transferencia':
        # Para transferencia, verificamos que se haya proporcionado una referencia
        if not referencia:
            flash('Debe proporcionar el número de referencia de la transferencia', 'warning')
            return redirect(url_for('carrito.pago', pedido_id=pedido_id))
        estado = 'PENDIENTE'
        mensaje = 'Transferencia registrada. Nuestro equipo verificará el pago.'
    elif metodo_pago == 'oxxo':
        # Para OXXO, generamos un código de pago (simulado)
        referencia = f"OXXO-{pedido_id}-{int(time.time())}"
        estado = 'PENDIENTE'
        mensaje = f'Código OXXO generado: {referencia}. Debes pagar en cualquier tienda OXXO.'
    elif metodo_pago == 'pse':
        # Para PSE, redirigimos al usuario a la ruta de iniciar pago PSE
        banco_id = request.form.get('banco_pse')
        tipo_persona = request.form.get('tipo_persona')
        tipo_documento = request.form.get('tipo_documento')
        numero_documento = request.form.get('numero_documento')
        
        # Verificar que se hayan proporcionado todos los datos necesarios
        if not banco_id or not tipo_persona or not tipo_documento or not numero_documento:
            flash('Debe proporcionar todos los datos requeridos para el pago con PSE', 'warning')
            return redirect(url_for('carrito.pago', pedido_id=pedido_id))
        
        # Actualizar estado a pendiente y guardar el método de pago
        Pedido.actualizar_estado_pago(pedido_id, 'pse', '', 'PENDIENTE')
        
        # Redirigir a PSE con los datos necesarios
        return redirect(url_for('pagos_pse.iniciar', 
                               factura_id=pedido_id,
                               banco_id=banco_id,
                               tipo_persona=tipo_persona,
                               tipo_documento=tipo_documento,
                               numero_documento=numero_documento,
                               email=pedido.get('email', '')))
    elif metodo_pago in ['paypal', 'google_pay', 'mercadopago']:
        # Para pagos electrónicos, simulamos un pago exitoso
        estado = 'PAGADO'
        mensaje = f'Pago con {metodo_pago.upper()} procesado correctamente.'
        referencia = f"{metodo_pago.upper()}-{pedido_id}-{int(time.time())}"
    
    # Actualizar estado del pago en la base de datos
    try:
        Pedido.actualizar_estado_pago(pedido_id, metodo_pago, referencia, estado)
        
        # Si el pago fue exitoso, enviar correo de confirmación
        if estado == 'PAGADO':
            # Aquí iría el código para enviar correo de confirmación
            pass
        
        flash(mensaje, 'success')
        return redirect(url_for('carrito.confirmacion', pedido_id=pedido_id))
    except Exception as e:
        flash(f'Error al procesar el pago: {str(e)}', 'danger')
        return redirect(url_for('carrito.pago', pedido_id=pedido_id))

@carrito_bp.route('/confirmacion/<int:pedido_id>')
@login_required
def confirmacion(pedido_id):
    """Muestra la página de confirmación de pedido"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para ver la confirmación', 'warning')
        return redirect(url_for('auth.login'))
    
    # Verificar que el pedido pertenece al usuario actual
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.*, c.nombre, c.email, c.telefono, c.direccion
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.id = %s AND p.cliente_id = %s
    """, (pedido_id, current_user.id))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Pedido no encontrado o no autorizado', 'danger')
        cursor.close()
        return redirect(url_for('carrito.mis_pedidos'))
    
    # Obtener detalles del pedido
    cursor.execute("""
        SELECT pd.*, p.nombre, p.imagen
        FROM pedido_detalles pd
        JOIN productos p ON pd.producto_id = p.id
        WHERE pd.pedido_id = %s
    """, (pedido_id,))
    detalles = cursor.fetchall()
    cursor.close()
    
    return render_template('carrito/confirmacion.html', 
                           pedido=pedido, 
                           detalles=detalles)

@carrito_bp.route('/mis-pedidos')
@login_required
def mis_pedidos():
    """Muestra la lista de pedidos del cliente"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para ver sus pedidos', 'warning')
        return redirect(url_for('auth.login'))
    
    pedidos = Pedido.listar_pedidos_cliente(current_user.id)
    
    return render_template('carrito/mis_pedidos.html', 
                           pedidos=pedidos)

@carrito_bp.route('/detalle-pedido/<int:pedido_id>')
@login_required
def detalle_pedido(pedido_id):
    """Muestra los detalles de un pedido específico"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para ver los detalles del pedido', 'warning')
        return redirect(url_for('auth.login'))
    
    pedido = Pedido.obtener_pedido(pedido_id)
    
    if not pedido:
        flash('Pedido no encontrado', 'danger')
        return redirect(url_for('carrito.mis_pedidos'))
    
    if pedido['cliente_id'] != current_user.id:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('carrito/detalle_pedido.html', 
                           pedido=pedido)

@carrito_bp.route('/actualizar-datos-cliente', methods=['POST'])
@login_required
def actualizar_datos_cliente():
    """Actualiza los datos del cliente directamente"""
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Debe iniciar sesión'})
    
    try:
        # Obtener datos del formulario
        telefono = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')
        identificacion = request.form.get('identificacion', '')
        
        # Verificar si los datos son válidos
        if not telefono or not direccion:
            return jsonify({'success': False, 'message': 'Por favor ingrese dirección y teléfono'})
        
        # Actualizar perfil del cliente
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE clientes 
            SET telefono = %s, direccion = %s, identificacion = %s
            WHERE id = %s
        """, (telefono, direccion, identificacion, current_user.id))
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({
            'success': True, 
            'message': 'Datos actualizados correctamente',
            'telefono': telefono,
            'direccion': direccion,
            'identificacion': identificacion
        })
        
    except Exception as e:
        print(f"Error al actualizar perfil: {e}")
        return jsonify({'success': False, 'message': f'Error al actualizar datos: {str(e)}'})