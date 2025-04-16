"""
Integración con la pasarela de pago Stripe
"""
import stripe
from flask import current_app, url_for

class StripeGateway:
    """Clase para manejar pagos con Stripe"""
    
    @staticmethod
    def initialize():
        """Inicializa la API de Stripe con la clave secreta"""
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    @staticmethod
    def create_payment_intent(amount, currency='cop', metadata=None):
        """
        Crea una intención de pago en Stripe
        
        Args:
            amount: Cantidad a cobrar (en centavos)
            currency: Moneda (default: COP)
            metadata: Metadatos adicionales para el pago
            
        Returns:
            dict: Datos de la intención de pago
        """
        StripeGateway.initialize()
        
        try:
            # Convertir a centavos si es necesario
            amount_in_cents = int(amount * 100)
            
            # Crear intención de pago
            intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency,
                metadata=metadata or {},
                payment_method_types=['card'],
            )
            
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'id': intent.id
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def create_checkout_session(pedido, success_url=None, cancel_url=None):
        """
        Crea una sesión de pago de Stripe Checkout
        
        Args:
            pedido: Diccionario con información del pedido
            success_url: URL de redirección en caso de éxito
            cancel_url: URL de redirección en caso de cancelación
            
        Returns:
            dict: Datos de la sesión de checkout
        """
        StripeGateway.initialize()
        
        if not success_url:
            success_url = url_for('carrito.confirmacion', pedido_id=pedido['id'], _external=True)
        
        if not cancel_url:
            cancel_url = url_for('carrito.pago', pedido_id=pedido['id'], _external=True)
        
        try:
            # Crear los items de línea para la sesión de checkout
            line_items = []
            
            # Si hay productos en el pedido
            for item in pedido.get('detalles', []):
                line_items.append({
                    'price_data': {
                        'currency': 'cop',
                        'product_data': {
                            'name': item['nombre'],
                            'images': [item.get('imagen_url', '')],
                        },
                        'unit_amount': int(float(item['precio_unitario']) * 100),  # Convertir a centavos
                    },
                    'quantity': item['cantidad'],
                })
            
            # Si no hay detalles, usar el total del pedido
            if not line_items:
                line_items.append({
                    'price_data': {
                        'currency': 'cop',
                        'product_data': {
                            'name': f'Pedido #{pedido["id"]}',
                        },
                        'unit_amount': int(float(pedido['total']) * 100),  # Convertir a centavos
                    },
                    'quantity': 1,
                })
            
            # Crear la sesión de checkout
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'pedido_id': pedido['id']
                }
            )
            
            return {
                'success': True,
                'id': checkout_session.id,
                'url': checkout_session.url
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def verify_webhook_signature(payload, sig_header):
        """
        Verifica la firma de un webhook de Stripe
        
        Args:
            payload: Contenido del webhook
            sig_header: Cabecera de firma
            
        Returns:
            dict: Evento de webhook verificado o error
        """
        webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return {'success': True, 'event': event}
        except ValueError:
            # Invalid payload
            return {'success': False, 'error': 'Payload inválido'}
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return {'success': False, 'error': 'Firma inválida'} 