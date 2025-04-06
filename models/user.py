from flask_login import UserMixin
from flask import current_app
from extensions import mysql
import datetime

class Usuario(UserMixin):
    """Modelo para gestionar usuarios en la aplicación."""
    
    def __init__(self, id, nombre, email, activo=True):
        self.id = id
        self.nombre = nombre
        self.email = email
        self.activo = activo
        self._permisos = None
    
    @property
    def is_active(self):
        """Retorna si el usuario está activo (requerido por Flask-Login)"""
        return self.activo
    
    @classmethod
    def get_by_id(cls, user_id):
        """Obtiene un usuario por su ID."""
        cursor = mysql.connection.cursor()
        try:
            # Primero intentamos con la columna activo
            cursor.execute("""
                SELECT id, nombre, email, activo 
                FROM usuarios 
                WHERE id = %s
            """, (user_id,))
        except Exception:
            # Si falla, asumimos que la columna no existe y consultamos sin ella
            cursor.execute("""
                SELECT id, nombre, email 
                FROM usuarios 
                WHERE id = %s
            """, (user_id,))
            user = cursor.fetchone()
            cursor.close()
            
            if user:
                return cls(user[0], user[1], user[2], True)  # Asumimos activo=True
            return None
        else:
            user = cursor.fetchone()
            cursor.close()
            
            if user:
                return cls(user[0], user[1], user[2], bool(user[3]))
            return None
    
    @classmethod
    def get_by_email(cls, email):
        """Obtiene un usuario por su email."""
        cursor = mysql.connection.cursor()
        try:
            # Primero intentamos con la columna activo
            cursor.execute("""
                SELECT id, nombre, email, password, activo 
                FROM usuarios 
                WHERE email = %s
            """, (email,))
        except Exception:
            # Si falla, asumimos que la columna no existe y consultamos sin ella
            cursor.execute("""
                SELECT id, nombre, email, password 
                FROM usuarios 
                WHERE email = %s
            """, (email,))
            user = cursor.fetchone()
            cursor.close()
            
            if user:
                # Retornar objeto usuario y password hash por separado, asumiendo activo=True
                return cls(user[0], user[1], user[2], True), user[3]
            return None, None
        else:
            user = cursor.fetchone()
            cursor.close()
            
            if user:
                # Retornar objeto usuario y password hash por separado
                return cls(user[0], user[1], user[2], bool(user[4])), user[3]
            return None, None
    
    @classmethod
    def crear_usuario(cls, nombre, email, password_hash):
        """Crea un nuevo usuario en la base de datos."""
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO usuarios (nombre, email, password)
                VALUES (%s, %s, %s)
            """, (nombre, email, password_hash))
            mysql.connection.commit()
            user_id = cursor.lastrowid
            cursor.close()
            return cls(user_id, nombre, email)
        except Exception as e:
            mysql.connection.rollback()
            cursor.close()
            raise e
    
    def actualizar_perfil(self, nombre=None):
        """Actualiza datos del perfil del usuario."""
        if nombre:
            cursor = mysql.connection.cursor()
            cursor.execute("""
                UPDATE usuarios
                SET nombre = %s
                WHERE id = %s
            """, (nombre, self.id))
            mysql.connection.commit()
            cursor.close()
            self.nombre = nombre
            return True
        return False
    
    def cambiar_password(self, nuevo_password_hash):
        """Cambia la contraseña del usuario."""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE usuarios
            SET password = %s
            WHERE id = %s
        """, (nuevo_password_hash, self.id))
        mysql.connection.commit()
        cursor.close()
        return True
    
    def desactivar(self):
        """Desactiva la cuenta de usuario."""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE usuarios
            SET activo = 0
            WHERE id = %s
        """, (self.id,))
        mysql.connection.commit()
        cursor.close()
        self.activo = False
        return True
