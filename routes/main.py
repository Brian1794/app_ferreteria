from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import mysql
import datetime
import MySQLdb

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Página principal de la aplicación"""
    return render_template('index.html')

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
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Obtener últimas compras con una consulta simple sin alias
    cur.execute('''
        SELECT id, fecha, total, estado
        FROM ventas
        WHERE cliente_id = %s
        ORDER BY fecha DESC
        LIMIT 5
    ''', (current_user.id,))
    ultimas_compras = cur.fetchall()
    
    # Obtener reparaciones activas
    cur.execute('''
        SELECT id, electrodomestico, problema, fecha_recepcion, estado, 
               marca, modelo
        FROM reparaciones
        WHERE cliente_id = %s AND estado NOT IN ('ENTREGADO', 'CANCELADO')
        ORDER BY fecha_recepcion DESC
    ''', (current_user.id,))
    reparaciones_activas = cur.fetchall()
    
    # Formatear fechas para evitar errores al renderizar
    for reparacion in reparaciones_activas:
        if reparacion['fecha_recepcion'] is None:
            reparacion['fecha_recepcion'] = None
        # Asegurar que exista un campo descripción para mantener compatibilidad
        if 'descripcion' not in reparacion or not reparacion['descripcion']:
            if reparacion['electrodomestico']:
                reparacion['descripcion'] = f"{reparacion['electrodomestico']} {reparacion['marca']} {reparacion['modelo']}".strip()
            else:
                reparacion['descripcion'] = "Sin descripción"
    
    # Mapeo de estados para mostrar texto amigable
    estados_texto = {
        'RECIBIDO': 'Recibido',
        'DIAGNOSTICO': 'En diagnóstico',
        'REPARACION': 'En reparación',
        'ESPERA_REPUESTOS': 'Esperando repuestos',
        'LISTO': 'Listo para entrega',
        'ENTREGADO': 'Entregado',
        'CANCELADO': 'Cancelado'
    }
    
    # Agregar el texto amigable a cada reparación
    for reparacion in reparaciones_activas:
        if reparacion['estado'] in estados_texto:
            reparacion['estado'] = estados_texto[reparacion['estado']]
    
    cur.close()
    
    return render_template(
        'cliente/mi_cuenta.html',
        ultimas_compras=ultimas_compras,
        reparaciones_activas=reparaciones_activas
    ) 

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