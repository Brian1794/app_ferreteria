// Script para administración de reparaciones

document.addEventListener('DOMContentLoaded', function() {
    // Recuperar filtros de la URL y aplicarlos
    const urlParams = new URLSearchParams(window.location.search);
    
    const filtroEstado = document.getElementById('filtro-estado');
    const filtroFecha = document.getElementById('filtro-fecha');
    const filtroBusqueda = document.getElementById('filtro-busqueda');
    
    if (filtroEstado) { filtroEstado.value = urlParams.get('estado') || ''; }
    if (filtroFecha) { filtroFecha.value = urlParams.get('fecha') || ''; }
    if (filtroBusqueda) { filtroBusqueda.value = urlParams.get('q') || ''; }
    
    // Cerrar menús cuando se hace clic fuera
    document.addEventListener('click', function(event) {
        if (!event.target.closest('.action-dropdown')) {
            const dropdowns = document.querySelectorAll('.action-dropdown.show');
            if (dropdowns && dropdowns.length) {
                dropdowns.forEach(function(dropdown) {
                    dropdown.classList.remove('show');
                });
            }
        }
    });
    
    // Delegación de eventos para todos los botones/enlaces con data-action
    document.addEventListener('click', function(event) {
        // Buscar el elemento con data-action más cercano al target del evento
        const actionElement = event.target.closest('[data-action]');
        
        if (!actionElement) return; // Si no hay elemento con data-action, salir
        
        // Prevenir el comportamiento por defecto del enlace
        event.preventDefault();
        
        // Obtener el tipo de acción y el ID
        const action = actionElement.getAttribute('data-action');
        const id = actionElement.getAttribute('data-id');
        
        // Ejecutar la acción correspondiente
        switch (action) {
            case 'toggle-menu':
                toggleActionMenu(actionElement);
                break;
            case 'ver-detalles':
                verDetalles(id);
                break;
            case 'cambiar-estado':
                cambiarEstado(id);
                break;
            case 'asignar-tecnico':
                asignarTecnico(id);
                break;
            case 'cancelar':
                confirmarCancelar(id);
                break;
        }
    });
});

// Función para mostrar/ocultar el menú de acciones
function toggleActionMenu(button) {
    // Cerrar cualquier otro menú abierto
    const dropdowns = document.querySelectorAll('.action-dropdown.show');
    if (dropdowns && dropdowns.length) {
        dropdowns.forEach(function(dropdown) {
            if (dropdown !== button.parentElement) {
                dropdown.classList.remove('show');
            }
        });
    }
    
    // Toggle el menú actual
    if (button && button.parentElement) {
        button.parentElement.classList.toggle('show');
    }
}

// Función para mostrar modal de cambio de estado
function cambiarEstado(id) {
    const form = document.getElementById('formCambiarEstado');
    if (form) {
        // La URL se reemplazará en la plantilla
        const actionUrlTemplate = form.getAttribute('data-url-template');
        if (actionUrlTemplate) {
            form.action = actionUrlTemplate.replace('0', id);
            
            // Mostrar el modal
            const modalElement = document.getElementById('modalCambiarEstado');
            if (modalElement && typeof bootstrap !== 'undefined') {
                const modal = new bootstrap.Modal(modalElement);
                modal.show();
            } else {
                console.error('No se pudo mostrar el modal. Bootstrap no está disponible o el elemento no existe.');
            }
        }
    }
}

// Función para ver detalles (pendiente de implementar)
function verDetalles(id) {
    alert('Funcionalidad de ver detalles por implementar para la reparación #' + id);
}

// Función para asignar técnico (pendiente de implementar)
function asignarTecnico(id) {
    alert('Funcionalidad de asignar técnico por implementar para la reparación #' + id);
}

// Función para confirmar cancelación
function confirmarCancelar(id) {
    if (confirm('¿Estás seguro de que deseas cancelar esta reparación? Esta acción no se puede deshacer.')) {
        const form = document.getElementById('formCambiarEstado');
        if (form) {
            const actionUrlTemplate = form.getAttribute('data-url-template');
            if (actionUrlTemplate) {
                form.action = actionUrlTemplate.replace('0', id);
                
                const estadoSelect = document.getElementById('estado');
                if (estadoSelect) { estadoSelect.value = 'cancelada'; }
                
                const comentarioTextarea = document.getElementById('comentario');
                if (comentarioTextarea) { comentarioTextarea.value = 'Reparación cancelada por el administrador.'; }
                
                form.submit();
            }
        }
    }
} 