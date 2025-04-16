// Código para preservar el tema seleccionado por el usuario
document.addEventListener('DOMContentLoaded', function() {
    // Obtener tema guardado en localStorage
    const savedTheme = localStorage.getItem('theme') || 'light';
    console.log('Tema guardado en localStorage:', savedTheme);
    
    // Aplicar el tema guardado en lugar de forzar el tema claro
    document.documentElement.setAttribute('data-theme', savedTheme);
    document.body.setAttribute('data-theme', savedTheme);
    
    // Establecer las clases apropiadas
    document.documentElement.classList.remove('theme-dark', 'theme-light');
    document.body.classList.remove('theme-dark', 'theme-light');
    
    document.documentElement.classList.add('theme-' + savedTheme);
    document.body.classList.add('theme-' + savedTheme);
    
    // Desactivar cualquier selector de tema existente para evitar conflictos
    const themeSelectors = document.querySelectorAll('.theme-selector, [data-toggle="theme"], .theme-toggle, .theme-switch');
    themeSelectors.forEach(selector => {
        if (selector.id !== 'theme-toggle') { // Mantener el selector principal
            selector.style.display = 'none';
            selector.disabled = true;
        }
    });
    
    // Desactivar el observador que forzaba el tema claro
    // Ya no necesitamos este observador, dejaremos que el tema se gestione por base.html
}); 