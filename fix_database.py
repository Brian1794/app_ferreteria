import os
import sys
from flask import Flask
from dotenv import load_dotenv
import MySQLdb
from MySQLdb.cursors import DictCursor

# Cargar variables de entorno
load_dotenv()

# Crear una app Flask temporal para contexto
app = Flask(__name__)

# Configurar la conexión MySQL desde variables de entorno
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB = os.environ.get('MYSQL_DB', 'ferreteria')

# Crear la conexión
try:
    connection = MySQLdb.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        passwd=MYSQL_PASSWORD,
        db=MYSQL_DB,
        cursorclass=DictCursor
    )
    print(f"Conexión establecida a la base de datos {MYSQL_DB}")
except Exception as e:
    print(f"Error al conectar a la base de datos: {e}")
    sys.exit(1)

# Crear cursor
cursor = connection.cursor()

# Función para ejecutar SQL y manejar errores
def execute_sql(sql, params=None, commit=True, ignore_errors=False):
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        if commit:
            connection.commit()
        print(f"Ejecutado: {sql[:80]}...")
        return True
    except Exception as e:
        if not ignore_errors:
            print(f"Error en SQL: {sql[:100]}...\nError: {e}")
            connection.rollback()
        return False

# Eliminar tablas que podrían tener problemas con claves foráneas
print("Eliminando tablas con dependencias...")
execute_sql("DROP TABLE IF EXISTS detalles_venta", ignore_errors=True)
execute_sql("DROP TABLE IF EXISTS reparaciones_repuestos", ignore_errors=True)
execute_sql("DROP TABLE IF EXISTS historial_reparaciones", ignore_errors=True)

# Corrección de la tabla ventas
print("Verificando tabla ventas...")
# Verificar si existe la tabla ventas
execute_sql("SHOW TABLES LIKE 'ventas'")
if cursor.fetchone():
    # Verificar si tiene clave primaria
    execute_sql("SHOW KEYS FROM ventas WHERE Key_name = 'PRIMARY'")
    if not cursor.fetchone():
        print("Recreando tabla ventas...")
        execute_sql("DROP TABLE IF EXISTS ventas")
        
# Crear tabla ventas correctamente
execute_sql('''
    CREATE TABLE IF NOT EXISTS ventas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        cliente_id INT,
        empleado_id INT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total DECIMAL(12,2) NOT NULL,
        estado VARCHAR(50) DEFAULT 'COMPLETADA',
        observaciones TEXT,
        tipo_pago VARCHAR(50),
        FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
        FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE SET NULL
    )
''')

# Recrear tabla detalles_venta
print("Recreando tabla detalles_venta...")
execute_sql('''
    CREATE TABLE IF NOT EXISTS detalles_venta (
        id INT AUTO_INCREMENT PRIMARY KEY,
        venta_id INT NOT NULL,
        producto_id INT,
        cantidad INT NOT NULL,
        precio_unitario DECIMAL(12,2) NOT NULL,
        subtotal DECIMAL(12,2) NOT NULL,
        FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
        FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
    )
''')

# Corregir estructura de la tabla empleados
print("Verificando tabla empleados...")
execute_sql("SHOW COLUMNS FROM empleados LIKE 'cargo_id'")
if not cursor.fetchone():
    print("Agregando columna cargo_id a empleados...")
    execute_sql("ALTER TABLE empleados ADD COLUMN cargo_id INT AFTER password")
    execute_sql("ALTER TABLE empleados ADD FOREIGN KEY (cargo_id) REFERENCES cargos(id) ON DELETE SET NULL")

execute_sql("SHOW COLUMNS FROM empleados LIKE 'es_admin'")
if not cursor.fetchone():
    print("Agregando columna es_admin a empleados...")
    execute_sql("ALTER TABLE empleados ADD COLUMN es_admin BOOLEAN DEFAULT FALSE AFTER cargo_id")

# Corregir estructura de la tabla clientes
print("Verificando tabla clientes...")
execute_sql("SHOW COLUMNS FROM clientes LIKE 'email'")
if not cursor.fetchone():
    print("Agregando columna email a clientes...")
    execute_sql("ALTER TABLE clientes ADD COLUMN email VARCHAR(100) UNIQUE AFTER nombre")

execute_sql("SHOW COLUMNS FROM clientes LIKE 'password'")
if not cursor.fetchone():
    print("Agregando columna password a clientes...")
    execute_sql("ALTER TABLE clientes ADD COLUMN password VARCHAR(255) NOT NULL DEFAULT '' AFTER email")

# Insertar datos iniciales si faltan
print("Verificando datos iniciales...")

# Verificar si hay cargos
execute_sql("SELECT COUNT(*) as count FROM cargos")
count = cursor.fetchone()['count']
if count == 0:
    print("Creando cargos...")
    cargos = [
        ('Administrador', 'Control total del sistema'),
        ('Vendedor', 'Gestión de ventas y atención al cliente'),
        ('Técnico', 'Encargado de reparaciones'),
        ('Almacenista', 'Gestión de inventario')
    ]
    for nombre, descripcion in cargos:
        execute_sql(
            "INSERT INTO cargos (nombre, descripcion, activo) VALUES (%s, %s, %s)",
            (nombre, descripcion, True)
        )

# Verificar si hay usuario administrador
execute_sql("SELECT COUNT(*) as count FROM empleados WHERE es_admin = TRUE")
count = cursor.fetchone()['count']
if count == 0:
    print("Creando usuario administrador...")
    # Contraseña segura (usar hash en producción)
    execute_sql(
        "INSERT INTO empleados (nombre, email, password, es_admin, activo) VALUES (%s, %s, %s, %s, %s)",
        ('Administrador', 'admin@ferreteria.com', 'admin123', True, True)
    )

print("¡Corrección de la base de datos completada!")
print("Puede ser necesario reiniciar la aplicación para que los cambios tengan efecto.")

cursor.close()
connection.close() 