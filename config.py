"""
Configuración de la aplicación Flask para diferentes entornos
"""
import os
from dotenv import load_dotenv
from datetime import timedelta

# Cargar variables de entorno desde el archivo .env
load_dotenv()

class Config:
    """Configuración base para todos los entornos"""
    # Configuración básica
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-por-defecto'
    DEBUG = False
    TESTING = False
    
    # Configuración de la base de datos
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'ferreteria_la_u'
    MYSQL_CURSORCLASS = 'DictCursor'
    
    # Configuración de conexiones para evitar error max_user_connections
    MYSQL_MAX_CONNECTIONS = int(os.environ.get('MYSQL_MAX_CONNECTIONS') or 20)
    MYSQL_POOL_SIZE = int(os.environ.get('MYSQL_POOL_SIZE') or 10)
    MYSQL_POOL_RECYCLE = int(os.environ.get('MYSQL_POOL_RECYCLE') or 280)
    
    # Tiempos de espera MySQL
    MYSQL_CONNECT_TIMEOUT = int(os.environ.get('MYSQL_CONNECT_TIMEOUT') or 10)
    MYSQL_READ_TIMEOUT = int(os.environ.get('MYSQL_READ_TIMEOUT') or 30)
    MYSQL_WRITE_TIMEOUT = int(os.environ.get('MYSQL_WRITE_TIMEOUT') or 30)
    
    # Opciones de conexión para MySQL
    MYSQL_OPTIONS = {
        'connect_timeout': MYSQL_CONNECT_TIMEOUT,
        'read_timeout': MYSQL_READ_TIMEOUT,
        'write_timeout': MYSQL_WRITE_TIMEOUT,
        'charset': 'utf8mb4',
        'use_unicode': True,
        'autocommit': True,
        'ssl': None  # Mantener SSL deshabilitado para desarrollo
    }
    
    # Configuración de la sesión
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    
    # Configuración de carga de archivos
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'xlsx', 'xls', 'csv', 'doc', 'docx'}
    
    # Configuración de WhatsApp
    WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL') or 'https://api.whatsapp.com/v1/'
    WHATSAPP_API_KEY = os.environ.get('WHATSAPP_API_KEY') or ''
    
    # Página principal para redirección
    INDEX_REDIRECT = 'main.index'
    
    # Configuración de correo electrónico
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Configuración de la aplicación
    APP_NAME = 'Ferretería "La U"'
    ITEMS_PER_PAGE = 10
    
    @classmethod
    def init_app(cls, app):
        """Inicialización común para todos los entornos"""
        pass

class DevelopmentConfig(Config):
    """Configuración para entorno de desarrollo"""
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    # Log de SQL para desarrollo
    SQLALCHEMY_ECHO = True
    
    # Variables específicas para desarrollo
    DEVELOPMENT = True
    WTF_CSRF_ENABLED = True
    
    # Tiempo de espera de sesión más corto en desarrollo
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Configuración de conexiones para desarrollo
    MYSQL_POOL_SIZE = 5
    MYSQL_MAX_CONNECTIONS = 10
    
    # Tiempos de espera más cortos para desarrollo
    MYSQL_CONNECT_TIMEOUT = 5
    MYSQL_READ_TIMEOUT = 15
    MYSQL_WRITE_TIMEOUT = 15
    
    # Nombre de base de datos para desarrollo
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'ferreteria_la_u'

class TestingConfig(Config):
    """Configuración para entorno de pruebas"""
    TESTING = True
    DEBUG = True
    MYSQL_DB = 'ferreteria_test'
    SECRET_KEY = 'test-secret-key'
    
    # Configuración de conexiones para pruebas
    MYSQL_POOL_SIZE = 3
    MYSQL_MAX_CONNECTIONS = 5
    
    # Deshabilitar protección CSRF para pruebas
    WTF_CSRF_ENABLED = False
    
    # Base de datos en memoria para pruebas más rápidas
    # Nota: MySQL no soporta bases de datos en memoria como SQLite
    # pero podemos usar una base de datos específica para pruebas

class ProductionConfig(Config):
    """Configuración para entorno de producción"""
    # En producción, usar variables de entorno para configuración sensible
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Asegurarse de que DEBUG está desactivado en producción
    DEBUG = False
    
    # Configuración de conexiones optimizada para producción
    MYSQL_POOL_SIZE = int(os.environ.get('MYSQL_POOL_SIZE') or 10)
    MYSQL_MAX_CONNECTIONS = int(os.environ.get('MYSQL_MAX_CONNECTIONS') or 20)
    MYSQL_POOL_RECYCLE = int(os.environ.get('MYSQL_POOL_RECYCLE') or 280)
    
    # Tiempos de espera para producción
    MYSQL_CONNECT_TIMEOUT = int(os.environ.get('MYSQL_CONNECT_TIMEOUT') or 15)
    MYSQL_READ_TIMEOUT = int(os.environ.get('MYSQL_READ_TIMEOUT') or 60)
    MYSQL_WRITE_TIMEOUT = int(os.environ.get('MYSQL_WRITE_TIMEOUT') or 60)
    
    # Configuración SSL para MySQL en producción
    MYSQL_OPTIONS = {
        'connect_timeout': MYSQL_CONNECT_TIMEOUT,
        'read_timeout': MYSQL_READ_TIMEOUT,
        'write_timeout': MYSQL_WRITE_TIMEOUT,
        'charset': 'utf8mb4',
        'use_unicode': True,
        'autocommit': True,
        'ssl': {'ca': '/etc/ssl/certs/ca-certificates.crt'}  # Certificado SSL para conexiones seguras
    }
    
    # Configuración de seguridad para producción
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # SSL/HTTPS
    SSL_REDIRECT = True
    
    # Tiempo de espera de sesión para producción
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    
    # Directorio de logs en producción
    LOG_DIR = os.path.join(os.getcwd(), 'logs')
    
    # Configuración de copias de seguridad
    BACKUP_DIR = os.path.join(os.getcwd(), 'backups')
    
    @classmethod
    def init_app(cls, app):
        """Inicializa configuraciones específicas para producción"""
        Config.init_app(app)
        
        # Configuración de logging en producción
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not os.path.exists(cls.LOG_DIR):
            os.makedirs(cls.LOG_DIR)
            
        file_handler = RotatingFileHandler(
            os.path.join(cls.LOG_DIR, 'ferreteria.log'),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Inicialización de la aplicación Ferretería en producción')
        
        # Asegurarse de que existan los directorios necesarios
        if not os.path.exists(cls.BACKUP_DIR):
            os.makedirs(cls.BACKUP_DIR)
        
        # Configurar proxy headers si la aplicación está detrás de un proxy
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)

# Configuración para desarrollo con Docker
class DockerDevConfig(DevelopmentConfig):
    """Configuración para desarrollo con Docker"""
    MYSQL_HOST = 'mysql'  # Nombre del servicio en docker-compose
    MYSQL_PORT = '3306'
    
    # Configuración para servir archivos estáticos en Docker
    PREFERRED_URL_SCHEME = 'http'
    SERVER_NAME = 'localhost:5000'

# Configuración para entorno de staging
class StagingConfig(ProductionConfig):
    """Configuración para entorno de pruebas de producción (staging)"""
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'staging-secret-key'
    
    # Usar una base de datos diferente para staging
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'ferreteria_staging'
    
    # Configuración de seguridad algo menos estricta que en producción
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Tiempo de espera de sesión intermedio
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

# Configuración por defecto
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'docker': DockerDevConfig,
    'staging': StagingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Obtiene la configuración según el entorno"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])()
