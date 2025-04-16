import MySQLdb
import os
import re
from dotenv import load_dotenv

# Cargar variables de entorno si existe un archivo .env
load_dotenv()

# Intentar leer la configuración de base de datos desde config.py
db_host = None
db_user = None
db_password = None
db_name = None

try:
    # Intentar leer config.py
    with open('config.py', 'r') as f:
        config_content = f.read()
        
        # Buscar los valores de configuración de la base de datos
        mysql_host_match = re.search(r"MYSQL_HOST\s*=\s*['\"](.+?)['\"]", config_content)
        mysql_user_match = re.search(r"MYSQL_USER\s*=\s*['\"](.+?)['\"]", config_content)
        mysql_password_match = re.search(r"MYSQL_PASSWORD\s*=\s*['\"](.+?)['\"]", config_content)
        mysql_db_match = re.search(r"MYSQL_DB\s*=\s*['\"](.+?)['\"]", config_content)
        
        if mysql_host_match:
            db_host = mysql_host_match.group(1)
        if mysql_user_match:
            db_user = mysql_user_match.group(1)
        if mysql_password_match:
            db_password = mysql_password_match.group(1)
        if mysql_db_match:
            db_name = mysql_db_match.group(1)
            
        print(f"Configuración encontrada en config.py: Host={db_host}, User={db_user}, DB={db_name}")
except Exception as e:
    print(f"No se pudo leer config.py: {e}")

# Usar valores de las variables de entorno como respaldo
DB_HOST = os.getenv('DB_HOST', db_host) or 'localhost'
DB_USER = os.getenv('DB_USER', db_user) or 'root'
DB_PASSWORD = os.getenv('DB_PASSWORD', db_password) or ''
DB_NAME = os.getenv('DB_NAME', db_name) or 'ferreteria_db'

print(f"Intentando conectar a: Host={DB_HOST}, User={DB_USER}, DB={DB_NAME}")

try:
    # Conectar a la base de datos
    conn = MySQLdb.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASSWORD,
        db=DB_NAME
    )
    
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)
    
    # Verificar la estructura de la tabla clientes
    print("\n=== ESTRUCTURA DE LA TABLA CLIENTES ===")
    cursor.execute("DESCRIBE clientes")
    columns = cursor.fetchall()
    
    for col in columns:
        print(f"{col['Field']}: {col['Type']} (Null: {col['Null']}, Key: {col['Key']})")
    
    print("\n=== VERIFICANDO ID DE CLIENTE ===")
    # Buscar todos los campos que podrían ser un ID
    id_columns = [col for col in columns if 'id' in col['Field'].lower()]
    
    for col in id_columns:
        print(f"Posible columna ID: {col['Field']}: {col['Type']} (Key: {col['Key']})")
    
    # Verificar la existencia de registros
    print("\n=== VERIFICANDO REGISTROS DE CLIENTES ===")
    cursor.execute("SELECT COUNT(*) as total FROM clientes")
    count = cursor.fetchone()
    print(f"Total de registros: {count['total']}")
    
    if count['total'] > 0:
        # Obtener el primer registro para ver su estructura
        cursor.execute("SELECT * FROM clientes LIMIT 1")
        sample = cursor.fetchone()
        print("\nEstructura de un registro de ejemplo:")
        for field, value in sample.items():
            print(f"{field}: {value}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error al conectar a la base de datos: {e}")
    
    # Intentar listar bases de datos disponibles si la conexión fue exitosa pero la base de datos no existe
    if "Unknown database" in str(e):
        try:
            conn = MySQLdb.connect(
                host=DB_HOST,
                user=DB_USER,
                passwd=DB_PASSWORD
            )
            
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            
            print("\nBases de datos disponibles:")
            for db in databases:
                print(f"- {db[0]}")
                
            cursor.close()
            conn.close()
            
        except Exception as db_list_err:
            print(f"No se pudieron listar las bases de datos: {db_list_err}") 