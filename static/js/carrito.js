/**
 * carrito.js - Funciones para gestionar el carrito de compras
 */

// Objeto global para gestión del carrito
window.CartManager = (function() {
    
    // Función para agregar producto al carrito
    function agregarAlCarrito(productoId, cantidad, callback) {
        if (!productoId) {
            console.error('Error: ID de producto no proporcionado');
            mostrarNotificacionError('Error: ID de producto no proporcionado');
            if (typeof callback === 'function') {
                callback(false, { message: 'ID de producto no proporcionado' });
            }
            return;
        }
        
        // Crear el objeto de datos
        const datos = {
            producto_id: productoId,
            cantidad: cantidad || 1
        };

        // URL para agregar al carrito
        const url = '/carrito/agregar';

        // Crear el Toast de notificación
        const notificacion = crearNotificacion();
        
        // Obtener el token CSRF
        const csrfToken = obtenerCSRFToken();
        
        console.log('Enviando petición para agregar al carrito:', datos);
        
        // Realizar la petición AJAX
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(datos),
            credentials: 'same-origin'
        })
        .then(response => {
            // Verificar si la respuesta es exitosa
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Respuesta del servidor:', data);
            
            if (data.success) {
                // Actualizar contador del carrito en la barra de navegación
                actualizarContadorCarrito(data.total_items);
                
                // Mostrar notificación de éxito
                mostrarNotificacion(notificacion, 'success', data.message, data.product_image);
                
                // Ejecutar callback si existe
                if (typeof callback === 'function') {
                    callback(true, data);
                }
            } else {
                // Mostrar notificación de error
                mostrarNotificacion(notificacion, 'error', data.message);
                
                // Ejecutar callback si existe
                if (typeof callback === 'function') {
                    callback(false, data);
                }
            }
        })
        .catch(error => {
            console.error('Error en la petición:', error);
            
            // Mostrar notificación de error
            mostrarNotificacion(notificacion, 'error', 'Ocurrió un error al agregar el producto al carrito');
            
            // Ejecutar callback si existe
            if (typeof callback === 'function') {
                callback(false, { message: error.message });
            }
        });
    }
    
    // Función auxiliar para mostrar notificación de error
    function mostrarNotificacionError(mensaje) {
        const notificacion = crearNotificacion();
        mostrarNotificacion(notificacion, 'error', mensaje);
    }
    
    // Exponemos las funciones públicas
    return {
        agregarAlCarrito: agregarAlCarrito,
        mostrarNotificacionError: mostrarNotificacionError
    };
})();

// Función para obtener el token CSRF
function obtenerCSRFToken() {
    // Primero, buscamos un meta tag con el token CSRF
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    
    // Si no hay meta tag, buscamos en los formularios
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    if (csrfInput) {
        return csrfInput.value;
    }
    
    // Si no encontramos el token, buscamos en todas las cookies
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') {
            return decodeURIComponent(value);
        }
    }
    
    // Si todo falla, devolvemos un string vacío
    console.warn('No se encontró token CSRF');
    return '';
}

// Función para crear una notificación toast
function crearNotificacion() {
    // Si ya existe la notificación, la reutilizamos
    const existente = document.getElementById('carrito-notificacion');
    if (existente) {
        return existente;
    }
    
    // Crear el elemento de notificación
    const notificacion = document.createElement('div');
    notificacion.id = 'carrito-notificacion';
    notificacion.className = 'carrito-toast';
    notificacion.innerHTML = `
        <div class="carrito-toast-contenido">
            <div class="carrito-toast-icono">
                <i class="fas fa-check-circle"></i>
            </div>
            <div class="carrito-toast-mensaje">
                <div class="carrito-toast-titulo">Éxito</div>
                <div class="carrito-toast-texto"></div>
            </div>
            <button class="carrito-toast-cerrar">&times;</button>
        </div>
    `;
    
    // Agregar estilos
    const estilos = document.createElement('style');
    estilos.textContent = `
        .carrito-toast {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 9999;
            display: none;
            transform: translateY(100px);
            transition: all 0.4s cubic-bezier(0.68, -0.55, 0.27, 1.55);
        }
        
        .carrito-toast.mostrar {
            display: block;
            transform: translateY(0);
        }
        
        .carrito-toast-contenido {
            display: flex;
            align-items: center;
            background: white;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            padding: 15px;
            min-width: 300px;
            max-width: 500px;
            overflow: hidden;
            position: relative;
        }
        
        .carrito-toast-icono {
            margin-right: 15px;
            font-size: 24px;
        }
        
        .carrito-toast-icono.success i {
            color: #4CAF50;
        }
        
        .carrito-toast-icono.error i {
            color: #F44336;
        }
        
        .carrito-toast-mensaje {
            flex: 1;
        }
        
        .carrito-toast-titulo {
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .carrito-toast-cerrar {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            opacity: 0.5;
            transition: opacity 0.3s;
        }
        
        .carrito-toast-cerrar:hover {
            opacity: 1;
        }
        
        .carrito-toast-imagen {
            width: 50px;
            height: 50px;
            object-fit: cover;
            border-radius: 5px;
            margin-right: 15px;
        }
        
        /* Estilos para tema oscuro */
        html[data-theme="dark"] .carrito-toast-contenido {
            background: #333;
            color: #eee;
        }
    `;
    
    // Agregar elementos al DOM
    document.head.appendChild(estilos);
    document.body.appendChild(notificacion);
    
    // Agregar evento para cerrar la notificación
    const btnCerrar = notificacion.querySelector('.carrito-toast-cerrar');
    btnCerrar.addEventListener('click', () => {
        notificacion.classList.remove('mostrar');
    });
    
    return notificacion;
}

// Función para mostrar la notificación
function mostrarNotificacion(notificacion, tipo, mensaje, imagenUrl = null) {
    // Actualizar contenido
    const icono = notificacion.querySelector('.carrito-toast-icono');
    const titulo = notificacion.querySelector('.carrito-toast-titulo');
    const texto = notificacion.querySelector('.carrito-toast-texto');
    
    // Quitar clases anteriores
    icono.classList.remove('success', 'error');
    
    // Actualizar según tipo
    if (tipo === 'success') {
        icono.classList.add('success');
        icono.innerHTML = '<i class="fas fa-check-circle"></i>';
        titulo.textContent = 'Producto agregado';
    } else {
        icono.classList.add('error');
        icono.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
        titulo.textContent = 'Error';
    }
    
    // Establecer mensaje
    texto.textContent = mensaje;
    
    // Agregar imagen si existe
    const imagenExistente = notificacion.querySelector('.carrito-toast-imagen');
    if (imagenExistente) {
        imagenExistente.remove();
    }
    
    if (imagenUrl && tipo === 'success') {
        const imagen = document.createElement('img');
        imagen.className = 'carrito-toast-imagen';
        imagen.src = imagenUrl.startsWith('/') ? imagenUrl : '/static/uploads/productos/' + imagenUrl;
        imagen.alt = 'Producto';
        
        const contenido = notificacion.querySelector('.carrito-toast-contenido');
        contenido.insertBefore(imagen, contenido.firstChild);
    }
    
    // Mostrar notificación
    notificacion.classList.add('mostrar');
    
    // Ocultar después de 4 segundos
    setTimeout(() => {
        notificacion.classList.remove('mostrar');
    }, 4000);
}

// Función para actualizar el contador del carrito
function actualizarContadorCarrito(cantidad) {
    const contador = document.querySelector('.cart-counter');
    if (contador) {
        contador.textContent = cantidad;
        
        // Hacer efecto de animación
        contador.style.animation = 'none';
        setTimeout(() => {
            contador.style.animation = 'bounce 0.5s';
        }, 10);
    }
}

// Agregar animación CSS 
const style = document.createElement('style');
style.textContent = `
@keyframes bounce {
    0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
    40% {transform: translateY(-10px);}
    60% {transform: translateY(-5px);}
}
`;
document.head.appendChild(style); 

// Función para formatear precios en miles con puntos (formato colombiano)
window.formatearPrecioCOP = function(valor) {
    // Multiplicar por 1000 para convertir a miles y formatear con separadores de miles
    return '$' + (parseFloat(valor) * 1000).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
};

// Función para formatear precios existentes en la página
window.formatearPreciosEnPagina = function() {
    // Seleccionar todos los elementos con precios en la página
    document.querySelectorAll('.precio-formato, .subtotal-formato, .total-formato').forEach(function(elemento) {
        // Obtener el valor actual, quitar el símbolo $ y espacios
        const valorActual = elemento.textContent.replace('$', '').trim();
        if (!isNaN(parseFloat(valorActual))) {
            // Formatear y actualizar el contenido
            elemento.textContent = window.formatearPrecioCOP(valorActual/1000); // Dividir por 1000 porque ya multiplicamos en la función
        }
    });
};

// Ejecutar al cargar el documento
document.addEventListener('DOMContentLoaded', function() {
    // Formatear precios existentes en la página
    window.formatearPreciosEnPagina();
}); 