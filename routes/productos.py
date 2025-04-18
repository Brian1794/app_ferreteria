from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import mysql
from MySQLdb.cursors import DictCursor
import os
from werkzeug.utils import secure_filename
import uuid

productos_bp = Blueprint('productos', __name__)

# Configuración para carga de archivos
UPLOAD_FOLDER = 'static/uploads/productos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

def convertir_a_dict(filas, claves):
    """
    Recibe una lista de filas y las convierte a diccionarios usando la lista 'claves'
    Si la fila ya es un diccionario, se retorna tal cual.
    """
    resultado = []
    for fila in filas:
        if isinstance(fila, dict):
            resultado.append(fila)
        else:
            resultado.append(dict(zip(claves, fila)))
    return resultado

@productos_bp.route('/catalogo')
def catalogo():
    """Muestra el catálogo de productos para clientes"""
    cursor = mysql.connection.cursor()
    
    try:
        # Obtener categorías activas para filtrado
        cursor.execute("""
            SELECT DISTINCT c.id, c.nombre 
            FROM categorias c 
            WHERE c.activo = TRUE
            ORDER BY c.nombre
        """)
        categorias_raw = cursor.fetchall()
        
        # Obtener el ID de categoría del querystring
        categoria_id = request.args.get('categoria')
        
        # Construir la consulta base - Ya no filtramos por activo = TRUE
        query = """
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE 1=1
        """
        params = []
        
        # Agregar filtro por categoría si se especifica
        if categoria_id:
            query += " AND p.categoria_id = %s"
            params.append(categoria_id)
        
        # Ordenar productos
        query += " ORDER BY p.destacado DESC, p.nombre"
        
        # Ejecutar la consulta
        cursor.execute(query, params)
        productos_raw = cursor.fetchall()
        
        # Convertir resultados a diccionarios
        productos = []
        for producto in productos_raw:
            if isinstance(producto, dict):
                productos.append(producto)
            else:
                productos.append({
                    'id': producto[0],
                    'nombre': producto[1],
                    'descripcion': producto[2],
                    'precio_venta': producto[5],
                    'stock': producto[6],
                    'imagen': producto[9],
                    'categoria_id': producto[10],
                    'categoria_nombre': producto[-1],
                    'destacado': producto[7],
                    'activo': producto[8]
                })
        
        # Convertir categorías a diccionarios
        categorias = []
        for cat in categorias_raw:
            if isinstance(cat, dict):
                categorias.append(cat)
            else:
                categorias.append({
                    'id': cat[0],
                    'nombre': cat[1]
                })
        
        return render_template('productos/catalogo.html',
                             productos=productos,
                             categorias=categorias,
                             categoria_actual=categoria_id)
                             
    except Exception as e:
        flash(f'Error al cargar el catálogo: {str(e)}', 'danger')
        return redirect(url_for('main.index'))
    finally:
        cursor.close()

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
    filas = cursor.fetchall()
    cursor.close()
    
    claves = ['id', 'nombre', 'codigo_barras', 'precio_compra', 'precio_venta', 'stock', 'categoria', 'imagen']
    productos = convertir_a_dict(filas, claves)
    
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
    
    # Obtener categorías para el formulario usando DictCursor
    cursor = mysql.connection.cursor(DictCursor)
    try:
        cursor.execute("""
            SELECT id, nombre 
            FROM categorias 
            WHERE activo = TRUE 
            ORDER BY nombre
        """)
        categorias = cursor.fetchall()
        
        if not categorias:
            flash('No hay categorías activas disponibles. Por favor, cree una categoría primero.', 'warning')
            return redirect(url_for('categorias.agregar'))
            
        return render_template('productos/agregar.html', categorias=categorias)
    except Exception as e:
        flash(f'Error al cargar las categorías: {str(e)}', 'danger')
        return render_template('productos/agregar.html', categorias=[])
    finally:
        cursor.close()

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
                
                # Si hay una imagen existente, intentar borrarla
                cursor.execute("SELECT imagen FROM productos WHERE id = %s", (id,))
                old_image_data = cursor.fetchone()
                if old_image_data:
                    # Dependiendo de cómo se devuelvan los datos, puede ser dict o tupla
                    old_image = old_image_data.get(0) if isinstance(old_image_data, dict) else old_image_data[0]
                    if old_image:
                        old_image_path = os.path.join(UPLOAD_FOLDER, old_image)
                        if os.path.exists(old_image_path):
                            try:
                                os.remove(old_image_path)
                            except Exception as e:
                                print(f"Error al eliminar imagen anterior: {str(e)}")
        
        # Validar datos
        if not all([nombre, precio_compra, precio_venta]):
            flash('Los campos nombre, precio de compra y precio de venta son obligatorios', 'danger')
            return redirect(url_for('productos.editar', id=id))
        
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
        finally:
            cursor.close()
    
    # Obtener datos del producto a editar
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT id, nombre, descripcion, codigo_barras, precio_compra, precio_venta, 
               stock, stock_minimo, categoria_id, imagen
        FROM productos
        WHERE id = %s
    """, (id,))
    prod = cursor.fetchone()
    cursor.close()
    
    if not prod:
        flash('Producto no encontrado', 'danger')
        return redirect(url_for('productos.listar_productos'))
    
    # Convertir el producto a diccionario
    if isinstance(prod, dict):
        producto = prod
    else:
        producto = {
            'id': prod[0],
            'nombre': prod[1],
            'descripcion': prod[2],
            'codigo_barras': prod[3],
            'precio_compra': prod[4],
            'precio_venta': prod[5],
            'stock': prod[6],
            'stock_minimo': prod[7],
            'categoria_id': prod[8],
            'imagen': prod[9]
        }
    
    # Obtener categorías para el formulario
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id, nombre FROM categorias WHERE activo = TRUE ORDER BY nombre")
        categorias_raw = cursor.fetchall()
        print(f"Categorías obtenidas: {categorias_raw}")
        
        # Verificar si hay categorías
        if not categorias_raw:
            print("¡No se encontraron categorías activas!")
            # Si no hay categorías activas, buscar todas
            cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
            categorias_raw = cursor.fetchall()
            print(f"Categorías totales: {categorias_raw}")
    except Exception as e:
        print(f"Error al consultar categorías: {str(e)}")
        categorias_raw = []
    finally:
        cursor.close()
    
    # Convertir a formato compatible con la plantilla
    categorias = []
    for cat in categorias_raw:
        if isinstance(cat, dict):
            categorias.append(cat)
        else:
            # Crear diccionario con claves 'id' y 'nombre'
            categorias.append({
                'id': cat[0],
                'nombre': cat[1]
            })
    
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
    filas = cursor.fetchall()
    cursor.close()
    
    claves = ['id', 'nombre', 'descripcion', 'precio_compra', 'precio_venta', 'stock', 'stock_minimo', 'categoria']
    productos = convertir_a_dict(filas, claves)
    
    return render_template('productos/stock_bajo.html', productos=productos)

@productos_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar(id):
    """Elimina un producto del inventario"""
    cursor = mysql.connection.cursor()
    try:
        # Primero verificamos si el producto existe
        cursor.execute("SELECT nombre FROM productos WHERE id = %s", (id,))
        producto_data = cursor.fetchone()
        
        if not producto_data:
            flash('Producto no encontrado', 'danger')
            return redirect(url_for('productos.listar_productos'))
        
        # Verificar si el producto está referenciado en otras tablas
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
        
        # Si no hay referencias, eliminar el producto
        cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
        mysql.connection.commit()
        
        # producto_data puede ser diccionario o tupla; se accede de forma segura
        nombre_prod = producto_data.get(0) if isinstance(producto_data, dict) else producto_data[0]
        flash(f'Producto "{nombre_prod}" eliminado correctamente', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al eliminar el producto: {str(e)}', 'danger')
    finally:
        cursor.close()
    
    return redirect(url_for('productos.listar_productos'))

@productos_bp.route('/buscar')
def buscar():
    """Permite buscar productos por nombre, descripción o categoría"""
    query = request.args.get('q', '')
    
    if not query or len(query) < 2:
        flash('Por favor ingresa al menos 2 caracteres para realizar la búsqueda', 'info')
        return redirect(url_for('productos.catalogo'))
    
    cursor = mysql.connection.cursor()
    
    # Consulta para buscar productos que coincidan con la búsqueda
    cursor.execute("""
        SELECT p.id, p.nombre, p.descripcion, p.precio_compra, p.precio_venta, 
               p.stock, p.stock_minimo, p.destacado, p.activo, p.imagen, 
               p.categoria_id, c.nombre as categoria_nombre 
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.activo = TRUE AND (
            p.nombre LIKE %s OR 
            p.descripcion LIKE %s OR
            c.nombre LIKE %s
        )
        ORDER BY p.destacado DESC, p.nombre
    """, (f'%{query}%', f'%{query}%', f'%{query}%'))
    
    productos_raw = cursor.fetchall()
    
    # Obtener categorías para el filtro lateral
    cursor.execute("SELECT id, nombre FROM categorias WHERE activo = TRUE ORDER BY nombre")
    categorias_raw = cursor.fetchall()
    cursor.close()
    
    # Definir claves según la consulta
    claves_producto = ['id', 'nombre', 'descripcion', 'precio_compra', 'precio_venta', 
                       'stock', 'stock_minimo', 'destacado', 'activo', 'imagen', 
                       'categoria_id', 'categoria_nombre']
    productos = convertir_a_dict(productos_raw, claves_producto)
    
    # Convertir categorías a diccionarios
    claves_categoria = ['id', 'nombre']
    categorias = convertir_a_dict(categorias_raw, claves_categoria)
    
    return render_template('productos/catalogo.html', 
                          productos=productos, 
                          categorias=categorias,
                          busqueda=query,
                          titulo=f'Resultados para: {query}')
