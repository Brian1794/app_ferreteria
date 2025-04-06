#!/usr/bin/env python
"""
Script para verificar y arreglar la estructura de la tabla de reparaciones.
Este script intentará:
1. Verificar la existencia de la tabla reparaciones
2. Verificar la estructura actual
3. Asegurarse de que tenga los campos necesarios
4. Criar la tabla si no existe
"""

from flask import Flask
from extensions import mysql
import sys
import time

app = Flask(__name__)

# Asumimos que estamos usando la misma configuración que en app.py
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'ferreteria'

# Para bases de datos remotas, descomenta y modifica las siguientes líneas
# app.config['MYSQL_HOST'] = 'bzm5uc8abvbfoesn7g5v-mysql.services.clever-cloud.com'
# app.config['MYSQL_USER'] = 'uiwd7cwaqxfkr4f2'
# app.config['MYSQL_PASSWORD'] = 'zIKIjNS03xLHjGPIwCoA'
# app.config['MYSQL_DB'] = 'bzm5uc8abvbfoesn7g5v'

mysql.init_app(app)

def execute_query(cursor, query, params=None, quiet=False):
    """Ejecuta una consulta SQL y maneja posibles errores"""
    try:
        if not quiet:
            print(f"Ejecutando: {query[:50]}...")
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return True
    except Exception as e:
        print(f"Error en SQL: {query[:100]}...")
        print(f"Error: {e}")
        return False

def fix_reparaciones_table():
    """Verifica y arregla la tabla de reparaciones"""
    with app.app_context():
        try:
            cursor = mysql.connection.cursor()
            
            # 1. Verificar si la tabla existe
            cursor.execute("SHOW TABLES LIKE 'reparaciones'")
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                print("La tabla 'reparaciones' no existe. Creándola...")
                schema = """
                CREATE TABLE reparaciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cliente_id INT,
                    descripcion TEXT NOT NULL,
                    electrodomestico VARCHAR(100),
                    marca VARCHAR(50),
                    modelo VARCHAR(50),
                    problema TEXT,
                    estado VARCHAR(20) DEFAULT 'RECIBIDO',
                    fecha_recepcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_entrega_estimada DATE NULL,
                    fecha_entrega TIMESTAMP NULL,
                    tecnico_id INT NULL,
                    costo_estimado DECIMAL(10,2) NULL,
                    costo_final DECIMAL(10,2) NULL,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
                    FOREIGN KEY (tecnico_id) REFERENCES empleados(id) ON DELETE SET NULL
                )
                """
                execute_query(cursor, schema)
                mysql.connection.commit()
                print("Tabla 'reparaciones' creada exitosamente")
            else:
                print("La tabla 'reparaciones' ya existe. Verificando su estructura...")
                
                # 2. Verificar la estructura actual
                cursor.execute("DESCRIBE reparaciones")
                columns = cursor.fetchall()
                column_names = [column[0] for column in columns]
                print(f"Columnas actuales: {column_names}")
                
                # 3. Verificar campos necesarios y agregarlos si no existen
                required_columns = {
                    'electrodomestico': "VARCHAR(100)",
                    'problema': "TEXT",
                    'marca': "VARCHAR(50)",
                    'modelo': "VARCHAR(50)"
                }
                
                for column, data_type in required_columns.items():
                    if column not in column_names:
                        print(f"Agregando columna '{column}'...")
                        query = f"ALTER TABLE reparaciones ADD COLUMN {column} {data_type}"
                        execute_query(cursor, query)
                        mysql.connection.commit()
            
            # 4. Verificar la tabla historial_reparaciones
            cursor.execute("SHOW TABLES LIKE 'historial_reparaciones'")
            historial_exists = cursor.fetchone() is not None
            
            if not historial_exists:
                print("La tabla 'historial_reparaciones' no existe. Creándola...")
                schema = """
                CREATE TABLE historial_reparaciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    reparacion_id INT NOT NULL,
                    estado_anterior VARCHAR(20),
                    estado_nuevo VARCHAR(20),
                    descripcion TEXT,
                    usuario_id INT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE
                )
                """
                execute_query(cursor, schema)
                mysql.connection.commit()
                print("Tabla 'historial_reparaciones' creada exitosamente")
            
            cursor.close()
            return True
        except Exception as e:
            print(f"Error al verificar/arreglar la tabla: {e}")
            return False

def check_connection():
    """Verifica la conexión a la base de datos"""
    print("Verificando conexión a la base de datos...")
    with app.app_context():
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            print(f"Conexión exitosa: {result}")
            return True
        except Exception as e:
            print(f"Error de conexión: {e}")
            return False

if __name__ == "__main__":
    print("=== Script de verificación y arreglo de tabla 'reparaciones' ===")
    
    if check_connection():
        if fix_reparaciones_table():
            print("\n✅ Proceso completado con éxito.")
            sys.exit(0)
        else:
            print("\n❌ Hubo errores durante el proceso.")
            sys.exit(1)
    else:
        print("\n❌ No se pudo conectar a la base de datos.")
        sys.exit(1) 