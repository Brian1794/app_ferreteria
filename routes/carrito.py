from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models.carrito import Carrito, Pedido
from extensions import mysql
import json
from flask_wtf.csrf import CSRFProtect

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
    
    return render_template('cart/view.html', 
                           items=items, 
                           total=total)

@carrito_bp.route('/agregar', methods=['POST'])
@login_required
def agregar_al_carrito():
    """Agrega un producto al carrito"""
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Debe iniciar sesión'})
    
    try:
        data = request.get_json()
        producto_id = int(data.get('producto_id'))
        cantidad = int(data.get('cantidad', 1))
        
        # Validar que la cantidad sea positiva
        if cantidad <= 0:
            return jsonify({'success': False, 'message': 'La cantidad debe ser mayor a 0'})
        
        # Verificar stock disponible
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT stock, nombre, imagen FROM productos WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()
        cursor.close()
        
        if not producto:
            return jsonify({'success': False, 'message': 'Producto no encontrado'})
        
        # Obtener información del producto
        stock = producto['stock'] if isinstance(producto, dict) else producto[0]
        nombre = producto['nombre'] if isinstance(producto, dict) else producto[1]
        imagen = producto['imagen'] if isinstance(producto, dict) else producto[2]
        
        if cantidad > stock:
            return jsonify({
                'success': False, 
                'message': f'No hay suficiente stock disponible. Máximo: {stock}'
            })
        
        # Agregar al carrito
        Carrito.agregar_producto(current_user.id, producto_id, cantidad)
        
        # Obtener conteo actualizado
        total_items = Carrito.contar_items(current_user.id)
        
        return jsonify({
            'success': True, 
            'message': f'{nombre} agregado al carrito ({cantidad} unidad(es))',
            'total_items': total_items,
            'product_name': nombre,
            'product_image': imagen,
            'quantity': cantidad
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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
    
    # Obtener los items del carrito
    items = Carrito.obtener_items(current_user.id)
    
    if not items:
        flash('Su carrito está vacío', 'warning')
        return redirect(url_for('carrito.ver_carrito'))
    
    total = Carrito.obtener_total(current_user.id)
    
    # Obtener información del cliente
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id = %s", (current_user.id,))
    cliente = cursor.fetchone()
    cursor.close()
    
    return render_template('carrito/checkout.html', 
                           items=items, 
                           total=total,
                           cliente=cliente)

@carrito_bp.route('/procesar-pedido', methods=['POST'])
@login_required
def procesar_pedido():
    """Procesa un nuevo pedido"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para completar la compra', 'warning')
        return redirect(url_for('auth.login'))
    
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
                SET telefono = %s, direccion = %s
                WHERE id = %s
            """, (telefono, direccion, current_user.id))
            mysql.connection.commit()
        except Exception as e:
            print(f"Error al actualizar perfil: {e}")
    
    # Crear datos de envío con la información proporcionada
    datos_envio = {
        'direccion': direccion,
        'telefono': telefono,
        'notas': notas
    }
    
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
    """Muestra la página de pago"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para completar el pago', 'warning')
        return redirect(url_for('auth.login'))
    
    # Verificar que el pedido pertenezca al cliente
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT cliente_id, total FROM pedidos WHERE id = %s", (pedido_id,))
    pedido = cursor.fetchone()
    cursor.close()
    
    if not pedido:
        flash('Pedido no encontrado', 'danger')
        return redirect(url_for('main.index'))
    
    cliente_id = pedido['cliente_id'] if isinstance(pedido, dict) else pedido[0]
    total = pedido['total'] if isinstance(pedido, dict) else pedido[1]
    
    if cliente_id != current_user.id:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('carrito/pago.html', 
                           pedido_id=pedido_id,
                           total=total)

@carrito_bp.route('/procesar-pago/<int:pedido_id>', methods=['POST'])
@login_required
def procesar_pago(pedido_id):
    """Procesa el pago de un pedido"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para completar el pago', 'warning')
        return redirect(url_for('auth.login'))
    
    # Verificar que el pedido pertenezca al cliente
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT cliente_id FROM pedidos WHERE id = %s", (pedido_id,))
    pedido = cursor.fetchone()
    cursor.close()
    
    if not pedido:
        flash('Pedido no encontrado', 'danger')
        return redirect(url_for('main.index'))
    
    cliente_id = pedido['cliente_id'] if isinstance(pedido, dict) else pedido[0]
    
    if cliente_id != current_user.id:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('main.index'))
    
    # Recoger datos del formulario
    metodo_pago = request.form.get('metodo_pago')
    
    if not metodo_pago:
        flash('Por favor seleccione un método de pago', 'danger')
        return redirect(url_for('carrito.pago', pedido_id=pedido_id))
    
    referencia = ""
    detalles_pago = {}
    
    # Procesar según el método de pago seleccionado
    if metodo_pago == 'tarjeta':
        # En un entorno real, aquí iría la integración con una pasarela de pagos
        detalles_pago = {
            'card_number': request.form.get('card_number', '')[-4:],  # Solo guardar los últimos 4 dígitos por seguridad
            'card_name': request.form.get('card_name', ''),
            'card_expiry': request.form.get('card_expiry', ''),
        }
        referencia = f"Tarjeta terminada en {detalles_pago['card_number']}"
    elif metodo_pago == 'pse':
        # En un entorno real, aquí iría la integración con PSE
        detalles_pago = {
            'banco': request.form.get('pse_bank', ''),
            'tipo_persona': request.form.get('pse_person_type', ''),
            'tipo_documento': request.form.get('pse_document_type', ''),
            'numero_documento': request.form.get('pse_document_number', '')
        }
        referencia = f"PSE - Banco: {detalles_pago['banco']}"
    elif metodo_pago == 'transferencia':
        referencia = request.form.get('transferencia_referencia', '')
    elif metodo_pago == 'efectivo':
        referencia = "Pago en efectivo al recibir"
    
    # Convertir detalles_pago a formato JSON para almacenamiento
    detalles_json = json.dumps(detalles_pago)
    
    # Actualizar estado del pedido
    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE pedidos 
        SET metodo_pago = %s, 
            referencia_pago = %s,
            detalles_pago = %s,
            estado = 'Pagado',
            fecha_pago = NOW()
        WHERE id = %s
    """, (metodo_pago, referencia, detalles_json, pedido_id))
    mysql.connection.commit()
    cursor.close()
    
    flash('¡Pago realizado con éxito! Su pedido ha sido procesado.', 'success')
    
    # Limpiar sesión
    if 'pedido_id' in session:
        session.pop('pedido_id')
    
    # Vaciar el carrito después del pago exitoso
    session['carrito'] = []
    session['carrito_cantidad'] = 0
    
    return redirect(url_for('carrito.confirmacion', pedido_id=pedido_id))

@carrito_bp.route('/confirmacion/<int:pedido_id>')
@login_required
def confirmacion(pedido_id):
    """Muestra la página de confirmación del pedido"""
    if not current_user.is_authenticated:
        flash('Debe iniciar sesión para ver esta página', 'warning')
        return redirect(url_for('auth.login'))
    
    # Verificar que el pedido pertenezca al cliente
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.*, c.nombre as cliente_nombre, c.email
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.id
        WHERE p.id = %s
    """, (pedido_id,))
    pedido = cursor.fetchone()
    
    if not pedido:
        flash('Pedido no encontrado', 'danger')
        return redirect(url_for('main.index'))
    
    # Convertir a diccionario si no lo es
    if not isinstance(pedido, dict):
        columnas = [desc[0] for desc in cursor.description]
        pedido = dict(zip(columnas, pedido))
    
    cliente_id = pedido['cliente_id']
    
    if cliente_id != current_user.id:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('main.index'))
    
    # Obtener detalles del pedido
    cursor.execute("""
        SELECT pd.*, p.nombre, p.imagen
        FROM pedido_detalles pd
        JOIN productos p ON pd.producto_id = p.id
        WHERE pd.pedido_id = %s
    """, (pedido_id,))
    
    detalles_raw = cursor.fetchall()
    cursor.close()
    
    # Convertir a lista de diccionarios
    detalles = []
    for detalle in detalles_raw:
        if isinstance(detalle, dict):
            detalles.append(detalle)
        else:
            columnas = [desc[0] for desc in cursor.description]
            detalles.append(dict(zip(columnas, detalle)))
    
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
        
        # Verificar si los datos son válidos
        if not telefono or not direccion:
            return jsonify({'success': False, 'message': 'Por favor ingrese dirección y teléfono'})
        
        # Actualizar perfil del cliente
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE clientes 
            SET telefono = %s, direccion = %s
            WHERE id = %s
        """, (telefono, direccion, current_user.id))
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({
            'success': True, 
            'message': 'Datos actualizados correctamente',
            'telefono': telefono,
            'direccion': direccion
        })
        
    except Exception as e:
        print(f"Error al actualizar perfil: {e}")
        return jsonify({'success': False, 'message': f'Error al actualizar datos: {str(e)}'}) 