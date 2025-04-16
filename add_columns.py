from app import create_app
from extensions import mysql

def agregar_columnas_clientes():
    """Agrega columnas faltantes a la tabla clientes"""
    print("Agregando columnas a la tabla clientes...")
    
    try:
        # Crear contexto de aplicación
        app = create_app()
        with app.app_context():
            cursor = mysql.connection.cursor()
            
            # Verificar y agregar columna apellido 
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'apellido'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE clientes ADD COLUMN apellido VARCHAR(100) DEFAULT ''")
                print("Columna 'apellido' agregada correctamente")
            else:
                print("La columna 'apellido' ya existe")
                
            # Verificar y agregar columna codigo_postal
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'codigo_postal'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE clientes ADD COLUMN codigo_postal VARCHAR(20) DEFAULT NULL")
                print("Columna 'codigo_postal' agregada correctamente")
            else:
                print("La columna 'codigo_postal' ya existe")
                
            # Verificar y agregar columna ciudad
            cursor.execute("SHOW COLUMNS FROM clientes LIKE 'ciudad'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE clientes ADD COLUMN ciudad VARCHAR(100) DEFAULT NULL")
                print("Columna 'ciudad' agregada correctamente")
            else:
                print("La columna 'ciudad' ya existe")
            
            # Confirmar cambios
            mysql.connection.commit()
            cursor.close()
            
            print("Proceso completado con éxito")
    except Exception as e:
        print(f"Error al agregar columnas: {e}")

if __name__ == "__main__":
    agregar_columnas_clientes() 