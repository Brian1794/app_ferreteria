import requests
import json
from flask import current_app
from extensions import mysql
import datetime

class WhatsAppManager:
    """
    Clase para gestionar integraciones con WhatsApp
    Puede usar Twilio u otras APIs según configuración
    """
    
    @staticmethod
    def _get_config():
        """Obtiene la configuración de WhatsApp desde la base de datos"""
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT nombre, valor FROM configuracion WHERE grupo = 'whatsapp'")
        config = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        return config
    
    @staticmethod
    def guardar_plantilla(nombre, contenido, variables, tipo="TEXT"):
        """Guarda una plantilla de mensaje en la base de datos"""
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO whatsapp_plantillas (nombre, contenido, variables, tipo)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                contenido = VALUES(contenido),
                variables = VALUES(variables),
                tipo = VALUES(tipo)
            """, (nombre, contenido, variables, tipo))
            mysql.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            mysql.connection.rollback()
            cursor.close()
            raise e
    
    @staticmethod
    def obtener_plantillas():
        """Obtiene todas las plantillas disponibles"""
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, nombre, contenido, variables, tipo FROM whatsapp_plantillas")
        plantillas = cursor.fetchall()
        cursor.close()
        return plantillas
    
    @staticmethod
    def obtener_plantilla(id):
        """Obtiene una plantilla específica por ID"""
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, nombre, contenido, variables, tipo FROM whatsapp_plantillas WHERE id = %s", (id,))
        plantilla = cursor.fetchone()
        cursor.close()
        return plantilla
    
    @staticmethod
    def eliminar_plantilla(id):
        """Elimina una plantilla"""
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM whatsapp_plantillas WHERE id = %s", (id,))
        mysql.connection.commit()
        cursor.close()
        return True
    
    @staticmethod
    def registrar_mensaje(telefono, mensaje, tipo_mensaje, estado='ENVIADO', error=None):
        """Registra un mensaje enviado en la base de datos"""
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO whatsapp_mensajes (telefono, mensaje, tipo_mensaje, estado, error)
                VALUES (%s, %s, %s, %s, %s)
            """, (telefono, mensaje, tipo_mensaje, estado, error))
            mysql.connection.commit()
            mensaje_id = cursor.lastrowid
            cursor.close()
            return mensaje_id
        except Exception as e:
            mysql.connection.rollback()
            cursor.close()
            raise e
    
    @classmethod
    def enviar_mensaje(cls, telefono, mensaje, tipo_mensaje="MANUAL"):
        """
        Envía un mensaje de WhatsApp utilizando la API configurada
        Soporta Twilio o WhatsApp Business API
        """
        config = cls._get_config()
        
        # Validar que el teléfono tenga el formato correcto (con código de país)
        if not telefono.startswith('+'):
            telefono = '+' + telefono
        
        # Determinar qué proveedor usar según configuración
        provider = config.get('provider', 'twilio')
        
        try:
            if provider == 'twilio':
                return cls._enviar_por_twilio(telefono, mensaje, config)
            elif provider == 'whatsapp_business':
                return cls._enviar_por_whatsapp_business(telefono, mensaje, config)
            else:
                raise ValueError(f"Proveedor de WhatsApp no soportado: {provider}")
        except Exception as e:
            # Registrar el error
            cls.registrar_mensaje(telefono, mensaje, tipo_mensaje, 'ERROR', str(e))
            raise e
    
    @classmethod
    def _enviar_por_twilio(cls, telefono, mensaje, config):
        """Envía mensaje usando Twilio API"""
        account_sid = config.get('twilio_account_sid')
        auth_token = config.get('twilio_auth_token')
        from_number = config.get('twilio_from_number')
        
        if not all([account_sid, auth_token, from_number]):
            raise ValueError("Faltan credenciales de Twilio en la configuración")
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        payload = {
            'To': f'whatsapp:{telefono}',
            'From': f'whatsapp:{from_number}',
            'Body': mensaje
        }
        
        response = requests.post(
            url, 
            data=payload,
            auth=(account_sid, auth_token)
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            response_data = response.json()
            cls.registrar_mensaje(telefono, mensaje, 'TWILIO', 'ENVIADO')
            return response_data.get('sid')
        else:
            error_msg = f"Error al enviar mensaje. Código: {response.status_code}, Mensaje: {response.text}"
            cls.registrar_mensaje(telefono, mensaje, 'TWILIO', 'ERROR', error_msg)
            raise Exception(error_msg)
    
    @classmethod
    def _enviar_por_whatsapp_business(cls, telefono, mensaje, config):
        """Envía mensaje usando WhatsApp Business API"""
        token = config.get('whatsapp_token')
        phone_number_id = config.get('whatsapp_phone_number_id')
        
        if not all([token, phone_number_id]):
            raise ValueError("Faltan credenciales de WhatsApp Business API en la configuración")
        
        url = f"https://graph.facebook.com/v13.0/{phone_number_id}/messages"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': telefono,
            'type': 'text',
            'text': {
                'body': mensaje
            }
        }
        
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload)
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            response_data = response.json()
            cls.registrar_mensaje(telefono, mensaje, 'WHATSAPP_BUSINESS', 'ENVIADO')
            return response_data.get('messages', [{}])[0].get('id')
        else:
            error_msg = f"Error al enviar mensaje. Código: {response.status_code}, Mensaje: {response.text}"
            cls.registrar_mensaje(telefono, mensaje, 'WHATSAPP_BUSINESS', 'ERROR', error_msg)
            raise Exception(error_msg)
    
    @classmethod
    def notificar_venta(cls, venta_id):
        """Envía notificación de venta al cliente"""
        cursor = mysql.connection.cursor()
        # Obtener datos de la venta
        cursor.execute("""
            SELECT v.id, v.total, c.nombre, c.telefono, DATE_FORMAT(v.fecha, '%d/%m/%Y %H:%i') as fecha_formateada
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = %s
        """, (venta_id,))
        venta = cursor.fetchone()
        cursor.close()
        
        if not venta or not venta[3]:  # No hay venta o no hay teléfono
            return False
        
        venta_id, total, cliente_nombre, telefono, fecha = venta
        
        # Obtener plantilla
        plantilla = cls.obtener_plantilla_por_nombre("confirmacion_venta")
        if not plantilla:
            # Usar mensaje predeterminado
            mensaje = f"Hola {cliente_nombre}, gracias por tu compra por ${total} realizada el {fecha}. Tu número de orden es #{venta_id}. ¡Gracias por confiar en Ferretería La U!"
        else:
            # Reemplazar variables en la plantilla
            mensaje = plantilla[2]  # contenido
            mensaje = mensaje.replace("{{cliente}}", cliente_nombre)
            mensaje = mensaje.replace("{{monto}}", str(total))
            mensaje = mensaje.replace("{{fecha}}", fecha)
            mensaje = mensaje.replace("{{id}}", str(venta_id))
        
        # Enviar mensaje
        return cls.enviar_mensaje(telefono, mensaje, "VENTA")
    
    @classmethod
    def notificar_estado_reparacion(cls, reparacion_id):
        """Envía notificación de cambio de estado en reparación"""
        cursor = mysql.connection.cursor()
        # Obtener datos de la reparación
        cursor.execute("""
            SELECT r.id, r.estado, c.nombre, c.telefono, r.descripcion, 
                   DATE_FORMAT(r.fecha_entrega_estimada, '%d/%m/%Y') as fecha_entrega
            FROM reparaciones r
            LEFT JOIN clientes c ON r.cliente_id = c.id
            WHERE r.id = %s
        """, (reparacion_id,))
        reparacion = cursor.fetchone()
        cursor.close()
        
        if not reparacion or not reparacion[3]:  # No hay reparación o no hay teléfono
            return False
        
        rep_id, estado, cliente_nombre, telefono, descripcion, fecha_entrega = reparacion
        
        # Obtener plantilla según estado
        plantilla = cls.obtener_plantilla_por_nombre(f"reparacion_{estado.lower()}")
        if not plantilla:
            # Usar mensaje predeterminado
            mensaje = f"Hola {cliente_nombre}, tu reparación #{rep_id} ({descripcion}) ha cambiado de estado a: {estado}."
            if fecha_entrega and estado == "EN_PROGRESO":
                mensaje += f" Fecha estimada de entrega: {fecha_entrega}."
            elif estado == "LISTO":
                mensaje += " Ya puedes pasar a retirarla."
        else:
            # Reemplazar variables en la plantilla
            mensaje = plantilla[2]  # contenido
            mensaje = mensaje.replace("{{cliente}}", cliente_nombre)
            mensaje = mensaje.replace("{{descripcion}}", descripcion)
            mensaje = mensaje.replace("{{estado}}", estado)
            mensaje = mensaje.replace("{{id}}", str(rep_id))
            if fecha_entrega:
                mensaje = mensaje.replace("{{fecha_entrega}}", fecha_entrega)
        
        # Enviar mensaje
        return cls.enviar_mensaje(telefono, mensaje, "REPARACION")
    
    @staticmethod
    def obtener_plantilla_por_nombre(nombre):
        """Obtiene una plantilla por su nombre"""
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, nombre, contenido, variables, tipo FROM whatsapp_plantillas WHERE nombre = %s", (nombre,))
        plantilla = cursor.fetchone()
        cursor.close()
        return plantilla 