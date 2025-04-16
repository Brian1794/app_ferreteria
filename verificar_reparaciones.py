from app import app, mysql
import sys
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verificar_tabla_reparaciones():
    try:
        logger.info("Conectando a la base de datos...")
        with app.app_context():
            # Verificar que mysql existe y tiene el atributo connection
            if not hasattr(mysql, 'connection'):
                logger.error("Objeto mysql no tiene atributo connection")
                return False
                
            # Obtener la conexión de manera segura
            connection = mysql.connection
            if not connection:
                logger.error("No se pudo establecer conexión a la base de datos")
                return False
            
            cursor = connection.cursor()
            if not cursor:
                logger.error("No se pudo obtener el cursor de la base de datos")
                return False
            
            # Verificar si la tabla existe
            cursor.execute("SHOW TABLES LIKE 'reparaciones'")
            if cursor.fetchone():
                logger.info("Tabla 'reparaciones' encontrada")
                
                # Describir la estructura de la tabla
                cursor.execute("DESCRIBE reparaciones")
                columnas = cursor.fetchall()
                
                logger.info("Estructura de la tabla reparaciones:")
                for columna in columnas:
                    logger.info(f"{columna[0]} - {columna[1]} - {columna[2]}")
                
                # Verificar campos necesarios para registro de solicitud
                campos_requeridos = {
                    'cliente_id': False,
                    'electrodomestico': False,
                    'marca': False,
                    'modelo': False,
                    'problema': False,
                    'estado': False,
                    'fecha_solicitud': False
                }
                
                for columna in columnas:
                    if columna[0] in campos_requeridos:
                        campos_requeridos[columna[0]] = True
                
                # Verificar campos faltantes
                campos_faltantes = [campo for campo, existe in campos_requeridos.items() if not existe]
                if campos_faltantes:
                    logger.info("CAMPOS FALTANTES en la tabla reparaciones:")
                    for campo in campos_faltantes:
                        logger.info(f" - {campo}")
                    
                    # Agregar campos faltantes
                    logger.info("Agregando campos faltantes...")
                    for campo in campos_faltantes:
                        try:
                            if campo == 'fecha_solicitud':
                                cursor.execute(f"ALTER TABLE reparaciones ADD COLUMN {campo} DATETIME")
                            elif campo == 'cliente_id':
                                cursor.execute(f"ALTER TABLE reparaciones ADD COLUMN {campo} INT, ADD FOREIGN KEY (cliente_id) REFERENCES clientes(id)")
                            elif campo == 'estado':
                                cursor.execute(f"ALTER TABLE reparaciones ADD COLUMN {campo} VARCHAR(50)")
                            elif campo == 'problema':
                                cursor.execute(f"ALTER TABLE reparaciones ADD COLUMN {campo} TEXT")
                            else:
                                cursor.execute(f"ALTER TABLE reparaciones ADD COLUMN {campo} VARCHAR(255)")
                            logger.info(f"Campo {campo} agregado correctamente")
                        except Exception as field_error:
                            logger.error(f"Error al agregar campo {campo}: {str(field_error)}")
                    
                    connection.commit()
                    logger.info("Cambios en la estructura de la tabla guardados correctamente.")
                else:
                    logger.info("Todos los campos requeridos existen en la tabla.")
                
                # Verificar si hay datos en la tabla
                cursor.execute("SELECT COUNT(*) FROM reparaciones")
                count = cursor.fetchone()[0]
                logger.info(f"La tabla tiene {count} registros.")
                
            else:
                logger.warning("La tabla 'reparaciones' no existe.")
                logger.info("Creando tabla reparaciones...")
                
                # Crear la tabla si no existe
                create_table_sql = """
                CREATE TABLE reparaciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cliente_id INT,
                    electrodomestico VARCHAR(255),
                    marca VARCHAR(255),
                    modelo VARCHAR(255),
                    problema TEXT,
                    estado VARCHAR(50) DEFAULT 'PENDIENTE',
                    fecha_solicitud DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
                )
                """
                try:
                    cursor.execute(create_table_sql)
                    connection.commit()
                    logger.info("Tabla reparaciones creada exitosamente")
                except Exception as create_error:
                    logger.error(f"Error al crear tabla reparaciones: {str(create_error)}")
                    connection.rollback()
            
            cursor.close()
            return True
        
    except Exception as e:
        logger.error(f"Error al verificar tabla reparaciones: {str(e)}")
        return False

if __name__ == "__main__":
    resultado = verificar_tabla_reparaciones()
    if resultado:
        logger.info("Verificación completada exitosamente")
    else:
        logger.error("La verificación falló") 