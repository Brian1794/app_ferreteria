from flask import Flask
from flask_cors import CORS
import os

# Importación de blueprints
from app.routes.productos import productos_bp
from app.routes.categorias import categorias_bp
from app.routes.clientes import clientes_bp
from app.routes.usuarios import usuarios_bp
from app.routes.auth import auth_bp
from app.routes.pedidos import pedidos_bp
from app.routes.facturas import facturas_bp
from app.routes.pagos_pse import pagos_pse_bp

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Registro de blueprints
    app.register_blueprint(productos_bp, url_prefix='/api/productos')
    app.register_blueprint(categorias_bp, url_prefix='/api/categorias')
    app.register_blueprint(clientes_bp, url_prefix='/api/clientes')
    app.register_blueprint(usuarios_bp, url_prefix='/api/usuarios')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(pedidos_bp, url_prefix='/api/pedidos')
    app.register_blueprint(facturas_bp, url_prefix='/api/facturas')
    app.register_blueprint(pagos_pse_bp, url_prefix='/api/pagos/pse')
    
    @app.route('/')
    def index():
        return "API de Ferretería El Tornillo Feliz"
    
    return app 