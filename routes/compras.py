"""
Rutas para la gestión de compras de la ferretería
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from flask_login import login_required, current_user
from extensions import mysql
import MySQLdb
from database import get_cursor, ejecutar_consulta, close_connection

# Crear el Blueprint de compras
compras_bp = Blueprint('compras', __name__)

@compras_bp.route('/compras')
@login_required
def index():
    """Vista principal de compras"""
    if not current_user.es_admin and not current_user.es_empleado:
        flash('No tienes permiso para acceder a esta sección', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        # Obtener lista de compras
        cursor = get_cursor(dictionary=True)
        query = """
            SELECT c.*, p.nombre as proveedor_nombre, e.nombre as empleado_nombre
            FROM compras c
            LEFT JOIN proveedores p ON c.proveedor_id = p.id
            LEFT JOIN empleados e ON c.empleado_id = e.id
            ORDER BY c.fecha_compra DESC
            LIMIT 50
        """
        compras = ejecutar_consulta(query)
        
        return render_template('compras/index.html', compras=compras)
        
    except Exception as e:
        flash(f'Error al cargar las compras: {str(e)}', 'danger')
        return redirect(url_for('main.index'))
