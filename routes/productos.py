from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import mysql
import os
from werkzeug.utils import secure_filename
import uuid

productos_bp = Blueprint('productos', __name__)

# Configuración para carga de archivos
UPLOAD_FOLDER = 'static/uploads/productos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    if file and allowed_file(file.filename):
        # Crear directorio si no existe
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            
        # Generar nombre único para el archivo
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Guardar archivo
        file.save(file_path)
        return unique_filename
    return None

@productos_bp.route('/catalogo')
def catalogo():
    """Muestra el catálogo de productos para clientes"""
    cursor = mysql.connection.cursor()
    
    # Obtener categorías para filtrado
    cursor.execute("SELECT id, nombre FROM categorias WHERE activo = TRUE ORDER BY nombre")
    categorias = cursor.fetchall()
    
    # Obtener productos destacados o todos si no hay destacados
    categoria_id = request.args.get('categoria')
    
    if categoria_id:
        cursor.execute("""
            SELECT p.id, p.nombre, p.descripcion, p.precio_compra, p.precio_venta, 
                   p.stock, p.stock_minimo, p.destacado, p.activo, p.imagen, 
                   p.categoria_id, c.nombre as categoria_nombre 
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.activo = TRUE AND p.categoria_id = %s
            ORDER BY p.nombre
        """, (categoria_id,))
    else:
        cursor.execute("""
            SELECT p.id, p.nombre, p.descripcion, p.precio_compra, p.precio_venta, 
                   p.stock, p.stock_minimo, p.destacado, p.activo, p.imagen, 
                   p.categoria_id, c.nombre as categoria_nombre 
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.activo = TRUE
            ORDER BY p.destacado DESC, p.nombre
        """)
    
    productos_raw = cursor.fetchall()
    # Convertir lista de tuplas a lista de diccionarios para mantener compatibilidad con la plantilla
    productos = []
    for p in productos_raw:
        productos.append({
            'id': p[0],
            'nombre': p[1],
            'descripcion': p[2],
            'precio_compra': p[3],
            'precio_venta': p[4],
            'stock': p[5],
            'stock_minimo': p[6],
            'destacado': p[7],
            'activo': p[8],
            'imagen': p[9],
            'categoria_id': p[10],
            'categoria_nombre': p[11]
        })
    
    # Convertir categorías de tuplas a diccionarios
    categorias_dict = []
    for c in categorias:
        categorias_dict.append({
            'id': c[0],
            'nombre': c[1]
        })
    
    cursor.close()
    
    return render_template('productos/catalogo.html', 
                          productos=productos, 
                          categorias=categorias_dict,
                          categoria_actual=categoria_id)

@productos_bp.route('/')
@login_required
def listar_productos():
    """Lista todos los productos disponibles"""
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.id, p.nombre, p.codigo_barras, p.precio_compra, p.precio_venta, p.stock, 
               c.nombre as categoria, p.imagen
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.nombre
    """)
    productos = cursor.fetchall()
    cursor.close()
    return render_template('productos/lista.html', productos=productos)

@productos_bp.route('/agregar', methods=['GET', 'POST'])
@login_required
def agregar():
    """Agrega un nuevo producto al inventario"""
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        codigo_barras = request.form.get('codigo_barras')
        precio_compra = request.form.get('precio_compra')
        precio_venta = request.form.get('precio_venta')
        stock = request.form.get('stock')
        stock_minimo = request.form.get('stock_minimo')
        categoria_id = request.form.get('categoria_id')
        
        # Procesar imagen si fue enviada
        imagen_filename = None
        if 'imagen' in request.files:
            imagen_file = request.files['imagen']
            if imagen_file.filename != '':
                imagen_filename = save_image(imagen_file)
        
        # Validar datos
        if not all([nombre, precio_compra, precio_venta]):
            flash('Los campos nombre, precio de compra y precio de venta son obligatorios', 'danger')
            return redirect(url_for('productos.agregar'))
        
        # Insertar en la base de datos
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO productos (nombre, descripcion, codigo_barras, precio_compra, precio_venta, 
                                      stock, stock_minimo, categoria_id, imagen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nombre, descripcion, codigo_barras, precio_compra, precio_venta, 
                 stock, stock_minimo, categoria_id if categoria_id else None, imagen_filename))
            mysql.connection.commit()
            flash('Producto agregado correctamente', 'success')
            return redirect(url_for('productos.listar_productos'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al agregar producto: {str(e)}', 'danger')
        finally:
            cursor.close()
    
    # Obtener categorías para el formulario
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
    categorias = cursor.fetchall()
    cursor.close()
    
    return render_template('productos/agregar.html', categorias=categorias)

@productos_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Edita un producto existente"""
    cursor = mysql.connection.cursor()
    
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        codigo_barras = request.form.get('codigo_barras')
        precio_compra = request.form.get('precio_compra')
        precio_venta = request.form.get('precio_venta')
        stock = request.form.get('stock')
        stock_minimo = request.form.get('stock_minimo')
        categoria_id = request.form.get('categoria_id')
        
        # Procesar imagen si fue enviada
        imagen_filename = None
        if 'imagen' in request.files:
            imagen_file = request.files['imagen']
            if imagen_file.filename != '':
                imagen_filename = save_image(imagen_file)
                
                # Si hay una imagen existente, podríamos borrarla
                cursor.execute("SELECT imagen FROM productos WHERE id = %s", (id,))
                old_image = cursor.fetchone()[0]
                if old_image:
                    try:
                        old_image_path = os.path.join(UPLOAD_FOLDER, old_image)
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                    except Exception as e:
                        print(f"Error al eliminar imagen anterior: {str(e)}")
        
        # Validar datos
        if not all([nombre, precio_compra, precio_venta]):
            flash('Los campos nombre, precio de compra y precio de venta son obligatorios', 'danger')
            return redirect(url_for('productos.editar', id=id))
        
        # Actualizar en la base de datos
        try:
            if imagen_filename:
                # Si se subió una nueva imagen
                cursor.execute("""
                    UPDATE productos 
                    SET nombre = %s, descripcion = %s, codigo_barras = %s, precio_compra = %s, 
                        precio_venta = %s, stock = %s, stock_minimo = %s, categoria_id = %s, imagen = %s
                    WHERE id = %s
                """, (nombre, descripcion, codigo_barras, precio_compra, precio_venta, 
                     stock, stock_minimo, categoria_id if categoria_id else None, imagen_filename, id))
            else:
                # Si no se subió nueva imagen, mantener la existente
                cursor.execute("""
                    UPDATE productos 
                    SET nombre = %s, descripcion = %s, codigo_barras = %s, precio_compra = %s, 
                        precio_venta = %s, stock = %s, stock_minimo = %s, categoria_id = %s
                    WHERE id = %s
                """, (nombre, descripcion, codigo_barras, precio_compra, precio_venta, 
                     stock, stock_minimo, categoria_id if categoria_id else None, id))
            
            mysql.connection.commit()
            flash('Producto actualizado correctamente', 'success')
            return redirect(url_for('productos.listar_productos'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al actualizar producto: {str(e)}', 'danger')
    
    # Obtener datos del producto
    cursor.execute("""
        SELECT id, nombre, descripcion, codigo_barras, precio_compra, precio_venta, 
               stock, stock_minimo, categoria_id, imagen
        FROM productos
        WHERE id = %s
    """, (id,))
    producto = cursor.fetchone()
    
    if not producto:
        cursor.close()
        flash('Producto no encontrado', 'danger')
        return redirect(url_for('productos.listar_productos'))
    
    # Obtener categorías para el formulario
    cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
    categorias = cursor.fetchall()
    cursor.close()
    
    return render_template('productos/editar.html', producto=producto, categorias=categorias)

@productos_bp.route('/stock_bajo')
@login_required
def stock_bajo():
    """Muestra productos con stock por debajo del mínimo"""
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.id, p.nombre, p.descripcion, p.precio_compra, p.precio_venta, 
               p.stock, p.stock_minimo, c.nombre as categoria
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.stock <= p.stock_minimo
        ORDER BY p.stock ASC
    """)
    productos = cursor.fetchall()
    cursor.close()
    return render_template('productos/stock_bajo.html', productos=productos)

@productos_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar(id):
    """Elimina un producto del inventario"""
    cursor = mysql.connection.cursor()
    try:
        # Primero verificamos si el producto existe
        cursor.execute("SELECT nombre FROM productos WHERE id = %s", (id,))
        producto = cursor.fetchone()
        
        if not producto:
            flash('Producto no encontrado', 'danger')
            return redirect(url_for('productos.listar_productos'))
        
        # Verificamos si el producto está referenciado en otras tablas
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM detalles_venta WHERE producto_id = %s) +
                (SELECT COUNT(*) FROM detalles_compra WHERE producto_id = %s) +
                (SELECT COUNT(*) FROM reparaciones_repuestos WHERE producto_id = %s) as total_referencias
        """, (id, id, id))
        
        total_referencias = cursor.fetchone()[0]
        
        if total_referencias > 0:
            flash('No se puede eliminar el producto porque está siendo utilizado en ventas, compras o reparaciones', 'danger')
            return redirect(url_for('productos.listar_productos'))
        
        # Si no hay referencias, eliminamos el producto
        cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
        mysql.connection.commit()
        
        flash(f'Producto "{producto[0]}" eliminado correctamente', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al eliminar el producto: {str(e)}', 'danger')
    finally:
        cursor.close()
    
    return redirect(url_for('productos.listar_productos'))
