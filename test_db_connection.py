import os
from dotenv import load_dotenv
import MySQLdb
from MySQLdb.cursors import DictCursor

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos
MYSQL_HOST = os.environ.get('MYSQL_HOST')
MYSQL_USER = os.environ.get('MYSQL_USER')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')
MYSQL_DB = os.environ.get('MYSQL_DB')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

print(f"Intentando conectar a {MYSQL_HOST}:{MYSQL_PORT}...")

try:
    connection = MySQLdb.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        passwd=MYSQL_PASSWORD,
        db=MYSQL_DB,
        port=MYSQL_PORT,
        cursorclass=DictCursor
    )
    print("¡Conexión exitosa!")
    
    # Probar una consulta simple
    cursor = connection.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    print(f"Resultado de la consulta: {result}")
    
    # Verificar tablas existentes
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print("\nTablas existentes:")
    for table in tables:
        print(f"- {table['Tables_in_' + MYSQL_DB]}")
    
    cursor.close()
    connection.close()
    
except Exception as e:
    print(f"Error al conectar a la base de datos: {e}") 