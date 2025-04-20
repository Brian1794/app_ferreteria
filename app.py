import os
from flask import Flask, render_template, redirect, url_for, flash, session, g, current_app, request
from dotenv import load_dotenv
from flask_login import current_user
from datetime import datetime
import logging
from flask_wtf.csrf import CSRFProtect

# Importar extensiones
from extensions import login_manager, bcrypt, mysql, init_extensions, get_cursor, mail

# Importar configuración
from config import get_config

# Importar blueprints
from routes.auth import auth_bp
from routes.main import main_bp
from routes.productos import productos_bp
from routes.categorias import categorias_bp
from routes.reparaciones import reparaciones_bp
from routes.whatsapp import whatsapp_bp
from routes.tienda import tienda_bp
from routes.clientes import clientes_bp
from routes.admin import admin_bp
from routes.ventas import ventas_bp
from routes.empleados import empleados_bp
from routes.carrito import carrito_bp
from routes.notificaciones import notificaciones_bp
from routes.carousel import carousel_bp
from routes.pagos_pse import pagos_pse_bp

# Importar database
import database as db
from models.models import crear_tablas, insertar_datos_iniciales, verificar_estructura_tablas, inicializar_tablas_reparaciones
from models.usuario import Usuario
import MySQLdb

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario desde la base de datos"""
    try:
        user_id = int(user_id)
        
        # Buscar primero en la tabla de clientes
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Verificar la estructura de la tabla clientes antes de consultarla
        cursor.execute("SHOW COLUMNS FROM clientes")
        columnas_clientes = {col['Field']: col for col in cursor.fetchall()}
        
        id_campo = 'id_cliente' if 'id_cliente' in columnas_clientes else 'id'
        correo_campo = 'correo' if 'correo' in columnas_clientes else 'email'
        
        # Intentar primero como cliente
        try:
            cursor.execute(f'SELECT * FROM clientes WHERE {id_campo} = %s', (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                # Es un cliente
                user = Usuario(
                    id=user_data.get(id_campo, user_data.get('id', user_id)),
                    nombre=user_data.get('nombre', 'Cliente'),
                    email=user_data.get(correo_campo, user_data.get('email', '')),
                    es_cliente=True,
                    foto_perfil=user_data.get('foto_perfil', None)
                )
                cursor.close()
                return user
        except Exception as e:
            print(f"Error al buscar cliente: {e}")
            
        # Verificar la estructura de la tabla empleados antes de consultarla
        cursor.execute("SHOW COLUMNS FROM empleados")
        columnas_empleados = {col['Field']: col for col in cursor.fetchall()}
        
        id_campo = 'id_empleado' if 'id_empleado' in columnas_empleados else 'id'
        cargo_campo = 'id_cargo' if 'id_cargo' in columnas_empleados else 'cargo_id'
        
        # Depuración de empleados
        print("=== LOAD_USER DEBUG ===")
        print(f"Columnas empleados: {list(columnas_empleados.keys())}")
        print(f"ID campo: {id_campo}")
        print(f"Cargo campo: {cargo_campo}")
        
        # Si no es cliente, intentar buscar en empleados
        try:
            # Adaptar la consulta según la estructura
            cargo_nombre = None
            cursor.execute(f"""
                SELECT e.*, c.nombre as nombre_cargo 
                FROM empleados e 
                LEFT JOIN cargos c ON e.{cargo_campo} = c.id
                WHERE e.{id_campo} = %s
            """, (user_id,))
            user_data = cursor.fetchone()
            
            print(f"Datos del empleado: {user_data}")
            
            if user_data:
                if 'nombre_cargo' in user_data and user_data['nombre_cargo']:
                    cargo_nombre = user_data['nombre_cargo']
                    print(f"Cargo del usuario encontrado: {cargo_nombre}")
                elif user_data.get(cargo_campo):
                    try:
                        cursor.execute("SELECT nombre FROM cargos WHERE id = %s", (user_data.get(cargo_campo),))
                        cargo_result = cursor.fetchone()
                        if cargo_result:
                            cargo_nombre = cargo_result['nombre']
                            print(f"Cargo obtenido por consulta adicional: {cargo_nombre}")
                    except Exception as e:
                        print(f"Error al obtener nombre de cargo: {e}")
                
                # Determinar si es admin por el campo es_admin o por el nombre del cargo
                es_admin = user_data.get('es_admin', False) or cargo_nombre == 'Administrador'
                
                # Crear usuario con los datos disponibles
                user = Usuario(
                    id=user_data.get(id_campo, user_data.get('id', user_id)),
                    nombre=f"{user_data.get('nombre', '')} {user_data.get('')}".strip(),
                    email=user_data.get('correo', user_data.get('email', user_data.get('cedula', ''))),
                    es_admin=es_admin,
                    es_cliente=False,
                    cargo_id=user_data.get(cargo_campo),
                    cargo_nombre=cargo_nombre,
                    foto_perfil=user_data.get('foto_perfil', None)
                )
                
                print(f"Usuario cargado: id={user.id}, cargo_id={user.cargo_id}, cargo_nombre={user.cargo_nombre}")
                print("=======================")
                
                cursor.close()
                return user
        except Exception as e:
            print(f"Error al buscar empleado: {e}")
            
        cursor.close()
        return None
    except Exception as e:
        print(f"Error al cargar usuario: {e}")
        return None

def register_error_handlers(app):
    """Registra manejadores de error personalizados"""
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

def init_db():
    """
    Inicializa la base de datos comprobando conexión y estructura básica
    """
    with current_app.app_context():
        try:
            # Verificar conexión
            logger.info("Verificando conexión a base de datos...")
            cursor = None
            try:
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                logger.info("Conexión a base de datos establecida correctamente")
            except Exception as e:
                logger.error(f"Error al conectar a la base de datos: {e}")
                return False
            finally:
                if cursor:
                    cursor.close()
            
            # Verificar estructura de tablas
            with mysql.connection.cursor() as cursor:
                try:
                    # Verificar tabla clientes 
                    cursor.execute("SHOW TABLES LIKE 'clientes'")
                    if not cursor.fetchone():
                        logger.warning("Tabla 'clientes' no existe. La aplicación puede necesitar inicializar la base de datos")
                    
                    # Verificar campos críticos en clientes
                    cursor.execute("DESCRIBE clientes")
                    columnas_clientes = [col[0] for col in cursor.fetchall()]
                    id_campo = 'id_cliente' if 'id_cliente' in columnas_clientes else 'id'
                    logger.info(f"Campo ID en tabla clientes: {id_campo}")
                except Exception as e:
                    logger.error(f"Error al verificar estructura de clientes: {e}")
                
                try:
                    # Verificar tabla reparaciones
                    cursor.execute("SHOW TABLES LIKE 'reparaciones'")
                    if cursor.fetchone():
                        logger.info("Tabla 'reparaciones' encontrada")
                    else:
                        logger.warning("Tabla 'reparaciones' no encontrada")
                except Exception as e:
                    logger.error(f"Error al verificar tabla reparaciones: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error en init_db: {e}")
            return False

def initialize_database():
    """Inicializa la base de datos en un contexto seguro"""
    from flask import Flask
    temp_app = Flask(__name__)
    
    # Configurar la aplicación con lo mínimo necesario para la base de datos
    config = get_config()
    temp_app.config.from_object(config)
    
    # Aplicar opciones de conexión desde la configuración
    if hasattr(config, 'MYSQL_OPTIONS') and config.MYSQL_OPTIONS:
        temp_app.config['MYSQL_OPTIONS'] = config.MYSQL_OPTIONS
    
    # Inicializar mysql
    mysql.init_app(temp_app)
    
    # Crear contexto de aplicación
    with temp_app.app_context():
        try:
            # Crear tablas si no existen
            crear_tablas()
            # Insertar datos iniciales
            insertar_datos_iniciales()
            # Verificar y actualizar estructura de tablas si es necesario
            verificar_estructura_tablas()
            # Inicializar tablas de reparaciones
            inicializar_tablas_reparaciones()
            print("Base de datos inicializada correctamente")
            return True
        except Exception as e:
            print(f"Error al inicializar la base de datos: {e}")
            return False
        finally:
            # No necesitamos cerrar manualmente la conexión aquí
            # El teardown se encargará de ello de forma segura
            pass

def create_app(config_name=None):
    """Crea y configura la aplicación Flask"""
    app = Flask(__name__)
    
    # Cargar configuración
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Asegurar que hay una SECRET_KEY
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.urandom(32)
    
    # Inicializar extensiones
    mysql.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Inicializar CSRF con configuración explícita
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # Asegurar que CSRF esté habilitado
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hora
    
    # Registrar blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(productos_bp, url_prefix='/productos')
    app.register_blueprint(categorias_bp, url_prefix='/categorias')
    app.register_blueprint(reparaciones_bp, url_prefix='/reparaciones')
    app.register_blueprint(whatsapp_bp, url_prefix='/whatsapp')
    app.register_blueprint(tienda_bp, url_prefix='/tienda')
    app.register_blueprint(clientes_bp, url_prefix='/clientes')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(ventas_bp, url_prefix='/ventas')
    app.register_blueprint(empleados_bp, url_prefix='/empleados')
    app.register_blueprint(carrito_bp, url_prefix='/carrito')
    app.register_blueprint(notificaciones_bp, url_prefix='/notificaciones')
    app.register_blueprint(carousel_bp, url_prefix='/carousel')
    app.register_blueprint(pagos_pse_bp, url_prefix='/pagos-pse')
    
    # Registrar manejadores de error
    register_error_handlers(app)
    
    # Verificar conexión a la base de datos
    with app.app_context():
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            logger.info("Conexión a la base de datos establecida correctamente")
            
            # Inicializar la base de datos
            init_db()
            
            # Verificar y crear tablas si es necesario
            crear_tablas()
            
            # Insertar datos iniciales si es necesario
            insertar_datos_iniciales()
            
            # Verificar estructura de tablas
            verificar_estructura_tablas()
            
        except Exception as e:
            logger.error(f"Error al conectar con la base de datos: {e}")
            # No levantar la excepción, permitir que la aplicación continúe
            # pero registrar el error para diagnóstico
    
    @app.before_request
    def before_request():
        """Verificar la conexión a la base de datos antes de cada solicitud"""
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception as e:
            logger.error(f"Error de conexión a la base de datos: {e}")
            if not request.endpoint or not request.endpoint.startswith('static'):
                flash("Error de conexión a la base de datos. Por favor, inténtelo más tarde.", "error")
                return redirect(url_for('main.index'))
    
    
    return app

if __name__ == '__main__':
    # Crear la base de datos primero, antes de la aplicación principal
    initialize_database()
    
    # Crear y ejecutar la aplicación
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)

# Para producción: gunicorn busca esta variable
app = create_app()

    
    

