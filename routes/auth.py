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
            
            if not empleado:
                flash('Usuario o contraseña incorrectos', 'danger')
                cursor.close()
                return render_template('auth/login_empleado.html')
            
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
            # Intentar verificar como hash bcrypt si no coincide como texto plano
            elif len(stored_password) > 20:  # Los hashes bcrypt son largos
                try:
                    password_es_correcta = bcrypt.check_password_hash(stored_password, password)
                except Exception as e:
                    print(f"Error al verificar hash bcrypt: {e}")
            
            if not password_es_correcta:
                flash('Usuario o contraseña incorrectos', 'danger')
                cursor.close()
                return render_template('auth/login_empleado.html')
            
            # Obtener información del cargo si existe
            cargo_id = empleado.get('cargo_id')
            cargo_nombre = None
            
            if cargo_id:
                cursor.execute('SELECT nombre FROM cargos WHERE id = %s', (cargo_id,))
                cargo = cursor.fetchone()
                if cargo:
                    cargo_nombre = cargo['nombre']
            
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
                    next_page = url_for('main.dashboard')
                elif cargo_nombre == 'Técnico':
                    next_page = url_for('reparaciones.pendientes')
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
    response = redirect(url_for('main.index', _external=True, _fresh=True))
    
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
        
        try:
            import MySQLdb
            cursor = mysql.connection.cursor()
            
            # Verificar contraseña actual según tipo de usuario
            if current_user.es_cliente:
                # Obtener nombre de columnas para cliente
                cursor.execute("DESCRIBE clientes")
                columnas = cursor.fetchall()
                print("Columnas en tabla clientes:", [col[0] for col in columnas])
                
                # Determinar el nombre de la columna ID
                cursor.execute("SHOW COLUMNS FROM clientes LIKE 'id%'")
                id_column = cursor.fetchone()
                id_column_name = id_column[0] if id_column else 'id'
                
                # Determinar el nombre de la columna de contraseña
                cursor.execute("SHOW COLUMNS FROM clientes LIKE '%password%'")
                pwd_columns = cursor.fetchall()
                pwd_column_name = 'password'  # Valor por defecto
                
                for col in pwd_columns:
                    if col[0].lower() in ['password', 'contrasena', 'clave']:
                        pwd_column_name = col[0]
                        break
                
                print(f"Usando columna de contraseña: {pwd_column_name}")
                
                # Obtener contraseña actual
                cursor.execute(f"SELECT {pwd_column_name} FROM clientes WHERE {id_column_name} = %s", (current_user.id,))
                user_data = cursor.fetchone()
                
                if user_data and bcrypt.check_password_hash(user_data[0], password_actual):
                    # Actualizar contraseña
                    hashed_password = bcrypt.generate_password_hash(password_nuevo).decode('utf-8')
                    cursor.execute(f'UPDATE clientes SET {pwd_column_name} = %s WHERE {id_column_name} = %s', 
                                  (hashed_password, current_user.id))
                    mysql.connection.commit()
                    flash('Contraseña actualizada con éxito', 'success')
                else:
                    flash('La contraseña actual es incorrecta', 'danger')
            else:
                # Obtener nombre de columnas para empleado
                cursor.execute("DESCRIBE empleados")
                columnas = cursor.fetchall()
                print("Columnas en tabla empleados:", [col[0] for col in columnas])
                
                # Determinar el nombre de la columna ID
                cursor.execute("SHOW COLUMNS FROM empleados LIKE 'id%'")
                id_column = cursor.fetchone()
                id_column_name = id_column[0] if id_column else 'id_empleado'
                
                # Determinar el nombre de la columna de contraseña
                cursor.execute("SHOW COLUMNS FROM empleados LIKE '%password%'")
                pwd_columns = cursor.fetchall()
                pwd_column_name = 'password'  # Valor por defecto
                
                for col in pwd_columns:
                    if col[0].lower() in ['password', 'contrasena', 'clave']:
                        pwd_column_name = col[0]
                        break
                
                print(f"Usando columna de contraseña: {pwd_column_name}")
                
                # Para empleados, verificar contraseña
                cursor.execute(f"SELECT {pwd_column_name} FROM empleados WHERE {id_column_name} = %s", (current_user.id,))
                user_data = cursor.fetchone()
                
                if user_data:
                    try:
                        if bcrypt.check_password_hash(user_data[0], password_actual):
                            # Actualizar contraseña
                            hashed_password = bcrypt.generate_password_hash(password_nuevo).decode('utf-8')
                            cursor.execute(f'UPDATE empleados SET {pwd_column_name} = %s WHERE {id_column_name} = %s', 
                                        (hashed_password, current_user.id))
                            mysql.connection.commit()
                            flash('Contraseña actualizada con éxito', 'success')
                        else:
                            flash('La contraseña actual es incorrecta', 'danger')
                    except Exception as e:
                        print(f"Error al verificar contraseña: {e}")
                        flash('Error al verificar la contraseña actual', 'danger')
            
            cursor.close()
            
        except Exception as e:
            print(f"Error al cambiar contraseña: {e}")
            flash('Error al procesar la solicitud', 'danger')
    
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
            cursor = mysql.connection.cursor()
            
            # Buscar en tabla clientes
            cursor.execute("SELECT id_cliente as id, nombre, 'cliente' as tipo FROM clientes WHERE correo = %s", (email,))
            usuario = cursor.fetchone()
            
            # Si no se encuentra, buscar en empleados
            if not usuario:
                cursor.execute("SELECT id_empleado as id, CONCAT(nombre, ' ', apellido) as nombre, 'empleado' as tipo FROM empleados WHERE correo = %s", (email,))
                usuario = cursor.fetchone()
                
            if not usuario:
                # No informamos al usuario si el correo existe o no por seguridad
                flash('Si el correo existe en nuestro sistema, recibirás instrucciones para restablecer tu contraseña.', 'info')
                return render_template('auth/recuperar_password.html')
                
            # Generar token único
            token = secrets.token_urlsafe(32)
            expiration = datetime.now() + timedelta(hours=1)
            
            # Crear tabla para tokens de recuperación si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reset_tokens (
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
            
            # Guardar token en la base de datos
            cursor.execute(
                "INSERT INTO reset_tokens (token, user_id, user_type, expiration) VALUES (%s, %s, %s, %s)",
                (token, usuario['id'], usuario['tipo'], expiration)
            )
            mysql.connection.commit()
            
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
                
                flash('Se han enviado instrucciones de recuperación a tu correo electrónico.', 'success')
            except Exception as e:
                current_app.logger.error(f"Error al enviar correo: {str(e)}")
                # Guardar el enlace en los logs para pruebas
                current_app.logger.info(f"URL de recuperación (para pruebas): {reset_url}")
                
                # Mensaje genérico para el usuario
                flash('Ocurrió un problema al enviar el correo. Contacta con soporte técnico.', 'warning')
                
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
        cursor = mysql.connection.cursor()
        
        # Buscar el token en la base de datos
        cursor.execute("""
            SELECT reset_tokens.*, 
                   CASE 
                       WHEN user_type = 'cliente' THEN clientes.correo
                       WHEN user_type = 'empleado' THEN empleados.correo
                   END as email
            FROM reset_tokens
            LEFT JOIN clientes ON reset_tokens.user_id = clientes.id_cliente AND reset_tokens.user_type = 'cliente'
            LEFT JOIN empleados ON reset_tokens.user_id = empleados.id_empleado AND reset_tokens.user_type = 'empleado'
            WHERE token = %s AND used = FALSE AND expiration > NOW()
        """, (token,))
        
        token_data = cursor.fetchone()
        
        if not token_data:
            flash('El enlace para restablecer tu contraseña es inválido o ha expirado.', 'danger')
            return redirect(url_for('auth.recuperar_password'))
        
        if request.method == 'POST':
            # Obtener los datos del formulario
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            # Validar la contraseña
            if not password or len(password) < 6:
                flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
                return render_template('auth/reset_password.html', token=token)
                
            if password != confirm_password:
                flash('Las contraseñas no coinciden.', 'danger')
                return render_template('auth/reset_password.html', token=token)
            
            # Encriptar la nueva contraseña
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            
            # Actualizar la contraseña según el tipo de usuario
            if token_data['user_type'] == 'cliente':
                cursor.execute(
                    "UPDATE clientes SET password = %s WHERE id_cliente = %s",
                    (hashed_password, token_data['user_id'])
                )
            else:  # Empleado
                cursor.execute(
                    "UPDATE empleados SET password = %s WHERE id_empleado = %s",
                    (hashed_password, token_data['user_id'])
                )
            
            # Marcar el token como usado
            cursor.execute(
                "UPDATE reset_tokens SET used = TRUE WHERE id = %s",
                (token_data['id'],)
            )
            
            mysql.connection.commit()
            
            flash('Tu contraseña ha sido actualizada correctamente. Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('auth/reset_password.html', token=token)
        
    except Exception as e:
        current_app.logger.error(f"Error en restablecimiento de contraseña: {str(e)}")
        flash('Ocurrió un error en el proceso. Por favor, inténtalo de nuevo más tarde.', 'danger')
        return redirect(url_for('auth.recuperar_password'))
    
    finally:
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
            cursor = mysql.connection.cursor()
            
            try:
                # Eliminar foto anterior si existe
                foto_anterior = None
                
                if current_user.es_cliente:
                    # Obtener los nombres de tablas y columnas
                    cursor.execute("DESCRIBE clientes")
                    columnas = cursor.fetchall()
                    print("Columnas en tabla clientes:", [col[0] for col in columnas])
                    
                    # Verificar primero si la tabla tiene la columna foto_perfil
                    cursor.execute("SHOW COLUMNS FROM clientes LIKE 'foto_perfil'")
                    tiene_columna = cursor.fetchone()
                    
                    if not tiene_columna:
                        cursor.execute("ALTER TABLE clientes ADD COLUMN foto_perfil VARCHAR(255) NULL")
                        mysql.connection.commit()
                    
                    # Obtener foto anterior y el nombre de la columna ID
                    cursor.execute("SHOW COLUMNS FROM clientes LIKE 'id%'")
                    id_column = cursor.fetchone()
                    id_column_name = id_column[0] if id_column else 'id_cliente'
                    
                    # Obtener foto anterior
                    cursor.execute(f"SELECT foto_perfil FROM clientes WHERE {id_column_name} = %s", (current_user.id,))
                    resultado = cursor.fetchone()
                    if resultado and resultado[0]:
                        foto_anterior = resultado[0]
                    
                    # Actualizar en la base de datos
                    cursor.execute(f"UPDATE clientes SET foto_perfil = %s WHERE {id_column_name} = %s", 
                                 (nombre_archivo, current_user.id))
                else:
                    # Obtener los nombres de tablas y columnas
                    cursor.execute("DESCRIBE empleados")
                    columnas = cursor.fetchall()
                    print("Columnas en tabla empleados:", [col[0] for col in columnas])
                    
                    # Verificar primero si la tabla tiene la columna foto_perfil
                    cursor.execute("SHOW COLUMNS FROM empleados LIKE 'foto_perfil'")
                    tiene_columna = cursor.fetchone()
                    
                    if not tiene_columna:
                        cursor.execute("ALTER TABLE empleados ADD COLUMN foto_perfil VARCHAR(255) NULL")
                        mysql.connection.commit()
                    
                    # Obtener foto anterior y el nombre de la columna ID
                    cursor.execute("SHOW COLUMNS FROM empleados LIKE 'id%'")
                    id_column = cursor.fetchone()
                    id_column_name = id_column[0] if id_column else 'id_empleado'
                    
                    # Obtener foto anterior
                    cursor.execute(f"SELECT foto_perfil FROM empleados WHERE {id_column_name} = %s", (current_user.id,))
                    resultado = cursor.fetchone()
                    if resultado and resultado[0]:
                        foto_anterior = resultado[0]
                    
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
            
    # Redirigir a la página de perfil si es cliente, o al dashboard si es empleado
    if current_user.es_cliente:
        return redirect(url_for('main.mi_cuenta'))
    else:
        return redirect(url_for('main.dashboard'))
