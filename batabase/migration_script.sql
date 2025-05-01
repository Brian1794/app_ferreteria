-- ----------------------------------------------------------------------------
-- MySQL Workbench Migration
-- Migrated Schemata: bzm5uc8abvbfoesn7g5v
-- Source Schemata: bzm5uc8abvbfoesn7g5v
-- Created: Sat Apr 19 11:15:40 2025
-- Workbench Version: 8.0.33
-- ----------------------------------------------------------------------------

SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------------------------
-- Schema bzm5uc8abvbfoesn7g5v
-- ----------------------------------------------------------------------------
DROP SCHEMA IF EXISTS `bzm5uc8abvbfoesn7g5v` ;
CREATE SCHEMA IF NOT EXISTS `bzm5uc8abvbfoesn7g5v` ;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.actividades
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`actividades` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `usuario_id` INT NULL DEFAULT NULL,
  `tipo` VARCHAR(50) NOT NULL,
  `descripcion` TEXT NOT NULL,
  `fecha` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `modulo` VARCHAR(50) NULL DEFAULT NULL,
  `entidad_id` INT NULL DEFAULT NULL,
  `entidad_tipo` VARCHAR(50) NULL DEFAULT NULL,
  `datos_extra` JSON NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_usuario` (`usuario_id` ASC) VISIBLE,
  INDEX `idx_fecha` (`fecha` ASC) VISIBLE,
  INDEX `idx_tipo` (`tipo` ASC) VISIBLE,
  INDEX `idx_modulo` (`modulo` ASC) VISIBLE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.cargos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`cargos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(100) NOT NULL,
  `descripcion` TEXT NULL DEFAULT NULL,
  `permisos` TEXT NULL DEFAULT NULL,
  `activo` TINYINT(1) NULL DEFAULT '1',
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 6
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.carousel
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`carousel` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `titulo` VARCHAR(100) NOT NULL,
  `descripcion` TEXT NULL DEFAULT NULL,
  `imagen` VARCHAR(255) NOT NULL,
  `enlace` VARCHAR(255) NULL DEFAULT NULL,
  `orden` INT NULL DEFAULT '0',
  `activo` TINYINT(1) NULL DEFAULT '1',
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 4
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.carrito_items
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`carrito_items` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `carrito_id` INT NOT NULL,
  `producto_id` INT NOT NULL,
  `cantidad` INT NOT NULL,
  `fecha_agregado` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `carrito_id` (`carrito_id` ASC) VISIBLE,
  INDEX `producto_id` (`producto_id` ASC) VISIBLE,
  CONSTRAINT `carrito_items_ibfk_1`
    FOREIGN KEY (`carrito_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`carritos` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `carrito_items_ibfk_2`
    FOREIGN KEY (`producto_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`productos` (`id`)
    ON DELETE CASCADE)
ENGINE = InnoDB
AUTO_INCREMENT = 59
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.carritos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`carritos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `cliente_id` INT NOT NULL,
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `cliente_id` (`cliente_id` ASC) VISIBLE,
  CONSTRAINT `carritos_ibfk_1`
    FOREIGN KEY (`cliente_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`clientes` (`id`)
    ON DELETE CASCADE)
ENGINE = InnoDB
AUTO_INCREMENT = 6
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.categorias
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`categorias` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(100) NOT NULL,
  `descripcion` VARCHAR(500) NULL DEFAULT NULL,
  `imagen` VARCHAR(2505) NULL DEFAULT NULL,
  `slug` VARCHAR(100) NULL DEFAULT NULL,
  `activo` TINYINT(1) NULL DEFAULT '1',
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 15
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.clientes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`clientes` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(200) NOT NULL,
  `identificacion` VARCHAR(45) NULL DEFAULT NULL,
  `apellido` VARCHAR(100) NULL DEFAULT NULL,
  `email` VARCHAR(100) NULL DEFAULT NULL,
  `password` VARCHAR(255) NOT NULL,
  `direccion` VARCHAR(2055) NULL DEFAULT NULL,
  `telefono` VARCHAR(50) NULL DEFAULT NULL,
  `activo` TINYINT(1) NULL DEFAULT '1',
  `fecha_registro` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `ultimo_login` TIMESTAMP NULL DEFAULT NULL,
  `foto_perfil` VARCHAR(255) NULL DEFAULT NULL,
  `codigo_postal` VARCHAR(20) NULL DEFAULT NULL,
  `ciudad` VARCHAR(100) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `email` (`email` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 9
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.compras
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`compras` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `proveedor` VARCHAR(200) NULL DEFAULT NULL,
  `empleado_id` INT NULL DEFAULT NULL,
  `fecha` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `total` DECIMAL(12,2) NOT NULL,
  `estado` VARCHAR(50) NULL DEFAULT 'COMPLETADA',
  `observaciones` TEXT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `empleado_id` (`empleado_id` ASC) VISIBLE,
  CONSTRAINT `compras_ibfk_1`
    FOREIGN KEY (`empleado_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`empleados` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.configuracion
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`configuracion` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `grupo` VARCHAR(50) NOT NULL COMMENT 'Grupo al que pertenece la configuración',
  `nombre` VARCHAR(100) NOT NULL COMMENT 'Nombre de la configuración',
  `tipo` ENUM('texto', 'numero', 'booleano', 'json') NOT NULL DEFAULT 'texto' COMMENT 'Tipo de dato de la configuración',
  `valor` TEXT NULL DEFAULT NULL COMMENT 'Valor de la configuración',
  `descripcion` TEXT NULL DEFAULT NULL COMMENT 'Descripción de la configuración',
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uk_grupo_nombre` (`grupo` ASC, `nombre` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 19
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.detalles_compra
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`detalles_compra` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `compra_id` INT NOT NULL,
  `producto_id` INT NULL DEFAULT NULL,
  `cantidad` INT NOT NULL,
  `precio_unitario` DECIMAL(12,2) NOT NULL,
  `subtotal` DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `compra_id` (`compra_id` ASC) VISIBLE,
  INDEX `producto_id` (`producto_id` ASC) VISIBLE,
  CONSTRAINT `detalles_compra_ibfk_1`
    FOREIGN KEY (`compra_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`compras` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `detalles_compra_ibfk_2`
    FOREIGN KEY (`producto_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`productos` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.detalles_venta
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`detalles_venta` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `venta_id` INT NOT NULL,
  `producto_id` INT NULL DEFAULT NULL,
  `cantidad` INT NOT NULL,
  `precio_unitario` DECIMAL(12,2) NOT NULL,
  `subtotal` DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `venta_id` (`venta_id` ASC) VISIBLE,
  INDEX `producto_id` (`producto_id` ASC) VISIBLE,
  CONSTRAINT `detalles_venta_ibfk_1`
    FOREIGN KEY (`venta_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`ventas` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `detalles_venta_ibfk_2`
    FOREIGN KEY (`producto_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`productos` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
AUTO_INCREMENT = 11
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.empleados
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`empleados` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(200) NOT NULL,
  `email` VARCHAR(100) NULL DEFAULT NULL,
  `password` VARCHAR(255) NOT NULL,
  `cargo_id` INT NULL DEFAULT NULL,
  `es_admin` TINYINT(1) NULL DEFAULT '0',
  `activo` TINYINT(1) NULL DEFAULT '1',
  `fecha_registro` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `ultimo_login` TIMESTAMP NULL DEFAULT NULL,
  `foto_perfil` VARCHAR(255) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `email` (`email` ASC) VISIBLE,
  INDEX `cargo_id` (`cargo_id` ASC) VISIBLE,
  CONSTRAINT `empleados_ibfk_1`
    FOREIGN KEY (`cargo_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`cargos` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
AUTO_INCREMENT = 5
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.estados_producto
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`estados_producto` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(50) NOT NULL,
  `descripcion` TEXT NULL DEFAULT NULL,
  `color` VARCHAR(20) NULL DEFAULT NULL,
  `activo` TINYINT(1) NULL DEFAULT '1',
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 6
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.facturas
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`facturas` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `numero_factura` VARCHAR(100) NOT NULL,
  `pedido_id` INT NOT NULL,
  `fecha_emision` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_vencimiento` TIMESTAMP NULL DEFAULT NULL,
  `subtotal` DECIMAL(12,2) NOT NULL,
  `iva` DECIMAL(12,2) NOT NULL,
  `total` DECIMAL(12,2) NOT NULL,
  `estado` VARCHAR(50) NULL DEFAULT 'EMITIDA',
  `formato` VARCHAR(50) NULL DEFAULT 'PDF',
  `url_descarga` VARCHAR(255) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `numero_factura` (`numero_factura` ASC) VISIBLE,
  INDEX `pedido_id` (`pedido_id` ASC) VISIBLE,
  CONSTRAINT `facturas_ibfk_1`
    FOREIGN KEY (`pedido_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`pedidos` (`id`)
    ON DELETE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.historial_reparaciones
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`historial_reparaciones` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `reparacion_id` INT NOT NULL,
  `estado_anterior` VARCHAR(50) NULL DEFAULT NULL,
  `estado_nuevo` VARCHAR(50) NOT NULL,
  `descripcion` TEXT NULL DEFAULT NULL,
  `usuario_id` INT NULL DEFAULT NULL,
  `fecha` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `reparacion_id` (`reparacion_id` ASC) VISIBLE,
  INDEX `usuario_id` (`usuario_id` ASC) VISIBLE,
  CONSTRAINT `historial_reparaciones_ibfk_1`
    FOREIGN KEY (`reparacion_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`reparaciones` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `historial_reparaciones_ibfk_2`
    FOREIGN KEY (`usuario_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`empleados` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
AUTO_INCREMENT = 6
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.mensajes_reparacion
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`mensajes_reparacion` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `reparacion_id` INT NOT NULL,
  `remitente_id` INT NOT NULL,
  `remitente_tipo` VARCHAR(20) NOT NULL,
  `remitente_nombre` VARCHAR(100) NOT NULL,
  `destinatario_id` INT NOT NULL,
  `destinatario_tipo` VARCHAR(20) NOT NULL,
  `mensaje` TEXT NOT NULL,
  `leido` TINYINT(1) NULL DEFAULT '0',
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `reparacion_id` (`reparacion_id` ASC) VISIBLE,
  INDEX `remitente_id` (`remitente_id` ASC) VISIBLE,
  INDEX `destinatario_id` (`destinatario_id` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 2
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.modulos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`modulos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(100) NOT NULL,
  `descripcion` TEXT NULL DEFAULT NULL,
  `ruta` VARCHAR(100) NULL DEFAULT NULL,
  `icono` VARCHAR(50) NULL DEFAULT NULL,
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 11
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.notificaciones
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`notificaciones` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `remitente_id` INT NOT NULL,
  `destinatario_id` INT NOT NULL,
  `tipo` VARCHAR(20) NOT NULL,
  `titulo` VARCHAR(255) NOT NULL,
  `mensaje` TEXT NOT NULL,
  `url` VARCHAR(255) NULL DEFAULT '#',
  `icono` VARCHAR(50) NULL DEFAULT 'bell',
  `leida` TINYINT(1) NULL DEFAULT '0',
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_lectura` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 2
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.pagos_pse
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`pagos_pse` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `pedido_id` INT NOT NULL,
  `factura_id` INT NULL DEFAULT NULL,
  `referencia_pago` VARCHAR(100) NOT NULL,
  `banco_id` VARCHAR(50) NOT NULL,
  `banco_nombre` VARCHAR(100) NOT NULL,
  `estado` VARCHAR(50) NULL DEFAULT 'PENDIENTE',
  `monto` DECIMAL(12,2) NOT NULL,
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_procesado` TIMESTAMP NULL DEFAULT NULL,
  `tipo_persona` VARCHAR(10) NOT NULL,
  `tipo_documento` VARCHAR(50) NOT NULL,
  `numero_documento` VARCHAR(50) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `url_retorno` VARCHAR(255) NULL DEFAULT NULL,
  `ip_origen` VARCHAR(50) NULL DEFAULT NULL,
  `user_agent` TEXT NULL DEFAULT NULL,
  `respuesta_pse` TEXT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `referencia_pago` (`referencia_pago` ASC) VISIBLE,
  INDEX `pedido_id` (`pedido_id` ASC) VISIBLE,
  INDEX `factura_id` (`factura_id` ASC) VISIBLE,
  CONSTRAINT `pagos_pse_ibfk_1`
    FOREIGN KEY (`pedido_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`pedidos` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `pagos_pse_ibfk_2`
    FOREIGN KEY (`factura_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`facturas` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.pedido_detalles
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`pedido_detalles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `pedido_id` INT NOT NULL,
  `producto_id` INT NOT NULL,
  `cantidad` INT NOT NULL,
  `precio_unitario` DECIMAL(12,2) NOT NULL,
  `subtotal` DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `pedido_id` (`pedido_id` ASC) VISIBLE,
  INDEX `producto_id` (`producto_id` ASC) VISIBLE,
  CONSTRAINT `pedido_detalles_ibfk_1`
    FOREIGN KEY (`pedido_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`pedidos` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `pedido_detalles_ibfk_2`
    FOREIGN KEY (`producto_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`productos` (`id`)
    ON DELETE CASCADE)
ENGINE = InnoDB
AUTO_INCREMENT = 46
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.pedidos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`pedidos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `cliente_id` INT NOT NULL,
  `fecha_pedido` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `estado` VARCHAR(50) NULL DEFAULT 'PENDIENTE',
  `total` DECIMAL(12,2) NOT NULL,
  `metodo_pago` VARCHAR(50) NULL DEFAULT NULL,
  `referencia_pago` VARCHAR(100) NULL DEFAULT NULL,
  `direccion_envio` TEXT NULL DEFAULT NULL,
  `telefono` VARCHAR(50) NULL DEFAULT NULL,
  `identificacion` VARCHAR(50) NULL DEFAULT NULL,
  `notas` TEXT NULL DEFAULT NULL,
  `subtotal` DECIMAL(10,2) NOT NULL DEFAULT '0.00',
  `costo_envio` DECIMAL(10,2) NOT NULL DEFAULT '0.00',
  PRIMARY KEY (`id`),
  INDEX `cliente_id` (`cliente_id` ASC) VISIBLE,
  CONSTRAINT `pedidos_ibfk_1`
    FOREIGN KEY (`cliente_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`clientes` (`id`)
    ON DELETE CASCADE)
ENGINE = InnoDB
AUTO_INCREMENT = 45
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.permisos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`permisos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `cargo_id` INT NULL DEFAULT NULL,
  `modulo_id` INT NULL DEFAULT NULL,
  `puede_ver` TINYINT(1) NULL DEFAULT '0',
  `puede_crear` TINYINT(1) NULL DEFAULT '0',
  `puede_editar` TINYINT(1) NULL DEFAULT '0',
  `puede_eliminar` TINYINT(1) NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  INDEX `cargo_id` (`cargo_id` ASC) VISIBLE,
  INDEX `modulo_id` (`modulo_id` ASC) VISIBLE,
  CONSTRAINT `permisos_ibfk_1`
    FOREIGN KEY (`cargo_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`cargos` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `permisos_ibfk_2`
    FOREIGN KEY (`modulo_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`modulos` (`id`)
    ON DELETE CASCADE)
ENGINE = InnoDB
AUTO_INCREMENT = 11
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.productos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`productos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `codigo` VARCHAR(50) NULL DEFAULT NULL,
  `nombre` VARCHAR(200) NOT NULL,
  `descripcion` TEXT NULL DEFAULT NULL,
  `precio_venta` VARCHAR(50) NOT NULL,
  `precio_compra` VARCHAR(50) NULL DEFAULT NULL,
  `stock` INT NULL DEFAULT '0',
  `stock_minimo` INT NULL DEFAULT '5',
  `categoria_id` INT NULL DEFAULT NULL,
  `estado_id` INT NULL DEFAULT NULL,
  `imagen` VARCHAR(2055) NULL DEFAULT NULL,
  `activo` TINYINT(1) NULL DEFAULT '1',
  `destacado` TINYINT(1) NULL DEFAULT '0',
  `codigo_barras` VARCHAR(100) NULL DEFAULT NULL,
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_actualizacion` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `codigo` (`codigo` ASC) VISIBLE,
  INDEX `categoria_id` (`categoria_id` ASC) VISIBLE,
  INDEX `estado_id` (`estado_id` ASC) VISIBLE,
  CONSTRAINT `productos_ibfk_1`
    FOREIGN KEY (`categoria_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`categorias` (`id`)
    ON DELETE SET NULL,
  CONSTRAINT `productos_ibfk_2`
    FOREIGN KEY (`estado_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`estados_producto` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
AUTO_INCREMENT = 22
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.reparaciones
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`reparaciones` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `cliente_id` INT NULL DEFAULT NULL,
  `tecnico_id` INT NULL DEFAULT NULL,
  `recepcionista_id` INT NULL DEFAULT NULL,
  `descripcion` TEXT NOT NULL,
  `electrodomestico` VARCHAR(100) NULL DEFAULT NULL,
  `marca` VARCHAR(100) NULL DEFAULT NULL,
  `modelo` VARCHAR(100) NULL DEFAULT NULL,
  `problema` TEXT NULL DEFAULT NULL,
  `diagnostico` TEXT NULL DEFAULT NULL,
  `notas` TEXT NULL DEFAULT NULL,
  `estado` VARCHAR(50) NULL DEFAULT 'RECIBIDO',
  `costo_estimado` DECIMAL(12,2) NULL DEFAULT '0.00',
  `costo_final` DECIMAL(12,2) NULL DEFAULT '0.00',
  `fecha_recepcion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_entrega_estimada` DATE NULL DEFAULT NULL,
  `fecha_entrega` DATE NULL DEFAULT NULL,
  `fecha_actualizacion` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `cliente_id` (`cliente_id` ASC) VISIBLE,
  INDEX `tecnico_id` (`tecnico_id` ASC) VISIBLE,
  INDEX `recepcionista_id` (`recepcionista_id` ASC) VISIBLE,
  CONSTRAINT `reparaciones_ibfk_1`
    FOREIGN KEY (`cliente_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`clientes` (`id`)
    ON DELETE SET NULL,
  CONSTRAINT `reparaciones_ibfk_2`
    FOREIGN KEY (`tecnico_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`empleados` (`id`)
    ON DELETE SET NULL,
  CONSTRAINT `reparaciones_ibfk_3`
    FOREIGN KEY (`recepcionista_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`empleados` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
AUTO_INCREMENT = 11
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.reparaciones_repuestos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`reparaciones_repuestos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `reparacion_id` INT NOT NULL,
  `producto_id` INT NULL DEFAULT NULL,
  `repuesto_descripcion` TEXT NOT NULL,
  `cantidad` INT NOT NULL,
  `precio_unitario` DECIMAL(12,2) NOT NULL,
  `subtotal` DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `reparacion_id` (`reparacion_id` ASC) VISIBLE,
  INDEX `producto_id` (`producto_id` ASC) VISIBLE,
  CONSTRAINT `reparaciones_repuestos_ibfk_1`
    FOREIGN KEY (`reparacion_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`reparaciones` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `reparaciones_repuestos_ibfk_2`
    FOREIGN KEY (`producto_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`productos` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.reset_tokens
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`reset_tokens` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `user_type` VARCHAR(20) NOT NULL,
  `token` VARCHAR(255) NOT NULL,
  `expiracion` DATETIME NOT NULL,
  `usado` TINYINT(1) NULL DEFAULT '0',
  `expiration` DATETIME NOT NULL,
  `used` TINYINT(1) NULL DEFAULT '0',
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `token` (`token` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 3
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.ventas
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`ventas` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `cliente_id` INT NULL DEFAULT NULL,
  `empleado_id` INT NULL DEFAULT NULL,
  `fecha` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `total` DECIMAL(12,2) NOT NULL,
  `estado` VARCHAR(50) NULL DEFAULT 'COMPLETADA',
  `observaciones` TEXT NULL DEFAULT NULL,
  `tipo_pago` VARCHAR(50) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `cliente_id` (`cliente_id` ASC) VISIBLE,
  INDEX `empleado_id` (`empleado_id` ASC) VISIBLE,
  CONSTRAINT `ventas_ibfk_1`
    FOREIGN KEY (`cliente_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`clientes` (`id`)
    ON DELETE SET NULL,
  CONSTRAINT `ventas_ibfk_2`
    FOREIGN KEY (`empleado_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`empleados` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
AUTO_INCREMENT = 6
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.whatsapp_mensajes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`whatsapp_mensajes` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `telefono` VARCHAR(50) NOT NULL,
  `mensaje` TEXT NOT NULL,
  `tipo_mensaje` VARCHAR(50) NULL DEFAULT 'MANUAL',
  `estado` VARCHAR(50) NULL DEFAULT 'ENVIADO',
  `error` TEXT NULL DEFAULT NULL,
  `fecha_envio` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `objeto_tipo` VARCHAR(50) NULL DEFAULT NULL,
  `objeto_id` INT NULL DEFAULT NULL,
  `plantilla_id` INT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `plantilla_id` (`plantilla_id` ASC) VISIBLE,
  CONSTRAINT `whatsapp_mensajes_ibfk_1`
    FOREIGN KEY (`plantilla_id`)
    REFERENCES `bzm5uc8abvbfoesn7g5v`.`whatsapp_plantillas` (`id`)
    ON DELETE SET NULL)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table bzm5uc8abvbfoesn7g5v.whatsapp_plantillas
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `bzm5uc8abvbfoesn7g5v`.`whatsapp_plantillas` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(100) NOT NULL,
  `contenido` TEXT NOT NULL,
  `variables` TEXT NULL DEFAULT NULL,
  `tipo` VARCHAR(50) NULL DEFAULT NULL,
  `activo` TINYINT(1) NULL DEFAULT '1',
  `fecha_creacion` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `nombre` (`nombre` ASC) VISIBLE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;
SET FOREIGN_KEY_CHECKS = 1;
