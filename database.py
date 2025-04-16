"""
Módulo de conexión y operaciones de base de datos MySQL para la Ferretería
"""
import MySQLdb
from flask import current_app, g
from extensions import mysql
import os
import time
from MySQLdb.cursors import DictCursor

def get_connection():
    """
    Obtiene una conexión a la base de datos.
    Si ya existe una conexión en el contexto de la solicitud, la reutiliza.
    """
    if 'db' not in g:
        g.db = mysql.connection
    return g.db

def get_cursor(dictionary=False):
    """
    Obtiene un cursor para ejecutar consultas SQL.
    Reutiliza la conexión del contexto actual.
    
    Args:
        dictionary (bool): Si es True, devuelve resultados como diccionarios.
    
    Returns:
        cursor: Un cursor de MySQL.
    """
    conn = get_connection()
    if dictionary:
        return conn.cursor(DictCursor)
    return conn.cursor()

def close_connection(e=None):
    """
    Cierra la conexión a la base de datos y la devuelve al pool.
    Esta función debe ser llamada cuando finaliza una solicitud.
    """
    try:
        db = g.pop('db', None)
        if db is not None:
            try:
                # Asegurarse de que no haya transacciones pendientes
                db.rollback()
                # Cerrar todos los cursores abiertos
                if hasattr(db, '_cursors'):
                    for cursor in db._cursors:
                        try:
                            cursor.close()
                        except Exception:
                            pass
                # Cerrar la conexión
                db.close()
            except MySQLdb.OperationalError as e:
                # Manejo específico para error de servidor desconectado
                if e.args[0] != 2006:  # MySQL server has gone away
                    print(f"Error operacional al cerrar la conexión: {e}")
            except Exception as e:
                print(f"Error al cerrar la conexión: {e}")
    except Exception as e:
        print(f"Error general en close_connection: {e}")

def init_db():
    """
    Inicializa la base de datos creando todas las tablas.
    Esta función debe ser llamada solo una vez, cuando se configura la aplicación.
    Implementa reintentos con backoff exponencial.
    """
    from models.models import crear_tablas, insertar_datos_iniciales
    
    # Intentar conectarse a la base de datos con reintentos
    max_retries = 5
    retry_delay = 2  # segundos
    
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            crear_tablas()
            insertar_datos_iniciales()
            print(f"Base de datos inicializada correctamente después de {attempt+1} intentos")
            return True
        except Exception as e:
            print(f"Error al inicializar la base de datos (intento {attempt+1}): {e}")
            if attempt < max_retries - 1:
                print(f"Reintentando en {retry_delay} segundos...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Incrementar el tiempo de espera entre reintentos
            else:
                print("Se alcanzó el número máximo de reintentos. No se pudo inicializar la base de datos.")
                return False

def ejecutar_consulta(query, params=None, fetchone=False, commit=False, dictionary=False):
    """
    Ejecuta una consulta SQL y devuelve el resultado.
    Optimizado para liberar el cursor y gestionar errores adecuadamente.
    
    Args:
        query (str): Consulta SQL a ejecutar.
        params (tuple): Parámetros para la consulta SQL.
        fetchone (bool): Si es True, devuelve solo un resultado.
        commit (bool): Si es True, confirma los cambios en la base de datos.
        dictionary (bool): Si es True, devuelve resultados como diccionarios.
    
    Returns:
        result: Resultado de la consulta.
    """
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(DictCursor) if dictionary else conn.cursor()
        cursor.execute(query, params or ())
        
        if commit:
            conn.commit()
            return cursor.lastrowid
        
        if fetchone:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
        
        return result
    except Exception as e:
        if commit:
            conn.rollback()
        print(f"Error en consulta SQL: {e}")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                print(f"Aviso: Error al cerrar el cursor: {e}")
                pass  # Ignoramos el error para evitar que la aplicación falle al cerrar

def obtener_por_id(tabla, id, columnas="*", dictionary=False):
    """
    Obtiene un registro por su ID.
    
    Args:
        tabla (str): Nombre de la tabla.
        id (int): ID del registro.
        columnas (str): Columnas a seleccionar.
        dictionary (bool): Si es True, devuelve resultados como diccionarios.
    
    Returns:
        result: Registro encontrado o None.
    """
    query = f"SELECT {columnas} FROM {tabla} WHERE id = %s"
    return ejecutar_consulta(query, (id,), fetchone=True, dictionary=dictionary)

def insertar(tabla, datos, commit=True):
    """
    Inserta un nuevo registro en la tabla.
    
    Args:
        tabla (str): Nombre de la tabla.
        datos (dict): Datos a insertar.
        commit (bool): Si es True, confirma los cambios.
    
    Returns:
        int: ID del registro insertado.
    """
    columnas = ", ".join(datos.keys())
    placeholders = ", ".join(["%s"] * len(datos))
    
    query = f"INSERT INTO {tabla} ({columnas}) VALUES ({placeholders})"
    
    return ejecutar_consulta(query, tuple(datos.values()), commit=commit)

def actualizar(tabla, datos, condicion, commit=True):
    """
    Actualiza registros en la tabla.
    
    Args:
        tabla (str): Nombre de la tabla.
        datos (dict): Datos a actualizar.
        condicion (str): Condición WHERE.
        commit (bool): Si es True, confirma los cambios.
    
    Returns:
        int: Número de filas afectadas.
    """
    sets = ", ".join([f"{k} = %s" for k in datos.keys()])
    
    query = f"UPDATE {tabla} SET {sets} WHERE {condicion}"
    
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(query, tuple(datos.values()))
        
        if commit:
            conn.commit()
        
        return cursor.rowcount
    except Exception as e:
        if commit:
            conn.rollback()
        print(f"Error en actualización SQL: {e}")
        raise
    finally:
        if cursor:
            cursor.close()

def eliminar(tabla, condicion, commit=True):
    """
    Elimina registros de la tabla.
    
    Args:
        tabla (str): Nombre de la tabla.
        condicion (str): Condición WHERE.
        commit (bool): Si es True, confirma los cambios.
    
    Returns:
        int: Número de filas afectadas.
    """
    query = f"DELETE FROM {tabla} WHERE {condicion}"
    
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        
        if commit:
            conn.commit()
        
        return cursor.rowcount
    except Exception as e:
        if commit:
            conn.rollback()
        print(f"Error en eliminación SQL: {e}")
        raise
    finally:
        if cursor:
            cursor.close()

def listar(tabla, columnas="*", condicion=None, orden=None, limite=None, dictionary=False):
    """
    Lista registros de una tabla con diversas opciones de filtrado.
    
    Args:
        tabla (str): Nombre de la tabla.
        columnas (str): Columnas a seleccionar.
        condicion (str): Condición WHERE.
        orden (str): Cláusula ORDER BY.
        limite (int): Número máximo de resultados.
        dictionary (bool): Si es True, devuelve resultados como diccionarios.
    
    Returns:
        list: Lista de registros.
    """
    query = f"SELECT {columnas} FROM {tabla}"
    
    if condicion:
        query += f" WHERE {condicion}"
    
    if orden:
        query += f" ORDER BY {orden}"
    
    if limite:
        query += f" LIMIT {limite}"
    
    return ejecutar_consulta(query, dictionary=dictionary)

def contar(tabla, condicion=None):
    """
    Cuenta los registros en una tabla.
    
    Args:
        tabla (str): Nombre de la tabla.
        condicion (str): Condición WHERE.
    
    Returns:
        int: Número de registros.
    """
    query = f"SELECT COUNT(*) AS count FROM {tabla}"
    
    if condicion:
        query += f" WHERE {condicion}"
    
    result = ejecutar_consulta(query, fetchone=True, dictionary=True)
    return result['count'] if result else 0

def verificar_tabla_existe(tabla):
    """
    Verifica si una tabla existe en la base de datos.
    
    Args:
        tabla (str): Nombre de la tabla.
    
    Returns:
        bool: True si la tabla existe, False en caso contrario.
    """
    query = """
        SELECT COUNT(*) AS count 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
    """
    result = ejecutar_consulta(
        query, 
        (current_app.config['MYSQL_DB'], tabla), 
        fetchone=True,
        dictionary=True
    )
    return result['count'] > 0 if result else False

def ejecutar_script(ruta_script):
    """
    Ejecuta un script SQL desde un archivo.
    
    Args:
        ruta_script (str): Ruta al archivo de script SQL.
    
    Returns:
        bool: True si se ejecutó correctamente, False en caso contrario.
    """
    if not os.path.exists(ruta_script):
        print(f"El archivo {ruta_script} no existe")
        return False
    
    with open(ruta_script, 'r') as file:
        script = file.read()
    
    # Dividir el script en declaraciones individuales
    statements = script.split(';')
    
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        for statement in statements:
            if statement.strip():
                cursor.execute(statement)
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error al ejecutar script SQL: {e}")
        return False
    finally:
        if cursor:
            cursor.close()

def crear_database_schema():
    """
    Crea el esquema de la base de datos a partir del archivo schema.sql.
    """
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
    if os.path.exists(schema_path):
        return ejecutar_script(schema_path)
    else:
        print(f"No se encontró el archivo de esquema en {schema_path}")
        return False

def backup_database(ruta_destino):
    """
    Realiza una copia de seguridad de la base de datos.
    
    Args:
        ruta_destino (str): Ruta donde se guardará el archivo de copia de seguridad.
    
    Returns:
        bool: True si se realizó la copia correctamente, False en caso contrario.
    """
    try:
        # Este método requiere acceso al sistema de archivos y ejecutar comandos
        # Usar configuración de la aplicación para obtener credenciales
        host = current_app.config['MYSQL_HOST']
        user = current_app.config['MYSQL_USER']
        password = current_app.config['MYSQL_PASSWORD']
        db = current_app.config['MYSQL_DB']
        
        # Generar nombre de archivo con fecha y hora
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        if not os.path.exists(os.path.dirname(ruta_destino)):
            os.makedirs(os.path.dirname(ruta_destino))
        
        archivo_backup = f"{ruta_destino}/backup-{db}-{timestamp}.sql"
        
        # Comando para MySQL Dump
        comando = f"mysqldump -h {host} -u {user}"
        if password:
            comando += f" -p{password}"
        comando += f" {db} > {archivo_backup}"
        
        # Ejecutar comando
        resultado = os.system(comando)
        
        if resultado == 0:
            print(f"Copia de seguridad creada en {archivo_backup}")
            return True
        else:
            print(f"Error al crear copia de seguridad. Código: {resultado}")
            return False
    
    except Exception as e:
        print(f"Error al realizar copia de seguridad: {e}")
        return False

def restaurar_backup(ruta_archivo):
    """
    Restaura una copia de seguridad de la base de datos.
    
    Args:
        ruta_archivo (str): Ruta al archivo de copia de seguridad.
    
    Returns:
        bool: True si se restauró correctamente, False en caso contrario.
    """
    if not os.path.exists(ruta_archivo):
        print(f"El archivo {ruta_archivo} no existe")
        return False
    
    try:
        # Usar configuración de la aplicación para obtener credenciales
        host = current_app.config['MYSQL_HOST']
        user = current_app.config['MYSQL_USER']
        password = current_app.config['MYSQL_PASSWORD']
        db = current_app.config['MYSQL_DB']
        
        # Comando para restaurar
        comando = f"mysql -h {host} -u {user}"
        if password:
            comando += f" -p{password}"
        comando += f" {db} < {ruta_archivo}"
        
        # Ejecutar comando
        resultado = os.system(comando)
        
        if resultado == 0:
            print(f"Base de datos restaurada desde {ruta_archivo}")
            return True
        else:
            print(f"Error al restaurar base de datos. Código: {resultado}")
            return False
    
    except Exception as e:
        print(f"Error al restaurar copia de seguridad: {e}")
        return False