document.addEventListener("DOMContentLoaded", function () {
    console.log("Scripts cargado");

// ============================
// VARIABLES (con verificación)
// ============================

const inputBusqueda = document.getElementById('busqueda-productos');
const sugerencias = document.getElementById('sugerencias');
const tablaVenta = document.querySelector('#tabla-venta tbody');
const totalPagar = document.getElementById('total-pagar');
const montoRecibido = document.getElementById('monto-recibido');
const cambio = document.getElementById('cambio');
const btnFinalizar = document.getElementById('finalizar-venta');

let listaProductos = [];

// ============================
// ACTUALIZAR TABLA
// ============================

function actualizarTabla() {
    if (!tablaVenta) return;

    tablaVenta.innerHTML = '';
    let total = 0;

    listaProductos.forEach((p, i) => {
        const fila = document.createElement('tr');

        fila.innerHTML = `
            <td>${p.nombre}</td>
            <td>
                <button class="menos">-</button>
                ${p.cantidad}
                <button class="mas">+</button>
            </td>
            <td>${p.precio.toFixed(2)}</td>
            <td>${(p.precio * p.cantidad).toFixed(2)}</td>
            <td>
                <button class="eliminar">🗑</button>
            </td>
        `;

        tablaVenta.appendChild(fila);

        // Botón +
        fila.querySelector('.mas').addEventListener('click', () => {
            p.cantidad++;
            actualizarTabla();
        });

        // Botón -
        fila.querySelector('.menos').addEventListener('click', () => {
            p.cantidad--;

            if (p.cantidad <= 0) {
                listaProductos.splice(i, 1);
            }

            actualizarTabla();
        });

        // Botón eliminar
        fila.querySelector('.eliminar').addEventListener('click', () => {
            listaProductos.splice(i, 1);
            actualizarTabla();
        });

        total += p.precio * p.cantidad;
    });

    if (totalPagar) totalPagar.textContent = total.toFixed(2);

    if (montoRecibido && cambio) {
        const recibido = parseFloat(montoRecibido.value) || 0;

        if (recibido > total) {
            cambio.textContent = (recibido - total).toFixed(2);
        } else {
            cambio.textContent = '0.00';
        }
    }
}

// ============================
// BUSQUEDA PRODUCTOS
// ============================

if (inputBusqueda) {
    inputBusqueda.addEventListener('input', async () => {

        const q = inputBusqueda.value.trim();
        if (q.length === 0) {
            sugerencias.innerHTML = '';
            return;
        }

        const resp = await fetch(`/buscar_productos?q=${q}`);
        const productos = await resp.json();

        sugerencias.innerHTML = '';

        productos.forEach(p => {
            const li = document.createElement('li');
            li.textContent = `${p.nombre} - $${p.precio_venta.toFixed(2)}`;

            li.addEventListener('click', () => {
                listaProductos.push({
                    id: p.id,
                    nombre: p.nombre,
                    precio: p.precio_venta,
                    cantidad: 1
                });

                actualizarTabla();
                inputBusqueda.value = '';
                sugerencias.innerHTML = '';
            });

            sugerencias.appendChild(li);
        });
    });
}

// ============================
// MONTO RECIBIDO
// ============================

if (montoRecibido) {
    montoRecibido.addEventListener('input', actualizarTabla);
}

// ============================
// FINALIZAR VENTA
// ============================

if (btnFinalizar) {
    btnFinalizar.addEventListener('click', async () => {

        console.log("Productos actuales:", listaProductos);

        if (listaProductos.length === 0)
            return alert('No hay productos');

        const total = parseFloat(totalPagar.textContent) || 0;
        const recibido = parseFloat(montoRecibido.value) || 0;

        if (recibido < total) {
        return alert('El monto recibido es menor al total');
    }

        const resp = await fetch('/vender', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                detalles: listaProductos,
                recibido: parseFloat(montoRecibido.value || 0)
            })
        });

        if (!resp.ok) {
            const errorData = await resp.json();
            console.error("Error del servidor:", errorData);
            alert(errorData.error || "Error inesperado");
            return;
        }

        const data = await resp.json();

        alert("Venta registrada");

listaProductos = [];
actualizarTabla();

montoRecibido.value = '';
cambio.textContent = '0.00';
    });
}

// ============================
// MODAL TICKET (MEJORADO)
// ============================

document.addEventListener('click', function (e) {

    if (e.target.classList.contains('btn-ticket')) {

        const ventaId = e.target.dataset.id;
        const modalTicket = document.getElementById('modal-ticket');

        if (!modalTicket) return;

        const tablaTicketBody = document.querySelector('#tabla-ticket tbody');
        const totalTicket = document.getElementById('total-ticket');
        const recibidoTicket = document.getElementById('recibido-ticket');
        const cambioTicket = document.getElementById('cambio-ticket');

        fetch(`/ticket/${ventaId}`)
            .then(resp => resp.json())
            .then(data => {
            console.log("DATA COMPLETA:", data);
                let total = 0;

                tablaTicketBody.innerHTML = data.detalles.map(d => {

                    const precio = parseFloat(d.precio_unitario) || 0;
                    const subtotal = parseFloat(d.total) || 0;
                    total += subtotal;

                    return `
                        <tr>
                            <td>${d.nombre}</td>
                            <td>${d.cantidad}</td>
                            <td>${precio.toFixed(2)}</td>
                            <td>${subtotal.toFixed(2)}</td>
                        </tr>
                    `;
                }).join('');

                totalTicket.textContent = total.toFixed(2);
                recibidoTicket.textContent = parseFloat(data.recibido).toFixed(2);
                cambioTicket.textContent = parseFloat(data.cambio).toFixed(2);

                modalTicket.style.display = 'flex';
            });
    }
});

// ============================
// CERRAR MODAL
// ============================

const cerrarBtn = document.getElementById('cerrar-ticket');

if (cerrarBtn) {
    cerrarBtn.addEventListener('click', () => {
        document.getElementById('modal-ticket').style.display = 'none';
    });
}

});