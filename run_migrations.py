import importlib
import os
import sys
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migrations():
    """Ejecuta todas las migraciones pendientes"""
    # Verificar que exista el directorio de migraciones
    if not os.path.exists('migrations'):
        logger.error("El directorio 'migrations' no existe")
        return False
    
    # Obtener todos los scripts de migración
    migration_files = [f for f in os.listdir('migrations') 
                      if f.endswith('.py') and f != '__init__.py']
    
    if not migration_files:
        logger.info("No hay migraciones para ejecutar")
        return True
    
    # Ordenar los archivos para ejecutarlos en orden
    migration_files.sort()
    
    # Agregar directorio de migraciones al path para poder importarlos
    if 'migrations' not in sys.path:
        sys.path.append('migrations')
    
    # Ejecutar cada migración
    for migration_file in migration_files:
        logger.info(f"Ejecutando migración: {migration_file}")
        
        try:
            # Quitar extensión .py para importar
            module_name = migration_file[:-3]
            
            # Importar el módulo de migración
            migration_module = importlib.import_module(module_name)
            
            # Ejecutar la migración
            if hasattr(migration_module, 'run_migration'):
                success = migration_module.run_migration()
                
                if success:
                    logger.info(f"Migración {module_name} completada con éxito")
                else:
                    logger.error(f"Error al ejecutar migración {module_name}")
                    return False
            else:
                logger.warning(f"El archivo {migration_file} no tiene una función run_migration()")
        
        except Exception as e:
            logger.error(f"Error al ejecutar migración {migration_file}: {str(e)}")
            return False
    
    logger.info("Todas las migraciones se han ejecutado correctamente")
    return True

if __name__ == "__main__":
    logger.info("Iniciando proceso de migración de base de datos...")
    run_migrations() 