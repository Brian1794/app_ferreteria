from extensions import mysql 
from decimal import Decimal
from datetime import datetime

class Pedido:
    @staticmethod
    def crear_pedido(cliente_id, datos_envio, items):
        """Crea un nuevo pedido"""
        cursor = mysql.connection.cursor()
        try:
            # Calcular total
            total = sum(item['cantidad'] * item['precio'] for item in items)
            
            # Crear pedido
            cursor.execute("""
                INSERT INTO pedidos (
                    cliente_id, 
                    total, 
                    direccion_envio, 
                    telefono, 
                    identificacion, 
                    notas,
                    fecha_creacion,
                    estado
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cliente_id,
                total,
                datos_envio.get('direccion', ''),
                datos_envio.get('telefono', ''),
                datos_envio.get('identificacion', ''),
                datos_envio.get('notas', ''),
                datetime.now(),
                'PENDIENTE'
            ))
            
            pedido_id = cursor.lastrowid
            
            # Crear detalles del pedido
            for item in items:
                cursor.execute("""
                    INSERT INTO pedido_detalles (
                        pedido_id, 
                        producto_id, 
                        cantidad, 
                        precio_unitario, 
                        subtotal
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    pedido_id,
                    item['producto_id'],
                    item['cantidad'],
                    item['precio'],
                    item['cantidad'] * item['precio']
                ))
            
            mysql.connection.commit()
            return True, pedido_id
            
        except Exception as e:
            mysql.connection.rollback()
            return False, str(e)
        finally:
            cursor.close()

    @staticmethod
    def obtener_pedido(pedido_id):
        """Obtiene los datos de un pedido"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT p.*, 
                   c.nombre as cliente_nombre,
                   c.email as cliente_email
            FROM pedidos p
            LEFT JOIN clientes c ON p.cliente_id = c.id 
            WHERE p.id = %s
        """, (pedido_id,))
        
        pedido = cursor.fetchone()
        
        if not pedido:
            cursor.close()
            return None
            
        # Obtener detalles
        cursor.execute("""
            SELECT pd.*, 
                   pr.nombre as producto_nombre,
                   pr.codigo_barras as producto_codigo,
                   pr.imagen as producto_imagen
            FROM pedido_detalles pd
            JOIN productos pr ON pd.producto_id = pr.id
            WHERE pd.pedido_id = %s
        """, (pedido_id,))
        
        detalles = cursor.fetchall()
        cursor.close()
        
        if isinstance(pedido, dict):
            pedido['detalles'] = detalles if isinstance(detalles[0], dict) else [
                dict(zip([column[0] for column in cursor.description], d)) 
                for d in detalles
            ]
            return pedido
        else:
            # Convertir a diccionario
            columnas = [desc[0] for desc in cursor.description]
            pedido_dict = dict(zip(columnas, pedido))
            pedido_dict['detalles'] = [
                dict(zip([column[0] for column in cursor.description], d)) 
                for d in detalles
            ]
            return pedido_dict

    @staticmethod
    def listar_pedidos(filtros=None, page=1, per_page=10):
        """Lista todos los pedidos con paginación y filtros opcionales"""
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT p.*, 
                   c.nombre as cliente_nombre,
                   c.email as cliente_email
            FROM pedidos p
            LEFT JOIN clientes c ON p.cliente_id = c.id
            WHERE 1=1
        """
        params = []
        
        if filtros:
            if 'cliente_id' in filtros:
                query += " AND p.cliente_id = %s"
                params.append(filtros['cliente_id'])
            if 'estado' in filtros:
                query += " AND p.estado = %s"
                params.append(filtros['estado'])
            if 'fecha_inicio' in filtros and 'fecha_fin' in filtros:
                query += " AND p.fecha_creacion BETWEEN %s AND %s"
                params.extend([filtros['fecha_inicio'], filtros['fecha_fin']])
        
        # Agregar ordenamiento y paginación
        query += " ORDER BY p.fecha_creacion DESC LIMIT %s OFFSET %s"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor.execute(query, tuple(params))
        pedidos = cursor.fetchall()
        
        # Contar total de registros
        count_query = """
            SELECT COUNT(*) as total
            FROM pedidos p
            WHERE 1=1
        """
        if filtros and 'cliente_id' in filtros:
            count_query += " AND p.cliente_id = %s"
        
        cursor.execute(count_query, (filtros['cliente_id'],) if filtros and 'cliente_id' in filtros else ())
        total = cursor.fetchone()
        total = total['total'] if isinstance(total, dict) else total[0]
        
        cursor.close()
        
        return {
            'items': pedidos if isinstance(pedidos[0], dict) else [
                dict(zip([column[0] for column in cursor.description], p))
                for p in pedidos
            ],
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'current_page': page
        }

    @staticmethod
    def actualizar_estado(pedido_id, nuevo_estado, metodo_pago=None, referencia=None):
        """Actualiza el estado de un pedido"""
        cursor = mysql.connection.cursor()
        try:
            update_query = "UPDATE pedidos SET estado = %s"
            params = [nuevo_estado]
            
            if metodo_pago:
                update_query += ", metodo_pago = %s"
                params.append(metodo_pago)
            if referencia:
                update_query += ", referencia_pago = %s"
                params.append(referencia)
                
            update_query += " WHERE id = %s"
            params.append(pedido_id)
            
            cursor.execute(update_query, tuple(params))
            
            # Si el pedido está pagado, actualizar stock
            if nuevo_estado == 'PAGADO':
                cursor.execute("""
                    UPDATE productos p
                    JOIN pedido_detalles pd ON p.id = pd.producto_id
                    SET p.stock = p.stock - pd.cantidad
                    WHERE pd.pedido_id = %s
                """, (pedido_id,))
            
            mysql.connection.commit()
            return True, "Estado actualizado correctamente"
            
        except Exception as e:
            mysql.connection.rollback()
            return False, str(e)
        finally:
            cursor.close()

    @staticmethod
    def calcular_estadisticas(fecha_inicio=None, fecha_fin=None):
        """Calcula estadísticas de pedidos"""
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT 
                COUNT(*) as total_pedidos,
                SUM(CASE WHEN estado = 'PAGADO' THEN 1 ELSE 0 END) as pedidos_pagados,
                SUM(CASE WHEN estado = 'PENDIENTE' THEN 1 ELSE 0 END) as pedidos_pendientes,
                SUM(total) as monto_total,
                SUM(CASE WHEN estado = 'PAGADO' THEN total ELSE 0 END) as monto_pagado
            FROM pedidos
            WHERE 1=1
        """
        params = []
        
        if fecha_inicio and fecha_fin:
            query += " AND fecha_creacion BETWEEN %s AND %s"
            params.extend([fecha_inicio, fecha_fin])
            
        cursor.execute(query, tuple(params) if params else ())
        stats = cursor.fetchone()
        cursor.close()
        
        if isinstance(stats, dict):
            return stats
        else:
            return {
                'total_pedidos': stats[0],
                'pedidos_pagados': stats[1],
                'pedidos_pendientes': stats[2],
                'monto_total': float(stats[3]) if stats[3] else 0,
                'monto_pagado': float(stats[4]) if stats[4] else 0
            }