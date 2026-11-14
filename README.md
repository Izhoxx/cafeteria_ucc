# Cafetería UCC (Flask + SQLite)

    python -m venv venv
    venv\Scripts\activate        (Windows)   |   source venv/bin/activate  (Mac/Linux)
    pip install -r requirements.txt
    python app.py                # abre http://127.0.0.1:5000

Cuentas demo: admin / admin123 · trabajador / trab123 · estudiante / est123
(en la pantalla de login hay botones para llenar los datos con un toque)

- Estudiante: menú con búsqueda, carrito, pago virtual, ticket, mis pedidos con progreso y avisos.
- Trabajador: productos, inventario y pedidos (cambiar estado, cancelar).
- Admin: todo lo anterior + reportes con gráfico y gestión de usuarios y roles.
Interfaz con modo claro/oscuro (botón de la luna), adaptada a celular.
Contraseñas con SHA-256. Pago simulado. En producción define SECRET_KEY.
