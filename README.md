# Ferretería "La U" - Sistema de Gestión

Sistema de gestión integral para una ferretería, que permite administrar inventario, ventas, reparaciones, clientes y comunicaciones por WhatsApp.

## Características

- Gestión de inventario de productos
- Registro y seguimiento de ventas
- Sistema de reparación de electrodomésticos
- Gestión de clientes y proveedores
- Integración con WhatsApp para marketing y notificaciones
- Panel administrativo con estadísticas
- Roles y permisos para diferentes tipos de usuarios
- Punto de venta (POS)

## Requisitos

- Python 3.8 o superior
- MySQL 5.7 o superior
- Pip (gestor de paquetes de Python)

## Instalación

1. Clonar el repositorio:
   ```
   git clone https://github.com/tu-usuario/ferreteria-la-u.git
   cd ferreteria-la-u
   ```

2. Crear y activar un entorno virtual:
   ```
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```

3. Instalar dependencias:
   ```
   pip install -r requirements.txt
   ```

4. Configurar variables de entorno:
   - Copiar el archivo `.env.example` a `.env`
   - Actualizar los valores según tu entorno

5. Crear la base de datos:
   ```
   # Acceder a MySQL
   mysql -u root -p
   
   # Crear base de datos
   CREATE DATABASE ferreteria_la_u;
   
   # Aumentar límite de conexiones por usuario (soluciona el error max_user_connections)
   SET GLOBAL max_user_connections = 20;
   
   # Salir de MySQL
   exit;
   ```

6. Inicializar la base de datos:
   ```
   # Esto creará automáticamente todas las tablas y cargará datos iniciales
   python app.py
   ```

## Solución al error "max_user_connections"

Si encuentras el error "max_user_connections", sigue estos pasos:

1. En MySQL Workbench o consola MySQL como administrador:
   ```sql
   SET GLOBAL max_user_connections = 20;
   ```

2. Para una solución permanente, editar el archivo `my.cnf` (Linux/Mac) o `my.ini` (Windows):
   ```
   [mysqld]
   max_user_connections=20
   ```

3. Reiniciar el servicio MySQL después de hacer cambios al archivo de configuración.

4. Si usas un servicio en la nube, contacta al proveedor para aumentar este límite.

## Optimización de conexiones

La aplicación está configurada para usar un pool de conexiones y cerrar las conexiones correctamente. Puedes ajustar la configuración en el archivo `.env`:

```
MYSQL_MAX_CONNECTIONS=20
MYSQL_POOL_SIZE=10
MYSQL_POOL_RECYCLE=280
```

## Estructura del proyecto

- `/routes`: Contiene los controladores y rutas de la aplicación. Cada archivo en este directorio maneja diferentes aspectos de la aplicación, como autenticación, gestión de reparaciones, ventas, etc.
  - `auth.py`: Maneja la autenticación de usuarios, incluyendo inicio de sesión, registro y recuperación de contraseñas.
  - `reparaciones.py`: Gestiona las reparaciones de electrodomésticos, incluyendo la creación, listado y actualización de reparaciones.
  - `compras.py`, `admin.py`, `empleados.py`, `productos.py`, `main.py`, `tienda.py`, `ventas.py`, `clientes.py`, `categorias.py`, `whatsapp.py`: Cada uno maneja diferentes aspectos de la aplicación relacionados con su nombre.

- `/models`: Define los modelos de datos y la lógica de negocio. Aquí se encuentran las definiciones de las tablas de la base de datos y las operaciones relacionadas.
  - `usuario.py`: Define el modelo de usuario y sus operaciones.
  - `models.py`: Contiene modelos adicionales y lógica de negocio.
  - `whatsapp.py`: Maneja la integración con WhatsApp para notificaciones y marketing.

- `/templates`: Contiene las plantillas HTML Jinja2 utilizadas para renderizar las páginas web.

- `/static`: Almacena archivos estáticos como CSS, JavaScript e imágenes.

- `/extensions.py`: Configura las extensiones de Flask utilizadas en la aplicación, como la base de datos y la autenticación.

- `/database.py`: Proporciona funciones para interactuar con la base de datos, incluyendo la conexión y ejecución de consultas.

- `/config.py`: Contiene la configuración de la aplicación para diferentes entornos, como desarrollo y producción.

- `/app.py`: Es el punto de entrada de la aplicación. Configura y ejecuta el servidor Flask.

## Ejecutar la aplicación

```
python app.py
```

La aplicación estará disponible en http://localhost:5000

## Usuario administrador por defecto

- Email: admin@ferreterialaU.com
- Contraseña: admin123

## Contribuir

1. Haz un fork del repositorio
2. Crea una rama para tu característica (`git checkout -b feature/nueva-caracteristica`)
3. Realiza tus cambios
4. Haz commit de tus cambios (`git commit -am 'Añadir nueva característica'`)
5. Haz push a la rama (`git push origin feature/nueva-caracteristica`)
6. Crea un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo LICENSE para más detalles. 