import os
import sys
from flask import Flask
from dotenv import load_dotenv
import MySQLdb

# Cargar variables de entorno
load_dotenv()

# Configuración de la base de datos
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB = os.environ.get('MYSQL_DB', 'ferreteria')

print("=== Script de reconstrucción de la base de datos ===")
print(f"Host: {MYSQL_HOST}")
print(f"Usuario: {MYSQL_USER}")
print(f"Base de datos: {MYSQL_DB}")

# Confirmar antes de continuar
confirm = input("Este script eliminará y recreará TODA la base de datos. ¿Está seguro? (s/n): ")
if confirm.lower() != 's':
    print("Operación cancelada.")
    sys.exit(0)

# Conectar a MySQL sin especificar base de datos
try:
    # Conexión sin base de datos específica
    conn = MySQLdb.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        passwd=MYSQL_PASSWORD
    )
    cursor = conn.cursor()
    print("Conexión establecida a MySQL")
except Exception as e:
    print(f"Error al conectar a MySQL: {e}")
    sys.exit(1)

# Eliminar y recrear la base de datos
try:
    # Eliminar base de datos si existe
    cursor.execute(f"DROP DATABASE IF EXISTS {MYSQL_DB}")
    print(f"Base de datos {MYSQL_DB} eliminada (si existía)")
    
    # Crear nueva base de datos
    cursor.execute(f"CREATE DATABASE {MYSQL_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"Base de datos {MYSQL_DB} creada correctamente")
    
    # Usar la base de datos
    cursor.execute(f"USE {MYSQL_DB}")
except Exception as e:
    print(f"Error al recrear la base de datos: {e}")
    conn.close()
    sys.exit(1)

# Crear tablas
print("Creando tablas...")

# NOTA: Estas sentencias SQL deben ser consistentes con models/models.py
# pero corregidas para asegurar que todo funcione sin errores

table_queries = [
    # Tabla de estados de producto
    '''
    CREATE TABLE IF NOT EXISTS estados_producto (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(50) NOT NULL,
        descripcion TEXT,
        color VARCHAR(20),
        activo BOOLEAN DEFAULT TRUE
    )
    ''',
    
    # Tabla de categorías
    '''
    CREATE TABLE IF NOT EXISTS categorias (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        descripcion TEXT,
        imagen VARCHAR(255),
        slug VARCHAR(100),
        activo BOOLEAN DEFAULT TRUE,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    
    # Tabla de cargos
    '''
    CREATE TABLE IF NOT EXISTS cargos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        descripcion TEXT,
        permisos TEXT,
        activo BOOLEAN DEFAULT TRUE
    )
    ''',
    
    # Tabla de módulos del sistema
    '''
    CREATE TABLE IF NOT EXISTS modulos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        descripcion TEXT,
        ruta VARCHAR(100),
        icono VARCHAR(50)
    )
    ''',
    
    # Tabla de productos (depende de categorías y estados)
    '''
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
    ''',
    
    # Tabla de clientes
    '''
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
    ''',
    
    # Tabla de empleados
    '''
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
    ''',
    
    # Tabla de permisos por cargo
    '''
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
    ''',
    
    # Tabla de ventas
    '''
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
    ''',
    
    # Tabla de detalle de ventas
    '''
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
    ''',
    
    # Tabla de compras
    '''
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
    ''',
    
    # Tabla de detalle de compras
    '''
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
    ''',
    
    # Tabla de reparaciones
    '''
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
    ''',
    
    # Tabla de historial de reparaciones
    '''
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
    ''',
    
    # Tabla de repuestos para reparaciones
    '''
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
    ''',
    
    # Tabla de configuración
    '''
    CREATE TABLE IF NOT EXISTS configuracion (
        id INT AUTO_INCREMENT PRIMARY KEY,
        grupo VARCHAR(100) NOT NULL,
        nombre VARCHAR(100) NOT NULL,
        valor TEXT,
        descripcion TEXT,
        UNIQUE KEY grupo_nombre (grupo, nombre)
    )
    ''',
    
    # Tabla de plantillas de WhatsApp
    '''
    CREATE TABLE IF NOT EXISTS whatsapp_plantillas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL UNIQUE,
        contenido TEXT NOT NULL,
        variables TEXT,
        tipo VARCHAR(50),
        activo BOOLEAN DEFAULT TRUE,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''',
    
    # Tabla de mensajes de WhatsApp enviados
    '''
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
    '''
]

# Ejecutar las consultas de creación de tablas
for i, query in enumerate(table_queries):
    try:
        cursor.execute(query)
        print(f"Tabla {i+1}/{len(table_queries)} creada correctamente")
    except Exception as e:
        print(f"Error al crear tabla {i+1}: {e}")

# Insertar datos iniciales
print("\nInsertando datos iniciales...")

# Insertar estados de producto
estados = [
    ('Disponible', 'Producto en stock y listo para venta', '#28a745'),
    ('Agotado', 'Sin existencias', '#dc3545'),
    ('Por llegar', 'Producto ordenado pero aún no recibido', '#ffc107'),
    ('Descontinuado', 'Producto que ya no se venderá', '#6c757d'),
    ('Promoción', 'Producto en oferta especial', '#17a2b8')
]

try:
    for nombre, descripcion, color in estados:
        cursor.execute('''
            INSERT INTO estados_producto (nombre, descripcion, color, activo)
            VALUES (%s, %s, %s, %s)
        ''', (nombre, descripcion, color, True))
    print("Estados de producto creados con éxito")
except Exception as e:
    print(f"Error al crear estados de producto: {e}")

# Insertar cargos
cargos = [
    ('Administrador', 'Control total del sistema'),
    ('Vendedor', 'Gestión de ventas y atención al cliente'),
    ('Técnico', 'Encargado de reparaciones'),
    ('Almacenista', 'Gestión de inventario')
]

try:
    for nombre, descripcion in cargos:
        cursor.execute('''
            INSERT INTO cargos (nombre, descripcion, activo)
            VALUES (%s, %s, %s)
        ''', (nombre, descripcion, True))
    print("Cargos creados con éxito")
except Exception as e:
    print(f"Error al crear cargos: {e}")

# Insertar usuario administrador
try:
    # Usar una contraseña sencilla para desarrollo
    cursor.execute('''
        INSERT INTO empleados (nombre, email, password, es_admin, activo)
        VALUES (%s, %s, %s, %s, %s)
    ''', ('Administrador', 'admin@ferreteria.com', 'admin123', True, True))
    print("Usuario administrador creado con éxito")
except Exception as e:
    print(f"Error al crear usuario administrador: {e}")

# Insertar módulos
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

try:
    for nombre, descripcion, ruta, icono in modulos:
        cursor.execute('''
            INSERT INTO modulos (nombre, descripcion, ruta, icono)
            VALUES (%s, %s, %s, %s)
        ''', (nombre, descripcion, ruta, icono))
    print("Módulos creados con éxito")
except Exception as e:
    print(f"Error al crear módulos: {e}")

# Insertar configuraciones básicas
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

try:
    for grupo, nombre, valor, descripcion in configuraciones:
        cursor.execute('''
            INSERT INTO configuracion (grupo, nombre, valor, descripcion)
            VALUES (%s, %s, %s, %s)
        ''', (grupo, nombre, valor, descripcion))
    print("Configuraciones básicas creadas con éxito")
except Exception as e:
    print(f"Error al crear configuraciones: {e}")

# Asignar permisos al administrador
try:
    # Obtener ID del cargo de Administrador
    cursor.execute('SELECT id FROM cargos WHERE nombre = %s', ('Administrador',))
    admin_cargo = cursor.fetchone()
    
    if admin_cargo:
        admin_id = admin_cargo[0]
        
        # Obtener todos los módulos
        cursor.execute('SELECT id FROM modulos')
        modulos = cursor.fetchall()
        
        # Asignar todos los permisos al administrador
        for modulo in modulos:
            modulo_id = modulo[0]
            cursor.execute('''
                INSERT INTO permisos (cargo_id, modulo_id, puede_ver, puede_crear, puede_editar, puede_eliminar)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (admin_id, modulo_id, True, True, True, True))
            
        print("Permisos para administrador creados con éxito")
except Exception as e:
    print(f"Error al asignar permisos: {e}")

# Confirmar cambios
conn.commit()
print("\n¡Base de datos recreada e inicializada correctamente!")
print("Ahora puede reiniciar la aplicación.")

# Cerrar conexiones
cursor.close()
conn.close() 