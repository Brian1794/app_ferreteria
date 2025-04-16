"""
Gestor unificado de pasarelas de pago
"""
from flask import current_app, session
from .stripe_gateway import StripeGateway

class PaymentGateway:
    """Gestor unificado de pasarelas de pago"""
    
    # Mapeo de métodos de pago a pasarelas
    GATEWAYS = {
        'stripe': StripeGateway,
    }
    
    @staticmethod
    def is_available(gateway_name):
        """
        Verifica si una pasarela de pago está disponible
        
        Args:
            gateway_name: Nombre de la pasarela (stripe)
            
        Returns:
            bool: True si la pasarela está disponible
        """
        if gateway_name not in PaymentGateway.GATEWAYS:
            return False
            
        # Verificar configuración según la pasarela
        if gateway_name == 'stripe':
            return bool(current_app.config.get('STRIPE_PUBLIC_KEY')) and \
                   bool(current_app.config.get('STRIPE_SECRET_KEY'))
        
        return False
    
    @staticmethod
    def get_available_gateways():
        """
        Obtiene una lista de pasarelas de pago disponibles
        
        Returns:
            list: Lista de nombres de pasarelas disponibles
        """
        available = []
        for gateway_name in PaymentGateway.GATEWAYS:
            if PaymentGateway.is_available(gateway_name):
                available.append(gateway_name)
        return available
    
    @staticmethod
    def create_payment(gateway_name, pedido, **kwargs):
        """
        Crea un pago utilizando la pasarela especificada
        
        Args:
            gateway_name: Nombre de la pasarela (stripe)
            pedido: Diccionario con información del pedido
            **kwargs: Argumentos adicionales específicos de cada pasarela
            
        Returns:
            dict: Resultado de la creación del pago
        """
        if not PaymentGateway.is_available(gateway_name):
            return {
                'success': False,
                'error': f'La pasarela de pago {gateway_name} no está disponible'
            }
        
        gateway = PaymentGateway.GATEWAYS[gateway_name]
        
        # Guardar en sesión la pasarela utilizada para este pedido
        session[f'payment_gateway_{pedido["id"]}'] = gateway_name
        
        # Crear el pago según la pasarela
        if gateway_name == 'stripe':
            return gateway.create_checkout_session(pedido, **kwargs)
        
        return {
            'success': False,
            'error': f'Pasarela de pago no implementada: {gateway_name}'
        }
    
    @staticmethod
    def process_webhook(gateway_name, *args, **kwargs):
        """
        Procesa un webhook de una pasarela de pago
        
        Args:
            gateway_name: Nombre de la pasarela (stripe)
            *args, **kwargs: Argumentos específicos de cada pasarela
            
        Returns:
            dict: Resultado del procesamiento del webhook
        """
        if not PaymentGateway.is_available(gateway_name):
            return {
                'success': False,
                'error': f'La pasarela de pago {gateway_name} no está disponible'
            }
        
        gateway = PaymentGateway.GATEWAYS[gateway_name]
        
        # Verificar el webhook según la pasarela
        if gateway_name == 'stripe':
            return gateway.verify_webhook_signature(*args, **kwargs)
        
        return {
            'success': False,
            'error': f'Procesamiento de webhook no implementado para: {gateway_name}'
        } 