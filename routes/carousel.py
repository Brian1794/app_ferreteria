from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models.carousel import Carousel
from models.models import mysql
from routes.auth import admin_required
import os
from werkzeug.utils import secure_filename
import time

carousel_bp = Blueprint('carousel', __name__)

@carousel_bp.route('/')
@login_required
@admin_required
def index():
    """Lista todos los elementos del carousel"""
    # Obtener todos los elementos del carousel
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT * FROM carousel 
        ORDER BY orden ASC
    ''')
    carousel_items = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/carousel.html', carousel_items=carousel_items)

@carousel_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo():
    """Crea un nuevo elemento para el carousel"""
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion', '')
        enlace = request.form.get('enlace', '')
        orden = request.form.get('orden', 0)
        activo = 'activo' in request.form
        imagen_file = request.files.get('imagen')
        
        # Validaciones básicas
        if not titulo:
            flash('El título es obligatorio', 'warning')
            return render_template('admin/carousel_form.html')
        
        if not imagen_file or imagen_file.filename == '':
            flash('Debe seleccionar una imagen', 'warning')
            return render_template('admin/carousel_form.html')
        
        try:
            # Guardar la imagen
            filename = guardar_imagen(imagen_file)
            
            # Insertar en la base de datos
            cursor = mysql.connection.cursor()
            cursor.execute('''
                INSERT INTO carousel (titulo, descripcion, imagen, enlace, orden, activo)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (titulo, descripcion, filename, enlace, orden, activo))
            mysql.connection.commit()
            cursor.close()
            
            flash('Elemento del carousel creado con éxito', 'success')
            return redirect(url_for('carousel.index'))
            
        except Exception as e:
            flash(f'Error al crear elemento: {str(e)}', 'danger')
            return render_template('admin/carousel_form.html')
    
    return render_template('admin/carousel_form.html')

@carousel_bp.route('/<int:carousel_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(carousel_id):
    """Edita un elemento del carousel"""
    # Obtener el elemento actual
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM carousel WHERE id = %s', (carousel_id,))
    carousel_item = cursor.fetchone()
    
    if not carousel_item:
        flash('Elemento no encontrado', 'warning')
        return redirect(url_for('carousel.index'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion', '')
        enlace = request.form.get('enlace', '')
        orden = request.form.get('orden', 0)
        activo = 'activo' in request.form
        imagen_file = request.files.get('imagen')
        
        # Validaciones básicas
        if not titulo:
            flash('El título es obligatorio', 'warning')
            return render_template('admin/carousel_form.html', carousel=carousel_item)
        
        try:
            # Preparar la consulta
            query = '''
                UPDATE carousel
                SET titulo = %s, descripcion = %s, enlace = %s, orden = %s, activo = %s
            '''
            params = [titulo, descripcion, enlace, orden, activo]
            
            # Si hay una nueva imagen, guardarla y actualizar el campo
            if imagen_file and imagen_file.filename != '':
                # Eliminar la imagen anterior si existe
                if carousel_item['imagen']:
                    eliminar_imagen(carousel_item['imagen'])
                
                # Guardar la nueva imagen
                filename = guardar_imagen(imagen_file)
                query += ", imagen = %s"
                params.append(filename)
            
            # Completar la consulta
            query += " WHERE id = %s"
            params.append(carousel_id)
            
            # Ejecutar la actualización
            cursor.execute(query, params)
            mysql.connection.commit()
            
            flash('Elemento del carousel actualizado con éxito', 'success')
            return redirect(url_for('carousel.index'))
            
        except Exception as e:
            flash(f'Error al actualizar elemento: {str(e)}', 'danger')
        
        finally:
            cursor.close()
    
    return render_template('admin/carousel_form.html', carousel=carousel_item)

@carousel_bp.route('/<int:carousel_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar(carousel_id):
    """Elimina un elemento del carousel"""
    try:
        cursor = mysql.connection.cursor()
        
        # Obtener información para eliminar la imagen
        cursor.execute('SELECT imagen FROM carousel WHERE id = %s', (carousel_id,))
        carousel_item = cursor.fetchone()
        
        if not carousel_item:
            flash('Elemento no encontrado', 'warning')
            return redirect(url_for('carousel.index'))
        
        # Eliminar la imagen del servidor
        if carousel_item['imagen']:
            eliminar_imagen(carousel_item['imagen'])
        
        # Eliminar el registro de la base de datos
        cursor.execute('DELETE FROM carousel WHERE id = %s', (carousel_id,))
        mysql.connection.commit()
        cursor.close()
        
        flash('Elemento del carousel eliminado con éxito', 'success')
        
    except Exception as e:
        flash(f'Error al eliminar elemento: {str(e)}', 'danger')
    
    return redirect(url_for('carousel.index'))

def guardar_imagen(imagen_file):
    """Guarda una imagen en el servidor y retorna el nombre del archivo"""
    if not imagen_file:
        return None
        
    # Asegurar nombre de archivo único
    filename = secure_filename(imagen_file.filename)
    timestamp = int(time.time())
    new_filename = f"{timestamp}_{filename}"
    
    # Ruta donde se guardarán las imágenes
    upload_folder = os.path.join(current_app.static_folder, 'uploads', 'carousel')
    
    # Crear el directorio si no existe
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Guardar la imagen
    imagen_file.save(os.path.join(upload_folder, new_filename))
    
    return new_filename

def eliminar_imagen(filename):
    """Elimina una imagen del servidor"""
    if not filename:
        return
        
    # Ruta de la imagen
    ruta_imagen = os.path.join(current_app.static_folder, 'uploads', 'carousel', filename)
    
    # Eliminar si existe
    if os.path.exists(ruta_imagen):
        os.remove(ruta_imagen) 