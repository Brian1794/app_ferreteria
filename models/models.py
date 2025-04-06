from extensions import mysql
from flask_bcrypt import Bcrypt
bcrypt = Bcrypt()
import MySQLdb
from flask import flash
from extensions import get_cursor
from models.usuario import Usuario
import datetime

def crear_tablas():
    """Crea las tablas necesarias en la base de datos si no existen"""
    cursor = mysql.connection.cursor()
    
    try:
        # Intentar ejecutar comandos y continuar si hay errores
        try:
            # Tabla de estados de producto
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS estados_producto (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(50) NOT NULL,
                    descripcion TEXT,
                    color VARCHAR(20),
                    activo BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Tabla de categorías
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categorias (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    descripcion TEXT,
                    imagen VARCHAR(255),
                    slug VARCHAR(100),
                    activo BOOLEAN DEFAULT TRUE,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de productos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS productos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    codigo VARCHAR(50) UNIQUE,
                    nombre VARCHAR(200) NOT NULL,
                    descripcion TEXT,
                    precio_venta DECIMAL(12,2) NOT NULL,
                    precio_compra DECIMAL(12,2),
                    stock INT DEFAULT 0,
                    stock_minimo INT DEFAULT 5,
                    categoria_id INT,
                    estado_id INT,
                    imagen VARCHAR(255),
                    activo BOOLEAN DEFAULT TRUE,
                    destacado BOOLEAN DEFAULT FALSE,
                    codigo_barras VARCHAR(100),
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
                    FOREIGN KEY (estado_id) REFERENCES estados_producto(id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla de clientes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clientes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(200) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    direccion VARCHAR(255),
                    telefono VARCHAR(50),
                    activo BOOLEAN DEFAULT TRUE,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ultimo_login TIMESTAMP NULL,
                    foto_perfil VARCHAR(255) NULL
                )
            ''')
            
            # Verificar si existe la columna password en la tabla clientes
            try:
                cursor.execute("SHOW COLUMNS FROM clientes LIKE 'password'")
                if not cursor.fetchone():
                    # Si no existe la columna password, agregarla
                    cursor.execute("ALTER TABLE clientes ADD COLUMN password VARCHAR(255) NOT NULL AFTER email")
                    print("Agregada columna password a la tabla clientes")
            except Exception as e:
                print(f"Error al verificar o agregar columna password: {e}")
            
            # Tabla de cargos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cargos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    descripcion TEXT,
                    permisos TEXT,
                    activo BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Tabla de empleados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS empleados (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(200) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    cargo_id INT,
                    es_admin BOOLEAN DEFAULT FALSE,
                    activo BOOLEAN DEFAULT TRUE,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ultimo_login TIMESTAMP NULL,
                    foto_perfil VARCHAR(255) NULL,
                    FOREIGN KEY (cargo_id) REFERENCES cargos(id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla de módulos del sistema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS modulos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    descripcion TEXT,
                    ruta VARCHAR(100),
                    icono VARCHAR(50)
                )
            ''')
            
            # Tabla de permisos por cargo
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS permisos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cargo_id INT,
                    modulo_id INT,
                    puede_ver BOOLEAN DEFAULT FALSE,
                    puede_crear BOOLEAN DEFAULT FALSE,
                    puede_editar BOOLEAN DEFAULT FALSE,
                    puede_eliminar BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (cargo_id) REFERENCES cargos(id) ON DELETE CASCADE,
                    FOREIGN KEY (modulo_id) REFERENCES modulos(id) ON DELETE CASCADE
                )
            ''')
            
            # Tabla de ventas
            cursor.execute('''
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
            
            # Tabla de detalle de ventas
            cursor.execute('''
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
            
            # Tabla de compras
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS compras (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    proveedor VARCHAR(200),
                    empleado_id INT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total DECIMAL(12,2) NOT NULL,
                    estado VARCHAR(50) DEFAULT 'COMPLETADA',
                    observaciones TEXT,
                    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla de detalle de compras
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS detalles_compra (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    compra_id INT NOT NULL,
                    producto_id INT,
                    cantidad INT NOT NULL,
                    precio_unitario DECIMAL(12,2) NOT NULL,
                    subtotal DECIMAL(12,2) NOT NULL,
                    FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
                    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla de reparaciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reparaciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cliente_id INT,
                    tecnico_id INT,
                    recepcionista_id INT,
                    descripcion TEXT NOT NULL,
                    electrodomestico VARCHAR(100),
                    marca VARCHAR(100),
                    modelo VARCHAR(100),
                    problema TEXT,
                    diagnostico TEXT,
                    notas TEXT,
                    estado VARCHAR(50) DEFAULT 'RECIBIDO',
                    costo_estimado DECIMAL(12,2) DEFAULT 0,
                    costo_final DECIMAL(12,2) DEFAULT 0,
                    fecha_recepcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_entrega_estimada DATE,
                    fecha_entrega DATE,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
                    FOREIGN KEY (tecnico_id) REFERENCES empleados(id) ON DELETE SET NULL,
                    FOREIGN KEY (recepcionista_id) REFERENCES empleados(id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla de historial de reparaciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historial_reparaciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    reparacion_id INT NOT NULL,
                    estado_anterior VARCHAR(50),
                    estado_nuevo VARCHAR(50) NOT NULL,
                    descripcion TEXT,
                    usuario_id INT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
                    FOREIGN KEY (usuario_id) REFERENCES empleados(id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla de repuestos para reparaciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reparaciones_repuestos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    reparacion_id INT NOT NULL,
                    producto_id INT,
                    repuesto_descripcion TEXT NOT NULL,
                    cantidad INT NOT NULL,
                    precio_unitario DECIMAL(12,2) NOT NULL,
                    subtotal DECIMAL(12,2) NOT NULL,
                    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
                    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
                )
            ''')
            
            # Tabla de configuración
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuracion (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    grupo VARCHAR(100) NOT NULL,
                    nombre VARCHAR(100) NOT NULL,
                    valor TEXT,
                    descripcion TEXT,
                    UNIQUE KEY grupo_nombre (grupo, nombre)
                )
            ''')
            
            # Tabla de plantillas de WhatsApp
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS whatsapp_plantillas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL UNIQUE,
                    contenido TEXT NOT NULL,
                    variables TEXT,
                    tipo VARCHAR(50),
                    activo BOOLEAN DEFAULT TRUE,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de mensajes de WhatsApp enviados
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS whatsapp_mensajes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    telefono VARCHAR(50) NOT NULL,
                    mensaje TEXT NOT NULL,
                    tipo_mensaje VARCHAR(50) DEFAULT 'MANUAL',
                    estado VARCHAR(50) DEFAULT 'ENVIADO',
                    error TEXT,
                    fecha_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    objeto_tipo VARCHAR(50),
                    objeto_id INT,
                    plantilla_id INT,
                    FOREIGN KEY (plantilla_id) REFERENCES whatsapp_plantillas(id) ON DELETE SET NULL
                )
            ''')
        except Exception as e:
            print(f"Error durante la creación de tablas: {e}")
            
        # Confirmar cambios
        mysql.connection.commit()
    finally:
        cursor.close()

def insertar_datos_iniciales():
    """Inserta datos iniciales en la base de datos si no existen"""
    cursor = mysql.connection.cursor()
    
    try:
        # Verificar si ya existe un usuario administrador
        cursor.execute('SELECT COUNT(*) FROM empleados WHERE es_admin = TRUE')
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        # Si no hay usuario administrador, crear uno por defecto
        if count == 0:
            # Generar hash para la contraseña 'admin123'
            hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
            
            cursor.execute('''
                INSERT INTO empleados (nombre, email, password, es_admin, activo)
                VALUES (%s, %s, %s, %s, %s)
            ''', ('Administrador', 'admin@ferreteria.com', hashed_password, True, True))
            
            print("Usuario administrador creado con éxito")
            
        # Verificar si existen cargos
        cursor.execute('SELECT COUNT(*) FROM cargos')
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        # Si no hay cargos, crear los básicos
        if count == 0:
            cargos = [
                ('Administrador', 'Control total del sistema'),
                ('Vendedor', 'Gestión de ventas y atención al cliente'),
                ('Técnico', 'Encargado de reparaciones'),
                ('Almacenista', 'Gestión de inventario')
            ]
            
            for nombre, descripcion in cargos:
                cursor.execute('''
                    INSERT INTO cargos (nombre, descripcion, activo)
                    VALUES (%s, %s, %s)
                ''', (nombre, descripcion, True))
                
            print("Cargos básicos creados con éxito")
            
        # Verificar si existen estados de producto
        cursor.execute('SELECT COUNT(*) FROM estados_producto')
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        # Si no hay estados de producto, crear los básicos
        if count == 0:
            estados = [
                ('Disponible', 'Producto en stock y listo para venta', '#28a745'),
                ('Agotado', 'Sin existencias', '#dc3545'),
                ('Por llegar', 'Producto ordenado pero aún no recibido', '#ffc107'),
                ('Descontinuado', 'Producto que ya no se venderá', '#6c757d'),
                ('Promoción', 'Producto en oferta especial', '#17a2b8')
            ]
            
            for nombre, descripcion, color in estados:
                cursor.execute('''
                    INSERT INTO estados_producto (nombre, descripcion, color, activo)
                    VALUES (%s, %s, %s, %s)
                ''', (nombre, descripcion, color, True))
                
            print("Estados de producto creados con éxito")
            
        # Verificar si existen módulos
        cursor.execute('SELECT COUNT(*) FROM modulos')
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        # Si no hay módulos, crear los básicos
        if count == 0:
            modulos = [
                ('Dashboard', 'Página principal con estadísticas', '/dashboard', 'fas fa-chart-line'),
                ('Productos', 'Gestión de inventario', '/productos', 'fas fa-boxes'),
                ('Ventas', 'Registro y consulta de ventas', '/ventas', 'fas fa-shopping-cart'),
                ('Compras', 'Registro y consulta de compras', '/compras', 'fas fa-truck-loading'),
                ('Clientes', 'Gestión de clientes', '/clientes', 'fas fa-users'),
                ('Empleados', 'Gestión de empleados', '/empleados', 'fas fa-user-tie'),
                ('Reparaciones', 'Gestión de servicio técnico', '/reparaciones', 'fas fa-tools'),
                ('WhatsApp', 'Gestión de mensajería', '/whatsapp', 'fab fa-whatsapp'),
                ('Reportes', 'Generación de informes', '/reportes', 'fas fa-file-alt'),
                ('Configuración', 'Ajustes del sistema', '/configuracion', 'fas fa-cogs')
            ]
            
            for nombre, descripcion, ruta, icono in modulos:
                cursor.execute('''
                    INSERT INTO modulos (nombre, descripcion, ruta, icono)
                    VALUES (%s, %s, %s, %s)
                ''', (nombre, descripcion, ruta, icono))
                
            print("Módulos básicos creados con éxito")
            
        # Insertar permisos para el cargo de Administrador
        cursor.execute('SELECT id FROM cargos WHERE nombre = %s', ('Administrador',))
        admin_cargo = cursor.fetchone()
        
        if admin_cargo:
            admin_id = admin_cargo[0]
            
            # Obtener todos los módulos
            cursor.execute('SELECT id FROM modulos')
            modulos = cursor.fetchall()
            
            # Verificar si ya existen permisos para el administrador
            cursor.execute('SELECT COUNT(*) FROM permisos WHERE cargo_id = %s', (admin_id,))
            result = cursor.fetchone()
            count = result[0] if result else 0
            
            # Si no hay permisos, asignar todos los permisos al administrador
            if count == 0:
                for modulo in modulos:
                    modulo_id = modulo[0]
                    cursor.execute('''
                        INSERT INTO permisos (cargo_id, modulo_id, puede_ver, puede_crear, puede_editar, puede_eliminar)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (admin_id, modulo_id, True, True, True, True))
                    
                print("Permisos para administrador creados con éxito")
        
        # Insertar configuraciones básicas
        cursor.execute('SELECT COUNT(*) FROM configuracion')
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        if count == 0:
            configuraciones = [
                # Generales
                ('general', 'nombre_negocio', 'Ferretería La U', 'Nombre del negocio'),
                ('general', 'telefono', '+573001234567', 'Teléfono principal'),
                ('general', 'direccion', 'Calle Principal #123', 'Dirección física'),
                ('general', 'correo', 'contacto@ferreteria.com', 'Correo electrónico'),
                
                # WhatsApp
                ('whatsapp', 'api_key', '', 'Clave de API para WhatsApp Business'),
                ('whatsapp', 'numero', '', 'Número de WhatsApp del negocio'),
                ('whatsapp', 'activo', 'no', 'Si el servicio de WhatsApp está activo'),
                
                # WhatsApp automáticos
                ('whatsapp_automaticos', 'notificar_ventas', 'no', 'Enviar notificación al completar una venta'),
                ('whatsapp_automaticos', 'notificar_reparaciones', 'no', 'Enviar notificación de cambios en reparaciones'),
                ('whatsapp_automaticos', 'recordatorio_pago', 'no', 'Enviar recordatorio de pagos pendientes')
            ]
            
            for grupo, nombre, valor, descripcion in configuraciones:
                cursor.execute('''
                    INSERT INTO configuracion (grupo, nombre, valor, descripcion)
                    VALUES (%s, %s, %s, %s)
                ''', (grupo, nombre, valor, descripcion))
                
            print("Configuraciones básicas creadas con éxito")
            
        mysql.connection.commit()
    except Exception as e:
        print(f"Error durante la inserción de datos iniciales: {e}")
        mysql.connection.rollback()
    finally:
        cursor.close()

def get_cursor():
    """Devuelve un cursor para la conexión a la base de datos"""
    return mysql.connection.cursor()

def verificar_estructura_tablas():
    """Verifica y actualiza la estructura de las tablas si es necesario"""
    try:
        cursor = mysql.connection.cursor()
        
        # Verificar y corregir la tabla clientes
        cursor.execute("SHOW TABLES LIKE 'clientes'")
        if cursor.fetchone():
            # Verificar si existe la columna email en la tabla clientes
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'email'")
            existe_columna_email = cursor.fetchone()
            
            if not existe_columna_email:
                cursor.execute("ALTER TABLE clientes ADD COLUMN email VARCHAR(100) UNIQUE AFTER nombre")
                mysql.connection.commit()
                print("Columna email añadida a la tabla clientes")
                
            # Verificar si existe la columna password
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'password'")
            existe_columna_password = cursor.fetchone()
            
            if not existe_columna_password:
                cursor.execute("ALTER TABLE clientes ADD COLUMN password VARCHAR(255) NOT NULL DEFAULT '' AFTER email")
                mysql.connection.commit()
                print("Columna password añadida a la tabla clientes")
        
            # Verificar si existe la columna foto_perfil
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'foto_perfil'")
            existe_columna_foto = cursor.fetchone()
            
            if not existe_columna_foto:
                cursor.execute("ALTER TABLE clientes ADD COLUMN foto_perfil VARCHAR(255) NULL")
                mysql.connection.commit()
                print("Columna foto_perfil añadida a la tabla clientes")
        
        # Verificar y corregir la tabla empleados
        cursor.execute("SHOW TABLES LIKE 'empleados'")
        if cursor.fetchone():
            # Verificar si existe la columna es_admin
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'es_admin'")
            existe_columna_admin = cursor.fetchone()
            
            if not existe_columna_admin:
                cursor.execute("ALTER TABLE empleados ADD COLUMN es_admin BOOLEAN DEFAULT FALSE AFTER cargo_id")
                mysql.connection.commit()
                print("Columna es_admin añadida a la tabla empleados")
            
            # Verificar si existe la columna foto_perfil
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'foto_perfil'")
            existe_columna_foto = cursor.fetchone()
            
            if not existe_columna_foto:
                cursor.execute("ALTER TABLE empleados ADD COLUMN foto_perfil VARCHAR(255) NULL")
                mysql.connection.commit()
                print("Columna foto_perfil añadida a la tabla empleados")
        
        # Verificar y corregir la tabla ventas
        cursor.execute("SHOW TABLES LIKE 'ventas'")
        if cursor.fetchone():
            # Asegurarse de que la estructura de ventas tenga la columna id como PRIMARY KEY
            cursor.execute("SHOW KEYS FROM ventas WHERE Key_name = 'PRIMARY'")
            tiene_primary_key = cursor.fetchone()
            
            if not tiene_primary_key:
                # Si no tiene primary key, intentamos agregar una
                try:
                    cursor.execute("ALTER TABLE ventas ADD PRIMARY KEY (id)")
                    mysql.connection.commit()
                    print("Clave primaria añadida a la tabla ventas")
                except Exception as e:
                    print(f"Error al agregar clave primaria a ventas: {e}")
                    
        # Verificar la existencia de la tabla detalles_venta
        cursor.execute("SHOW TABLES LIKE 'detalles_venta'")
        existe_tabla_detalles = cursor.fetchone()
        
        if not existe_tabla_detalles:
            # Crear la tabla detalles_venta si no existe
            try:
                cursor.execute('''
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
                mysql.connection.commit()
                print("Tabla detalles_venta creada")
            except Exception as e:
                print(f"Error al crear tabla detalles_venta: {e}")
            
        cursor.close()
    except Exception as e:
        print(f"Error al verificar estructura de tablas: {e}")
        mysql.connection.rollback()
