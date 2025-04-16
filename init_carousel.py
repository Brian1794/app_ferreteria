"""
Script para crear la tabla carousel y agregar imágenes de ejemplo
"""
import os
import sys
from flask import Flask
from dotenv import load_dotenv
import MySQLdb
import shutil
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

# Configurar la conexión MySQL desde variables de entorno
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB = os.environ.get('MYSQL_DB', 'ferreteria')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

def create_connection():
    """Crea una conexión a la base de datos"""
    try:
        connection = MySQLdb.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            passwd=MYSQL_PASSWORD,
            db=MYSQL_DB,
            port=MYSQL_PORT
        )
        print(f"Conexión establecida a la base de datos {MYSQL_DB}")
        return connection
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        sys.exit(1)

def crear_tabla_carousel(connection):
    """Crea la tabla carousel si no existe"""
    cursor = connection.cursor()
    try:
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
        cursor.execute(sql)
        connection.commit()
        print("Tabla carousel creada o verificada correctamente")
        return True
    except Exception as e:
        print(f"Error al crear tabla carousel: {e}")
        return False
    finally:
        cursor.close()

def verificar_directorio_uploads():
    """Verifica que exista el directorio para subir imágenes"""
    uploads_dir = os.path.join('static', 'uploads', 'carousel')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
        print(f"Directorio {uploads_dir} creado")
    return uploads_dir

def agregar_imagenes_ejemplo(connection, uploads_dir):
    """Agrega algunas imágenes de ejemplo al carousel"""
    cursor = connection.cursor()
    
    # Verificar si ya hay imágenes en el carousel
    cursor.execute("SELECT COUNT(*) FROM carousel")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"Ya existen {count} imágenes en el carousel, no se agregarán ejemplos")
        cursor.close()
        return
    
    # Lista de imágenes de ejemplo
    ejemplos = [
        {
            'titulo': "Ofertas especiales en herramientas",
            'descripcion': "Aprovecha nuestros descuentos en herramientas eléctricas y manuales",
            'imagen': "ejemplo_herramientas.jpg",
            'enlace': "/productos/catalogo?categoria=herramientas",
            'orden': 1
        },
        {
            'titulo': "Todo para tu construcción",
            'descripcion': "Encuentra los mejores materiales para tu proyecto",
            'imagen': "ejemplo_construccion.jpg",
            'enlace': "/productos/catalogo?categoria=construccion",
            'orden': 2
        },
        {
            'titulo': "Servicio de reparaciones",
            'descripcion': "Reparamos tus electrodomésticos con la mejor garantía",
            'imagen': "ejemplo_reparaciones.jpg",
            'enlace': "/reparaciones",
            'orden': 3
        }
    ]
    
    # Copiar imágenes de ejemplo a la carpeta de uploads si existen en static/img
    for ejemplo in ejemplos:
        ruta_origen = os.path.join('static', 'img', ejemplo['imagen'])
        if not os.path.exists(ruta_origen):
            # Si no existe, usar una imagen predeterminada
            print(f"Imagen {ejemplo['imagen']} no encontrada, creando un placeholder")
            
            # Generar un timestamp único
            timestamp = int(datetime.now().timestamp())
            ejemplo['imagen'] = f"{timestamp}_{ejemplo['imagen']}"
            
            # Crear una imagen placeholder
            with open(os.path.join(uploads_dir, ejemplo['imagen']), 'w') as f:
                f.write(f"Esta es una imagen placeholder para {ejemplo['titulo']}")
        else:
            # Copiar la imagen existente
            ruta_destino = os.path.join(uploads_dir, ejemplo['imagen'])
            shutil.copy(ruta_origen, ruta_destino)
            print(f"Imagen {ejemplo['imagen']} copiada a {uploads_dir}")
        
        # Insertar en la base de datos
        try:
            sql = """
            INSERT INTO carousel (titulo, descripcion, imagen, enlace, orden, activo)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                ejemplo['titulo'],
                ejemplo['descripcion'],
                ejemplo['imagen'],
                ejemplo['enlace'],
                ejemplo['orden'],
                True
            ))
            connection.commit()
            print(f"Ejemplo '{ejemplo['titulo']}' agregado al carousel")
        except Exception as e:
            print(f"Error al insertar ejemplo '{ejemplo['titulo']}': {e}")
    
    cursor.close()

def main():
    """Función principal"""
    # Establecer conexión
    connection = create_connection()
    
    # Crear tabla
    if crear_tabla_carousel(connection):
        # Verificar directorio de uploads
        uploads_dir = verificar_directorio_uploads()
        
        # Agregar imágenes de ejemplo
        agregar_imagenes_ejemplo(connection, uploads_dir)
    
    # Cerrar conexión
    connection.close()
    print("Proceso completado")

if __name__ == "__main__":
    main() 