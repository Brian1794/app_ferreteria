from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from extensions import mysql

categorias_bp = Blueprint('categorias', __name__)

@categorias_bp.route('/')
@login_required
def listar():
    """Lista todas las categorías disponibles"""
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT c.id, c.nombre, c.descripcion, c.activa, 
               COUNT(p.id) as total_productos
        FROM categorias c
        LEFT JOIN productos p ON c.id = p.categoria_id
        GROUP BY c.id
        ORDER BY c.nombre
    """)
    categorias = cursor.fetchall()
    cursor.close()
    return render_template('categorias/lista.html', categorias=categorias)

@categorias_bp.route('/agregar', methods=['GET', 'POST'])
@login_required
def agregar():
    """Agrega una nueva categoría"""
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        activa = 'activa' in request.form
        
        if not nombre:
            flash('El nombre de la categoría es obligatorio', 'danger')
            return redirect(url_for('categorias.agregar'))
        
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO categorias (nombre, descripcion, activa)
                VALUES (%s, %s, %s)
            """, (nombre, descripcion, activa))
            mysql.connection.commit()
            flash('Categoría agregada correctamente', 'success')
            return redirect(url_for('categorias.listar'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al agregar categoría: {str(e)}', 'danger')
        finally:
            cursor.close()
    
    return render_template('categorias/agregar.html')

@categorias_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Edita una categoría existente"""
    cursor = mysql.connection.cursor()
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        activa = 'activa' in request.form
        
        if not nombre:
            flash('El nombre de la categoría es obligatorio', 'danger')
            return redirect(url_for('categorias.editar', id=id))
        
        try:
            cursor.execute("""
                UPDATE categorias 
                SET nombre = %s, descripcion = %s, activa = %s
                WHERE id = %s
            """, (nombre, descripcion, activa, id))
            mysql.connection.commit()
            flash('Categoría actualizada correctamente', 'success')
            return redirect(url_for('categorias.listar'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error al actualizar categoría: {str(e)}', 'danger')
    
    # Obtener datos de la categoría
    cursor.execute("SELECT id, nombre, descripcion, activa FROM categorias WHERE id = %s", (id,))
    categoria = cursor.fetchone()
    cursor.close()
    
    if not categoria:
        flash('Categoría no encontrada', 'danger')
        return redirect(url_for('categorias.listar'))
    
    return render_template('categorias/editar.html', categoria=categoria)

@categorias_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar(id):
    """Elimina una categoría"""
    cursor = mysql.connection.cursor()
    
    # Verificar si la categoría tiene productos asociados
    cursor.execute("SELECT COUNT(*) FROM productos WHERE categoria_id = %s", (id,))
    count = cursor.fetchone()[0]
    
    if count > 0:
        flash('No se puede eliminar la categoría porque tiene productos asociados', 'danger')
        cursor.close()
        return redirect(url_for('categorias.listar'))
    
    try:
        cursor.execute("DELETE FROM categorias WHERE id = %s", (id,))
        mysql.connection.commit()
        flash('Categoría eliminada correctamente', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al eliminar categoría: {str(e)}', 'danger')
    finally:
        cursor.close()
    
    return redirect(url_for('categorias.listar')) 