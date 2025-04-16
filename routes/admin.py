from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models.models import mysql
from routes.auth import admin_required
from models.carousel import Carousel
import json

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
@login_required
@admin_required
def index():
    """Panel de administración"""
    # Inicializar estadísticas con valores por defecto
    stats = {
        'ventas': {'total': 0, 'hoy': 0},
        'productos': {'total': 0, 'bajo_stock': 0},
        'clientes': {'total': 0, 'nuevos': 0},
        'reparaciones': {'total': 0, 'pendientes': 0}
    }
    
    try:
        # Obtener estadísticas del sistema
        cur = mysql.connection.cursor()
        
        try:
            # Estadísticas de ventas
            cur.execute("""
                SELECT COUNT(*) as total,
                    SUM(CASE WHEN DATE(fecha) = CURDATE() THEN 1 ELSE 0 END) as hoy
                FROM ventas
            """)
            ventas = cur.fetchone()
            if ventas:
                stats['ventas'] = {
                    'total': ventas['total'] if ventas['total'] is not None else 0,
                    'hoy': ventas['hoy'] if ventas['hoy'] is not None else 0
                }
        except Exception as e:
            print(f"Error al obtener estadísticas de ventas: {str(e)}")
        
        try:
            # Estadísticas de productos
            cur.execute("""
                SELECT COUNT(*) as total,
                    SUM(CASE WHEN stock <= stock_minimo THEN 1 ELSE 0 END) as bajo_stock
                FROM productos
            """)
            productos = cur.fetchone()
            if productos:
                stats['productos'] = {
                    'total': productos['total'] if productos['total'] is not None else 0,
                    'bajo_stock': productos['bajo_stock'] if productos['bajo_stock'] is not None else 0
                }
        except Exception as e:
            print(f"Error al obtener estadísticas de productos: {str(e)}")
        
        try:
            # Estadísticas de clientes
            cur.execute("""
                SELECT COUNT(*) as total,
                    SUM(CASE WHEN MONTH(fecha_registro) = MONTH(CURDATE()) AND YEAR(fecha_registro) = YEAR(CURDATE()) THEN 1 ELSE 0 END) as nuevos
                FROM clientes
            """)
            clientes = cur.fetchone()
            if clientes:
                stats['clientes'] = {
                    'total': clientes['total'] if clientes['total'] is not None else 0,
                    'nuevos': clientes['nuevos'] if clientes['nuevos'] is not None else 0
                }
        except Exception as e:
            print(f"Error al obtener estadísticas de clientes: {str(e)}")
        
        try:
            # Estadísticas de reparaciones - consulta modificada para ser más robusta
            cur.execute("""
                SELECT COUNT(*) as total,
                    SUM(CASE WHEN estado NOT IN ('ENTREGADO', 'CANCELADO', 'LISTO', 'entregado', 'cancelado', 'listo', 'completada') THEN 1 ELSE 0 END) as pendientes
                FROM reparaciones
            """)
            reparaciones = cur.fetchone()
            if reparaciones:
                stats['reparaciones'] = {
                    'total': reparaciones['total'] if reparaciones['total'] is not None else 0,
                    'pendientes': reparaciones['pendientes'] if reparaciones['pendientes'] is not None else 0
                }
        except Exception as e:
            print(f"Error al obtener estadísticas de reparaciones: {str(e)}")
        
        cur.close()
        
    except Exception as e:
        print(f"Error general al obtener estadísticas: {str(e)}")
    
    return render_template('admin/index.html', stats=stats)

@admin_bp.route('/configuracion', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion():
    """Gestión de configuración del sistema"""
    if request.method == 'POST':
        # Obtener grupo de configuración
        grupo = request.form.get('grupo')
        
        # Obtener todos los campos del formulario
        config_data = {}
        for key, value in request.form.items():
            if key.startswith(f'{grupo}_'):
                config_name = key.replace(f'{grupo}_', '')
                config_data[config_name] = value
        
        try:
            # Actualizar configuración en la base de datos
            cur = mysql.connection.cursor()
            for name, value in config_data.items():
                cur.execute('''
                    UPDATE configuracion
                    SET valor = %s
                    WHERE grupo = %s AND nombre = %s
                ''', (value, grupo, name))
            
            mysql.connection.commit()
            cur.close()
            
            flash('Configuración actualizada con éxito', 'success')
            return redirect(url_for('admin.configuracion', grupo=grupo))
            
        except Exception as e:
            flash(f'Error al actualizar configuración: {str(e)}', 'danger')
    
    # Obtener grupo de configuración solicitado
    grupo = request.args.get('grupo', 'sistema')
    
    # Obtener configuraciones
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM configuracion ORDER BY grupo, nombre')
    configuraciones = cur.fetchall()
    
    # Agrupar configuraciones por grupo
    grupos = {}
    for config in configuraciones:
        if config['grupo'] not in grupos:
            grupos[config['grupo']] = []
        grupos[config['grupo']].append(config)
    
    cur.close()
    
    return render_template('admin/configuracion.html', 
                          grupos=grupos, 
                          grupo_actual=grupo)

@admin_bp.route('/cargos')
@login_required
@admin_required
def cargos():
    """Gestión de cargos y permisos"""
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM cargos ORDER BY nombre')
    cargos = cur.fetchall()
    cur.close()
    
    return render_template('admin/cargos/lista.html', cargos=cargos)

@admin_bp.route('/cargos/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo_cargo():
    """Crear nuevo cargo"""
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion', '')
        
        # Validaciones básicas
        if not nombre:
            flash('El nombre del cargo es obligatorio', 'warning')
            return render_template('admin/cargos/formulario.html')
        
        # Obtener permisos del formulario
        permisos = {}
        for key in request.form:
            if key.startswith('permiso_'):
                modulo = key.replace('permiso_', '')
                if request.form.get(f'permiso_detalle_{modulo}') == 'simple':
                    # Permiso simple (boolean)
                    permisos[modulo] = True
                else:
                    # Permiso detallado (object)
                    permisos[modulo] = {
                        'ver': 'ver_' + modulo in request.form,
                        'crear': 'crear_' + modulo in request.form,
                        'editar': 'editar_' + modulo in request.form,
                        'eliminar': 'eliminar_' + modulo in request.form
                    }
        
        try:
            cur = mysql.connection.cursor()
            
            # Verificar si el nombre ya existe
            cur.execute('SELECT id FROM cargos WHERE nombre = %s', (nombre,))
            if cur.fetchone():
                flash('Ya existe un cargo con ese nombre', 'warning')
                return render_template('admin/cargos/formulario.html')
            
            # Insertar cargo
            cur.execute('''
                INSERT INTO cargos (nombre, descripcion, permisos)
                VALUES (%s, %s, %s)
            ''', (nombre, descripcion, json.dumps(permisos)))
            
            mysql.connection.commit()
            cur.close()
            
            flash('Cargo creado con éxito', 'success')
            return redirect(url_for('admin.cargos'))
            
        except Exception as e:
            flash(f'Error al crear cargo: {str(e)}', 'danger')
            return render_template('admin/cargos/formulario.html')
    
    return render_template('admin/cargos/formulario.html')

@admin_bp.route('/cargos/<int:cargo_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_cargo(cargo_id):
    """Editar cargo existente"""
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM cargos WHERE id = %s', (cargo_id,))
    cargo = cur.fetchone()
    cur.close()
    
    if not cargo:
        flash('Cargo no encontrado', 'warning')
        return redirect(url_for('admin.cargos'))
    
    # Convertir permisos de texto a diccionario
    try:
        permisos = json.loads(cargo['permisos'])
    except:
        permisos = {}
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion', '')
        
        # Validaciones básicas
        if not nombre:
            flash('El nombre del cargo es obligatorio', 'warning')
            return render_template('admin/cargos/formulario.html', cargo=cargo, permisos=permisos)
        
        # Obtener permisos del formulario
        nuevos_permisos = {}
        for key in request.form:
            if key.startswith('permiso_'):
                modulo = key.replace('permiso_', '')
                if request.form.get(f'permiso_detalle_{modulo}') == 'simple':
                    # Permiso simple (boolean)
                    nuevos_permisos[modulo] = True
                else:
                    # Permiso detallado (object)
                    nuevos_permisos[modulo] = {
                        'ver': 'ver_' + modulo in request.form,
                        'crear': 'crear_' + modulo in request.form,
                        'editar': 'editar_' + modulo in request.form,
                        'eliminar': 'eliminar_' + modulo in request.form
                    }
        
        try:
            cur = mysql.connection.cursor()
            
            # Verificar si el nombre ya existe
            cur.execute('SELECT id FROM cargos WHERE nombre = %s AND id != %s', (nombre, cargo_id))
            if cur.fetchone():
                flash('Ya existe un cargo con ese nombre', 'warning')
                return render_template('admin/cargos/formulario.html', cargo=cargo, permisos=permisos)
            
            # Actualizar cargo
            cur.execute('''
                UPDATE cargos
                SET nombre = %s, descripcion = %s, permisos = %s
                WHERE id = %s
            ''', (nombre, descripcion, json.dumps(nuevos_permisos), cargo_id))
            
            mysql.connection.commit()
            cur.close()
            
            flash('Cargo actualizado con éxito', 'success')
            return redirect(url_for('admin.cargos'))
            
        except Exception as e:
            flash(f'Error al actualizar cargo: {str(e)}', 'danger')
            return render_template('admin/cargos/formulario.html', cargo=cargo, permisos=permisos)
    
    return render_template('admin/cargos/formulario.html', cargo=cargo, permisos=permisos)

@admin_bp.route('/cargos/<int:cargo_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar_cargo(cargo_id):
    """Eliminar cargo"""
    try:
        cur = mysql.connection.cursor()
        
        # Verificar que no haya empleados con este cargo
        cur.execute('SELECT COUNT(*) as total FROM empleados WHERE cargo_id = %s', (cargo_id,))
        result = cur.fetchone()
        if result and result['total'] > 0:
            flash('No se puede eliminar el cargo porque hay empleados asignados a él', 'warning')
            return redirect(url_for('admin.cargos'))
        
        # Eliminar cargo
        cur.execute('DELETE FROM cargos WHERE id = %s', (cargo_id,))
        mysql.connection.commit()
        cur.close()
        
        flash('Cargo eliminado con éxito', 'success')
        
    except Exception as e:
        flash(f'Error al eliminar cargo: {str(e)}', 'danger')
    
    return redirect(url_for('admin.cargos'))

@admin_bp.route('/estadisticas')
@login_required
@admin_required
def estadisticas():
    """Estadísticas generales del sistema"""
    cur = mysql.connection.cursor()
    
    # Estadísticas de ventas
    cur.execute('''
        SELECT 
            COUNT(*) as total_ventas,
            COALESCE(SUM(total), 0) as ingresos_totales,
            COUNT(DISTINCT cliente_id) as total_clientes_compradores
        FROM ventas
        WHERE estado = 'Pagada'
    ''')
    stats_ventas = cur.fetchone()
    
    # Estadísticas de productos
    cur.execute('''
        SELECT
            COUNT(*) as total_productos,
            COUNT(CASE WHEN stock <= stock_minimo THEN 1 END) as productos_stock_bajo,
            AVG(precio_venta) as precio_promedio
        FROM productos
        WHERE activo = TRUE
    ''')
    stats_productos = cur.fetchone()
    
    # Estadísticas de reparaciones
    cur.execute('''
        SELECT
            COUNT(*) as total_reparaciones,
            COUNT(CASE WHEN estado = 'RECIBIDO' THEN 1 END) as reparaciones_recibidas,
            COUNT(CASE WHEN estado = 'EN_PROGRESO' THEN 1 END) as reparaciones_en_progreso,
            COUNT(CASE WHEN estado = 'TERMINADO' THEN 1 END) as reparaciones_terminadas,
            COALESCE(SUM(costo_final), 0) as ingresos_reparaciones
        FROM reparaciones
    ''')
    stats_reparaciones = cur.fetchone()
    
    # Productos más vendidos
    cur.execute('''
        SELECT p.nombre, SUM(d.cantidad) as total_vendido
        FROM detalles_venta d
        JOIN productos p ON d.producto_id = p.id
        JOIN ventas v ON d.venta_id = v.id
        WHERE v.estado = 'Pagada'
        GROUP BY p.id
        ORDER BY total_vendido DESC
        LIMIT 5
    ''')
    productos_mas_vendidos = cur.fetchall()
    
    # Clientes con más compras
    cur.execute('''
        SELECT c.nombre, c.apellido, COUNT(v.id) as total_compras, SUM(v.total) as total_gastado
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.estado = 'Pagada'
        GROUP BY c.id
        ORDER BY total_gastado DESC
        LIMIT 5
    ''')
    mejores_clientes = cur.fetchall()
    
    cur.close()
    
    return render_template('admin/estadisticas.html',
                          stats_ventas=stats_ventas,
                          stats_productos=stats_productos,
                          stats_reparaciones=stats_reparaciones,
                          productos_mas_vendidos=productos_mas_vendidos,
                          mejores_clientes=mejores_clientes)

@admin_bp.route('/usuarios')
@login_required
@admin_required
def usuarios():
    """Gestión de usuarios del sistema"""
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT e.*, c.nombre as cargo_nombre
        FROM empleados e
        LEFT JOIN cargos c ON e.cargo_id = c.id
        ORDER BY e.nombre
    ''')
    empleados = cur.fetchall()
    cur.close()
    
    return render_template('admin/usuarios/lista.html', empleados=empleados)

@admin_bp.route('/backup')
@login_required
@admin_required
def backup():
    """Página de gestión de copias de seguridad"""
    return render_template('admin/backup.html')

@admin_bp.route('/reportes')
@login_required
@admin_required
def reportes():
    """Página de reportes y estadísticas"""
    # Obtener el tipo de reporte solicitado
    tipo_reporte = request.args.get('tipo', 'ventas')
    periodo = request.args.get('periodo', 'mes')
    
    try:
        cur = mysql.connection.cursor()
        
        # Datos para el reporte según el tipo
        if tipo_reporte == 'ventas':
            if periodo == 'dia':
                # Ventas por día (últimos 30 días)
                cur.execute("""
                    SELECT DATE(fecha) as fecha, COUNT(*) as total, SUM(total) as monto
                    FROM ventas
                    WHERE fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                    GROUP BY DATE(fecha)
                    ORDER BY DATE(fecha)
                """)
            elif periodo == 'mes':
                # Ventas por mes (último año)
                cur.execute("""
                    SELECT CONCAT(YEAR(fecha), '-', MONTH(fecha)) as periodo,
                           COUNT(*) as total, SUM(total) as monto
                    FROM ventas
                    WHERE fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                    GROUP BY YEAR(fecha), MONTH(fecha)
                    ORDER BY YEAR(fecha), MONTH(fecha)
                """)
            else:  # año
                # Ventas por año
                cur.execute("""
                    SELECT YEAR(fecha) as periodo, COUNT(*) as total, SUM(total) as monto
                    FROM ventas
                    GROUP BY YEAR(fecha)
                    ORDER BY YEAR(fecha)
                """)
            
            datos_reporte = cur.fetchall()
            
            # Obtener los productos más vendidos
            cur.execute("""
                SELECT p.nombre, SUM(dv.cantidad) as total_vendido
                FROM detalle_ventas dv
                JOIN productos p ON dv.id_producto = p.id
                JOIN ventas v ON dv.id_venta = v.id
                WHERE v.fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY dv.id_producto
                ORDER BY total_vendido DESC
                LIMIT 10
            """)
            productos_mas_vendidos = cur.fetchall()
            
        elif tipo_reporte == 'reparaciones':
            if periodo == 'dia':
                # Reparaciones por día (últimos 30 días)
                cur.execute("""
                    SELECT DATE(fecha_recepcion) as fecha, COUNT(*) as total,
                           SUM(CASE WHEN estado = 'finalizado' THEN 1 ELSE 0 END) as finalizadas
                    FROM reparaciones
                    WHERE fecha_recepcion >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                    GROUP BY DATE(fecha_recepcion)
                    ORDER BY DATE(fecha_recepcion)
                """)
            elif periodo == 'mes':
                # Reparaciones por mes (último año)
                cur.execute("""
                    SELECT CONCAT(YEAR(fecha_recepcion), '-', MONTH(fecha_recepcion)) as periodo,
                           COUNT(*) as total,
                           SUM(CASE WHEN estado = 'finalizado' THEN 1 ELSE 0 END) as finalizadas
                    FROM reparaciones
                    WHERE fecha_recepcion >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                    GROUP BY YEAR(fecha_recepcion), MONTH(fecha_recepcion)
                    ORDER BY YEAR(fecha_recepcion), MONTH(fecha_recepcion)
                """)
            else:  # año
                # Reparaciones por año
                cur.execute("""
                    SELECT YEAR(fecha_recepcion) as periodo, COUNT(*) as total,
                           SUM(CASE WHEN estado = 'finalizado' THEN 1 ELSE 0 END) as finalizadas
                    FROM reparaciones
                    GROUP BY YEAR(fecha_recepcion)
                    ORDER BY YEAR(fecha_recepcion)
                """)
            
            datos_reporte = cur.fetchall()
            
            # Obtener los tipos de reparaciones más comunes
            cur.execute("""
                SELECT tipo_electrodomestico, COUNT(*) as total
                FROM reparaciones
                WHERE fecha_recepcion >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
                GROUP BY tipo_electrodomestico
                ORDER BY total DESC
                LIMIT 10
            """)
            tipos_reparaciones = cur.fetchall()
            
        elif tipo_reporte == 'clientes':
            # Nuevos clientes por período
            if periodo == 'dia':
                cur.execute("""
                    SELECT DATE(fecha_registro) as fecha, COUNT(*) as total
                    FROM clientes
                    WHERE fecha_registro >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                    GROUP BY DATE(fecha_registro)
                    ORDER BY DATE(fecha_registro)
                """)
            elif periodo == 'mes':
                cur.execute("""
                    SELECT CONCAT(YEAR(fecha_registro), '-', MONTH(fecha_registro)) as periodo,
                           COUNT(*) as total
                    FROM clientes
                    WHERE fecha_registro >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                    GROUP BY YEAR(fecha_registro), MONTH(fecha_registro)
                    ORDER BY YEAR(fecha_registro), MONTH(fecha_registro)
                """)
            else:  # año
                cur.execute("""
                    SELECT YEAR(fecha_registro) as periodo, COUNT(*) as total
                    FROM clientes
                    GROUP BY YEAR(fecha_registro)
                    ORDER BY YEAR(fecha_registro)
                """)
            
            datos_reporte = cur.fetchall()
            
            # Obtener los clientes con más compras
            cur.execute("""
                SELECT c.nombre, COUNT(v.id) as total_compras, SUM(v.total) as monto_total
                FROM ventas v
                JOIN clientes c ON v.id_cliente = c.id_cliente
                WHERE v.fecha >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
                GROUP BY v.id_cliente
                ORDER BY total_compras DESC
                LIMIT 10
            """)
            clientes_top = cur.fetchall()
            
        elif tipo_reporte == 'inventario':
            # Productos por categoría
            cur.execute("""
                SELECT c.nombre as categoria, COUNT(p.id) as total_productos,
                       SUM(p.stock) as stock_total
                FROM productos p
                JOIN categorias c ON p.id_categoria = c.id
                GROUP BY p.id_categoria
                ORDER BY total_productos DESC
            """)
            datos_reporte = cur.fetchall()
            
            # Productos sin stock o con stock bajo
            cur.execute("""
                SELECT p.nombre, p.stock, p.stock_minimo, c.nombre as categoria
                FROM productos p
                JOIN categorias c ON p.id_categoria = c.id
                WHERE p.stock <= p.stock_minimo
                ORDER BY p.stock ASC
                LIMIT 20
            """)
            productos_criticos = cur.fetchall()
        
        else:
            datos_reporte = []
        
        cur.close()
        
        # Preparar datos para gráficos
        labels = []
        values = []
        
        for dato in datos_reporte:
            if tipo_reporte == 'ventas':
                labels.append(dato['fecha'] if 'fecha' in dato else dato['periodo'])
                values.append(float(dato['monto']) if dato['monto'] else 0)
            elif tipo_reporte == 'reparaciones':
                labels.append(dato['fecha'] if 'fecha' in dato else dato['periodo'])
                values.append(int(dato['total']))
            elif tipo_reporte == 'clientes':
                labels.append(dato['fecha'] if 'fecha' in dato else dato['periodo'])
                values.append(int(dato['total']))
            elif tipo_reporte == 'inventario':
                labels.append(dato['categoria'])
                values.append(int(dato['stock_total']))
        
        # Convertir a formato JSON para usar en JavaScript
        chart_data = {
            'labels': labels,
            'values': values
        }
        
        # Datos adicionales específicos para cada tipo de reporte
        extras = {}
        if tipo_reporte == 'ventas':
            extras['productos_mas_vendidos'] = productos_mas_vendidos
        elif tipo_reporte == 'reparaciones':
            extras['tipos_reparaciones'] = tipos_reparaciones
        elif tipo_reporte == 'clientes':
            extras['clientes_top'] = clientes_top
        elif tipo_reporte == 'inventario':
            extras['productos_criticos'] = productos_criticos
        
    except Exception as e:
        print(f"Error al generar reporte: {str(e)}")
        datos_reporte = []
        chart_data = {'labels': [], 'values': []}
        extras = {}
    
    return render_template('admin/reportes.html',
                           tipo_reporte=tipo_reporte,
                           periodo=periodo,
                           datos_reporte=datos_reporte,
                           chart_data=json.dumps(chart_data),
                           extras=extras)

@admin_bp.route('/reportes/ventas')
@login_required
@admin_required
def reportes_ventas():
    """Vista detallada de reportes de ventas"""
    # Obtener el período solicitado
    periodo = request.args.get('periodo', 'mes')
    categoria_id = request.args.get('categoria')
    vendedor_id = request.args.get('vendedor')
    
    try:
        cur = mysql.connection.cursor()
        
        # Construir consulta base para ventas según el período
        if periodo == 'dia':
            # Ventas por día (últimos 30 días)
            query = """
                SELECT DATE(fecha) as fecha, COUNT(*) as total_ventas, SUM(total) as monto
                FROM ventas
                WHERE fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            """
        elif periodo == 'mes':
            # Ventas por mes (último año)
            query = """
                SELECT CONCAT(MONTH(fecha), '/', YEAR(fecha)) as fecha, 
                       COUNT(*) as total_ventas, SUM(total) as monto
                FROM ventas
                WHERE fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            """
        else:  # año
            # Ventas por año
            query = """
                SELECT YEAR(fecha) as fecha, COUNT(*) as total_ventas, SUM(total) as monto
                FROM ventas
            """
        
        # Aplicar filtros adicionales
        params = []
        if categoria_id:
            query += """
                AND EXISTS (
                    SELECT 1 FROM detalles_venta dv 
                    JOIN productos p ON dv.producto_id = p.id
                    WHERE dv.venta_id = ventas.id AND p.categoria_id = %s
                )
            """
            params.append(categoria_id)
        
        if vendedor_id:
            query += " AND empleado_id = %s"
            params.append(vendedor_id)
        
        # Agrupar y ordenar
        query += " GROUP BY fecha ORDER BY fecha"
        
        # Ejecutar consulta principal
        cur.execute(query, params)
        datos_ventas = cur.fetchall()
        
        # Preparar datos para el gráfico
        labels = []
        values = []
        
        for venta in datos_ventas:
            labels.append(str(venta['fecha']))
            values.append(float(venta['monto'] or 0))
        
        chart_data = {
            'labels': labels,
            'values': values
        }
        
        # Obtener estadísticas generales
        cur.execute("""
            SELECT COUNT(*) as total_ventas,
                   COALESCE(SUM(total), 0) as ingresos_totales,
                   COALESCE(AVG(total), 0) as promedio_venta,
                   COUNT(DISTINCT cliente_id) as total_clientes
            FROM ventas
            WHERE estado = 'Pagada'
        """)
        stats = cur.fetchone()
        
        # Obtener productos más vendidos
        cur.execute("""
            SELECT p.nombre, SUM(dv.cantidad) as cantidad, SUM(dv.subtotal) as total
            FROM detalles_venta dv
            JOIN productos p ON dv.producto_id = p.id
            JOIN ventas v ON dv.venta_id = v.id
            WHERE v.estado = 'Pagada'
            GROUP BY p.id
            ORDER BY cantidad DESC
            LIMIT 10
        """)
        productos_top = cur.fetchall()
        
        # Obtener mejores clientes
        cur.execute("""
            SELECT c.nombre, COUNT(v.id) as compras, SUM(v.total) as total
            FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            WHERE v.estado = 'Pagada'
            GROUP BY c.id
            ORDER BY total DESC
            LIMIT 10
        """)
        clientes_top = cur.fetchall()
        
        # Obtener categorías para filtrado
        cur.execute("SELECT id, nombre FROM categorias WHERE activo = TRUE ORDER BY nombre")
        categorias = cur.fetchall()
        
        # Obtener vendedores para filtrado
        cur.execute("SELECT id, nombre FROM empleados WHERE activo = TRUE ORDER BY nombre")
        vendedores = cur.fetchall()
        
        cur.close()
        
        return render_template('admin/reportes/ventas.html',
                              periodo=periodo,
                              chart_data=chart_data,
                              stats=stats,
                              productos_top=productos_top,
                              clientes_top=clientes_top,
                              categorias=categorias,
                              vendedores=vendedores)
                              
    except Exception as e:
        if cur:
            cur.close()
        print(f"Error en reporte de ventas: {str(e)}")
        flash(f'Error al generar reporte: {str(e)}', 'danger')
        return redirect(url_for('admin.reportes'))

@admin_bp.route('/clientes')
@login_required
@admin_required
def clientes():
    """Gestión de clientes"""
    # Obtener términos de búsqueda y filtros
    search = request.args.get('search', '')
    orderby = request.args.get('orderby', 'nombre')
    order = request.args.get('order', 'asc')
    
    try:
        cur = mysql.connection.cursor()
        
        # Construir la consulta SQL base
        query = "SELECT * FROM clientes"
        params = []
        
        # Añadir filtros de búsqueda si existen
        if search:
            query += " WHERE nombre LIKE %s OR email LIKE %s OR telefono LIKE %s"
            search_param = f"%{search}%"
            params = [search_param, search_param, search_param]
        
        # Añadir ordenamiento
        valid_orderby = ['nombre', 'email', 'fecha_registro', 'ultimo_login']
        valid_order = ['asc', 'desc']
        
        if orderby not in valid_orderby:
            orderby = 'nombre'
            
        if order not in valid_order:
            order = 'asc'
            
        query += f" ORDER BY {orderby} {order.upper()}"
        
        # Ejecutar la consulta
        cur.execute(query, params)
        clientes = cur.fetchall()
        
        # Obtener estadísticas de clientes
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN DATE(fecha_registro) = CURDATE() THEN 1 ELSE 0 END) as hoy,
                SUM(CASE WHEN MONTH(fecha_registro) = MONTH(CURDATE()) AND YEAR(fecha_registro) = YEAR(CURDATE()) THEN 1 ELSE 0 END) as mes
            FROM clientes
        """)
        stats = cur.fetchone()
        
        cur.close()
        
    except Exception as e:
        print(f"Error al obtener clientes: {str(e)}")
        clientes = []
        stats = {'total': 0, 'hoy': 0, 'mes': 0}
    
    return render_template('admin/clientes.html', 
                          clientes=clientes, 
                          stats=stats,
                          search=search,
                          orderby=orderby,
                          order=order)

@admin_bp.route('/clientes/<int:cliente_id>')
@login_required
@admin_required
def ver_cliente(cliente_id):
    """Ver detalles de un cliente específico"""
    try:
        cur = mysql.connection.cursor()
        
        # Obtener información del cliente
        cur.execute("""
            SELECT * FROM clientes WHERE id = %s
        """, (cliente_id,))
        cliente = cur.fetchone()
        
        if not cliente:
            flash('Cliente no encontrado', 'danger')
            return redirect(url_for('admin.clientes'))
        
        # Inicializar variables para evitar errores en el template
        compras = []
        metricas = {
            'total_compras': 0,
            'total_gastado': 0,
            'promedio_compra': 0,
            'ultima_compra': None
        }
        reparaciones = []
        
        try:
            # Obtener historial de compras
            cur.execute("""
                SELECT v.*, e.nombre as empleado
                FROM ventas v
                LEFT JOIN empleados e ON v.id_empleado = e.id_empleado
                WHERE v.cliente_id = %s
                ORDER BY v.fecha DESC
            """, (cliente_id,))
            compras = cur.fetchall()
        except Exception as e:
            print(f"Error al obtener compras: {str(e)}")
            # No redirigir, continuar con los datos que tenemos
        
        try:
            # Calcular métricas del cliente
            cur.execute("""
                SELECT 
                    COUNT(*) as total_compras,
                    COALESCE(SUM(total), 0) as total_gastado,
                    COALESCE(AVG(total), 0) as promedio_compra,
                    MAX(fecha) as ultima_compra
                FROM ventas
                WHERE cliente_id = %s
            """, (cliente_id,))
            metricas = cur.fetchone()
            
            # Si no hay métricas, proporcionar defaults
            if not metricas:
                metricas = {
                    'total_compras': 0,
                    'total_gastado': 0,
                    'promedio_compra': 0,
                    'ultima_compra': None
                }
        except Exception as e:
            print(f"Error al obtener métricas: {str(e)}")
            # No redirigir, continuar con los datos que tenemos
        
        try:
            # Obtener reparaciones solicitadas
            cur.execute("""
                SELECT id, cliente_id, electrodomestico, marca, modelo, problema, 
                      estado, fecha_recepcion, fecha_entrega_estimada, fecha_entrega
                FROM reparaciones
                WHERE cliente_id = %s
                ORDER BY fecha_recepcion DESC
            """, (cliente_id,))
            reparaciones = cur.fetchall()
        except Exception as e:
            print(f"Error al obtener reparaciones: {str(e)}")
            # No redirigir, continuar con los datos que tenemos
        
        cur.close()
        
        return render_template('admin/cliente_detalle.html',
                              cliente=cliente,
                              compras=compras,
                              metricas=metricas,
                              reparaciones=reparaciones)
        
    except Exception as e:
        print(f"Error al obtener detalles del cliente: {str(e)}")
        flash('Error al cargar información del cliente', 'danger')
        return redirect(url_for('admin.clientes'))

@admin_bp.route('/clientes/<int:cliente_id>/eliminar', methods=['POST', 'GET'])
@login_required
@admin_required
def eliminar_cliente(cliente_id):
    """Eliminar un cliente"""
    # Si la petición es GET, solo confirmar que el cliente existe y mostrar página de confirmación
    if request.method == 'GET':
        return redirect(url_for('admin.clientes'))
        
    # Para el método POST, verificar el token CSRF y procesar la eliminación
    try:
        cur = mysql.connection.cursor()
        
        # Verificar que el cliente existe
        cur.execute("SELECT nombre FROM clientes WHERE id = %s", (cliente_id,))
        cliente = cur.fetchone()
        
        if not cliente:
            flash('Cliente no encontrado', 'warning')
            return redirect(url_for('admin.clientes'))
        
        nombre_cliente = cliente['nombre']
        
        # Verificar si tiene relaciones antes de intentar eliminar
        cur.execute("SELECT COUNT(*) as total FROM ventas WHERE cliente_id = %s", (cliente_id,))
        result = cur.fetchone()
        if result and result['total'] > 0:
            flash('No se puede eliminar al cliente porque tiene ventas registradas', 'danger')
            return redirect(url_for('admin.clientes'))
        
        # Intentar eliminar directamente
        cur.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
        mysql.connection.commit()
        flash(f'Cliente "{nombre_cliente}" eliminado correctamente', 'success')
            
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error al eliminar cliente: {str(e)}")
        flash('Error al eliminar cliente', 'danger')
        
    finally:
        cur.close()
        
    return redirect(url_for('admin.clientes'))

@admin_bp.route('/compras')
@login_required
@admin_required
def compras():
    """Gestión de compras y proveedores"""
    return render_template('admin/compras.html')

@admin_bp.route('/carousel')
@login_required
@admin_required
def carousel():
    """Administración del carousel"""
    # Obtener todos los items del carousel
    items = Carousel.obtener_todos()
    return render_template('admin/carousel.html', items=items)

@admin_bp.route('/carousel/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def carousel_nuevo():
    """Crear un nuevo elemento del carousel"""
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        enlace = request.form.get('enlace')
        orden = request.form.get('orden', 0)
        activo = 'activo' in request.form
        imagen = request.files.get('imagen')
        
        # Validar datos
        if not titulo or not imagen:
            flash('El título y la imagen son obligatorios', 'danger')
            return redirect(url_for('admin.carousel_nuevo'))
        
        # Crear nuevo item
        datos = {
            'titulo': titulo,
            'descripcion': descripcion,
            'enlace': enlace,
            'orden': orden,
            'activo': activo
        }
        
        if Carousel.crear(datos, imagen):
            flash('Imagen añadida al carousel correctamente', 'success')
            return redirect(url_for('admin.carousel'))
        else:
            flash('Ocurrió un error al crear el elemento', 'danger')
    
    return render_template('admin/carousel_form.html')

@admin_bp.route('/carousel/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def carousel_editar(id):
    """Editar un elemento del carousel"""
    item = Carousel.obtener_por_id(id)
    if not item:
        flash('Elemento no encontrado', 'danger')
        return redirect(url_for('admin.carousel'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        enlace = request.form.get('enlace')
        orden = request.form.get('orden', 0)
        activo = 'activo' in request.form
        imagen = request.files.get('imagen')
        
        # Validar datos
        if not titulo:
            flash('El título es obligatorio', 'danger')
            return redirect(url_for('admin.carousel_editar', id=id))
        
        # Actualizar datos
        datos = {
            'titulo': titulo,
            'descripcion': descripcion,
            'enlace': enlace,
            'orden': orden,
            'activo': activo
        }
        
        # Solo actualizar imagen si se proporciona una nueva
        if imagen and imagen.filename:
            if Carousel.actualizar(id, datos, imagen):
                flash('Elemento actualizado correctamente', 'success')
                return redirect(url_for('admin.carousel'))
        else:
            if Carousel.actualizar(id, datos):
                flash('Elemento actualizado correctamente', 'success')
                return redirect(url_for('admin.carousel'))
        
        flash('Ocurrió un error al actualizar el elemento', 'danger')
    
    return render_template('admin/carousel_form.html', item=item)

@admin_bp.route('/carousel/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def carousel_eliminar(id):
    """Eliminar un elemento del carousel"""
    if Carousel.eliminar(id):
        flash('Elemento eliminado correctamente', 'success')
    else:
        flash('Error al eliminar el elemento', 'danger')
    
    return redirect(url_for('admin.carousel'))

@admin_bp.route('/clientes/<int:cliente_id>/editar')
@login_required
@admin_required
def editar_cliente(cliente_id):
    """Redirecciona a la página de edición de cliente"""
    return redirect(url_for('clientes.editar', cliente_id=cliente_id)) 