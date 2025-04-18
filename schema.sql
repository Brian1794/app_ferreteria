-- Archivo schema.sql
-- Esquema de base de datos para Ferretería La U

-- Aumentar el límite de conexiones máximas de usuario
SET GLOBAL max_user_connections = 20;

-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS ferreteria_la_u;
USE ferreteria_la_u;

-- Tabla de Categorías de Productos
CREATE TABLE IF NOT EXISTS categorias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabla de Estados de Producto
CREATE TABLE IF NOT EXISTS estados_producto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT,
    color VARCHAR(20) DEFAULT '#cccccc',
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Proveedores
CREATE TABLE IF NOT EXISTS proveedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    contacto VARCHAR(100),
    telefono VARCHAR(20),
    email VARCHAR(100),
    direccion TEXT,
    notas TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabla de Productos
CREATE TABLE IF NOT EXISTS productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    codigo VARCHAR(30) UNIQUE,
    precio_compra DECIMAL(10,2) NOT NULL,
    precio_venta DECIMAL(10,2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    stock_minimo INT DEFAULT 5,
    categoria_id INT,
    proveedor_id INT,
    imagen VARCHAR(255),
    estado_id INT,
    activo BOOLEAN DEFAULT TRUE,
    destacado BOOLEAN DEFAULT FALSE,
    ubicacion VARCHAR(100),
    unidad_medida VARCHAR(20) DEFAULT 'unidad',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL,
    FOREIGN KEY (estado_id) REFERENCES estados_producto(id) ON DELETE SET NULL
);

-- Tabla de Cargos
CREATE TABLE IF NOT EXISTS cargos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Módulos
CREATE TABLE IF NOT EXISTS modulos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT,
    ruta VARCHAR(100),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Permisos
CREATE TABLE IF NOT EXISTS permisos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cargo_id INT NOT NULL,
    modulo_id INT NOT NULL,
    puede_ver BOOLEAN DEFAULT FALSE,
    puede_crear BOOLEAN DEFAULT FALSE,
    puede_editar BOOLEAN DEFAULT FALSE,
    puede_eliminar BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cargo_id) REFERENCES cargos(id) ON DELETE CASCADE,
    FOREIGN KEY (modulo_id) REFERENCES modulos(id) ON DELETE CASCADE
);

-- Tabla de Clientes
CREATE TABLE IF NOT EXISTS clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255),
    direccion TEXT,
    telefono VARCHAR(20),
    activo BOOLEAN DEFAULT TRUE,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultima_compra TIMESTAMP NULL,
    notas TEXT
);

-- Tabla de Empleados
CREATE TABLE IF NOT EXISTS empleados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    cargo_id INT,
    es_admin BOOLEAN DEFAULT FALSE,
    activo BOOLEAN DEFAULT TRUE,
    fecha_contratacion DATE,
    telefono VARCHAR(20),
    direccion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (cargo_id) REFERENCES cargos(id) ON DELETE SET NULL
);

-- Tabla de Ventas
CREATE TABLE IF NOT EXISTS ventas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT,
    empleado_id INT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subtotal DECIMAL(10,2) NOT NULL,
    impuesto DECIMAL(10,2) DEFAULT 0,
    descuento DECIMAL(10,2) DEFAULT 0,
    total DECIMAL(10,2) NOT NULL,
    metodo_pago ENUM('Efectivo', 'Tarjeta', 'Transferencia', 'Otro') NOT NULL,
    estado ENUM('Completada', 'Pendiente', 'Cancelada') DEFAULT 'Completada',
    notas TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE SET NULL
);

-- Detalle de cada Venta
CREATE TABLE IF NOT EXISTS detalle_ventas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    venta_id INT NOT NULL,
    producto_id INT,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    descuento DECIMAL(10,2) DEFAULT 0,
    subtotal DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
);

-- Tabla de Compras (abastecimiento)
CREATE TABLE IF NOT EXISTS compras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    proveedor_id INT,
    empleado_id INT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subtotal DECIMAL(10,2) NOT NULL,
    impuesto DECIMAL(10,2) DEFAULT 0,
    total DECIMAL(10,2) NOT NULL,
    estado ENUM('Recibida', 'Pendiente', 'Cancelada') DEFAULT 'Recibida',
    numero_factura VARCHAR(30),
    notas TEXT,
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE SET NULL
);

-- Detalle de cada Compra
CREATE TABLE IF NOT EXISTS detalle_compras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    compra_id INT NOT NULL,
    producto_id INT,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
);

-- Tabla de Reparaciones de Electrodomésticos
CREATE TABLE IF NOT EXISTS reparaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT,
    descripcion TEXT NOT NULL,
    diagnostico TEXT,
    aparato VARCHAR(100) NOT NULL,
    marca VARCHAR(50),
    modelo VARCHAR(50),
    num_serie VARCHAR(50),
    estado ENUM('RECIBIDO', 'DIAGNOSTICADO', 'EN_REPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO') DEFAULT 'RECIBIDO',
    costo_estimado DECIMAL(10,2),
    costo_final DECIMAL(10,2),
    adelanto DECIMAL(10,2) DEFAULT 0,
    fecha_recepcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_entrega_estimada DATE,
    fecha_entrega TIMESTAMP NULL,
    tecnico_id INT,
    notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL,
    FOREIGN KEY (tecnico_id) REFERENCES empleados(id) ON DELETE SET NULL
);

-- Tabla de Repuestos usados en Reparaciones
CREATE TABLE IF NOT EXISTS repuestos_reparacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reparacion_id INT NOT NULL,
    producto_id INT,
    descripcion VARCHAR(100) NOT NULL,
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE SET NULL
);

-- Tabla de Historial de Reparaciones (Seguimiento de cambios)
CREATE TABLE IF NOT EXISTS historial_reparaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reparacion_id INT NOT NULL,
    estado_anterior ENUM('RECIBIDO', 'DIAGNOSTICADO', 'EN_REPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO'),
    estado_nuevo ENUM('RECIBIDO', 'DIAGNOSTICADO', 'EN_REPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO'),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    empleado_id INT,
    notas TEXT,
    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE CASCADE,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE SET NULL
);

-- Tabla de Mensajes de WhatsApp
CREATE TABLE IF NOT EXISTS mensajes_whatsapp (
    id INT AUTO_INCREMENT PRIMARY KEY,
    destinatario VARCHAR(20) NOT NULL,
    mensaje TEXT NOT NULL,
    tipo ENUM('INDIVIDUAL', 'GRUPAL') DEFAULT 'INDIVIDUAL',
    estado ENUM('ENVIADO', 'ENTREGADO', 'LEIDO', 'FALLIDO') DEFAULT 'ENVIADO',
    error TEXT,
    enviado_por INT,
    fecha_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enviado_por) REFERENCES empleados(id) ON DELETE SET NULL
);

-- Tabla de Plantillas de Mensajes
CREATE TABLE IF NOT EXISTS plantillas_whatsapp (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    contenido TEXT NOT NULL,
    variables JSON,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabla de Configuración de Mensajes Automáticos
CREATE TABLE IF NOT EXISTS config_whatsapp_auto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    evento ENUM('NUEVA_REPARACION', 'CAMBIO_ESTADO_REPARACION', 'COMPRA_COMPLETADA', 'RECORDATORIO') NOT NULL,
    plantilla_id INT,
    activo BOOLEAN DEFAULT TRUE,
    delay_minutos INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (plantilla_id) REFERENCES plantillas_whatsapp(id) ON DELETE SET NULL
);

-- Tabla de Configuración de la Aplicación
CREATE TABLE IF NOT EXISTS configuracion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clave VARCHAR(50) UNIQUE NOT NULL,
    valor TEXT,
    tipo ENUM('string', 'number', 'boolean', 'json') DEFAULT 'string',
    descripcion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabla de Logs del Sistema
CREATE TABLE IF NOT EXISTS logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT,
    accion TEXT NOT NULL,
    tabla VARCHAR(50),
    registro_id INT,
    detalles TEXT,
    ip VARCHAR(50),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES empleados(id) ON DELETE SET NULL
);

-- Tabla de Contabilidad (Ingresos/Egresos)
CREATE TABLE IF NOT EXISTS contabilidad (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo ENUM('INGRESO', 'EGRESO') NOT NULL,
    monto DECIMAL(10,2) NOT NULL,
    concepto VARCHAR(100) NOT NULL,
    descripcion TEXT,
    venta_id INT,
    compra_id INT,
    reparacion_id INT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    empleado_id INT,
    FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE SET NULL,
    FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE SET NULL,
    FOREIGN KEY (reparacion_id) REFERENCES reparaciones(id) ON DELETE SET NULL,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE SET NULL
);

-- Tabla de Pedidos
CREATE TABLE IF NOT EXISTS pedidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    fecha_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(50) DEFAULT 'PENDIENTE',
    total DECIMAL(12,2) NOT NULL,
    metodo_pago VARCHAR(50),
    referencia_pago VARCHAR(100),
    direccion_envio TEXT,
    telefono VARCHAR(50),
    identificacion VARCHAR(50),
    notas TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);

-- Inserta datos iniciales

-- Estados de Producto
INSERT INTO estados_producto (nombre, descripcion, color) VALUES 
('Disponible', 'Producto disponible para la venta', '#28a745'),
('Agotado', 'Sin existencias en inventario', '#dc3545'),
('Bajo Inventario', 'Stock por debajo del mínimo', '#ffc107'),
('Descontinuado', 'Ya no se venderá este producto', '#6c757d'),
('En Camino', 'Producto ordenado, pendiente de recibir', '#17a2b8');

-- Cargos básicos
INSERT INTO cargos (nombre, descripcion) VALUES 
('Administrador', 'Control total del sistema'),
('Vendedor', 'Atención a clientes y ventas'),
('Técnico', 'Reparación de electrodomésticos'),
('Almacenista', 'Control de inventario');

-- Módulos del sistema
INSERT INTO modulos (nombre, descripcion, ruta) VALUES 
('productos', 'Gestión de productos', '/productos'),
('ventas', 'Registro y consulta de ventas', '/ventas'),
('clientes', 'Administración de clientes', '/clientes'),
('empleados', 'Gestión de personal', '/empleados'),
('reparaciones', 'Reparaciones de electrodomésticos', '/reparaciones'),
('reportes', 'Reportes y estadísticas', '/reportes'),
('configuracion', 'Configuración del sistema', '/admin/configuracion'),
('whatsapp', 'Mensajería y marketing WhatsApp', '/whatsapp');

-- Permisos para Administrador
INSERT INTO permisos (cargo_id, modulo_id, puede_ver, puede_crear, puede_editar, puede_eliminar)
SELECT 1, id, true, true, true, true FROM modulos;

-- Permisos para Vendedor
INSERT INTO permisos (cargo_id, modulo_id, puede_ver, puede_crear, puede_editar, puede_eliminar)
SELECT 2, id, true, 
    CASE WHEN nombre IN ('ventas', 'clientes', 'productos') THEN true ELSE false END,
    CASE WHEN nombre IN ('ventas', 'clientes') THEN true ELSE false END,
    CASE WHEN nombre = 'ventas' THEN true ELSE false END
FROM modulos;

-- Permisos para Técnico
INSERT INTO permisos (cargo_id, modulo_id, puede_ver, puede_crear, puede_editar, puede_eliminar)
SELECT 3, id, 
    CASE WHEN nombre IN ('reparaciones', 'productos', 'clientes') THEN true ELSE false END,
    CASE WHEN nombre = 'reparaciones' THEN true ELSE false END,
    CASE WHEN nombre = 'reparaciones' THEN true ELSE false END,
    false
FROM modulos;

-- Configuración de la aplicación
INSERT INTO configuracion (clave, valor, tipo, descripcion) VALUES
('nombre_empresa', 'Ferretería La U', 'string', 'Nombre de la empresa'),
('direccion', 'Calle Principal #123', 'string', 'Dirección física'),
('telefono', '123-456-7890', 'string', 'Teléfono de contacto'),
('email', 'contacto@ferreterialaU.com', 'string', 'Email de contacto'),
('impuesto', '16', 'number', 'Porcentaje de impuesto (IVA)'),
('logo', 'logo.png', 'string', 'Ruta al logo de la empresa'),
('whatsapp_api_key', '', 'string', 'API Key para WhatsApp Business API'),
('whatsapp_phone', '', 'string', 'Número de teléfono para WhatsApp');

-- Usuario administrador inicial (password: admin123)
INSERT INTO empleados (nombre, email, password, cargo_id, es_admin, activo) VALUES
('Administrador', 'admin@ferreterialaU.com', '$2b$12$1IY4.xPFJ1p9vGZMc96QAOYBFnHFNdYGVy3QbT7jLe4tYPMvbOAjK', 1, true, true);

-- Categorías iniciales
INSERT INTO categorias (nombre, descripcion) VALUES
('Herramientas Manuales', 'Herramientas para uso sin electricidad'),
('Herramientas Eléctricas', 'Herramientas que funcionan con electricidad'),
('Tornillería', 'Tornillos, tuercas, clavos y similares'),
('Fontanería', 'Productos para instalaciones de agua'),
('Electricidad', 'Productos para instalaciones eléctricas'),
('Pintura', 'Pinturas, brochas y accesorios'),
('Jardinería', 'Productos para jardinería');

-- Proveedores iniciales
INSERT INTO proveedores (nombre, contacto, telefono, email) VALUES
('Herramientas SA', 'Juan Pérez', '123-456-7890', 'contacto@herramientas.com'),
('Distribuidora Eléctrica', 'María González', '987-654-3210', 'ventas@distribuidora.com');

-- Productos iniciales
INSERT INTO productos (nombre, descripcion, codigo, precio_compra, precio_venta, stock, categoria_id, proveedor_id, estado_id) VALUES
('Martillo Carpintero', 'Martillo profesional para carpintería', 'HM-001', 80.00, 120.00, 15, 1, 1, 1),
('Destornillador Phillips', 'Destornillador de cruz profesional', 'DP-002', 25.00, 45.00, 20, 1, 1, 1),
('Taladro Percutor', 'Taladro con función de martillo', 'TE-001', 700.00, 1200.00, 5, 2, 2, 1),
('Pintura Vinílica Blanca 1L', 'Pintura para interiores lavable', 'PB-001', 60.00, 95.00, 10, 6, 2, 1);