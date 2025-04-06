from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models.whatsapp import WhatsAppManager
from models.models import mysql
import json

whatsapp_bp = Blueprint('whatsapp', __name__)

@whatsapp_bp.route('/')
@login_required
def index():
    """Página principal de WhatsApp Marketing"""
    return render_template('whatsapp/index.html')

@whatsapp_bp.route('/enviar_mensaje', methods=['GET', 'POST'])
@login_required
def enviar_mensaje():
    """Envía un mensaje personalizado a un cliente"""
    if request.method == 'POST':
        telefono = request.form.get('telefono')
        mensaje = request.form.get('mensaje')
        
        if not telefono or not mensaje:
            flash('El teléfono y el mensaje son campos obligatorios', 'danger')
            return render_template('whatsapp/enviar_mensaje.html')
        
        try:
            # Limpiar y formatear número de teléfono
            telefono = telefono.replace(' ', '').replace('-', '')
            if not telefono.startswith('+'):
                telefono = '+' + telefono
            
            # Enviar mensaje
            WhatsAppManager.enviar_mensaje(telefono, mensaje)
            flash('Mensaje enviado con éxito', 'success')
            return redirect(url_for('whatsapp.historial'))
        except Exception as e:
            flash(f'Error al enviar mensaje: {str(e)}', 'danger')
    
    # Obtener lista de clientes para selector
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, nombre, telefono FROM clientes WHERE telefono IS NOT NULL AND telefono != ''")
    clientes = cursor.fetchall()
    cursor.close()
    
    return render_template('whatsapp/enviar_mensaje.html', clientes=clientes)

@whatsapp_bp.route('/plantillas')
@login_required
def plantillas():
    """Lista todas las plantillas disponibles"""
    plantillas = WhatsAppManager.obtener_plantillas()
    return render_template('whatsapp/plantillas.html', plantillas=plantillas)

@whatsapp_bp.route('/plantillas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_plantilla():
    """Crea una nueva plantilla de mensaje"""
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        contenido = request.form.get('contenido')
        variables = request.form.get('variables')
        tipo = request.form.get('tipo', 'TEXT')
        
        if not nombre or not contenido:
            flash('El nombre y el contenido son campos obligatorios', 'danger')
            return render_template('whatsapp/editar_plantilla.html')
        
        try:
            # Validar formato de variables
            variables_json = json.dumps({})
            if variables:
                # Formato esperado: variable1:descripcion1, variable2:descripcion2
                vars_dict = {}
                for var_pair in variables.split(','):
                    if ':' in var_pair:
                        var_name, var_desc = var_pair.strip().split(':', 1)
                        vars_dict[var_name.strip()] = var_desc.strip()
                variables_json = json.dumps(vars_dict)
            
            WhatsAppManager.guardar_plantilla(nombre, contenido, variables_json, tipo)
            flash('Plantilla guardada con éxito', 'success')
            return redirect(url_for('whatsapp.plantillas'))
        except Exception as e:
            flash(f'Error al guardar plantilla: {str(e)}', 'danger')
    
    return render_template('whatsapp/editar_plantilla.html')

@whatsapp_bp.route('/plantillas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_plantilla(id):
    """Edita una plantilla existente"""
    plantilla = WhatsAppManager.obtener_plantilla(id)
    
    if not plantilla:
        flash('Plantilla no encontrada', 'danger')
        return redirect(url_for('whatsapp.plantillas'))
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        contenido = request.form.get('contenido')
        variables = request.form.get('variables')
        tipo = request.form.get('tipo', 'TEXT')
        
        if not nombre or not contenido:
            flash('El nombre y el contenido son campos obligatorios', 'danger')
            return render_template('whatsapp/editar_plantilla.html', plantilla=plantilla)
        
        try:
            # Validar formato de variables
            variables_json = json.dumps({})
            if variables:
                # Formato esperado: variable1:descripcion1, variable2:descripcion2
                vars_dict = {}
                for var_pair in variables.split(','):
                    if ':' in var_pair:
                        var_name, var_desc = var_pair.strip().split(':', 1)
                        vars_dict[var_name.strip()] = var_desc.strip()
                variables_json = json.dumps(vars_dict)
            
            WhatsAppManager.guardar_plantilla(nombre, contenido, variables_json, tipo)
            flash('Plantilla actualizada con éxito', 'success')
            return redirect(url_for('whatsapp.plantillas'))
        except Exception as e:
            flash(f'Error al actualizar plantilla: {str(e)}', 'danger')
    
    # Preparar variables para mostrar en el formulario
    variables_str = ""
    if plantilla[3]:  # variables en formato JSON
        try:
            variables_dict = json.loads(plantilla[3])
            variables_str = ", ".join([f"{k}:{v}" for k, v in variables_dict.items()])
        except:
            pass
    
    return render_template('whatsapp/editar_plantilla.html', 
                           plantilla=plantilla, 
                           variables_str=variables_str)

@whatsapp_bp.route('/plantillas/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_plantilla(id):
    """Elimina una plantilla"""
    try:
        WhatsAppManager.eliminar_plantilla(id)
        flash('Plantilla eliminada con éxito', 'success')
    except Exception as e:
        flash(f'Error al eliminar plantilla: {str(e)}', 'danger')
    
    return redirect(url_for('whatsapp.plantillas'))

@whatsapp_bp.route('/automaticos')
@login_required
def automaticos():
    """Configuración de mensajes automáticos"""
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT nombre, valor FROM configuracion WHERE grupo = 'whatsapp_automaticos'")
    config = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    
    return render_template('whatsapp/automaticos.html', config=config)

@whatsapp_bp.route('/automaticos/actualizar', methods=['POST'])
@login_required
def actualizar_automaticos():
    """Actualiza la configuración de mensajes automáticos"""
    opciones = [
        'notificar_ventas',
        'notificar_reparaciones',
        'notificar_stock_bajo',
        'notificar_promociones'
    ]
    
    cursor = mysql.connection.cursor()
    
    for opcion in opciones:
        valor = 'si' if request.form.get(opcion) else 'no'
        
        # Actualizar o insertar configuración
        cursor.execute("""
            INSERT INTO configuracion (grupo, nombre, valor, descripcion) 
            VALUES ('whatsapp_automaticos', %s, %s, %s)
            ON DUPLICATE KEY UPDATE valor = %s
        """, (opcion, valor, f'Configuración de envío automático: {opcion}', valor))
    
    mysql.connection.commit()
    cursor.close()
    
    flash('Configuración actualizada con éxito', 'success')
    return redirect(url_for('whatsapp.automaticos'))

@whatsapp_bp.route('/configuracion')
@login_required
def configuracion():
    """Configuración de la integración con WhatsApp"""
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT nombre, valor, descripcion FROM configuracion WHERE grupo = 'whatsapp'")
    config = {row[0]: {'valor': row[1], 'descripcion': row[2]} for row in cursor.fetchall()}
    cursor.close()
    
    return render_template('whatsapp/configuracion.html', config=config)

@whatsapp_bp.route('/configuracion/actualizar', methods=['POST'])
@login_required
def actualizar_configuracion():
    """Actualiza la configuración de WhatsApp"""
    configuraciones = [
        'provider',
        'twilio_account_sid',
        'twilio_auth_token',
        'twilio_from_number',
        'whatsapp_token',
        'whatsapp_phone_number_id'
    ]
    
    cursor = mysql.connection.cursor()
    
    for config in configuraciones:
        valor = request.form.get(config, '')
        
        cursor.execute("""
            UPDATE configuracion 
            SET valor = %s
            WHERE grupo = 'whatsapp' AND nombre = %s
        """, (valor, config))
    
    mysql.connection.commit()
    cursor.close()
    
    flash('Configuración actualizada con éxito', 'success')
    return redirect(url_for('whatsapp.configuracion'))

@whatsapp_bp.route('/historial')
@login_required
def historial():
    """Muestra el historial de mensajes enviados"""
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT id, telefono, mensaje, tipo_mensaje, estado, 
               DATE_FORMAT(fecha_envio, '%d/%m/%Y %H:%i') as fecha, error
        FROM whatsapp_mensajes
        ORDER BY fecha_envio DESC
        LIMIT 100
    """)
    mensajes = cursor.fetchall()
    cursor.close()
    
    return render_template('whatsapp/historial.html', mensajes=mensajes)

@whatsapp_bp.route('/api/reenviar/<int:id>', methods=['POST'])
@login_required
def reenviar_mensaje(id):
    """Reenvía un mensaje fallido"""
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT telefono, mensaje, tipo_mensaje FROM whatsapp_mensajes WHERE id = %s", (id,))
    mensaje = cursor.fetchone()
    cursor.close()
    
    if not mensaje:
        return jsonify({'success': False, 'message': 'Mensaje no encontrado'}), 404
    
    try:
        telefono, contenido, tipo = mensaje
        WhatsAppManager.enviar_mensaje(telefono, contenido, tipo)
        return jsonify({'success': True, 'message': 'Mensaje reenviado con éxito'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500 