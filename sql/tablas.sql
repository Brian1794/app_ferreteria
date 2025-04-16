-- Tabla para facturas
CREATE TABLE IF NOT EXISTS facturas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    numero_factura VARCHAR(20) NOT NULL UNIQUE,
    fecha_emision DATETIME NOT NULL,
    fecha_vencimiento DATETIME NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    iva DECIMAL(10,2) NOT NULL,
    total DECIMAL(10,2) NOT NULL,
    estado ENUM('PENDIENTE', 'PAGADA', 'ANULADA') NOT NULL DEFAULT 'PENDIENTE',
    ruta_pdf VARCHAR(255),
    observaciones TEXT,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE
);

-- Tabla para bancos PSE
CREATE TABLE IF NOT EXISTS bancos_pse (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    logo_url VARCHAR(255),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla para pagos PSE
CREATE TABLE IF NOT EXISTS pagos_pse (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    factura_id INT NOT NULL,
    referencia_pago VARCHAR(50) NOT NULL UNIQUE,
    banco_id INT NOT NULL,
    banco_nombre VARCHAR(100) NOT NULL,
    estado ENUM('PENDIENTE', 'APROBADA', 'RECHAZADA', 'EXPIRADA') NOT NULL DEFAULT 'PENDIENTE',
    monto DECIMAL(10,2) NOT NULL,
    fecha_creacion DATETIME NOT NULL,
    fecha_procesado DATETIME,
    tipo_persona ENUM('NATURAL', 'JURIDICA') NOT NULL,
    tipo_documento VARCHAR(20) NOT NULL,
    numero_documento VARCHAR(20) NOT NULL,
    email VARCHAR(100) NOT NULL,
    url_retorno VARCHAR(255) NOT NULL,
    ip_origen VARCHAR(45) NOT NULL,
    user_agent TEXT,
    respuesta_pse TEXT,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (banco_id) REFERENCES bancos_pse(id)
);

-- Insertar bancos PSE de Colombia (principales)
INSERT INTO bancos_pse (nombre, codigo, logo_url, activo) VALUES
('Bancolombia', 'BCL', '/static/img/bancos/bancolombia.png', TRUE),
('Banco de Bogotá', 'BDB', '/static/img/bancos/bogota.png', TRUE),
('Davivienda', 'DVI', '/static/img/bancos/davivienda.png', TRUE),
('BBVA Colombia', 'BBVA', '/static/img/bancos/bbva.png', TRUE),
('Banco de Occidente', 'BOC', '/static/img/bancos/occidente.png', TRUE),
('Banco Popular', 'BPO', '/static/img/bancos/popular.png', TRUE),
('Banco AV Villas', 'AVV', '/static/img/bancos/avvillas.png', TRUE),
('Banco Caja Social', 'BCS', '/static/img/bancos/cajasocial.png', TRUE),
('Scotiabank Colpatria', 'SBC', '/static/img/bancos/colpatria.png', TRUE),
('Banco Agrario', 'BAG', '/static/img/bancos/agrario.png', TRUE),
('Bancoomeva', 'BCO', '/static/img/bancos/bancoomeva.png', TRUE),
('Banco Falabella', 'BFA', '/static/img/bancos/falabella.png', TRUE),
('Banco Pichincha', 'BPI', '/static/img/bancos/pichincha.png', TRUE),
('Banco Itaú', 'BIT', '/static/img/bancos/itau.png', TRUE),
('Banco GNB Sudameris', 'GNB', '/static/img/bancos/gnb.png', TRUE),
('Banco Serfinanza', 'BSF', '/static/img/bancos/serfinanza.png', TRUE); 