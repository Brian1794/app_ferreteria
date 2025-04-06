from app import app, mysql
import sys

def verificar_tabla_reparaciones():
    try:
        print("Conectando a la base de datos...")
        with app.app_context():
            cursor = mysql.connection.cursor()
            
            # Verificar si la tabla existe
            cursor.execute("SHOW TABLES LIKE 'reparaciones'")
            if cursor.fetchone():
                print("Tabla 'reparaciones' encontrada")
                
                # Describir la estructura de la tabla
                cursor.execute("DESCRIBE reparaciones")
                columnas = cursor.fetchall()
                
                print("\nEstructura de la tabla reparaciones:")
                for columna in columnas:
                    print(f"{columna[0]} - {columna[1]} - {columna[2]}")
                
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
                    print("\nCAMPOS FALTANTES en la tabla reparaciones:")
                    for campo in campos_faltantes:
                        print(f" - {campo}")
                    
                    # Agregar campos faltantes
                    print("\nAgregando campos faltantes...")
                    for campo in campos_faltantes:
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
                    
                    mysql.connection.commit()
                    print("Campos agregados correctamente.")
                else:
                    print("\nTodos los campos requeridos existen en la tabla.")
                
                # Verificar si hay datos en la tabla
                cursor.execute("SELECT COUNT(*) FROM reparaciones")
                count = cursor.fetchone()[0]
                print(f"\nLa tabla tiene {count} registros.")
                
            else:
                print("La tabla 'reparaciones' no existe.")
            
            cursor.close()
            return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    verificar_tabla_reparaciones() 