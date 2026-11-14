# Cafetería UCC (Flask + SQLite)

Aplicación web para hacer pedidos en la cafetería del Campus Montería sin filas.

## Requisitos
Python 3.10 o superior.

## Ejecución
```
python -m venv venv
venv\Scripts\activate          (Windows)
source venv/bin/activate       (Mac/Linux)
pip install -r requirements.txt
python app.py
```
Abrir http://127.0.0.1:5000. La base de datos (`cafeteria.db`) se crea sola la primera vez.

## Cuentas de prueba
| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | admin | admin123 |
| Trabajador | trabajador | trab123 |
| Estudiante | estudiante | est123 |

En la pantalla de login hay botones para llenar los datos con un toque.

## Funcionalidades
- **Estudiante:** menú con búsqueda, carrito, pago virtual, ticket, mis pedidos con progreso y avisos.
- **Trabajador:** productos, inventario y pedidos (cambiar estado, cancelar).
- **Administrador:** todo lo anterior, más reportes con gráfico y gestión de usuarios y roles.

Interfaz con modo claro/oscuro, adaptada a celular. Contraseñas con SHA-256. El pago es una simulación académica. En producción, definir la variable `SECRET_KEY`.

