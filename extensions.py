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

def init_app(app):
    """Inicializa todas las extensiones de Flask con la aplicación"""
    # Configurar opciones adicionales para MySQL
    app.config.setdefault('MYSQL_HOST', 'localhost')
    app.config.setdefault('MYSQL_USER', 'root')
    app.config.setdefault('MYSQL_PASSWORD', '')
    app.config.setdefault('MYSQL_DB', 'ferreteria_la_u')
    app.config.setdefault('MYSQL_CURSORCLASS', 'DictCursor')
    
    # Configurar MySQL con más conexiones
    app.config['MYSQL_MAX_CONNECTIONS'] = 20  # Aumentar el número máximo de conexiones
    app.config['MYSQL_POOL_SIZE'] = 10  # Tamaño del pool de conexiones
    app.config['MYSQL_POOL_RECYCLE'] = 280  # Tiempo en segundos para reciclar conexiones
    
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
    mysql.init_app(app)
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
    
    # Reemplazar el teardown de MySQL para evitar el error 2006
    # Primero guardamos una referencia al teardown original
    original_teardown = mysql.teardown
    
    # Eliminar el handler de teardown original
    app.teardown_appcontext_funcs = [f for f in app.teardown_appcontext_funcs 
                                    if f is not original_teardown]
    
    # Registrar nuestro propio teardown personalizado
    @app.teardown_appcontext
    def safe_mysql_teardown(exception):
        """Versión segura del teardown que maneja correctamente errores de conexión"""
        try:
            if hasattr(g, 'mysql_db'):
                if hasattr(g.mysql_db, '_con') and g.mysql_db._con and g.mysql_db._con.open:
                    try:
                        g.mysql_db.close()
                    except MySQLdb.OperationalError as e:
                        # Ignoramos el error 2006 específicamente
                        if e.args[0] != 2006:  # Si no es el error 2006, lo registramos
                            app.logger.warning(f"Error al cerrar conexión MySQL: {e}")
                    except Exception as e:
                        app.logger.warning(f"Error desconocido al cerrar conexión MySQL: {e}")
        except Exception as e:
            app.logger.warning(f"Error general en teardown de MySQL: {e}")
    
    # Asegurarse de cerrar conexiones al finalizar
    @app.teardown_appcontext
    def close_db_connection(exception):
        db = g.pop('db', None)
        if db is not None:
            try:
                db.close()
            except Exception as e:
                app.logger.warning(f"Error al cerrar conexión de la base de datos: {e}")

def get_connection():
    """
    Obtiene una conexión a la base de datos desde el pool.
    Si ya existe una conexión en el contexto actual, la reutiliza.
    """
    if 'db' not in g:
        g.db = mysql.connection
    return g.db

def get_cursor():
    """Obtiene un cursor normal de MySQL"""
    return mysql.connection.cursor()

def get_dict_cursor():
    """Obtiene un cursor de diccionario de MySQL"""
    return mysql.connection.cursor(MySQLdb.cursors.DictCursor)

def retry_on_connection_error(max_retries=3, delay=1):
    """
    Decorador para reintentar una función si ocurre un error de conexión MySQL.
    Útil para operaciones de base de datos que pueden fallar por timeout.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (MySQLdb.OperationalError, MySQLdb.InterfaceError) as e:
                    if retries == max_retries - 1:
                        raise  # Si ya agotamos los reintentos, propagar la excepción
                    
                    logging.warning(f"Error de conexión a la base de datos: {e}. Reintentando ({retries+1}/{max_retries})...")
                    time.sleep(delay)  # Esperar antes de reintentar
                    retries += 1
        return wrapper
    return decorator

def close_connection(e=None):
    """
    Cierra la conexión a la base de datos y la devuelve al pool.
    Esta función debe ser llamada cuando finaliza una solicitud.
    """
    try:
        db = g.pop('db', None)
        if db is not None:
            if hasattr(db, '_con') and db._con and db._con.open:
                try:
                    db.close()
                except MySQLdb.OperationalError as e:
                    # Ignorar específicamente el error 2006
                    if e.args[0] != 2006:
                        print(f"Aviso: Error al cerrar la conexión a la base de datos: {e}")
                except Exception as e:
                    print(f"Aviso: Error desconocido al cerrar la conexión: {e}")
    except Exception as e:
        # Capturar y loggear el error pero no propagarlo
        print(f"Aviso: Error general al gestionar la conexión a la base de datos: {e}")
        pass 