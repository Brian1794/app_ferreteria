from flask import Flask
import pymysql
import os

# Configuración de base de datos
DB_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
DB_USER = os.environ.get('MYSQL_USER') or 'root'
DB_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
DB_NAME = os.environ.get('MYSQL_DB') or 'ferreteria_la_u'

try:
    print(f"Conectando a la base de datos {DB_NAME} en {DB_HOST} con usuario {DB_USER}")
    # Conectar directamente a la base de datos sin Flask
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with connection.cursor() as cursor:
        # Verificar si las columnas ya existen
        cursor.execute("SHOW COLUMNS FROM pedidos LIKE 'subtotal'")
        subtotal_exists = cursor.fetchone() is not None
        
        cursor.execute("SHOW COLUMNS FROM pedidos LIKE 'costo_envio'")
        envio_exists = cursor.fetchone() is not None
        
        if not subtotal_exists:
            cursor.execute("ALTER TABLE pedidos ADD COLUMN subtotal DECIMAL(10,2) NOT NULL DEFAULT 0")
            print("Columna 'subtotal' agregada correctamente a la tabla pedidos")
        else:
            print("La columna 'subtotal' ya existe en la tabla pedidos")
        
        if not envio_exists:
            cursor.execute("ALTER TABLE pedidos ADD COLUMN costo_envio DECIMAL(10,2) NOT NULL DEFAULT 0")
            print("Columna 'costo_envio' agregada correctamente a la tabla pedidos")
        else:
            print("La columna 'costo_envio' ya existe en la tabla pedidos")
        
        # Actualizar los registros existentes
        if not subtotal_exists or not envio_exists:
            cursor.execute("UPDATE pedidos SET subtotal = total, costo_envio = 0 WHERE subtotal = 0")
            print("Registros existentes actualizados: subtotal = total, costo_envio = 0")
        
        connection.commit()
    
    connection.close()
    print("Actualización de base de datos completada con éxito")
    
except Exception as e:
    print(f"Error al modificar la base de datos: {str(e)}") 