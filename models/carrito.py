from extensions import mysql
from flask import session
from decimal import Decimal

class Carrito:
    @staticmethod
    def obtener_carrito(cliente_id):
        """Obtiene o crea un carrito para el cliente"""
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM carritos WHERE cliente_id = %s", (cliente_id,))
        carrito = cursor.fetchone()
        
        if not carrito:
            # Crear nuevo carrito
            cursor.execute("INSERT INTO carritos (cliente_id) VALUES (%s)", (cliente_id,))
            mysql.connection.commit()
            carrito_id = cursor.lastrowid
        else:
            carrito_id = carrito['id'] if isinstance(carrito, dict) else carrito[0]
            
        cursor.close()
        return carrito_id
    
    @staticmethod
    def agregar_producto(cliente_id, producto_id, cantidad=1):
        """Agrega un producto al carrito"""
        carrito_id = Carrito.obtener_carrito(cliente_id)
        
        cursor = mysql.connection.cursor()
        
        # Verificar si el producto ya está en el carrito
        cursor.execute("""
            SELECT id, cantidad FROM carrito_items 
            WHERE carrito_id = %s AND producto_id = %s
        """, (carrito_id, producto_id))
        item = cursor.fetchone()
        
        if item:
            # Actualizar cantidad
            item_id = item['id'] if isinstance(item, dict) else item[0]
            cantidad_actual = item['cantidad'] if isinstance(item, dict) else item[1]
            nueva_cantidad = cantidad_actual + cantidad
            
            cursor.execute("""
                UPDATE carrito_items SET cantidad = %s 
                WHERE id = %s
            """, (nueva_cantidad, item_id))
        else:
            # Insertar nuevo item
            cursor.execute("""
                INSERT INTO carrito_items (carrito_id, producto_id, cantidad) 
                VALUES (%s, %s, %s)
            """, (carrito_id, producto_id, cantidad))
            
        mysql.connection.commit()
        cursor.close()
        return True
    
    @staticmethod
    def actualizar_cantidad(cliente_id, producto_id, cantidad):
        """Actualiza la cantidad de un producto en el carrito"""
        if cantidad <= 0:
            return Carrito.eliminar_producto(cliente_id, producto_id)
            
        carrito_id = Carrito.obtener_carrito(cliente_id)
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE carrito_items SET cantidad = %s 
            WHERE carrito_id = %s AND producto_id = %s
        """, (cantidad, carrito_id, producto_id))
        
        resultado = cursor.rowcount > 0
        mysql.connection.commit()
        cursor.close()
        
        return resultado
    
    @staticmethod
    def eliminar_producto(cliente_id, producto_id):
        """Elimina un producto del carrito"""
        carrito_id = Carrito.obtener_carrito(cliente_id)
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            DELETE FROM carrito_items 
            WHERE carrito_id = %s AND producto_id = %s
        """, (carrito_id, producto_id))
        
        resultado = cursor.rowcount > 0
        mysql.connection.commit()
        cursor.close()
        
        return resultado
    
    @staticmethod
    def obtener_items(cliente_id):
        """Obtiene todos los items del carrito con información detallada"""
        carrito_id = Carrito.obtener_carrito(cliente_id)
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT ci.id, ci.producto_id, ci.cantidad, 
                   p.nombre, p.precio_venta, p.stock, p.imagen, p.codigo_barras as codigo,
                   (ci.cantidad * p.precio_venta) as subtotal
            FROM carrito_items ci
            JOIN productos p ON ci.producto_id = p.id
            WHERE ci.carrito_id = %s
            ORDER BY ci.fecha_agregado DESC
        """, (carrito_id,))
        
        items = cursor.fetchall()
        cursor.close()
        
        # Convertir a lista de diccionarios
        resultado = []
        for item in items:
            if isinstance(item, dict):
                # Asegurar que precio_venta sea un número
                item_dict = dict(item)
                item_dict['precio'] = float(item_dict.pop('precio_venta'))
                item_dict['subtotal'] = float(item_dict['subtotal'])
                resultado.append(item_dict)
            else:
                resultado.append({
                    'id': item[0],
                    'producto_id': item[1],
                    'cantidad': item[2],
                    'nombre': item[3],
                    'precio': float(item[4]),  # Asegurar que sea float
                    'stock': item[5],
                    'imagen': item[6],
                    'codigo': item[7],
                    'subtotal': float(item[8])  # Asegurar que sea float
                })
        
        return resultado
    
    @staticmethod
    def contar_items(cliente_id):
        """Cuenta cuántos ítems hay en el carrito"""
        carrito_id = Carrito.obtener_carrito(cliente_id)
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT SUM(cantidad) as total_items
            FROM carrito_items
            WHERE carrito_id = %s
        """, (carrito_id,))
        
        resultado = cursor.fetchone()
        cursor.close()
        
        if resultado:
            total = resultado['total_items'] if isinstance(resultado, dict) else resultado[0]
            return total or 0
        return 0
    
    @staticmethod
    def obtener_total(cliente_id):
        """Calcula el total del carrito"""
        carrito_id = Carrito.obtener_carrito(cliente_id)
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT SUM(ci.cantidad * p.precio_venta) as total
            FROM carrito_items ci
            JOIN productos p ON ci.producto_id = p.id
            WHERE ci.carrito_id = %s
        """, (carrito_id,))
        
        resultado = cursor.fetchone()
        cursor.close()
        
        if resultado:
            total = resultado['total'] if isinstance(resultado, dict) else resultado[0]
            return float(total or 0)
        return 0
    
    @staticmethod
    def vaciar_carrito(cliente_id):
        """Elimina todos los productos del carrito"""
        carrito_id = Carrito.obtener_carrito(cliente_id)
        
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM carrito_items WHERE carrito_id = %s", (carrito_id,))
        
        mysql.connection.commit()
        cursor.close()
        return True

class Pedido:
    @staticmethod
    def crear_desde_carrito(cliente_id, datos_envio):
        """Crea un nuevo pedido a partir del carrito del cliente"""
        # Obtener items del carrito
        items_carrito = Carrito.obtener_items(cliente_id)
        
        if not items_carrito:
            return False, "El carrito está vacío"
        
        # Verificar stock disponible
        for item in items_carrito:
            if item['cantidad'] > item['stock']:
                return False, f"No hay suficiente stock para {item['nombre']}"
        
        # Calcular total
        total = sum(item['subtotal'] for item in items_carrito)
        
        # Crear pedido
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO pedidos (cliente_id, total, direccion_envio, telefono_contacto, identificacion_cliente, notas) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                cliente_id, 
                total, 
                datos_envio.get('direccion', ''),
                datos_envio.get('telefono', ''),
                datos_envio.get('identificacion', ''),
                datos_envio.get('notas', '')
            ))
            
            pedido_id = cursor.lastrowid
            
            # Crear detalles del pedido
            for item in items_carrito:
                cursor.execute("""
                    INSERT INTO pedido_detalles (pedido_id, producto_id, cantidad, precio_unitario, subtotal) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    pedido_id,
                    item['producto_id'],
                    item['cantidad'],
                    item['precio'],
                    item['subtotal']
                ))
                
                # Ya no actualizamos el stock aquí, lo haremos en actualizar_estado_pago
            
            # Vaciar carrito
            Carrito.vaciar_carrito(cliente_id)
            
            mysql.connection.commit()
            cursor.close()
            
            return True, pedido_id
            
        except Exception as e:
            mysql.connection.rollback()
            cursor.close()
            return False, str(e)
    
    @staticmethod
    def actualizar_estado_pago(pedido_id, metodo_pago, referencia, estado="PAGADO"):
        """Actualiza el estado de pago de un pedido"""
        cursor = mysql.connection.cursor()
        try:
            # Primero obtenemos el estado actual del pedido
            cursor.execute("SELECT estado FROM pedidos WHERE id = %s", (pedido_id,))
            pedido_actual = cursor.fetchone()
            estado_actual = pedido_actual['estado'] if isinstance(pedido_actual, dict) else pedido_actual[0]
            
            # Actualizamos estado del pedido
            cursor.execute("""
                UPDATE pedidos 
                SET estado = %s, metodo_pago = %s, referencia_pago = %s 
                WHERE id = %s
            """, (estado, metodo_pago, referencia, pedido_id))
            
            # Si el pedido pasa a estado PAGADO, descontamos el stock
            if estado == "PAGADO" and estado_actual != "PAGADO":
                # Obtenemos los detalles del pedido
                cursor.execute("""
                    SELECT producto_id, cantidad FROM pedido_detalles
                    WHERE pedido_id = %s
                """, (pedido_id,))
                detalles = cursor.fetchall()
                
                # Actualizamos el stock de cada producto
                for detalle in detalles:
                    producto_id = detalle['producto_id'] if isinstance(detalle, dict) else detalle[0]
                    cantidad = detalle['cantidad'] if isinstance(detalle, dict) else detalle[1]
                    
                    cursor.execute("""
                        UPDATE productos 
                        SET stock = stock - %s 
                        WHERE id = %s
                    """, (cantidad, producto_id))
            
            mysql.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            mysql.connection.rollback()
            cursor.close()
            return False
    
    @staticmethod
    def obtener_pedido(pedido_id):
        """Obtiene los datos de un pedido"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.*, c.nombre as cliente_nombre, c.email as cliente_email, c.telefono as cliente_telefono
            FROM pedidos p
            JOIN clientes c ON p.cliente_id = c.id
            WHERE p.id = %s
        """, (pedido_id,))
        
        pedido = cursor.fetchone()
        
        if not pedido:
            cursor.close()
            return None
        
        # Convertir a diccionario si no lo es
        if not isinstance(pedido, dict):
            columnas = [desc[0] for desc in cursor.description]
            pedido = dict(zip(columnas, pedido))
        
        # Obtener detalles
        cursor.execute("""
            SELECT pd.*, pr.nombre as producto_nombre, pr.imagen as producto_imagen
            FROM pedido_detalles pd
            JOIN productos pr ON pd.producto_id = pr.id
            WHERE pd.pedido_id = %s
        """, (pedido_id,))
        
        detalles_raw = cursor.fetchall()
        cursor.close()
        
        # Convertir a lista de diccionarios
        detalles = []
        for d in detalles_raw:
            if isinstance(d, dict):
                detalles.append(d)
            else:
                columnas = [desc[0] for desc in cursor.description]
                detalles.append(dict(zip(columnas, d)))
        
        pedido['detalles'] = detalles
        return pedido
    
    @staticmethod
    def listar_pedidos_cliente(cliente_id):
        """Lista todos los pedidos de un cliente"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.*, COUNT(pd.id) as total_productos
            FROM pedidos p
            JOIN pedido_detalles pd ON p.id = pd.pedido_id
            WHERE p.cliente_id = %s
            GROUP BY p.id
            ORDER BY p.fecha_pedido DESC
        """, (cliente_id,))
        
        pedidos_raw = cursor.fetchall()
        cursor.close()
        
        # Convertir a lista de diccionarios
        pedidos = []
        for p in pedidos_raw:
            if isinstance(p, dict):
                pedidos.append(p)
            else:
                columnas = [desc[0] for desc in cursor.description]
                pedidos.append(dict(zip(columnas, p)))
        
        return pedidos 