import database as db

class Usuario:
    """
    Clase que representa un usuario del sistema (cliente o empleado)
    Compatible con Flask-Login
    """
    
    def __init__(self, id=None, nombre=None, email=None, es_admin=False, 
                 es_cliente=False, activo=True, telefono=None, cargo_id=None, 
                 cargo_nombre=None, foto_perfil=None):
        """
        Inicializa un usuario con sus atributos
        
        Args:
            id: ID del usuario en la base de datos (id_cliente o id_empleado)
            nombre: Nombre completo
            email: Correo electrónico o cédula (para empleados)
            es_admin: Si el usuario es administrador
            es_cliente: Si el usuario es cliente
            activo: Si el usuario está activo
            telefono: Número de teléfono
            cargo_id: ID del cargo (solo para empleados)
            cargo_nombre: Nombre del cargo (solo para empleados)
            foto_perfil: Nombre del archivo de la foto de perfil
        """
        self.id = id
        self.nombre = nombre
        self.email = email
        self.es_admin = es_admin
        self.es_cliente = es_cliente
        self.activo = activo
        self.telefono = telefono
        self.cargo_id = cargo_id
        self.cargo_nombre = cargo_nombre
        self.foto_perfil = foto_perfil
        
        # Atributos requeridos por Flask-Login
        self.is_authenticated = True
        self.is_active = activo
        self.is_anonymous = False
    
    def get_id(self):
        """
        Método requerido por Flask-Login para obtener el ID del usuario
        
        Returns:
            str: ID del usuario convertido a string
        """
        return str(self.id)
    
    @property
    def is_cliente(self):
        """
        Propiedad para mantener compatibilidad con código existente
        
        Returns:
            bool: True si es cliente, False en caso contrario
        """
        return self.es_cliente
    
    @property
    def is_empleado(self):
        """
        Verifica si el usuario es empleado
        
        Returns:
            bool: True si es empleado, False en caso contrario
        """
        return not self.es_cliente
    
    def can_access_admin(self):
        """
        Verifica si el usuario puede acceder a secciones administrativas
        
        Returns:
            bool: True si puede acceder, False en caso contrario
        """
        return self.is_empleado
    
    def tiene_cargo(self, nombre_cargo):
        """
        Verifica si el usuario tiene un cargo específico
        
        Args:
            nombre_cargo: Nombre del cargo a verificar (ej: 'Técnico', 'Vendedor')
            
        Returns:
            bool: True si tiene el cargo, False en caso contrario
        """
        # Si es cliente o no tiene cargo_id, retorna False
        if self.es_cliente or not self.cargo_id:
            return False
            
        # Si ya tenemos el nombre del cargo, comparamos directamente
        if self.cargo_nombre:
            return self.cargo_nombre == nombre_cargo
            
        # Si no tenemos el nombre, lo buscamos en la base de datos
        from extensions import mysql, get_cursor
        import MySQLdb
        
        try:
            cursor = get_cursor(dictionary=True)
            cursor.execute("SELECT nombre FROM cargos WHERE id = %s", (self.cargo_id,))
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                return False
                
            # Almacenar el nombre para uso futuro
            self.cargo_nombre = result['nombre']
            return self.cargo_nombre == nombre_cargo
        except Exception as e:
            print(f"Error al verificar cargo del usuario: {e}")
            return False
    
    def es_tecnico(self):
        """Verifica si el usuario es un técnico"""
        return self.tiene_cargo('Técnico')
    
    def es_vendedor(self):
        """Verifica si el usuario es un vendedor"""
        return self.tiene_cargo('Vendedor')
    
    def es_almacenista(self):
        """Verifica si el usuario es un almacenista"""
        return self.tiene_cargo('Almacenista')
    
    def puede_ver_modulo(self, modulo):
        """
        Verifica si el usuario tiene permiso para ver un módulo específico
        
        Args:
            modulo: Nombre del módulo (ej: 'ventas', 'productos')
            
        Returns:
            bool: True si puede ver el módulo, False en caso contrario
        """
        # Si es admin, siempre puede ver todos los módulos
        if self.es_admin:
            return True
            
        # Si es cliente o no tiene cargo_id, depende del módulo
        if self.es_cliente:
            # Los clientes solo pueden ver módulos públicos
            modulos_cliente = ['catalogo', 'mis_reparaciones', 'mi_cuenta']
            return modulo in modulos_cliente
            
        # Para empleados, verificar permisos según cargo
        if not self.cargo_id:
            return False
        
        from extensions import mysql, get_cursor
        import MySQLdb    
        
        try:
            cursor = get_cursor(dictionary=True)
            cursor.execute("""
                SELECT p.id_permiso FROM permisos p
                JOIN modulos m ON p.id_modulo = m.id_modulo
                WHERE p.id_rol IN (
                    SELECT id_rol FROM cargo_rol WHERE id_cargo = %s
                ) 
                AND m.nombre_modulo = %s
                """, 
                (self.cargo_id, modulo)
            )
            result = cursor.fetchone()
            cursor.close()
            
            return result is not None
        except Exception as e:
            print(f"Error al verificar permisos de módulo: {e}")
            return False
    
    @classmethod
    def get_by_email(cls, email, es_cliente=False):
        """
        Obtiene un usuario por su email
        
        Args:
            email: Email del usuario
            es_cliente: Si es cliente o empleado
            
        Returns:
            Usuario: Instancia de usuario o None
        """
        from extensions import mysql, get_cursor
        import MySQLdb
        
        try:
            cursor = get_cursor(dictionary=True)
            
            if es_cliente:
                cursor.execute("SELECT * FROM clientes WHERE correo = %s", (email,))
                result = cursor.fetchone()
                
                if result:
                    return cls(
                        id=result['id_cliente'],
                        nombre=result['nombre'],
                        email=result['correo'],
                        es_cliente=True,
                        foto_perfil=result.get('foto_perfil')
                    )
            else:
                # Para empleados, buscamos por cédula
                cursor.execute("""
                    SELECT e.*, c.nombre_cargo 
                    FROM empleados e 
                    JOIN cargos c ON e.id_cargo = c.id_cargo 
                    WHERE e.cedula = %s
                    """, (email,))
                result = cursor.fetchone()
                
                if result:
                    return cls(
                        id=result['id_empleado'],
                        nombre=f"{result['nombre']} {result['apellido']}",
                        email=result['cedula'],
                        es_admin=result['nombre_cargo'] == 'Administrador',
                        es_cliente=False,
                        cargo_id=result['id_cargo'],
                        cargo_nombre=result['nombre_cargo'],
                        foto_perfil=result.get('foto_perfil')
                    )
                
            cursor.close()
            return None
        except Exception as e:
            print(f"Error al obtener usuario por email: {e}")
            return None
    
    @classmethod
    def get_by_id(cls, id, es_cliente=False):
        """
        Obtiene un usuario por su id
        
        Args:
            id: ID del usuario
            es_cliente: Si es cliente o empleado
            
        Returns:
            Usuario: Instancia de usuario o None
        """
        from extensions import mysql, get_cursor
        import MySQLdb
        
        try:
            cursor = get_cursor(dictionary=True)
            
            if es_cliente:
                cursor.execute("SELECT * FROM clientes WHERE id_cliente = %s", (id,))
                result = cursor.fetchone()
                
                if result:
                    return cls(
                        id=result['id_cliente'],
                        nombre=result['nombre'],
                        email=result['correo'],
                        es_cliente=True,
                        foto_perfil=result.get('foto_perfil')
                    )
            else:
                # Para empleados
                cursor.execute("""
                    SELECT e.*, c.nombre_cargo 
                    FROM empleados e 
                    JOIN cargos c ON e.id_cargo = c.id_cargo 
                    WHERE e.id_empleado = %s
                    """, (id,))
                result = cursor.fetchone()
                
                if result:
                    return cls(
                        id=result['id_empleado'],
                        nombre=f"{result['nombre']} {result['apellido']}",
                        email=result['cedula'],
                        es_admin=result['nombre_cargo'] == 'Administrador',
                        es_cliente=False,
                        cargo_id=result['id_cargo'],
                        cargo_nombre=result['nombre_cargo'],
                        foto_perfil=result.get('foto_perfil')
                    )
                
            cursor.close()
            return None
        except Exception as e:
            print(f"Error al obtener usuario por ID: {e}")
            return None
    
    def __repr__(self):
        """Representación del objeto Usuario para depuración"""
        tipo = "Cliente" if self.es_cliente else "Empleado"
        admin = " (Admin)" if self.es_admin else ""
        return f"<Usuario {self.id}: {self.nombre} {tipo}{admin}>" 