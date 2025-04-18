"""
Extensiones globales de Flask para la aplicación.
Este archivo ayuda a evitar importaciones circulares.
"""
import os
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL
from flask import g, current_app
import MySQLdb
from MySQLdb.cursors import DictCursor
import functools
import time
import logging
from flask_mail import Mail  # Añadir importación de Flask-Mail

# Inicializar extensiones
mysql = MySQL()
bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()  # Crear instancia de Flask-Mail

# Configurar el login_manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página'
login_manager.login_message_category = 'warning'

def init_extensions(app):
    """Inicializa todas las extensiones de Flask"""
    
    # Configuración del pool de conexiones MySQL
    app.config['MYSQL_POOL_NAME'] = 'ferreteria_pool'
    app.config['MYSQL_POOL_SIZE'] = 5
    app.config['MYSQL_POOL_TIMEOUT'] = 30
    app.config['MYSQL_POOL_RECYCLE'] = 280  # Reciclar conexiones después de 280 segundos
    app.config['MYSQL_POOL_PRE_PING'] = True  # Verificar conexión antes de usar
    
    # Inicializar MySQL con la configuración del pool
    mysql.init_app(app)
    
    # Registrar la función de limpieza para cerrar conexiones
    app.teardown_appcontext(close_mysql_connection)

    # Configuración del correo electrónico - más flexible para cualquier proveedor
    app.config.setdefault('MAIL_SERVER', os.environ.get('MAIL_SERVER', 'smtp.gmail.com'))
    app.config.setdefault('MAIL_PORT', int(os.environ.get('MAIL_PORT', 587)))
    app.config.setdefault('MAIL_USE_TLS', os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true')
    app.config.setdefault('MAIL_USE_SSL', os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true')
    app.config.setdefault('MAIL_USERNAME', os.environ.get('MAIL_USERNAME', ''))
    app.config.setdefault('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD', ''))
    app.config.setdefault('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', 'Ferreteria La U <noreply@example.com>'))
    app.config.setdefault('MAIL_MAX_EMAILS', int(os.environ.get('MAIL_MAX_EMAILS', 50)))
    app.config.setdefault('MAIL_ASCII_ATTACHMENTS', os.environ.get('MAIL_ASCII_ATTACHMENTS', 'False').lower() == 'true')
    
    # Inicializar extensiones con la aplicación
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Añadir variables globales para todas las plantillas
    @app.context_processor
    def inject_global_variables():
        """Inyecta variables globales en todas las plantillas"""
        from datetime import datetime
        
        # Datos de la empresa desde variables de entorno
        return {
            'now': datetime.now(),
            'current_year': datetime.now().year,
            'empresa_nombre': os.environ.get('EMPRESA_NOMBRE', 'Ferretería y Cacharrería la U'),
            'empresa_propietario': os.environ.get('EMPRESA_PROPIETARIO', 'Michael Stiven Alfonso Rodríguez'),
            'empresa_direccion': os.environ.get('EMPRESA_DIRECCION', 'Cra. 69C # 7A-14, Bogotá D.C.'),
            'empresa_telefono': os.environ.get('EMPRESA_TELEFONO', '310 320 0632'),
            'empresa_email': os.environ.get('EMPRESA_EMAIL', 'michael.alfonso.rodri@gmail.com'),
            'empresa_whatsapp': os.environ.get('EMPRESA_WHATSAPP', '3103200632')
        }

def get_connection():
    """
    Obtiene una conexión del pool de MySQL.
    Reutiliza la conexión si ya existe en el contexto actual.
    """
    if 'db' not in g:
        g.db = mysql.connection
    return g.db

def get_cursor(dictionary=False):
    """
    Obtiene un cursor MySQL, opcionalmente configurado para devolver diccionarios.
    
    Args:
        dictionary (bool): Si es True, devuelve resultados como diccionarios.
    
    Returns:
        cursor: Un cursor MySQL configurado.
    """
    conn = get_connection()
    return conn.cursor(DictCursor) if dictionary else conn.cursor()

def get_dict_cursor():
    """
    Obtiene un cursor MySQL configurado para devolver resultados como diccionarios.
    Esta es una función de conveniencia que llama a get_cursor(dictionary=True).
    
    Returns:
        cursor: Un cursor MySQL configurado para devolver diccionarios.
    """
    return get_cursor(dictionary=True)

def retry_on_connection_error(max_retries=3, delay=1):
    """
    Decorador que reintenta una función cuando ocurre un error de conexión MySQL.
    
    Args:
        max_retries (int): Número máximo de intentos
        delay (int): Tiempo de espera entre intentos en segundos
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except MySQLdb.OperationalError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        current_app.logger.warning(
                            f"Error de conexión en {func.__name__}, "
                            f"reintentando ({attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(delay)
                    continue
            current_app.logger.error(
                f"Error de conexión persistente en {func.__name__} "
                f"después de {max_retries} intentos: {last_error}"
            )
            raise last_error
        return wrapper
    return decorator

def close_mysql_connection(e=None):
    """
    Cierra la conexión MySQL y la devuelve al pool.
    Esta función se llama automáticamente al final de cada solicitud.
    
    Args:
        e: Excepción que provocó el cierre (si existe).
    """
    db = g.pop('db', None)
    
    if db is not None:
        try:
            # Asegurarse de que no hay transacciones pendientes
            db.rollback()
            
            # Cerrar todos los cursores abiertos
            if hasattr(db, '_cursors'):
                for cursor in db._cursors:
                    try:
                        cursor.close()
                    except Exception:
                        pass
            
            # Devolver la conexión al pool
            db.close()
            
        except MySQLdb.OperationalError as e:
            # Ignorar específicamente el error de servidor desconectado
            if e.args[0] != 2006:  # MySQL server has gone away
                current_app.logger.warning(f"Error operacional al cerrar la conexión: {e}")
        except Exception as e:
            current_app.logger.error(f"Error al cerrar la conexión MySQL: {e}")

def check_connection_limits():
    """
    Verifica los límites actuales de conexiones MySQL.
    Útil para diagnóstico de problemas de conexión.
    
    Returns:
        dict: Información sobre los límites de conexión.
    """
    cursor = get_cursor(dictionary=True)
    try:
        # Verificar variables globales relacionadas con conexiones
        cursor.execute("""
            SHOW VARIABLES WHERE Variable_name IN 
            ('max_connections', 'max_user_connections', 'wait_timeout', 
             'interactive_timeout', 'connect_timeout')
        """)
        variables = {row['Variable_name']: row['Value'] for row in cursor.fetchall()}
        
        # Obtener conexiones actuales
        cursor.execute("SHOW STATUS WHERE Variable_name = 'Threads_connected'")
        current_connections = cursor.fetchone()['Value']
        
        return {
            'limits': variables,
            'current_connections': current_connections
        }
    finally:
        cursor.close()

def verify_connection():
    """
    Verifica que la conexión MySQL está funcionando correctamente.
    
    Returns:
        bool: True si la conexión está activa, False en caso contrario.
    """
    try:
        cursor = get_cursor()
        cursor.execute("SELECT 1")
        return cursor.fetchone()[0] == 1
    except Exception as e:
        current_app.logger.error(f"Error al verificar la conexión MySQL: {e}")
        return False
    finally:
        if cursor:
            cursor.close()