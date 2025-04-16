"""
Modelo para gestionar las imágenes del carousel de la página principal
"""
from flask import current_app
import os
import time
import datetime
from werkzeug.utils import secure_filename
from database import ejecutar_consulta, insertar, actualizar, eliminar, obtener_por_id

class Carousel:
    """Clase para gestionar las imágenes del carousel"""
    
    def __init__(self, id=None, titulo='', descripcion='', imagen='', enlace='', orden=0, activo=True, fecha_creacion=None):
        self.id = id
        self.titulo = titulo
        self.descripcion = descripcion
        self.imagen = imagen
        self.enlace = enlace
        self.orden = orden
        self.activo = activo
        self.fecha_creacion = fecha_creacion
    
    @staticmethod
    def crear_tabla():
        """Crea la tabla carousel si no existe"""
        sql = """
        CREATE TABLE IF NOT EXISTS carousel (
            id INT AUTO_INCREMENT PRIMARY KEY,
            titulo VARCHAR(100) NOT NULL,
            descripcion TEXT,
            imagen VARCHAR(255) NOT NULL,
            enlace VARCHAR(255),
            orden INT DEFAULT 0,
            activo BOOLEAN DEFAULT TRUE,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        ejecutar_consulta(sql, commit=True)
        
    @staticmethod
    def obtener_todos(solo_activos=False):
        """Obtiene todas las imágenes del carousel ordenadas por el campo orden"""
        where = "WHERE activo = 1" if solo_activos else ""
        sql = f"SELECT * FROM carousel {where} ORDER BY orden ASC"
        resultado = ejecutar_consulta(sql, dictionary=True)
        return resultado
    
    @staticmethod
    def obtener_por_id(id):
        """Obtiene una imagen del carousel por su ID"""
        return obtener_por_id('carousel', id, dictionary=True)
    
    @staticmethod
    def crear(datos, imagen_file=None):
        """Crea una nueva imagen para el carousel"""
        # Si hay una imagen, guardarla
        if imagen_file:
            filename = Carousel.guardar_imagen(imagen_file)
            datos['imagen'] = filename
        
        return insertar('carousel', datos)
    
    @staticmethod
    def actualizar(id, datos, imagen_file=None):
        """Actualiza una imagen del carousel"""
        # Si hay una nueva imagen, guardarla y actualizar el campo
        if imagen_file:
            # Eliminar imagen anterior si existe
            carousel_actual = Carousel.obtener_por_id(id)
            if carousel_actual and carousel_actual.get('imagen'):
                Carousel.eliminar_imagen(carousel_actual['imagen'])
            
            # Guardar nueva imagen
            filename = Carousel.guardar_imagen(imagen_file)
            datos['imagen'] = filename
        
        return actualizar('carousel', datos, f"id = {id}")
    
    @staticmethod
    def eliminar(id):
        """Elimina una imagen del carousel"""
        # Obtener información para eliminar la imagen física
        carousel = Carousel.obtener_por_id(id)
        if carousel and carousel.get('imagen'):
            Carousel.eliminar_imagen(carousel['imagen'])
        
        return eliminar('carousel', f"id = {id}")
    
    @staticmethod
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
    
    @staticmethod
    def eliminar_imagen(filename):
        """Elimina una imagen del servidor"""
        if not filename:
            return
            
        # Ruta de la imagen
        ruta_imagen = os.path.join(current_app.static_folder, 'uploads', 'carousel', filename)
        
        # Eliminar si existe
        if os.path.exists(ruta_imagen):
            os.remove(ruta_imagen) 