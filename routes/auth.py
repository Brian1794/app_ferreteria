from flask import Blueprint, request, redirect, url_for, render_template, flash, current_app, session, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from models.usuario import Usuario
from extensions import bcrypt, mysql, get_cursor, mail
import functools
import datetime
import MySQLdb
import os
import uuid
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
import secrets
from datetime import datetime, timedelta
from flask_mail import Message

auth_bp = Blueprint('auth', __name__)

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_admin:
            flash('No tienes permiso para acceder a esta página', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión para clientes"""
    # Si ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        if current_user.es_cliente:
            return redirect(url_for('main.index'))
        else:
            return redirect(url_for('main.dashboard'))
    
    # Si es una petición POST (envío de formulario)
    if request.method == 'POST':
        # Obtener datos del formulario
        username = request.form.get('username')
        password = request.form.get('password')
        recordar = 'recordar' in request.form
        
        if not username or not password:
            flash('Por favor ingrese todos los campos', 'danger')
            return render_template('auth/login.html')
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Consultar en la tabla de clientes
        cursor.execute('SELECT * FROM clientes WHERE email = %s', (username,))
        usuario = cursor.fetchone()
        cursor.close()
        
        # Si el usuario existe verificar contraseña
        if usuario:
            # Verificar si la contraseña está almacenada como texto plano o como hash
            stored_password = usuario['password']
            password_es_correcta = False
            
            # Verificar primero si la contraseña es texto plano
            if stored_password == password:
                password_es_correcta = True
            # Intentar verificar como hash bcrypt si no coincide como texto plano
            elif len(stored_password) > 20:  # Los hashes bcrypt son largos
                try:
                    password_es_correcta = bcrypt.check_password_hash(stored_password, password)
                except Exception as e:
                    print(f"Error al verificar hash bcrypt: {e}")
                    # Si falla la verificación bcrypt, mantener password_es_correcta en False
            
            if password_es_correcta:
                # Crear instancia de Usuario
                user = Usuario(
                    id=usuario['id'], 
                    nombre=usuario['nombre'],
                    email=usuario['email'],
                    es_cliente=True,
                    foto_perfil=usuario.get('foto_perfil')
                )
                    
                # Registrar la sesión con Flask-Login
                login_user(user, remember=recordar)
                
                # Registrar último login
                try:
                    cursor = mysql.connection.cursor()
                    cursor.execute('UPDATE clientes SET ultimo_login = NOW() WHERE id = %s', (usuario['id'],))
                    mysql.connection.commit()
                    cursor.close()
                except Exception as e:
                    print(f"Error al actualizar último login: {e}")
                
                # Verificar si hay una URL a la que redirigir después del login
                next_page = request.args.get('next')
                if not next_page or urlparse(next_page).netloc != '':
                    next_page = url_for('main.index')
                        
                flash('¡Inicio de sesión exitoso!', 'success')
                return redirect(next_page)
        
        # Si llegamos aquí, el usuario no existe o la contraseña es incorrecta
        flash('Usuario o contraseña incorrectos', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/login-empleado', methods=['GET', 'POST'])
def login_empleado():
    """Página de inicio de sesión para empleados"""
    # Si ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        if current_user.es_cliente:
            return redirect(url_for('main.index'))
        else:
            return redirect(url_for('main.dashboard'))
    
    # Si es una petición POST (envío de formulario)
    if request.method == 'POST':
        # Obtener datos del formulario
        correo = request.form.get('username')
        password = request.form.get('password')
        recordar = 'recordar' in request.form
        
        if not correo or not password:
            flash('Por favor ingrese todos los campos', 'danger')
            return render_template('auth/login_empleado.html')
        
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Determinar la columna correcta para el correo (puede ser 'email' o 'correo')
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'email'")
            columna_email = cursor.fetchone()
            
            columna_correo = "email" if columna_email else "correo"
            
            # Consultar en la tabla de empleados con la columna correcta
            query = f'SELECT * FROM empleados WHERE {columna_correo} = %s'
            cursor.execute(query, (correo,))
            empleado = cursor.fetchone()
            
            print(f"=== LOGIN_EMPLEADO DEBUG ===")
            print(f"Usuario encontrado: {empleado is not None}")
            
            if not empleado:
                flash('Usuario o contraseña incorrectos', 'danger')
                cursor.close()
                return render_template('auth/login_empleado.html')
            
            print(f"ID de empleado: {empleado['id']}")
            print(f"Columnas del empleado: {list(empleado.keys())}")
            
            # Verificar si la cuenta está activa
            if not empleado.get('activo', True):
                flash('Esta cuenta ha sido desactivada. Contacte al administrador.', 'danger')
                cursor.close()
                return render_template('auth/login_empleado.html')
            
            # Verificar contraseña almacenada
            stored_password = empleado['password']
            password_es_correcta = False
            
            # Verificar primero si la contraseña es texto plano
            if stored_password == password:
                password_es_correcta = True
                print("Contraseña verificada como texto plano")
            # Intentar verificar como hash bcrypt si no coincide como texto plano
            elif len(stored_password) > 20:  # Los hashes bcrypt son largos
                try:
                    password_es_correcta = bcrypt.check_password_hash(stored_password, password)
                    print(f"Contraseña bcrypt verificada: {password_es_correcta}")
                except Exception as e:
                    print(f"Error al verificar hash bcrypt: {e}")
            
            if not password_es_correcta:
                flash('Usuario o contraseña incorrectos', 'danger')
                cursor.close()
                return render_template('auth/login_empleado.html')
            
            # Obtener información del cargo si existe
            cargo_id = empleado.get('cargo_id')
            print(f"Cargo ID inicial: {cargo_id}")
            
            # Si no hay cargo_id, intentar con id_cargo que es otro nombre común
            if cargo_id is None and 'id_cargo' in empleado:
                cargo_id = empleado.get('id_cargo')
                print(f"Cargo ID obtenido de id_cargo: {cargo_id}")
            
            cargo_nombre = None
            
            if cargo_id:
                cursor.execute('SELECT id, nombre FROM cargos WHERE id = %s', (cargo_id,))
                cargo = cursor.fetchone()
                print(f"Información de cargo: {cargo}")
                
                if cargo:
                    cargo_nombre = cargo['nombre']
                    print(f"Nombre de cargo: {cargo_nombre}")
            
            # Crear instancia de Usuario con información de cargo
            user = Usuario(
                id=empleado['id'],
                nombre=f"{empleado.get('nombre', '')} {empleado.get('apellido', '')}".strip(),
                email=empleado.get(columna_correo, ''),
                es_admin=empleado.get('es_admin', False),
                es_cliente=False,
                cargo_id=cargo_id,
                cargo_nombre=cargo_nombre,
                foto_perfil=empleado.get('foto_perfil')
            )
            
            print(f"Usuario creado: id={user.id}, cargo_id={user.cargo_id}, cargo_nombre={user.cargo_nombre}")
            print("========================")
            
            # Registrar la sesión con Flask-Login
            login_user(user, remember=recordar)
            
            # Registrar último login
            try:
                cursor.execute('UPDATE empleados SET ultimo_login = NOW() WHERE id = %s', (empleado['id'],))
                mysql.connection.commit()
            except Exception as e:
                print(f"Error al actualizar último login: {e}")
            
            # Verificar si hay una URL a la que redirigir después del login
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                # Redirigir según el cargo
                if empleado.get('es_admin', False):
                    next_page = url_for('admin.index')
                elif cargo_nombre == 'Técnico':
                    # Para técnicos: verificar nuevamente el cargo
                    print(f"Redirigiendo a técnico. Cargo: {cargo_nombre}")
                    # Actualizar el objeto de usuario para asegurar que tenga el cargo correcto
                    user.cargo_id = cargo_id
                    user.cargo_nombre = cargo_nombre
                    # Redirigir a la vista de reparaciones
                    next_page = url_for('reparaciones.por_tecnico')
                elif cargo_nombre == 'Vendedor':
                    next_page = url_for('ventas.nueva')
                else:
                    next_page = url_for('main.dashboard')
            
            flash('¡Inicio de sesión exitoso!', 'success')
            cursor.close()
            return redirect(next_page)
                
        except Exception as e:
            print(f"Error en inicio de sesión de empleado: {e}")
            flash('Error en el servidor. Por favor, inténtelo de nuevo más tarde.', 'danger')
            # Asegurarse de cerrar el cursor si ocurre un error
            try:
                cursor.close()
            except:
                pass
    
    return render_template('auth/login_empleado.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión de usuario"""
    # Cerrar sesión en Flask-Login
    logout_user()
    
    # Limpiar todas las variables de sesión
    session.clear()
    
    # Mensaje de éxito
    flash('Has cerrado sesión correctamente.', 'success')
    
    # Redireccionar al inicio con una URL absoluta para forzar la recarga completa
    response = redirect(url_for('main.index', _external=True, _timestamp=datetime.now().timestamp()))
    
    # Añadir encabezados para evitar caché
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Invalidar y eliminar cookies de sesión
    session_cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    response.delete_cookie(session_cookie_name, path='/', domain=None)
    response.delete_cookie('remember_token', path='/', domain=None)
    
    return response

@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Registro de nuevos clientes"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        confirmar_password = request.form.get('confirmar_password')
        
        # Validaciones básicas
        if not nombre or not email or not password:
            flash('Por favor completa todos los campos requeridos.', 'danger')
            return render_template('auth/registro.html')
            
        if password != confirmar_password:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('auth/registro.html')
        
        try:
            # Conectar a la base de datos y obtener un cursor
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Verificar la estructura de la tabla clientes
            cursor.execute("DESCRIBE clientes")
            columns = cursor.fetchall()
            column_names = [column["Field"] for column in columns]
            print("Columnas en la tabla clientes:", column_names)
            
            # Determinar el nombre correcto de la columna ID
            id_column_name = "id"
            for col in column_names:
                if col.lower() in ["id", "id_cliente"]:
                    id_column_name = col
                    break
            print(f"Usando columna ID: {id_column_name}")
            
            # Verificar si el email ya está registrado
            cursor.execute(f"SELECT {id_column_name} FROM clientes WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash('El correo electrónico ya está registrado.', 'danger')
                cursor.close()
                return render_template('auth/registro.html')
                
            # Para mantener consistencia con las contraseñas existentes, guardamos en texto plano
            # Nota: En un entorno de producción real, SIEMPRE usar bcrypt u otro método seguro
            # hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            hashed_password = password  # Almacenar como texto plano temporalmente
            
            # Insertar cliente con las columnas correctas
            try:
                query = f"INSERT INTO clientes (nombre, email, password) VALUES (%s, %s, %s)"
                cursor.execute(query, (nombre, email, hashed_password))
                mysql.connection.commit()
                
                # Verificar si se insertó correctamente
                if cursor.rowcount > 0:
                    # Asignar rol de cliente por defecto (rol_id = 2 para clientes comunes)
                    nuevo_id = cursor.lastrowid
                    try:
                        # Verificar si existe la tabla cliente_rol
                        cursor.execute("SHOW TABLES LIKE 'cliente_rol'")
                        if cursor.fetchone():
                            # Verificar si existe el rol de cliente
                            cursor.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'Cliente'")
                            rol = cursor.fetchone()
                            if rol:
                                rol_id = rol['id_rol']
                                # Determinar el nombre correcto de la columna de cliente en la tabla cliente_rol
                                cursor.execute("DESCRIBE cliente_rol")
                                cliente_rol_columns = [col["Field"] for col in cursor.fetchall()]
                                cliente_id_column = "id_cliente"
                                for col in cliente_rol_columns:
                                    if col.lower() in ["id_cliente", "cliente_id"]:
                                        cliente_id_column = col
                                        break
                                
                                # Asignar el rol al cliente
                                cursor.execute(
                                    f"INSERT INTO cliente_rol ({cliente_id_column}, id_rol) VALUES (%s, %s)",
                                    (nuevo_id, rol_id)
                                )
                                mysql.connection.commit()
                        else:
                            print("La tabla cliente_rol no existe")
                    except Exception as e:
                        print(f"Advertencia: No se pudo asignar rol al cliente: {e}")
                    
                    flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
                    cursor.close()
                    return redirect(url_for('auth.login'))
                else:
                    flash('No se pudo completar el registro. Intenta nuevamente.', 'danger')
            except Exception as e:
                mysql.connection.rollback()
                error_message = str(e)
                print(f"Error al insertar nuevo cliente: {error_message}")
                flash(f'Error al registrar: {error_message}', 'danger')
            
            cursor.close()
        except Exception as e:
            error_message = str(e)
            print(f"Error general en registro: {error_message}")
            flash(f'Error de conexión: {error_message}', 'danger')
            
    return render_template('auth/registro.html')

@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    """Permite cambiar la contraseña del usuario actual"""
    if request.method == 'POST':
        password_actual = request.form.get('password_actual')
        password_nuevo = request.form.get('password_nuevo')
        confirmar_password = request.form.get('confirmar_password')
        
        # Validaciones básicas
        if not all([password_actual, password_nuevo, confirmar_password]):
            flash('Todos los campos son obligatorios', 'warning')
            return redirect(url_for('auth.cambiar_password'))
            
        if password_nuevo != confirmar_password:
            flash('Las contraseñas nuevas no coinciden', 'warning')
            return redirect(url_for('auth.cambiar_password'))
        
        cursor = None
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            print(f"Cambiando contraseña para usuario ID: {current_user.id}, tipo: {'cliente' if current_user.es_cliente else 'empleado'}")
            
            if current_user.es_cliente:
                # ===== PARA CLIENTES =====
                print("Procesando cambio de contraseña para CLIENTE")
                # 1. Obtener estructura de la tabla clientes
                cursor.execute("DESCRIBE clientes")
                columns = cursor.fetchall()
                column_names = [col['Field'] for col in columns]
                print(f"Columnas en tabla clientes: {column_names}")
                
                # 2. Determinar nombre de columna ID
                id_column_name = 'id'  # Valor por defecto
                for col in column_names:
                    if col.lower() in ['id', 'id_cliente']:
                        id_column_name = col
                        break
                print(f"Usando columna ID para clientes: '{id_column_name}'")
                
                # 3. Determinar nombre de columna password
                pwd_column_name = 'password'  # Valor por defecto
                for col in column_names:
                    if col.lower() in ['password', 'contrasena', 'clave']:
                        pwd_column_name = col
                        break
                print(f"Usando columna contraseña: '{pwd_column_name}'")
                
                # 4. Verificar existencia del usuario y obtener contraseña actual
                query = f"SELECT * FROM clientes WHERE {id_column_name} = %s"
                print(f"Ejecutando consulta: {query} con ID: {current_user.id}")
                cursor.execute(query, (current_user.id,))
                user_data = cursor.fetchone()
                
                if not user_data:
                    print(f"No se encontró cliente con ID {current_user.id}")
                    flash('No se pudo verificar la cuenta', 'danger')
                    return redirect(url_for('auth.cambiar_password'))
                
                print(f"Cliente encontrado: {user_data[id_column_name]}")
                
                # 5. Verificar formato de contraseña y comprobar
                stored_password = user_data.get(pwd_column_name)
                print(f"Contraseña almacenada (primeros 5 chars): {stored_password[:5] if stored_password and len(stored_password) > 5 else 'N/A'}")
                
                password_matched = False
                # Verificar si es texto plano
                if stored_password == password_actual:
                    print("Contraseña coincide como texto plano")
                    password_matched = True
                # Verificar como hash bcrypt
                elif stored_password and len(stored_password) > 20:
                    try:
                        password_matched = bcrypt.check_password_hash(stored_password, password_actual)
                        print(f"Verificación bcrypt: {password_matched}")
                    except Exception as e:
                        print(f"Error al verificar hash bcrypt: {e}")
                
                if not password_matched:
                    flash('La contraseña actual es incorrecta', 'danger')
                    return redirect(url_for('auth.cambiar_password'))
                
                # 6. Actualizar la contraseña
                hashed_password = bcrypt.generate_password_hash(password_nuevo).decode('utf-8')
                update_query = f"UPDATE clientes SET {pwd_column_name} = %s WHERE {id_column_name} = %s"
                print(f"Actualizando contraseña, query: {update_query}")
                cursor.execute(update_query, (hashed_password, current_user.id))
                mysql.connection.commit()
                print("Contraseña actualizada con éxito para cliente")
                
            else:
                # ===== PARA EMPLEADOS =====
                print("Procesando cambio de contraseña para EMPLEADO")
                # 1. Obtener estructura de la tabla empleados
                cursor.execute("DESCRIBE empleados")
                columns = cursor.fetchall()
                column_names = [col['Field'] for col in columns]
                print(f"Columnas en tabla empleados: {column_names}")
                
                # 2. Determinar nombre de columna ID
                id_column_name = 'id'  # Valor por defecto
                for col in column_names:
                    if col.lower() in ['id', 'id_empleado']:
                        id_column_name = col
                        break
                print(f"Usando columna ID para empleados: '{id_column_name}'")
                
                # 3. Determinar nombre de columna password
                pwd_column_name = 'password'  # Valor por defecto
                for col in column_names:
                    if col.lower() in ['password', 'contrasena', 'clave']:
                        pwd_column_name = col
                        break
                print(f"Usando columna contraseña: '{pwd_column_name}'")
                
                # 4. Verificar existencia del usuario y obtener contraseña actual
                query = f"SELECT * FROM empleados WHERE {id_column_name} = %s"
                print(f"Ejecutando consulta: {query} con ID: {current_user.id}")
                cursor.execute(query, (current_user.id,))
                user_data = cursor.fetchone()
                
                if not user_data:
                    print(f"No se encontró empleado con ID {current_user.id}")
                    flash('No se pudo verificar la cuenta', 'danger')
                    return redirect(url_for('auth.cambiar_password'))
                
                print(f"Empleado encontrado: {user_data[id_column_name]}")
                
                # 5. Verificar formato de contraseña y comprobar
                stored_password = user_data.get(pwd_column_name)
                print(f"Contraseña almacenada (primeros 5 chars): {stored_password[:5] if stored_password and len(stored_password) > 5 else 'N/A'}")
                
                password_matched = False
                # Verificar si es texto plano
                if stored_password == password_actual:
                    print("Contraseña coincide como texto plano")
                    password_matched = True
                # Verificar como hash bcrypt
                elif stored_password and len(stored_password) > 20:
                    try:
                        password_matched = bcrypt.check_password_hash(stored_password, password_actual)
                        print(f"Verificación bcrypt: {password_matched}")
                    except Exception as e:
                        print(f"Error al verificar hash bcrypt: {e}")
                
                if not password_matched:
                    flash('La contraseña actual es incorrecta', 'danger')
                    return redirect(url_for('auth.cambiar_password'))
                
                # 6. Actualizar la contraseña
                hashed_password = bcrypt.generate_password_hash(password_nuevo).decode('utf-8')
                update_query = f"UPDATE empleados SET {pwd_column_name} = %s WHERE {id_column_name} = %s"
                print(f"Actualizando contraseña, query: {update_query}")
                cursor.execute(update_query, (hashed_password, current_user.id))
                mysql.connection.commit()
                print("Contraseña actualizada con éxito para empleado")
            
            flash('Contraseña actualizada con éxito', 'success')
            
        except Exception as e:
            print(f"ERROR COMPLETO AL CAMBIAR CONTRASEÑA: {e}")
            import traceback
            traceback.print_exc()
            flash('Error al procesar la solicitud', 'danger')
            return redirect(url_for('auth.cambiar_password'))
        finally:
            if cursor:
                cursor.close()
    
    return render_template('auth/cambiar_password.html')

@auth_bp.route('/recuperar-password', methods=['GET', 'POST'])
def recuperar_password():
    """Permite al usuario solicitar la recuperación de su contraseña"""
    # Si el usuario está autenticado, redirigir a la página principal
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        # Validar formato de correo básico
        if not email or '@' not in email or '.' not in email:
            flash('Por favor, introduce un correo electrónico válido.', 'danger')
            return render_template('auth/recuperar_password.html')
            
        try:
            current_app.logger.info(f"Iniciando proceso de recuperación para: {email}")
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Buscar en tabla clientes
            # Primero verificamos si la columna es 'correo' o 'email'
            try:
                cursor.execute("SHOW COLUMNS FROM clientes LIKE 'correo'")
                tiene_correo = cursor.fetchone()
                current_app.logger.info(f"Tabla clientes tiene columna 'correo': {tiene_correo is not None}")
                
                if tiene_correo:
                    cursor.execute("SELECT id as id, nombre, 'cliente' as tipo FROM clientes WHERE correo = %s", (email,))
                else:
                    cursor.execute("SELECT id as id, nombre, 'cliente' as tipo FROM clientes WHERE email = %s", (email,))
                    
                usuario = cursor.fetchone()
                current_app.logger.info(f"Usuario encontrado en clientes: {usuario is not None}")
            except Exception as e:
                current_app.logger.error(f"Error buscando en tabla clientes: {str(e)}")
                usuario = None
            
            # Si no se encuentra, buscar en empleados
            if not usuario:
                try:
                    # Verificamos si la columna es 'correo' o 'email'
                    cursor.execute("SHOW COLUMNS FROM empleados LIKE 'correo'")
                    tiene_correo = cursor.fetchone()
                    current_app.logger.info(f"Tabla empleados tiene columna 'correo': {tiene_correo is not None}")
                    
                    if tiene_correo:
                        cursor.execute("SELECT id as id, CONCAT(nombre, ' ', apellido) as nombre, 'empleado' as tipo FROM empleados WHERE correo = %s", (email,))
                    else:
                        cursor.execute("SELECT id as id, CONCAT(nombre, ' ', apellido) as nombre, 'empleado' as tipo FROM empleados WHERE email = %s", (email,))
                        
                    usuario = cursor.fetchone()
                    current_app.logger.info(f"Usuario encontrado en empleados: {usuario is not None}")
                except Exception as e:
                    current_app.logger.error(f"Error buscando en tabla empleados: {str(e)}")
                    usuario = None
            
            if not usuario:
                # Informamos al cliente que no se encontró el correo
                flash('El correo electrónico no está registrado en nuestro sistema.', 'danger')
                return render_template('auth/recuperar_password.html')
                
            # Generar token único con mecanismo seguro
            token = secrets.token_urlsafe(48)  # Token más largo para mayor seguridad
            expiration = datetime.now() + timedelta(hours=24)  # Extendemos a 24 horas en lugar de 1 hora
            current_app.logger.info(f"Token generado para usuario: {usuario['id']} tipo: {usuario['tipo']}")
            
            # Primero eliminar tokens antiguos para el mismo usuario para mayor seguridad
            try:
                cursor.execute("DELETE FROM reset_tokens WHERE user_id = %s AND user_type = %s", 
                              (usuario['id'], usuario['tipo']))
                mysql.connection.commit()
                current_app.logger.info(f"Tokens antiguos eliminados para el usuario: {usuario['id']}")
            except Exception as e:
                current_app.logger.warning(f"No se pudieron eliminar tokens antiguos: {str(e)}")
                # Continuar con el proceso aunque falle esta parte
            
            # Crear tabla para tokens de recuperación si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reset_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    token VARCHAR(255) NOT NULL,
                    user_id INT NOT NULL,
                    user_type VARCHAR(20) NOT NULL,
                    expiration DATETIME NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_token (token),
                    INDEX idx_user (user_id, user_type)
                )
            """)
            mysql.connection.commit()
            current_app.logger.info("Tabla reset_tokens verificada")
            
            # Verificar que todas las columnas necesarias existen
            try:
                # Obtener todas las columnas en la tabla
                cursor.execute("SHOW COLUMNS FROM reset_tokens")
                columnas = cursor.fetchall()
                columnas_actuales = [col['Field'] for col in columnas]
                current_app.logger.info(f"Columnas actuales en reset_tokens: {columnas_actuales}")
                
                # Verificar y añadir columnas faltantes
                columnas_requeridas = {
                    'id': 'INT AUTO_INCREMENT PRIMARY KEY',
                    'token': 'VARCHAR(255) NOT NULL',
                    'user_id': 'INT NOT NULL',
                    'user_type': 'VARCHAR(20) NOT NULL',
                    'expiration': 'DATETIME NOT NULL',
                    'used': 'BOOLEAN DEFAULT FALSE',
                    'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                }
                
                # Si estamos en una sesión de alter table, terminarla
                cursor.execute("COMMIT")
                
                for columna, tipo in columnas_requeridas.items():
                    if columna not in columnas_actuales and columna != 'id': # id ya existe como PK
                        current_app.logger.info(f"Añadiendo columna '{columna}' a la tabla reset_tokens")
                        try:
                            cursor.execute(f"ALTER TABLE reset_tokens ADD COLUMN {columna} {tipo}")
                            mysql.connection.commit()
                        except Exception as e:
                            current_app.logger.error(f"Error al añadir columna {columna}: {str(e)}")
            except Exception as e:
                current_app.logger.error(f"Error al verificar estructura de reset_tokens: {str(e)}")
            
            # Guardar token en la base de datos
            try:
                cursor.execute(
                    "INSERT INTO reset_tokens (token, user_id, user_type, expiration) VALUES (%s, %s, %s, %s)",
                    (token, usuario['id'], usuario['tipo'], expiration)
                )
                mysql.connection.commit()
                current_app.logger.info(f"Token guardado con éxito para: {usuario['id']}")
            except Exception as e:
                error_str = str(e)
                current_app.logger.error(f"Error guardando token: {error_str}")
                
                # Si el error es por columna inexistente, intentar recrear la tabla
                if "Unknown column 'expiration'" in error_str:
                    try:
                        current_app.logger.info("Intentando recrear la tabla reset_tokens desde cero")
                        cursor.execute("DROP TABLE IF EXISTS reset_tokens")
                        cursor.execute("""
                            CREATE TABLE reset_tokens (
                                id INT AUTO_INCREMENT PRIMARY KEY,
                                token VARCHAR(255) NOT NULL,
                                user_id INT NOT NULL,
                                user_type VARCHAR(20) NOT NULL,
                                expiration DATETIME NOT NULL,
                                used BOOLEAN DEFAULT FALSE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        mysql.connection.commit()
                        
                        # Intentar insertar nuevamente
                        cursor.execute(
                            "INSERT INTO reset_tokens (token, user_id, user_type, expiration) VALUES (%s, %s, %s, %s)",
                            (token, usuario['id'], usuario['tipo'], expiration)
                        )
                        mysql.connection.commit()
                        current_app.logger.info("Tabla recreada e inserción exitosa")
                    except Exception as e2:
                        current_app.logger.error(f"Error al recrear tabla: {str(e2)}")
                        flash('Error técnico. Por favor, contacta al administrador.', 'danger')
                        return render_template('auth/recuperar_password.html')
                else:
                    flash('Error técnico. Por favor, contacta al administrador.', 'danger')
                    return render_template('auth/recuperar_password.html')
            
            # Construir URL de recuperación
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            # Obtener información de la empresa desde variables de entorno
            empresa_nombre = os.environ.get('EMPRESA_NOMBRE', 'Ferretería y Cacharrería la U')
            empresa_direccion = os.environ.get('EMPRESA_DIRECCION', 'Cra. 69C # 7A-14, Bogotá D.C.')
            empresa_telefono = os.environ.get('EMPRESA_TELEFONO', '310 320 0632')
            empresa_email = os.environ.get('EMPRESA_EMAIL', 'michael.alfonso.rodri@gmail.com')
            empresa_whatsapp = os.environ.get('EMPRESA_WHATSAPP', '3103200632')
            
            # Construir mensaje de correo
            subject = f"Recuperación de contraseña - {empresa_nombre}"
            
            # Plantilla de texto plano
            body_text = f"""
Hola {usuario['nombre']},

Has solicitado restablecer tu contraseña en {empresa_nombre}.

Para establecer una nueva contraseña, haz clic en el siguiente enlace:
{reset_url}

Este enlace expirará en 1 hora por razones de seguridad.

Si no solicitaste este cambio, puedes ignorar este correo.

Atentamente,
El equipo de {empresa_nombre}

--
Contacto:
Dirección: {empresa_direccion}
Teléfono: {empresa_telefono}
WhatsApp: {empresa_whatsapp}
Email: {empresa_email}
"""
            
            # Plantilla HTML con mejor diseño
            body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recuperación de Contraseña</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 0; }}
        .header {{ background-color: #f39c12; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .button {{ display: inline-block; background-color: #f39c12; color: white; text-decoration: none; padding: 12px 24px; border-radius: 4px; margin: 20px 0; font-weight: bold; }}
        .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; background-color: #f2f2f2; padding: 15px; }}
        .contact-info {{ background-color: #fff; border-radius: 4px; padding: 15px; margin-top: 20px; }}
        .social-links {{ text-align: center; margin: 15px 0; }}
        .social-links a {{ margin: 0 10px; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Recuperación de Contraseña</h1>
        </div>
        <div class="content">
            <p>Hola <strong>{usuario['nombre']}</strong>,</p>
            <p>Has solicitado restablecer tu contraseña en {empresa_nombre}.</p>
            <p>Para establecer una nueva contraseña, haz clic en el siguiente botón:</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="button">Restablecer Contraseña</a>
            </p>
            <p>O puedes copiar y pegar este enlace en tu navegador:</p>
            <p style="word-break: break-all; background-color: #eee; padding: 10px; border-radius: 4px; font-size: 14px;">{reset_url}</p>
            <p>Este enlace expirará en <strong>1 hora</strong> por razones de seguridad.</p>
            <p>Si no solicitaste este cambio, puedes ignorar este correo.</p>
            
            <div class="contact-info">
                <h3 style="margin-top: 0; color: #f39c12;">Información de Contacto</h3>
                <p><strong>Dirección:</strong> {empresa_direccion}</p>
                <p><strong>Teléfono:</strong> {empresa_telefono}</p>
                <p><strong>WhatsApp:</strong> {empresa_whatsapp}</p>
                <p><strong>Email:</strong> {empresa_email}</p>
                
                <div class="social-links">
                    <a href="https://wa.me/57{empresa_whatsapp}" style="color: #25D366;">
                        <strong>WhatsApp</strong>
                    </a>
                    <a href="mailto:{empresa_email}" style="color: #D44638;">
                        <strong>Correo</strong>
                    </a>
                </div>
            </div>
        </div>
        <div class="footer">
            <p>Este es un correo automático, por favor no respondas a este mensaje.</p>
            <p>&copy; {datetime.now().year} {empresa_nombre} - Todos los derechos reservados</p>
        </div>
    </div>
</body>
</html>
"""
            
            try:
                # Crear mensaje con formato HTML
                msg = Message(
                    subject,
                    recipients=[email],
                    body=body_text,
                    html=body_html
                )
                
                # Enviar correo
                current_app.logger.info(f"Enviando correo de recuperación a {email}")
                mail.send(msg)
                current_app.logger.info(f"Correo enviado exitosamente a {email}")
                
                # En caso de entorno de desarrollo, mostrar el enlace en los logs
                if current_app.config.get('DEBUG', False):
                    current_app.logger.info(f"[DEBUG] URL de recuperación: {reset_url}")
                
                flash('Se han enviado instrucciones de recuperación a tu correo electrónico. Por favor revisa tu bandeja de entrada.', 'success')
                
                # Registrar la actividad en la base de datos si existe la tabla
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS password_reset_logs (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id INT NOT NULL,
                            user_type VARCHAR(20) NOT NULL,
                            email VARCHAR(255) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            ip_address VARCHAR(50),
                            user_agent VARCHAR(255)
                        )
                    """)
                    mysql.connection.commit()
                    
                    # Obtener IP y user agent
                    ip = request.remote_addr
                    user_agent = request.user_agent.string if request.user_agent else 'Unknown'
                    
                    # Truncar user agent si es muy largo
                    if user_agent and len(user_agent) > 255:
                        user_agent = user_agent[:252] + '...'
                    
                    # Registrar en logs
                    cursor.execute(
                        "INSERT INTO password_reset_logs (user_id, user_type, email, ip_address, user_agent) VALUES (%s, %s, %s, %s, %s)",
                        (usuario['id'], usuario['tipo'], email, ip, user_agent)
                    )
                    mysql.connection.commit()
                except Exception as log_error:
                    current_app.logger.error(f"Error al registrar log de recuperación: {str(log_error)}")
                    # No afecta la experiencia del usuario, continuamos
                
            except Exception as e:
                current_app.logger.error(f"Error al enviar correo: {str(e)}")
                
                # Intentar con un método alternativo para entornos de desarrollo
                if current_app.config.get('DEBUG', False) or not current_app.config.get('MAIL_SERVER'):
                    current_app.logger.info(f"[Alternativa para desarrollo] URL de recuperación: {reset_url}")
                    flash(f'Modo de desarrollo: Usa este enlace para restablecer tu contraseña: <a href="{reset_url}" target="_blank">Click aquí</a>', 'info')
                    return render_template('auth/recuperar_password.html')
                
                # Mensaje genérico para el usuario en producción
                flash('Ocurrió un problema al enviar el correo. Por favor, inténtalo de nuevo más tarde o contacta a soporte técnico.', 'warning')
                
            return redirect(url_for('auth.login'))
                
        except Exception as e:
            current_app.logger.error(f"Error en recuperación de contraseña: {str(e)}")
            flash('Ocurrió un error en el proceso. Por favor, inténtalo de nuevo más tarde.', 'danger')
            
        finally:
            cursor.close()
            
    return render_template('auth/recuperar_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Procesa el token y permite al usuario establecer una nueva contraseña"""
    # Si el usuario está autenticado, redirigir a la página principal
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Verificar que el token sea válido
    try:
        # Validar el formato básico del token
        if not token or len(token) < 40:  # Los tokens son largos
            flash('El enlace para restablecer tu contraseña es inválido.', 'danger')
            return redirect(url_for('auth.recuperar_password'))
            
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Buscar el token en la base de datos
        cursor.execute("""
            SELECT reset_tokens.* 
            FROM reset_tokens
            WHERE token = %s AND used = FALSE AND expiration > NOW()
        """, (token,))
        
        token_data = cursor.fetchone()
        
        if not token_data:
            # Verificar si existe pero ya fue usado
            cursor.execute("""
                SELECT used, expiration FROM reset_tokens 
                WHERE token = %s
            """, (token,))
            token_status = cursor.fetchone()
            
            if token_status:
                if token_status['used']:
                    flash('Este enlace ya ha sido utilizado. Por motivos de seguridad, cada enlace de recuperación solo puede usarse una vez.', 'warning')
                elif token_status['expiration'] < datetime.now():
                    flash('Este enlace ha expirado. Por favor, solicita uno nuevo.', 'warning')
                else:
                    flash('El enlace no es válido.', 'danger')
            else:
                flash('El enlace para restablecer tu contraseña es inválido o ha expirado.', 'danger')
                
            return redirect(url_for('auth.recuperar_password'))
            
        # Obtener el correo electrónico del usuario según su tipo
        if token_data['user_type'] == 'cliente':
            # Verificar si la columna es 'correo' o 'email'
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'correo'")
            tiene_correo = cursor.fetchone()
            
            if tiene_correo:
                cursor.execute("SELECT correo as email, nombre FROM clientes WHERE id = %s", (token_data['user_id'],))
            else:
                cursor.execute("SELECT email, nombre FROM clientes WHERE id = %s", (token_data['user_id'],))
        else:
            # Verificar si la columna es 'correo' o 'email'
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'correo'")
            tiene_correo = cursor.fetchone()
            
            if tiene_correo:
                cursor.execute("SELECT correo as email, nombre, apellido FROM empleados WHERE id = %s", (token_data['user_id'],))
            else:
                cursor.execute("SELECT email, nombre, apellido FROM empleados WHERE id = %s", (token_data['user_id'],))
                
        user_data = cursor.fetchone()
        if not user_data:
            flash('No se pudo encontrar la información de usuario. Por favor, solicita un nuevo enlace.', 'danger')
            return redirect(url_for('auth.recuperar_password'))
            
        # Actualizar los datos del token con la información del usuario
        token_data['email'] = user_data['email']
        token_data['nombre_completo'] = user_data.get('nombre', '') + (' ' + user_data.get('apellido', '') if 'apellido' in user_data else '')
        
        if request.method == 'POST':
            # Obtener los datos del formulario
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            # Validar la contraseña de forma más rigurosa
            if not password:
                flash('La contraseña es obligatoria.', 'danger')
                return render_template('auth/reset_password.html', token=token)
                
            if len(password) < 6:
                flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
                return render_template('auth/reset_password.html', token=token)
                
            if not any(c.isupper() for c in password):
                flash('La contraseña debe incluir al menos una letra mayúscula.', 'danger')
                return render_template('auth/reset_password.html', token=token)
                
            if not any(c.islower() for c in password):
                flash('La contraseña debe incluir al menos una letra minúscula.', 'danger')
                return render_template('auth/reset_password.html', token=token)
                
            if not any(c.isdigit() for c in password):
                flash('La contraseña debe incluir al menos un número.', 'danger')
                return render_template('auth/reset_password.html', token=token)
                
            if password != confirm_password:
                flash('Las contraseñas no coinciden.', 'danger')
                return render_template('auth/reset_password.html', token=token)
            
            # Encriptar la nueva contraseña
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            
            # Actualizar la contraseña según el tipo de usuario
            if token_data['user_type'] == 'cliente':
                cursor.execute(
                    "UPDATE clientes SET password = %s WHERE id = %s",
                    (hashed_password, token_data['user_id'])
                )
            else:  # Empleado
                cursor.execute(
                    "UPDATE empleados SET password = %s WHERE id = %s",
                    (hashed_password, token_data['user_id'])
                )
            
            # Marcar el token como usado
            cursor.execute(
                "UPDATE reset_tokens SET used = TRUE WHERE id = %s",
                (token_data['id'],)
            )
            
            # Registrar el cambio de contraseña en los logs
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS password_change_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        user_type VARCHAR(20) NOT NULL,
                        token_id INT,
                        ip_address VARCHAR(50),
                        user_agent VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                mysql.connection.commit()
                
                # Obtener IP y user agent
                ip = request.remote_addr
                user_agent = request.user_agent.string if request.user_agent else 'Unknown'
                
                # Truncar user agent si es muy largo
                if user_agent and len(user_agent) > 255:
                    user_agent = user_agent[:252] + '...'
                
                cursor.execute(
                    "INSERT INTO password_change_logs (user_id, user_type, token_id, ip_address, user_agent) VALUES (%s, %s, %s, %s, %s)",
                    (token_data['user_id'], token_data['user_type'], token_data['id'], ip, user_agent)
                )
            except Exception as e:
                current_app.logger.error(f"Error al registrar cambio de contraseña: {str(e)}")
                # No afecta la experiencia del usuario, continuamos
            
            mysql.connection.commit()
            
            # Cerrar todas las sesiones activas del usuario (opcional)
            try:
                if token_data['user_type'] == 'cliente':
                    cursor.execute("UPDATE clientes SET session_token = NULL WHERE id = %s", (token_data['user_id'],))
                else:
                    cursor.execute("UPDATE empleados SET session_token = NULL WHERE id = %s", (token_data['user_id'],))
                mysql.connection.commit()
            except Exception as e:
                current_app.logger.warning(f"No se pudieron cerrar sesiones activas: {str(e)}")
                # Esto es opcional, no afecta la experiencia principal
            
            flash('¡Tu contraseña ha sido actualizada correctamente! Ya puedes iniciar sesión con tu nueva contraseña.', 'success')
            return redirect(url_for('auth.login'))
        
        # Mostrar página de restablecimiento de contraseña con los datos del token
        return render_template('auth/reset_password.html', token=token, email=token_data.get('email'))
        
    except Exception as e:
        current_app.logger.error(f"Error en restablecimiento de contraseña: {str(e)}")
        flash('Ocurrió un error en el proceso. Por favor, inténtalo de nuevo más tarde.', 'danger')
        return redirect(url_for('auth.recuperar_password'))
    
    finally:
        if 'cursor' in locals() and cursor is not None:
            cursor.close()

@auth_bp.route('/actualizar-foto-perfil', methods=['POST'])
@login_required
def actualizar_foto_perfil():
    """Actualizar la foto de perfil del usuario"""
    if 'foto' not in request.files:
        flash('No se seleccionó ningún archivo', 'warning')
        return redirect(url_for('main.index'))
        
    foto = request.files['foto']
    
    if foto.filename == '':
        flash('No se seleccionó ningún archivo', 'warning')
        return redirect(url_for('main.index'))
    
    if foto:
        # Verificar extensión del archivo
        extensiones_permitidas = {'png', 'jpg', 'jpeg', 'gif'}
        extension = foto.filename.rsplit('.', 1)[1].lower() if '.' in foto.filename else ''
        
        if extension not in extensiones_permitidas:
            flash('Formato de archivo no permitido. Use PNG, JPG, JPEG o GIF.', 'danger')
            return redirect(url_for('main.index'))
        
        # Crear nombre de archivo único
        nombre_seguro = secure_filename(foto.filename)
        nombre_archivo = f"{uuid.uuid4().hex}_{nombre_seguro}"
        
        # Asegurarse de que exista el directorio
        directorio_perfiles = os.path.join(current_app.static_folder, 'uploads/perfiles')
        os.makedirs(directorio_perfiles, exist_ok=True)
        
        # Ruta completa del archivo
        ruta_archivo = os.path.join(directorio_perfiles, nombre_archivo)
        
        try:
            # Guardar el archivo
            foto.save(ruta_archivo)
            
            # Actualizar la base de datos según el tipo de usuario
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            try:
                # Eliminar foto anterior si existe
                foto_anterior = None
                
                if current_user.es_cliente:
                    # Verificar si existe la columna foto_perfil en la tabla clientes
                    cursor.execute("SHOW COLUMNS FROM clientes LIKE 'foto_perfil'")
                    tiene_foto_perfil = cursor.fetchone()
                    
                    if not tiene_foto_perfil:
                        cursor.execute("ALTER TABLE clientes ADD COLUMN foto_perfil VARCHAR(255) DEFAULT NULL")
                        mysql.connection.commit()
                    
                    # Obtener el nombre correcto de la columna ID
                    try:
                        cursor.execute("SHOW KEYS FROM clientes WHERE Key_name = 'PRIMARY'")
                        primary_key = cursor.fetchone()
                        
                        # Verificar el formato devuelto
                        print(f"DEBUG - Formato de primary_key: {primary_key}")
                        
                        # Intentar diferentes accesos según el formato
                        if isinstance(primary_key, dict) and 'Column_name' in primary_key:
                            id_column_name = primary_key['Column_name']
                        elif isinstance(primary_key, tuple) and len(primary_key) >= 5:
                            id_column_name = primary_key[4]
                        else:
                            # Si no podemos determinar, usar 'id' por defecto
                            id_column_name = 'id'
                    except Exception as e:
                        print(f"Error al obtener clave primaria: {e}")
                        id_column_name = 'id'  # Valor seguro por defecto
                    
                    print(f"Usando columna ID para clientes: '{id_column_name}'")
                    
                    # Obtener foto anterior
                    cursor.execute(f"SELECT foto_perfil FROM clientes WHERE {id_column_name} = %s", (current_user.id,))
                    resultado = cursor.fetchone()
                    
                    # Verificar formato del resultado
                    print(f"DEBUG - Formato de resultado: {resultado}")
                    
                    # Extraer valor según formato
                    foto_anterior = None
                    if resultado:
                        if isinstance(resultado, dict) and 'foto_perfil' in resultado:
                            foto_anterior = resultado['foto_perfil']
                        elif isinstance(resultado, tuple) and len(resultado) > 0:
                            foto_anterior = resultado[0]
                    
                    # Mostrar información de depuración
                    print(f"Actualizando foto para cliente con ID {current_user.id} usando columna '{id_column_name}'")
                    print(f"Foto anterior: {foto_anterior}")
                    
                    # Actualizar en la base de datos
                    cursor.execute(f"UPDATE clientes SET foto_perfil = %s WHERE {id_column_name} = %s", 
                                 (nombre_archivo, current_user.id))
                else:
                    # Verificar si existe la columna foto_perfil en la tabla empleados
                    cursor.execute("SHOW COLUMNS FROM empleados LIKE 'foto_perfil'")
                    tiene_foto_perfil = cursor.fetchone()
                    
                    if not tiene_foto_perfil:
                        cursor.execute("ALTER TABLE empleados ADD COLUMN foto_perfil VARCHAR(255) DEFAULT NULL")
                        mysql.connection.commit()
                    
                    # Obtener el nombre correcto de la columna ID
                    try:
                        cursor.execute("SHOW KEYS FROM empleados WHERE Key_name = 'PRIMARY'")
                        primary_key = cursor.fetchone()
                        
                        # Verificar el formato devuelto
                        print(f"DEBUG - Formato de primary_key empleados: {primary_key}")
                        
                        # Intentar diferentes accesos según el formato
                        if isinstance(primary_key, dict) and 'Column_name' in primary_key:
                            id_column_name = primary_key['Column_name']
                        elif isinstance(primary_key, tuple) and len(primary_key) >= 5:
                            id_column_name = primary_key[4]
                        else:
                            # Si no podemos determinar, usar 'id' por defecto
                            id_column_name = 'id'
                    except Exception as e:
                        print(f"Error al obtener clave primaria de empleados: {e}")
                        id_column_name = 'id'  # Valor seguro por defecto
                    
                    print(f"Usando columna ID para empleados: '{id_column_name}'")
                    
                    # Obtener foto anterior
                    cursor.execute(f"SELECT foto_perfil FROM empleados WHERE {id_column_name} = %s", (current_user.id,))
                    resultado = cursor.fetchone()
                    
                    # Verificar formato del resultado
                    print(f"DEBUG - Formato de resultado empleados: {resultado}")
                    
                    # Extraer valor según formato
                    foto_anterior = None
                    if resultado:
                        if isinstance(resultado, dict) and 'foto_perfil' in resultado:
                            foto_anterior = resultado['foto_perfil']
                        elif isinstance(resultado, tuple) and len(resultado) > 0:
                            foto_anterior = resultado[0]
                    
                    print(f"Actualizando foto para empleado con ID {current_user.id} usando columna '{id_column_name}'")
                    print(f"Foto anterior de empleado: {foto_anterior}")
                    
                    # Actualizar en la base de datos
                    cursor.execute(f"UPDATE empleados SET foto_perfil = %s WHERE {id_column_name} = %s", 
                                 (nombre_archivo, current_user.id))
                
                mysql.connection.commit()
                
                # Actualizar el objeto current_user
                current_user.foto_perfil = nombre_archivo
                
                # Eliminar archivo anterior si existe
                if foto_anterior:
                    ruta_anterior = os.path.join(directorio_perfiles, foto_anterior)
                    if os.path.exists(ruta_anterior):
                        os.remove(ruta_anterior)
                
                flash('Foto de perfil actualizada correctamente', 'success')
            except Exception as e:
                print(f"Error al actualizar foto en base de datos: {e}")
                mysql.connection.rollback()
                flash('Error al actualizar la foto de perfil en la base de datos', 'danger')
                if os.path.exists(ruta_archivo):
                    os.remove(ruta_archivo)  # Eliminar archivo si no se pudo actualizar la DB
            finally:
                cursor.close()
                
        except Exception as e:
            print(f"Error al guardar foto: {e}")
            flash('Error al guardar la foto de perfil', 'danger')
            
    # Redirigir a la página adecuada según el tipo de usuario
    if current_user.es_cliente:
        return redirect(url_for('main.mi_cuenta'))
    else:
        if hasattr(current_user, 'cargo_nombre') and current_user.cargo_nombre == 'Técnico':
            return redirect(url_for('auth.perfil_tecnico'))
        else:
            return redirect(url_for('empleados.mi_perfil'))

@auth_bp.route('/actualizar-perfil', methods=['POST'])
@login_required
def actualizar_perfil():
    """Actualiza la información del perfil del usuario"""
    try:
        # Obtener datos del formulario
        nombre = request.form.get('nombre', '')
        telefono = request.form.get('telefono', '')
        identificacion = request.form.get('identificacion', '')
        
        # Actualizar en la base de datos según el tipo de usuario
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        try:
            if current_user.es_cliente:
                # Obtener el nombre de la columna ID
                cursor.execute("SHOW COLUMNS FROM clientes LIKE 'id%'")
                id_column = cursor.fetchone()
                id_column_name = id_column[0] if id_column else 'id_cliente'
                
                # Verificar si existe la columna telefono
                cursor.execute("SHOW COLUMNS FROM clientes LIKE 'telefono'")
                tiene_telefono = cursor.fetchone()
                
                if not tiene_telefono:
                    cursor.execute("ALTER TABLE clientes ADD COLUMN telefono VARCHAR(20) NULL")
                    mysql.connection.commit()
                
                # Verificar si existe la columna identificación
                cursor.execute("SHOW COLUMNS FROM clientes LIKE 'identificacion'")
                tiene_identificacion = cursor.fetchone()
                
                if not tiene_identificacion:
                    cursor.execute("ALTER TABLE clientes ADD COLUMN identificacion VARCHAR(50) NULL")
                    mysql.connection.commit()
                
                # Actualizar en la base de datos
                cursor.execute(f"UPDATE clientes SET nombre = %s, telefono = %s, identificacion = %s WHERE {id_column_name} = %s", 
                            (nombre, telefono, identificacion, current_user.id))
            else:
                # Obtener el nombre de la columna ID
                cursor.execute("SHOW COLUMNS FROM empleados LIKE 'id%'")
                id_column = cursor.fetchone()
                id_column_name = id_column[0] if id_column else 'id_empleado'
                
                # Verificar si existe la columna telefono
                cursor.execute("SHOW COLUMNS FROM empleados LIKE 'telefono'")
                tiene_telefono = cursor.fetchone()
                
                if not tiene_telefono:
                    cursor.execute("ALTER TABLE empleados ADD COLUMN telefono VARCHAR(20) NULL")
                    mysql.connection.commit()
                
                # Actualizar en la base de datos
                cursor.execute(f"UPDATE empleados SET nombre = %s, telefono = %s WHERE {id_column_name} = %s", 
                            (nombre, telefono, current_user.id))
            
            mysql.connection.commit()
            
            # Actualizar el objeto current_user
            current_user.nombre = nombre
            current_user.telefono = telefono
            if current_user.es_cliente:
                current_user.identificacion = identificacion
            
            flash('Información actualizada correctamente', 'success')
        except Exception as e:
            mysql.connection.rollback()
            print(f"Error al actualizar información en base de datos: {e}")
            flash('Error al actualizar la información', 'danger')
        finally:
            cursor.close()
    except Exception as e:
        print(f"Error general al actualizar perfil: {e}")
        flash('Error al procesar la solicitud', 'danger')
    
    # Redirigir según el tipo de usuario
    if current_user.es_cliente:
        return redirect(url_for('main.mi_cuenta'))
    elif hasattr(current_user, 'cargo_nombre') and current_user.cargo_nombre == 'Técnico':
        return redirect(url_for('auth.perfil_tecnico'))
    else:
        return redirect(url_for('main.dashboard'))

@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    """Muestra y actualiza el perfil del usuario"""
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre', '')
        telefono = request.form.get('telefono', '')
        identificacion = request.form.get('identificacion', '')
        
        try:
            # Actualizar en la base de datos según el tipo de usuario
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            try:
                if current_user.es_cliente:
                    # Obtener el nombre de la columna ID
                    cursor.execute("SHOW COLUMNS FROM clientes LIKE 'id%'")
                    id_column = cursor.fetchone()
                    id_column_name = id_column[0] if id_column else 'id_cliente'
                    
                    # Verificar si existe la columna telefono
                    cursor.execute("SHOW COLUMNS FROM clientes LIKE 'telefono'")
                    tiene_telefono = cursor.fetchone()
                    
                    if not tiene_telefono:
                        cursor.execute("ALTER TABLE clientes ADD COLUMN telefono VARCHAR(20) NULL")
                        mysql.connection.commit()
                    
                    # Verificar si existe la columna identificación
                    cursor.execute("SHOW COLUMNS FROM clientes LIKE 'identificacion'")
                    tiene_identificacion = cursor.fetchone()
                    
                    if not tiene_identificacion:
                        cursor.execute("ALTER TABLE clientes ADD COLUMN identificacion VARCHAR(50) NULL")
                        mysql.connection.commit()
                    
                    # Actualizar en la base de datos
                    cursor.execute(f"UPDATE clientes SET nombre = %s, telefono = %s, identificacion = %s WHERE {id_column_name} = %s", 
                                (nombre, telefono, identificacion, current_user.id))
                else:
                    # Obtener el nombre de la columna ID
                    cursor.execute("SHOW COLUMNS FROM empleados LIKE 'id%'")
                    id_column = cursor.fetchone()
                    id_column_name = id_column[0] if id_column else 'id_empleado'
                    
                    # Verificar si existe la columna telefono
                    cursor.execute("SHOW COLUMNS FROM empleados LIKE 'telefono'")
                    tiene_telefono = cursor.fetchone()
                    
                    if not tiene_telefono:
                        cursor.execute("ALTER TABLE empleados ADD COLUMN telefono VARCHAR(20) NULL")
                        mysql.connection.commit()
                    
                    # Actualizar en la base de datos
                    cursor.execute(f"UPDATE empleados SET nombre = %s, telefono = %s WHERE {id_column_name} = %s", 
                                (nombre, telefono, current_user.id))
                
                mysql.connection.commit()
                
                # Actualizar el objeto current_user
                current_user.nombre = nombre
                current_user.telefono = telefono
                if current_user.es_cliente:
                    current_user.identificacion = identificacion
                
                flash('Información actualizada correctamente', 'success')
            except Exception as e:
                mysql.connection.rollback()
                print(f"Error al actualizar información en base de datos: {e}")
                flash('Error al actualizar la información', 'danger')
            finally:
                cursor.close()
        except Exception as e:
            print(f"Error general al actualizar perfil: {e}")
            flash('Error al procesar la solicitud', 'danger')
        
        return redirect(url_for('auth.perfil'))
    
    # Para solicitudes GET, obtener información del usuario para mostrar
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        user_data = {}
        
        if current_user.es_cliente:
            # Obtener el nombre de la columna ID
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'id%'")
            id_column = cursor.fetchone()
            id_column_name = id_column[0] if id_column else 'id_cliente'
            
            cursor.execute(f"SELECT fecha_registro, ultimo_login, identificacion FROM clientes WHERE {id_column_name} = %s", 
                        (current_user.id,))
            user_data = cursor.fetchone() or {}
            
            # Asignar valor de identificación al current_user si existe
            if user_data and 'identificacion' in user_data:
                current_user.identificacion = user_data['identificacion']
        else:
            # Obtener el nombre de la columna ID
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'id%'")
            id_column = cursor.fetchone()
            id_column_name = id_column[0] if id_column else 'id_empleado'
            
            cursor.execute(f"SELECT fecha_registro, ultimo_login FROM empleados WHERE {id_column_name} = %s", 
                        (current_user.id,))
            user_data = cursor.fetchone() or {}
        
        cursor.close()
        
    except Exception as e:
        print(f"Error al cargar datos del usuario: {e}")
        user_data = {}
    
    return render_template('auth/perfil.html', user_data=user_data)

@auth_bp.route('/perfil-tecnico')
@login_required
def perfil_tecnico():
    """Muestra el perfil del técnico con estadísticas"""
    # Verificar que el usuario sea un técnico
    if not hasattr(current_user, 'cargo_nombre') or current_user.cargo_nombre != 'Técnico':
        flash('Esta página es solo para técnicos', 'warning')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Obtener estadísticas del técnico
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Total de reparaciones asignadas
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM reparaciones
            WHERE tecnico_id = %s
        """, (current_user.id,))
        total = cursor.fetchone()['total']
        
        # Reparaciones en proceso
        cursor.execute("""
            SELECT COUNT(*) as en_proceso
            FROM reparaciones
            WHERE tecnico_id = %s AND estado_id IN (1, 2, 3)
        """, (current_user.id,))
        en_proceso = cursor.fetchone()['en_proceso']
        
        # Reparaciones completadas
        cursor.execute("""
            SELECT COUNT(*) as completadas
            FROM reparaciones
            WHERE tecnico_id = %s AND estado_id = 4
        """, (current_user.id,))
        completadas = cursor.fetchone()['completadas']
        
        cursor.close()
        
        stats = {
            'total_reparaciones': total,
            'en_proceso': en_proceso,
            'completadas': completadas
        }
        
        return render_template('auth/perfil_tecnico.html', stats=stats)
    except Exception as e:
        print(f"Error al obtener estadísticas: {e}")
        flash('Error al obtener las estadísticas', 'danger')
        return render_template('auth/perfil_tecnico.html', stats={})
