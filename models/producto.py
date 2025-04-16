from extensions import mysql
from decimal import Decimal

class Producto:
    def __init__(self, db):
        self.db = db

    def obtener_producto(self, producto_id):
        """Obtiene un producto por su ID"""
        try:
            cursor = self.db.cursor(dictionary=True)
            cursor.execute("""
                SELECT p.*, c.nombre as categoria_nombre, e.nombre as estado_nombre
                FROM productos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                LEFT JOIN estados e ON p.estado_id = e.id
                WHERE p.id = %s
            """, (producto_id,))
            producto = cursor.fetchone()
            cursor.close()
            return producto
        except Exception as e:
            print(f"Error al obtener producto: {str(e)}")
            return None

    def verificar_stock(self, producto_id, cantidad):
        """Verifica si hay suficiente stock disponible"""
        try:
            cursor = self.db.cursor(dictionary=True)
            cursor.execute("""
                SELECT stock
                FROM productos
                WHERE id = %s
            """, (producto_id,))
            resultado = cursor.fetchone()
            cursor.close()
            
            if not resultado:
                return False, "Producto no encontrado"
                
            if resultado['stock'] < cantidad:
                return False, "Stock insuficiente"
                
            return True, "Stock disponible"
        except Exception as e:
            print(f"Error al verificar stock: {str(e)}")
            return False, "Error al verificar stock"

    def actualizar_stock(self, producto_id, cantidad):
        """Actualiza el stock de un producto"""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                UPDATE productos
                SET stock = stock - %s
                WHERE id = %s AND stock >= %s
            """, (cantidad, producto_id, cantidad))
            self.db.commit()
            cursor.close()
            return True, "Stock actualizado"
        except Exception as e:
            print(f"Error al actualizar stock: {str(e)}")
            return False, "Error al actualizar stock"

    def listar_productos(self, categoria_id=None, estado_id=None, busqueda=None):
        """Lista productos con filtros opcionales"""
        try:
            cursor = self.db.cursor(dictionary=True)
            
            query = """
                SELECT p.*, c.nombre as categoria_nombre, e.nombre as estado_nombre
                FROM productos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                LEFT JOIN estados e ON p.estado_id = e.id
                WHERE 1=1
            """
            params = []
            
            if categoria_id:
                query += " AND p.categoria_id = %s"
                params.append(categoria_id)
                
            if estado_id:
                query += " AND p.estado_id = %s"
                params.append(estado_id)
                
            if busqueda:
                query += " AND (p.nombre LIKE %s OR p.descripcion LIKE %s)"
                params.extend([f"%{busqueda}%", f"%{busqueda}%"])
                
            cursor.execute(query, params)
            productos = cursor.fetchall()
            cursor.close()
            return productos
        except Exception as e:
            print(f"Error al listar productos: {str(e)}")
            return [] 