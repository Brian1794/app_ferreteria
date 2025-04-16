import os
import pymysql
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        db=os.getenv('DB_NAME', 'ferreteria'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def crear_tablas():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Tabla de bancos PSE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bancos_pse (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            codigo_banco VARCHAR(20) NOT NULL,
            estado ENUM('activo', 'inactivo') DEFAULT 'activo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        
        # Tabla de pagos PSE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos_pse (
            id INT AUTO_INCREMENT PRIMARY KEY,
            factura_id INT NOT NULL,
            banco_id INT NOT NULL,
            referencia VARCHAR(50) NOT NULL,
            pse_id VARCHAR(50) NOT NULL,
            tipo_persona ENUM('N', 'J') NOT NULL COMMENT 'N: Natural, J: Jurídica',
            tipo_documento VARCHAR(10) NOT NULL COMMENT 'CC, CE, TI, NIT, etc.',
            documento VARCHAR(20) NOT NULL,
            nombre VARCHAR(100) NOT NULL,
            apellido VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            telefono VARCHAR(20) NULL,
            estado ENUM('pendiente', 'completado', 'rechazado', 'error') DEFAULT 'pendiente',
            monto DECIMAL(10,2) NOT NULL,
            fecha_creacion DATETIME NOT NULL,
            fecha_actualizacion DATETIME NOT NULL,
            respuesta_pse TEXT NULL,
            FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE,
            FOREIGN KEY (banco_id) REFERENCES bancos_pse(id) ON DELETE RESTRICT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        
        print("✅ Tablas PSE creadas correctamente")
        
        # Insertar bancos colombianos de ejemplo
        bancos = [
            ("Bancolombia", "1007"),
            ("Banco de Bogotá", "1013"),
            ("Davivienda", "1051"),
            ("BBVA Colombia", "1032"),
            ("Banco de Occidente", "1023"),
            ("Banco Popular", "1002"),
            ("Banco AV Villas", "1052"),
            ("Banco Caja Social", "1019"),
            ("Scotiabank Colpatria", "1001"),
            ("Itaú", "1006"),
            ("Banco Agrario", "1040"),
            ("Bancoomeva", "1061"),
            ("Banco Falabella", "1062"),
            ("Banco Pichincha", "1060"),
            ("Nequi", "1507"),
            ("Daviplata", "1551")
        ]
        
        # Verificar si ya hay bancos
        cursor.execute("SELECT COUNT(*) as total FROM bancos_pse")
        if cursor.fetchone()['total'] == 0:
            for banco in bancos:
                cursor.execute("""
                INSERT INTO bancos_pse (nombre, codigo_banco) 
                VALUES (%s, %s)
                """, banco)
            
            print(f"✅ {len(bancos)} bancos insertados correctamente")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    crear_tablas() 