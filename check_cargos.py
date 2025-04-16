import os
from flask import Flask
from extensions import mysql
import MySQLdb
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
# Configurar la aplicación para usar MySQL
app.config['MYSQL_HOST'] = os.environ.get('DB_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('DB_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('DB_NAME', 'ferreteria')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Inicializar la extensión MySQL
mysql.init_app(app)

def check_cargos():
    """Verifica y crea cargos predeterminados si no existen"""
    with app.app_context():
        cursor = mysql.connection.cursor()
        
        # Verificar estructura de la tabla cargos
        cursor.execute("DESCRIBE cargos")
        columns = {col['Field']: col for col in cursor.fetchall()}
        print("Estructura de la tabla cargos:")
        for col_name, col_info in columns.items():
            print(f"  {col_name}: {col_info['Type']}")
        
        # Verificar si hay campo 'activo'
        has_activo = 'activo' in columns
        
        # Verificar si hay cargos
        cursor.execute("SELECT COUNT(*) as total FROM cargos")
        result = cursor.fetchone()
        
        print(f"\nTotal de cargos encontrados: {result['total']}")
        
        if result['total'] == 0:
            print("No hay cargos. Creando cargos predeterminados...")
            
            # Crear cargos básicos
            if has_activo:
                cargos_default = [
                    ("Administrador", "Administrador del sistema con acceso completo", '{"ventas": true, "productos": true, "clientes": true, "reparaciones": true, "empleados": true, "reportes": true, "admin": true}', True),
                    ("Vendedor", "Gestión de ventas y atención al cliente", '{"ventas": true, "productos": {"ver": true, "crear": false, "editar": false, "eliminar": false}, "clientes": {"ver": true, "crear": true, "editar": true, "eliminar": false}}', True),
                    ("Técnico", "Reparación y mantenimiento", '{"reparaciones": true, "productos": {"ver": true, "crear": false, "editar": false, "eliminar": false}}', True),
                    ("Cajero", "Manejo de caja y facturación", '{"ventas": {"ver": true, "crear": true, "editar": false, "eliminar": false}}', True),
                    ("Almacenista", "Gestión de inventario", '{"productos": true}', True)
                ]
                
                for cargo in cargos_default:
                    cursor.execute(
                        "INSERT INTO cargos (nombre, descripcion, permisos, activo) VALUES (%s, %s, %s, %s)",
                        cargo
                    )
            else:
                # Sin campo activo
                cargos_default = [
                    ("Administrador", "Administrador del sistema con acceso completo", '{"ventas": true, "productos": true, "clientes": true, "reparaciones": true, "empleados": true, "reportes": true, "admin": true}'),
                    ("Vendedor", "Gestión de ventas y atención al cliente", '{"ventas": true, "productos": {"ver": true, "crear": false, "editar": false, "eliminar": false}, "clientes": {"ver": true, "crear": true, "editar": true, "eliminar": false}}'),
                    ("Técnico", "Reparación y mantenimiento", '{"reparaciones": true, "productos": {"ver": true, "crear": false, "editar": false, "eliminar": false}}'),
                    ("Cajero", "Manejo de caja y facturación", '{"ventas": {"ver": true, "crear": true, "editar": false, "eliminar": false}}'),
                    ("Almacenista", "Gestión de inventario", '{"productos": true}')
                ]
                
                for cargo in cargos_default:
                    cursor.execute(
                        "INSERT INTO cargos (nombre, descripcion, permisos) VALUES (%s, %s, %s)",
                        cargo
                    )
            
            mysql.connection.commit()
            print("Cargos predeterminados creados exitosamente")
        
        # Mostrar cargos actuales
        if has_activo:
            cursor.execute("SELECT id, nombre, descripcion, activo FROM cargos")
        else:
            cursor.execute("SELECT id, nombre, descripcion FROM cargos")
            
        cargos = cursor.fetchall()
        
        print("\nCargos disponibles:")
        for cargo in cargos:
            if has_activo:
                estado = "Activo" if cargo['activo'] else "Inactivo"
                print(f"ID: {cargo['id']} | Nombre: {cargo['nombre']} | Descripción: {cargo['descripcion']} | Estado: {estado}")
            else:
                print(f"ID: {cargo['id']} | Nombre: {cargo['nombre']} | Descripción: {cargo['descripcion']}")
        
        cursor.close()

if __name__ == "__main__":
    check_cargos() 