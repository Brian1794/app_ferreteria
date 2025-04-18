"""
Utilidades para autenticación y autorización
"""
from functools import wraps
from flask import request, jsonify, current_app
import jwt
from datetime import datetime, timedelta
from extensions import mysql

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].replace('Bearer ', '')
            
        if not token:
            return jsonify({'error': 'Token no proporcionado'}), 401
            
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            cursor = mysql.connection.cursor(dictionary=True)
            cursor.execute('SELECT * FROM clientes WHERE id = %s', (data['sub'],))
            usuario_actual = cursor.fetchone()
            cursor.close()
            
            if not usuario_actual:
                return jsonify({'error': 'Token inválido'}), 401
                
            return f(usuario_actual, *args, **kwargs)
            
        except Exception as e:
            return jsonify({'error': 'Token inválido'}), 401
            
    return decorated