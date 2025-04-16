from extensions import mysql
from flask_bcrypt import Bcrypt
bcrypt = Bcrypt()
import MySQLdb
from flask import flash
from extensions import get_cursor
from models.usuario import Usuario
import datetime
from models.carousel import Carousel

def crear_tablas():
    """Crea todas las tablas en la base de datos"""
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
            
            # Crear tabla carousel usando la clase Carousel
            try:
                Carousel.crear_tabla()
                print("Tabla carousel creada correctamente mediante la clase Carousel")
            except Exception as e:
                print(f"Error al crear tabla carousel mediante la clase: {e}")
                # Intento alternativo con SQL directo
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS carousel (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        titulo VARCHAR(100) NOT NULL,
                        descripcion TEXT,
                        imagen VARCHAR(255) NOT NULL,
                        enlace VARCHAR(255),
                        orden INT DEFAULT 0,
                        activo BOOLEAN DEFAULT TRUE,
                        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                ''')
                print("Tabla carousel creada mediante SQL directo")
            
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
                    identificacion VARCHAR(50),
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
                    solucion TEXT,
                    estado VARCHAR(50) DEFAULT 'RECIBIDO',
                    fecha_recepcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_entrega_estimada DATE,
                    fecha_entrega DATETIME,
                    fecha_actualizacion DATETIME,
                    costo_revision DECIMAL(10,2) DEFAULT 20000,
                    costo_reparacion DECIMAL(10,2),
                    total DECIMAL(10,2),
                    observaciones TEXT,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
                    FOREIGN KEY (tecnico_id) REFERENCES empleados(id) ON DELETE SET NULL,
                    FOREIGN KEY (recepcionista_id) REFERENCES empleados(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Tabla de repuestos para reparaciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reparaciones_repuestos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    reparacion_id INT NOT NULL,
                    producto_id INT,
                    cantidad INT NOT NULL,
                    precio_unitario DECIMAL(10,2) NOT NULL,
                    subtotal DECIMAL(10,2) NOT NULL,
                    fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
                    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
            
            # Tabla de carrito de compras
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS carritos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cliente_id INT NOT NULL,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
                )
            ''')
            
            # Tabla de items del carrito
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS carrito_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    carrito_id INT NOT NULL,
                    producto_id INT NOT NULL,
                    cantidad INT NOT NULL,
                    fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (carrito_id) REFERENCES carritos(id) ON DELETE CASCADE,
                    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
                )
            ''')
            
            # Tabla de pedidos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cliente_id INT NOT NULL,
                    fecha_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    estado VARCHAR(50) DEFAULT 'PENDIENTE',
                    total DECIMAL(12,2) NOT NULL,
                    metodo_pago VARCHAR(50),
                    referencia_pago VARCHAR(100),
                    direccion_envio TEXT,
                    telefono_contacto VARCHAR(50),
                    notas TEXT,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
                )
            ''')
            
            # Tabla de detalles de pedido
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pedido_detalles (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    pedido_id INT NOT NULL,
                    producto_id INT NOT NULL,
                    cantidad INT NOT NULL,
                    precio_unitario DECIMAL(12,2) NOT NULL,
                    subtotal DECIMAL(12,2) NOT NULL,
                    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
                    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
                )
            ''')
            
            # Tabla de facturas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS facturas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    numero_factura VARCHAR(100) UNIQUE NOT NULL,
                    pedido_id INT NOT NULL,
                    fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_vencimiento TIMESTAMP,
                    subtotal DECIMAL(12,2) NOT NULL,
                    iva DECIMAL(12,2) NOT NULL,
                    total DECIMAL(12,2) NOT NULL,
                    estado VARCHAR(50) DEFAULT 'EMITIDA',
                    formato VARCHAR(50) DEFAULT 'PDF',
                    url_descarga VARCHAR(255),
                    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE
                )
            ''')
            
            # Tabla de pagos PSE
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pagos_pse (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    pedido_id INT NOT NULL,
                    factura_id INT,
                    referencia_pago VARCHAR(100) UNIQUE NOT NULL,
                    banco_id VARCHAR(50) NOT NULL,
                    banco_nombre VARCHAR(100) NOT NULL,
                    estado VARCHAR(50) DEFAULT 'PENDIENTE',
                    monto DECIMAL(12,2) NOT NULL,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_procesado TIMESTAMP,
                    tipo_persona VARCHAR(10) NOT NULL,
                    tipo_documento VARCHAR(50) NOT NULL,
                    numero_documento VARCHAR(50) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    url_retorno VARCHAR(255),
                    ip_origen VARCHAR(50),
                    user_agent TEXT,
                    respuesta_pse TEXT,
                    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
                    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE SET NULL
                )
            ''')
        except Exception as e:
            print(f"Error durante la creación de tablas: {e}")
            
        # Crear tabla de carousel
        try:
            Carousel.crear_tabla()
            print("Tabla carousel creada o verificada correctamente")
        except Exception as e:
            print(f"Error al crear tabla carousel: {e}")
        
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
    """Verifica la estructura de las tablas críticas del sistema"""
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        
        # Verificar tabla clientes
        cursor.execute("SHOW TABLES LIKE 'clientes'")
        if cursor.fetchone():
            cursor.execute("DESCRIBE clientes")
            columnas = {col[0] for col in cursor.fetchall()}
            campos_requeridos = {'id', 'nombre', 'email', 'password', 'telefono'}
            campos_faltantes = campos_requeridos - columnas
            if campos_faltantes:
                print(f"Advertencia: Faltan campos en la tabla clientes: {campos_faltantes}")
        
        # Verificar tabla reparaciones
        cursor.execute("SHOW TABLES LIKE 'reparaciones'")
        if cursor.fetchone():
            cursor.execute("DESCRIBE reparaciones")
            columnas = {col[0] for col in cursor.fetchall()}
            campos_requeridos = {
                'id', 'cliente_id', 'descripcion', 'estado', 
                'fecha_recepcion', 'fecha_entrega_estimada'
            }
            campos_faltantes = campos_requeridos - columnas
            if campos_faltantes:
                print(f"Advertencia: Faltan campos en la tabla reparaciones: {campos_faltantes}")
                
            # Verificar si existen las tablas relacionadas
            tablas_relacionadas = [
                'historial_reparaciones',
                'reparaciones_repuestos'
            ]
            
            for tabla in tablas_relacionadas:
                cursor.execute(f"SHOW TABLES LIKE '{tabla}'")
                if not cursor.fetchone():
                    if tabla == 'historial_reparaciones':
                        crear_tabla_historial_reparaciones()
                    elif tabla == 'reparaciones_repuestos':
                        crear_tabla_reparaciones_repuestos()
        else:
            # Si no existe la tabla reparaciones, crearla
            inicializar_tablas_reparaciones()
        
        mysql.connection.commit()
        return True
        
    except Exception as e:
        print(f"Error al verificar estructura de tablas: {e}")
        if cursor:
            mysql.connection.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()

# Crear la tabla de historial de reparaciones si no existe
def crear_tabla_historial_reparaciones():
    """Crea la tabla historial_reparaciones si no existe"""
    cursor = mysql.connection.cursor()
    try:
        # Verificar si la tabla existe
        cursor.execute("SHOW TABLES LIKE 'historial_reparaciones'")
        if not cursor.fetchone():
            # Crear la tabla
            cursor.execute("""
                CREATE TABLE historial_reparaciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    reparacion_id INT NOT NULL,
                    estado VARCHAR(50) NOT NULL,
                    fecha DATETIME NOT NULL,
                    tecnico_id INT NULL,
                    comentario TEXT NULL,
                    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
                    FOREIGN KEY (tecnico_id) REFERENCES empleados(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            mysql.connection.commit()
            print("Tabla historial_reparaciones creada exitosamente")
        else:
            print("La tabla historial_reparaciones ya existe")
    except Exception as e:
        print(f"Error al crear tabla historial_reparaciones: {e}")
        mysql.connection.rollback()
    finally:
        cursor.close()

def crear_tabla_reparaciones_repuestos():
    """Crea la tabla para gestionar los repuestos usados en las reparaciones"""
    try:
        cursor = mysql.connection.cursor()
        
        # Comprobar si la tabla existe
        cursor.execute("SHOW TABLES LIKE 'reparaciones_repuestos'")
        if cursor.fetchone():
            print("La tabla reparaciones_repuestos ya existe")
            return
        
        # Crear la tabla
        cursor.execute("""
            CREATE TABLE reparaciones_repuestos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reparacion_id INT NOT NULL,
                producto_id INT NULL,
                repuesto_descripcion VARCHAR(255) NOT NULL,
                cantidad INT NOT NULL DEFAULT 1,
                precio_unitario DECIMAL(10,2) NOT NULL DEFAULT 0,
                subtotal DECIMAL(10,2) NOT NULL DEFAULT 0,
                fecha_agregado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        mysql.connection.commit()
        print("Tabla reparaciones_repuestos creada exitosamente")
    except Exception as e:
        print(f"Error al crear tabla reparaciones_repuestos: {e}")
    finally:
        cursor.close()

def crear_tabla_whatsapp_mensajes():
    """Crea la tabla para los mensajes de WhatsApp enviados"""
    try:
        cursor = mysql.connection.cursor()
        
        # Comprobar si la tabla existe
        cursor.execute("SHOW TABLES LIKE 'whatsapp_mensajes'")
        if cursor.fetchone():
            print("La tabla whatsapp_mensajes ya existe")
            return
        
        # Crear la tabla
        cursor.execute("""
            CREATE TABLE whatsapp_mensajes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telefono VARCHAR(20) NOT NULL,
                mensaje TEXT NOT NULL,
                tipo_mensaje VARCHAR(50) NOT NULL,
                objeto_tipo VARCHAR(50) NOT NULL,
                objeto_id INT NOT NULL,
                fecha_envio DATETIME NOT NULL,
                estado VARCHAR(20) DEFAULT 'enviado',
                respuesta TEXT NULL,
                INDEX (objeto_tipo, objeto_id),
                INDEX (telefono)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        mysql.connection.commit()
        print("Tabla whatsapp_mensajes creada exitosamente")
    except Exception as e:
        print(f"Error al crear tabla whatsapp_mensajes: {e}")
    finally:
        cursor.close()

def actualizar_tabla_reparaciones():
    """Actualiza la tabla de reparaciones para agregar campos necesarios para diagnóstico y solución"""
    try:
        cursor = mysql.connection.cursor()
        
        # Verificar si la columna diagnostico existe
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'diagnostico'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN diagnostico TEXT NULL")
            print("Columna diagnostico agregada")
            
        # Verificar si la columna notas existe
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'notas'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN notas TEXT NULL")
            print("Columna notas agregada")
            
        # Verificar si la columna costo_estimado existe
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'costo_estimado'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN costo_estimado DECIMAL(10,2) NULL")
            print("Columna costo_estimado agregada")
            
        # Verificar si la columna costo_final existe
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'costo_final'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN costo_final DECIMAL(10,2) NULL")
            print("Columna costo_final agregada")
            
        # Verificar si la columna fecha_actualizacion existe
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'fecha_actualizacion'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN fecha_actualizacion DATETIME NULL")
            print("Columna fecha_actualizacion agregada")
            
        # Añadir más campos específicos para la documentación técnica
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'solucion_tecnica'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN solucion_tecnica TEXT NULL")
            print("Columna solucion_tecnica agregada")
            
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'componentes_reemplazados'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN componentes_reemplazados TEXT NULL")
            print("Columna componentes_reemplazados agregada")
            
        cursor.execute("SHOW COLUMNS FROM reparaciones LIKE 'horas_trabajo'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reparaciones ADD COLUMN horas_trabajo DECIMAL(5,2) NULL")
            print("Columna horas_trabajo agregada")
            
        mysql.connection.commit()
        print("Tabla reparaciones actualizada exitosamente")
    except Exception as e:
        print(f"Error al actualizar tabla reparaciones: {e}")
    finally:
        cursor.close()

def inicializar_tablas_reparaciones():
    """Inicializa las tablas necesarias para el módulo de reparaciones"""
    cursor = None
    try:
        if not hasattr(mysql, 'connection'):
            print("Error: No hay conexión MySQL disponible")
            return False
            
        cursor = mysql.connection.cursor()
        
        # Crear tabla de reparaciones
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
                solucion TEXT,
                estado VARCHAR(50) DEFAULT 'RECIBIDO',
                fecha_recepcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_entrega_estimada DATE,
                fecha_entrega DATETIME,
                fecha_actualizacion DATETIME,
                costo_revision DECIMAL(10,2) DEFAULT 20000,
                costo_reparacion DECIMAL(10,2),
                total DECIMAL(10,2),
                observaciones TEXT,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
                FOREIGN KEY (tecnico_id) REFERENCES empleados(id) ON DELETE SET NULL,
                FOREIGN KEY (recepcionista_id) REFERENCES empleados(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Crear tabla de historial
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Crear tabla de repuestos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reparaciones_repuestos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reparacion_id INT NOT NULL,
                producto_id INT,
                cantidad INT NOT NULL,
                precio_unitario DECIMAL(10,2) NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        mysql.connection.commit()
        print("Tablas del módulo de reparaciones inicializadas correctamente")
        return True
        
    except Exception as e:
        print(f"Error al inicializar tablas de reparaciones: {e}")
        if cursor and mysql.connection:
            mysql.connection.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
