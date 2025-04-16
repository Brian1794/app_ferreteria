from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import mysql
import datetime
import MySQLdb
from models.carousel import Carousel

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Ruta de inicio"""
    # Obtener las imágenes activas del carousel
    carousel_items = Carousel.obtener_todos(solo_activos=True)
    
    # Obtener productos destacados para mostrar en la página principal
    productos_destacados = []
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            """SELECT p.*, c.nombre as categoria 
               FROM productos p
               LEFT JOIN categorias c ON p.categoria_id = c.id
               WHERE p.destacado = 1 AND p.activo = TRUE
               ORDER BY p.fecha_actualizacion DESC
               LIMIT 8"""
        )
        productos_destacados = cursor.fetchall()
        cursor.close()
    except Exception as e:
        print(f"Error al obtener productos destacados: {e}")
    
    return render_template('index.html', carousel_items=carousel_items, productos_destacados=productos_destacados)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal de la aplicación, varía según el tipo de usuario"""
    # Si el usuario es cliente, redirigir a mi cuenta
    if current_user.es_cliente:
        return redirect(url_for('main.mi_cuenta'))
    
    # Si el usuario es administrador, redirigir al panel de administración
    if current_user.es_admin:
        return redirect(url_for('admin.index'))
    
    # Para empleados, mostrar el dashboard adaptado a su rol
    cur = mysql.connection.cursor()
    
    # Obtener información completa del empleado con su cargo
    cur.execute('''
        SELECT e.*, c.nombre as cargo_nombre, c.permisos as permisos_json
        FROM empleados e
        LEFT JOIN cargos c ON e.cargo_id = c.id
        WHERE e.id = %s
    ''', (current_user.id,))
    empleado = cur.fetchone()
    
    # Obtener estadísticas básicas
    # Ventas recientes
    cur.execute('''
        SELECT COUNT(*) as total, 
               COUNT(CASE WHEN DATE(fecha) = CURDATE() THEN 1 END) as hoy
        FROM ventas 
        WHERE estado = 'Pagada'
    ''')
    stats_ventas = cur.fetchone()
    
    # Productos con bajo stock
    cur.execute('''
        SELECT COUNT(*) as total
        FROM productos
        WHERE stock <= stock_minimo AND activo = TRUE
    ''')
    productos_bajo_stock = cur.fetchone()
    
    # Reparaciones pendientes
    cur.execute('''
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN estado = 'RECIBIDO' THEN 1 END) as recibidas,
               COUNT(CASE WHEN estado = 'EN_PROGRESO' THEN 1 END) as en_progreso
        FROM reparaciones
        WHERE estado NOT IN ('ENTREGADO', 'CANCELADO')
    ''')
    reparaciones_pendientes = cur.fetchone()
    
    # Obtener los módulos que debe ver según permisos
    # Por defecto todos los administradores ven todo
    modulos_permitidos = []
    
    if current_user.es_admin:
        modulos_permitidos = [
            'ventas', 'productos', 'clientes', 'compras', 
            'reparaciones', 'whatsapp', 'empleados', 'reportes', 
            'configuracion'
        ]
    else:
        # Cargar permisos desde JSON en la tabla cargos
        import json
        try:
            permisos = json.loads(empleado['permisos_json']) if empleado['permisos_json'] else {}
            
            # Construir lista de módulos permitidos
            for modulo, permiso in permisos.items():
                if isinstance(permiso, bool) and permiso:
                    modulos_permitidos.append(modulo)
                elif isinstance(permiso, dict) and permiso.get('ver', False):
                    modulos_permitidos.append(modulo)
        except:
            # Si hay error en los permisos, mostrar solo ventas por seguridad
            modulos_permitidos = ['ventas']
    
    cur.close()
    
    return render_template('dashboard.html',
                          empleado=empleado,
                          stats_ventas=stats_ventas,
                          productos_bajo_stock=productos_bajo_stock,
                          reparaciones_pendientes=reparaciones_pendientes,
                          modulos_permitidos=modulos_permitidos) 

@main_bp.route('/mi-cuenta')
@login_required
def mi_cuenta():
    """Página de cuenta para clientes donde ven su actividad"""
    # Verificar que el usuario actual sea un cliente
    if not current_user.es_cliente:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('main.dashboard'))
    
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Obtener datos del cliente
        cur.execute("""
            SELECT c.*, 
                   COALESCE(COUNT(DISTINCT v.id), 0) as total_compras,
                   COALESCE(COUNT(DISTINCT r.id), 0) as total_reparaciones,
                   COALESCE(SUM(v.total), 0) as total_gastado
            FROM clientes c
            LEFT JOIN ventas v ON c.id = v.cliente_id
            LEFT JOIN reparaciones r ON c.id = r.cliente_id
            WHERE c.id = %s
            GROUP BY c.id
        """, (current_user.id,))
        
        cliente = cur.fetchone()
        
        if not cliente:
            flash('No se encontró información del cliente', 'danger')
            return redirect(url_for('main.index'))
        
        # Obtener las últimas compras del cliente
        cur.execute("""
            SELECT id, fecha, total, estado 
            FROM ventas 
            WHERE cliente_id = %s 
            ORDER BY fecha DESC LIMIT 5
        """, (current_user.id,))
        compras = cur.fetchall() or []
        
        # Obtener las últimas reparaciones del cliente
        cur.execute("""
            SELECT id, fecha_recepcion, descripcion, estado
            FROM reparaciones 
            WHERE cliente_id = %s 
            ORDER BY fecha_recepcion DESC LIMIT 5
        """, (current_user.id,))
        reparaciones = cur.fetchall() or []
        
        cur.close()
        
        # Renderizar la plantilla con los datos obtenidos
        return render_template(
            'cliente/mi_cuenta.html',
            cliente=cliente,
            compras=compras,
            reparaciones=reparaciones,
            total_gastado=cliente.get('total_gastado', 0)
        )
        
    except Exception as e:
        import traceback
        print(f"Error en mi_cuenta: {str(e)}")
        print(traceback.format_exc())
        flash('Ha ocurrido un error al cargar tu cuenta', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route('/contacto', methods=['GET', 'POST'])
def contacto():
    """Vista para la página de contacto"""
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        asunto = request.form.get('asunto')
        mensaje = request.form.get('mensaje')
        
        # Validar datos
        if not nombre or not email or not mensaje:
            flash('Por favor completa todos los campos requeridos.', 'danger')
            return render_template('contacto.html')
        
        try:
            # Guardar mensaje en la base de datos
            cursor = mysql.connection.cursor()
            query = """
                INSERT INTO mensajes_contacto 
                (nombre, email, asunto, mensaje, fecha_creacion) 
                VALUES (%s, %s, %s, %s, NOW())
            """
            cursor.execute(query, (nombre, email, asunto, mensaje))
            mysql.connection.commit()
            
            # Enviar correo de notificación (si está configurado)
            # Aquí podría implementarse la lógica para enviar un correo
            
            flash('¡Gracias por contactarnos! Te responderemos a la brevedad.', 'success')
            return redirect(url_for('main.contacto'))
            
        except Exception as e:
            print(f"Error al guardar mensaje de contacto: {e}")
            flash('Ocurrió un error al enviar tu mensaje. Por favor intenta nuevamente.', 'danger')
    
    return render_template('contacto.html') 