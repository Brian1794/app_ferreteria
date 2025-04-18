document.addEventListener('DOMContentLoaded', function() {
    const termsCheck = document.getElementById('terms-check');
    const completarPagoBtn = document.querySelector('#completar-pago-btn');
    const pagoForm = document.getElementById('pago-form');
    
    termsCheck?.addEventListener('change', function() {
        completarPagoBtn.disabled = !this.checked;
    });

    pagoForm?.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validar campos requeridos
        const requiredFields = ['banco_pse', 'tipo_persona', 'tipo_documento', 'numero_documento'];
        let hasErrors = false;
        
        requiredFields.forEach(field => {
            const input = this.querySelector(`[name="${field}"]`);
            if (!input || !input.value.trim()) {
                hasErrors = true;
                input?.classList.add('is-invalid');
            } else {
                input.classList.remove('is-invalid');
            }
        });

        if (hasErrors) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Por favor complete todos los campos requeridos'
            });
            return;
        }

        if (!termsCheck?.checked) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Debes aceptar los términos y condiciones para continuar'
            });
            return;
        }

        // Mostrar confirmación antes de proceder
        Swal.fire({
            title: '¿Desea continuar con el pago?',
            text: 'Se procederá a redirigirle al portal de pagos PSE de su banco seleccionado',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Sí, proceder al pago',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                const formData = new FormData(this);
                
                // Mostrar loading
                Swal.fire({
                    title: 'Procesando...',
                    text: 'Por favor espere mientras procesamos su pago',
                    allowOutsideClick: false,
                    allowEscapeKey: false,
                    showConfirmButton: false,
                    willOpen: () => {
                        Swal.showLoading();
                    }
                });

                // Enviar petición al servidor
                fetch('/pagos/pse/iniciar', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Error en la respuesta del servidor');
                    }
                    return response.text();
                })
                .then(html => {
                    // Como la respuesta es HTML, reemplazamos el contenido
                    document.documentElement.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error:', error);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'Ocurrió un error al procesar el pago. Por favor intente nuevamente.'
                    });
                });
            }
        });
    });
});