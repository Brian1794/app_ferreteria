from flask import Flask
from extensions import mysql
import os
from dotenv import load_dotenv
import MySQLdb

# Cargar variables de entorno
load_dotenv()

# Crear aplicación Flask
app = Flask(__name__)

# Configurar MySQL
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'ferreteria')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Inicializar MySQL
mysql.init_app(app)

# Verificar la estructura de las tablas
with app.app_context():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Verificar tabla empleados
        print("=== Estructura de la tabla empleados ===")
        cursor.execute("DESCRIBE empleados")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
        
        # Verificar tabla cargos
        print("\n=== Estructura de la tabla cargos ===")
        cursor.execute("DESCRIBE cargos")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
        
        # Verificar registros en cargos
        print("\n=== Cargos disponibles ===")
        cursor.execute("SELECT * FROM cargos")
        cargos = cursor.fetchall()
        for cargo in cargos:
            print(cargo)
        
        # Verificar empleados y sus cargos
        print("\n=== Empleados y sus cargos ===")
        cursor.execute("""
            SELECT e.id, e.nombre, e.email, e.cargo_id, e.es_admin, c.nombre as cargo_nombre 
            FROM empleados e
            LEFT JOIN cargos c ON e.cargo_id = c.id
        """)
        empleados = cursor.fetchall()
        for empleado in empleados:
            print(empleado)
        
        # Verificar la estructura de la tabla de reparaciones
        cursor.execute("DESCRIBE reparaciones")
        print('=== Estructura de la tabla reparaciones ===')
        columnas = cursor.fetchall()
        for col in columnas:
            print(f"{col['Field']}: {col['Type']}")
        
        # Verificar datos en la tabla de reparaciones
        cursor.execute("SELECT id, estado FROM reparaciones LIMIT 10")
        print('\n=== Estados en reparaciones ===')
        reparaciones = cursor.fetchall()
        if reparaciones:
            for rep in reparaciones:
                print(f"ID: {rep['id']}, Estado: \"{rep['estado']}\"")
        else:
            print("No hay reparaciones en la base de datos")
        
        cursor.close()
    except Exception as e:
        print(f"Error: {e}") 