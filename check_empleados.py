from flask import Flask
from extensions import mysql
import MySQLdb

def check_empleados():
    app = Flask(__name__)
    
    # Configuración de la base de datos
    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_USER'] = 'root'
    app.config['MYSQL_PASSWORD'] = ''
    app.config['MYSQL_DB'] = 'bzm5uc8abvbfoesn7g5v'
    
    # Inicializar MySQL
    mysql.init_app(app)
    
    # Usar el contexto de la aplicación
    with app.app_context():
        cursor = mysql.connection.cursor()
        
        # Obtener la estructura de la tabla empleados
        cursor.execute('DESCRIBE empleados')
        columns = cursor.fetchall()
        
        print("Estructura de la tabla empleados:")
        for column in columns:
            print(f"Campo: {column[0]}, Tipo: {column[1]}, Null: {column[2]}, Key: {column[3]}, Default: {column[4]}, Extra: {column[5]}")
        
        # Agregar la columna telefono si no existe
        try:
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'telefono'")
            if not cursor.fetchone():
                print("Agregando columna 'telefono' a la tabla empleados...")
                cursor.execute("ALTER TABLE empleados ADD COLUMN telefono VARCHAR(50) NULL AFTER email")
                mysql.connection.commit()
                print("Columna 'telefono' agregada correctamente")
            else:
                print("La columna 'telefono' ya existe en la tabla empleados")
        except Exception as e:
            print(f"Error al agregar columna 'telefono': {e}")
            
        # Agregar la columna cedula si no existe
        try:
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'cedula'")
            if not cursor.fetchone():
                print("Agregando columna 'cedula' a la tabla empleados...")
                cursor.execute("ALTER TABLE empleados ADD COLUMN cedula VARCHAR(20) NULL AFTER telefono")
                mysql.connection.commit()
                print("Columna 'cedula' agregada correctamente")
            else:
                print("La columna 'cedula' ya existe en la tabla empleados")
        except Exception as e:
            print(f"Error al agregar columna 'cedula': {e}")
            
        # Agregar la columna direccion si no existe
        try:
            cursor.execute("SHOW COLUMNS FROM empleados LIKE 'direccion'")
            if not cursor.fetchone():
                print("Agregando columna 'direccion' a la tabla empleados...")
                cursor.execute("ALTER TABLE empleados ADD COLUMN direccion VARCHAR(255) NULL AFTER cedula")
                mysql.connection.commit()
                print("Columna 'direccion' agregada correctamente")
            else:
                print("La columna 'direccion' ya existe en la tabla empleados")
        except Exception as e:
            print(f"Error al agregar columna 'direccion': {e}")
        
        # Cerrar cursor
        cursor.close()

if __name__ == "__main__":
    check_empleados() 