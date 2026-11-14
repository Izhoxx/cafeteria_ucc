"""Cafetería UCC - Flask + SQLite. Ejecutar: python app.py"""
import hashlib, os, sqlite3, uuid, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "cafeteria.db")
os.makedirs(UPLOADS, exist_ok=True)
UPLOADS = os.path.join(BASE, "static", "uploads")
EXT = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB


def sha(t): return hashlib.sha256(t.encode()).hexdigest()
def cop(n): return "$" + f"{int(n):,}".replace(",", ".")
app.jinja_env.filters["cop"] = cop


# ---------- Base de datos ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios(
      id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, rol TEXT NOT NULL DEFAULT 'Estudiante');
    CREATE TABLE IF NOT EXISTS productos(
      id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, descripcion TEXT DEFAULT '',
      precio INTEGER NOT NULL, stock INTEGER NOT NULL DEFAULT 0,
      disponible INTEGER NOT NULL DEFAULT 1, foto TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS pedidos(
      id INTEGER PRIMARY KEY, ref TEXT UNIQUE NOT NULL, usuario_id INTEGER NOT NULL,
      fecha TEXT NOT NULL, metodo TEXT NOT NULL, transaccion TEXT NOT NULL,
      estado TEXT NOT NULL DEFAULT 'Pendiente', total INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS detalle(
      id INTEGER PRIMARY KEY, pedido_id INTEGER NOT NULL, producto_id INTEGER,
      nombre TEXT NOT NULL, cantidad INTEGER NOT NULL, precio INTEGER NOT NULL);
    """)
    if not c.execute("SELECT 1 FROM usuarios").fetchone():
        c.executemany("INSERT INTO usuarios(nombre,username,password_hash,rol) VALUES(?,?,?,?)", [
            ("Administrador", "admin", sha("admin123"), "Admin"),
            ("Estudiante Demo", "estudiante", sha("est123"), "Estudiante")])
        c.executemany("INSERT INTO productos(nombre,descripcion,precio,stock) VALUES(?,?,?,?)", [
            ("Café americano", "Café negro recién preparado, 8 oz.", 2500, 40),
            ("Empanada de carne", "Empanada crocante rellena de carne y papa.", 2000, 30),
            ("Jugo de naranja", "Jugo natural exprimido al momento.", 4000, 20),
            ("Sándwich mixto", "Jamón, queso y pan tostado.", 6500, 15),
            ("Brownie", "Brownie de chocolate con nueces.", 3500, 0)])
    cols = lambda t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
    if "activo" not in cols("usuarios"):
        c.execute("ALTER TABLE usuarios ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
    if "fecha_iso" not in cols("pedidos"):
        c.execute("ALTER TABLE pedidos ADD COLUMN fecha_iso TEXT")
        for i, f in c.execute("SELECT id,fecha FROM pedidos").fetchall():
            try: c.execute("UPDATE pedidos SET fecha_iso=? WHERE id=?", (datetime.strptime(f, "%d/%m/%Y %H:%M").strftime("%Y-%m-%d %H:%M"), i))
            except ValueError: pass
    c.executescript("""
    CREATE TABLE IF NOT EXISTS movimientos(
      id INTEGER PRIMARY KEY, producto_id INTEGER, producto TEXT NOT NULL, tipo TEXT NOT NULL,
      cantidad INTEGER NOT NULL, fecha TEXT NOT NULL, usuario TEXT, nota TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS notificaciones(
      id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL, mensaje TEXT NOT NULL,
      fecha TEXT NOT NULL, leida INTEGER NOT NULL DEFAULT 0);
    """)
    if not c.execute("SELECT 1 FROM usuarios WHERE username='trabajador'").fetchone():
        c.execute("INSERT INTO usuarios(nombre,username,password_hash,rol) VALUES(?,?,?,?)", ("Trabajador Demo", "trabajador", sha("trab123"), "Trabajador"))
    c.commit(); c.close()


# ---------- Autenticación ----------
@app.before_request
def cargar_usuario():
    g.user = None
    if session.get("uid"):
        g.user = db().execute("SELECT * FROM usuarios WHERE id=?", (session["uid"],)).fetchone()
    if request.method == "POST":  # protección CSRF básica
        if not request.form.get("csrf") or request.form.get("csrf") != session.get("csrf"):
            abort(400, "Sesión inválida. Recarga la página.")

@app.context_processor
def inject():
    if "csrf" not in session: session["csrf"] = secrets.token_hex(16)
    n = sum(session.get("cart", {}).values())
    nn = 0
    if g.get("user") and g.user["rol"] == "Estudiante":
        nn = db().execute("SELECT COUNT(*) FROM notificaciones WHERE usuario_id=? AND leida=0", (g.user["id"],)).fetchone()[0]
    return dict(user=g.get("user"), csrf=session["csrf"], cart_n=n, notif_n=nn)

def login_required(rol=None):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if not g.user: return redirect(url_for("login"))
            if rol == "Admin" and g.user["rol"] != "Admin": abort(403)
            if rol == "Staff" and g.user["rol"] == "Estudiante": abort(403)
            if rol == "Estudiante" and g.user["rol"] != "Estudiante": return redirect(url_for("index"))
            return f(*a, **k)
        return w
    return deco

@app.route("/")
def index():
    if not g.user: return redirect(url_for("login"))
    return redirect(url_for({"Estudiante": "menu", "Trabajador": "admin_pedidos"}.get(g.user["rol"], "admin")))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM usuarios WHERE username=? AND password_hash=? AND activo=1",
                         (request.form["username"].strip(), sha(request.form["password"]))).fetchone()
        if u:
            session.clear(); session["uid"] = u["id"]; return redirect(url_for("index"))
        flash("Usuario o contraseña incorrectos. Intenta de nuevo.", "error")
    return render_template("login.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        n, u, p = (request.form[k].strip() for k in ("nombre", "username", "password"))
        if not n or not u or len(p) < 4:
            flash("Completa todos los campos (contraseña mínimo 4 caracteres).", "error")
        else:
            try:
                db().execute("INSERT INTO usuarios(nombre,username,password_hash) VALUES(?,?,?)", (n, u, sha(p)))
                db().commit(); flash("Cuenta creada. Ya puedes ingresar.", "ok")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Ese usuario ya existe.", "error")
    return render_template("registro.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear(); return redirect(url_for("login"))


# ---------- Panel estudiante ----------
@app.route("/menu")
@login_required("Estudiante")
def menu():
    return render_template("menu.html", productos=db().execute("SELECT * FROM productos WHERE disponible=1 OR stock>0 ORDER BY id").fetchall())

def items_carrito():
    items, total = [], 0
    for pid, q in session.get("cart", {}).items():
        p = db().execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone()
        if p: items.append((p, q)); total += p["precio"] * q
    return items, total

@app.route("/carrito")
@login_required("Estudiante")
def carrito():
    items, total = items_carrito()
    return render_template("carrito.html", items=items, total=total)

@app.route("/carrito/<int:pid>/<accion>", methods=["POST"])
@login_required("Estudiante")
def carrito_accion(pid, accion):
    cart = session.get("cart", {}); k = str(pid)
    p = db().execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone()
    if not p: abort(404)
    q = cart.get(k, 0)
    if accion == "mas":
        if not p["disponible"] or q + 1 > p["stock"]:
            flash(f"No hay más unidades disponibles de {p['nombre']}.", "error")
        else: cart[k] = q + 1
    elif accion == "menos":
        if q <= 1: cart.pop(k, None)
        else: cart[k] = q - 1
    elif accion == "quitar": cart.pop(k, None)
    session["cart"] = cart
    return redirect(request.form.get("next") or url_for("carrito"))

@app.route("/carrito/vaciar", methods=["POST"])
@login_required("Estudiante")
def vaciar():
    session["cart"] = {}; return redirect(url_for("carrito"))

@app.route("/pago", methods=["GET", "POST"])
@login_required("Estudiante")
def pago():
    items, total = items_carrito()
    if not items: return redirect(url_for("carrito"))
    if request.method == "POST":
        metodo = request.form.get("metodo", "Nequi"); dato = request.form.get("dato", "").replace(" ", "")
        if metodo != "PSE" and len(dato) < (12 if metodo == "Tarjeta" else 10):
            flash("Verifica los datos de pago.", "error")
            return render_template("pago.html", total=total)
        con = db()
        try:
            con.execute("BEGIN IMMEDIATE")
            for p, q in items:  # verificar inventario justo antes de cobrar
                act = con.execute("SELECT stock,disponible FROM productos WHERE id=?", (p["id"],)).fetchone()
                if not act or not act["disponible"] or act["stock"] < q:
                    con.rollback(); flash(f"Sin disponibilidad suficiente de {p['nombre']}. Ajusta tu pedido.", "error")
                    return redirect(url_for("carrito"))
            cur = con.execute("INSERT INTO pedidos(ref,usuario_id,fecha,fecha_iso,metodo,transaccion,total) VALUES('',?,?,?,?,?,?)",
                (g.user["id"], datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M"), metodo, "TX" + uuid.uuid4().hex[:8].upper(), total))
            pid = cur.lastrowid; ref = f"UCC-{1000 + pid}"
            con.execute("UPDATE pedidos SET ref=? WHERE id=?", (ref, pid))
            for p, q in items:
                con.execute("INSERT INTO detalle(pedido_id,producto_id,nombre,cantidad,precio) VALUES(?,?,?,?,?)", (pid, p["id"], p["nombre"], q, p["precio"]))
                con.execute("UPDATE productos SET stock=stock-? WHERE id=?", (q, p["id"]))
                mov(con, p["id"], p["nombre"], "Venta", q, ref, g.user["nombre"])
            notificar(con, g.user["id"], f"Tu pedido {ref} fue confirmado y está Pendiente.")
            con.commit()
        except Exception:
            con.rollback(); raise
        session["cart"] = {}
        return redirect(url_for("ticket", ref=ref))
    return render_template("pago.html", total=total)

@app.route("/ticket/<ref>")
@login_required()
def ticket(ref):
    o = db().execute("SELECT p.*,u.nombre cliente FROM pedidos p JOIN usuarios u ON u.id=p.usuario_id WHERE ref=?", (ref,)).fetchone()
    if not o or (g.user["rol"] == "Estudiante" and o["usuario_id"] != g.user["id"]): abort(404)
    det = db().execute("SELECT * FROM detalle WHERE pedido_id=?", (o["id"],)).fetchall()
    return render_template("ticket.html", o=o, det=det)

@app.route("/mis-pedidos")
@login_required("Estudiante")
def mis_pedidos():
    return render_template("mis_pedidos.html", pedidos=db().execute("SELECT * FROM pedidos WHERE usuario_id=? ORDER BY id DESC", (g.user["id"],)).fetchall())


# ---------- Panel administrador ----------
@app.route("/admin")
@login_required("Staff")
def admin():
    return render_template("admin_productos.html", productos=db().execute("SELECT * FROM productos ORDER BY id").fetchall())

def guardar_foto(f, actual=""):
    if not f or not f.filename: return actual
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in EXT:
        flash("Formato de imagen no permitido (usa png, jpg, webp o gif).", "error"); return actual
    nombre = uuid.uuid4().hex + "." + ext
    f.save(os.path.join(UPLOADS, secure_filename(nombre)))
    return nombre

@app.route("/admin/producto/nuevo", methods=["GET", "POST"])
@app.route("/admin/producto/<int:pid>/editar", methods=["GET", "POST"])
@login_required("Staff")
def producto_form(pid=None):
    p = db().execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone() if pid else None
    if pid and not p: abort(404)
    if request.method == "POST":
        try:
            nombre = request.form["nombre"].strip(); precio = int(request.form["precio"]); stock = max(0, int(request.form["stock"] or 0))
            if not nombre or precio <= 0: raise ValueError
        except ValueError:
            flash("Ingresa un nombre y un precio válido.", "error")
            return render_template("producto_form.html", p=p)
        desc = request.form.get("descripcion", "").strip(); disp = 1 if request.form.get("disponible") else 0
        foto = guardar_foto(request.files.get("foto"), p["foto"] if p else "")
        if p:
            db().execute("UPDATE productos SET nombre=?,descripcion=?,precio=?,stock=?,disponible=?,foto=? WHERE id=?", (nombre, desc, precio, stock, disp, foto, pid))
        else:
            db().execute("INSERT INTO productos(nombre,descripcion,precio,stock,disponible,foto) VALUES(?,?,?,?,?,?)", (nombre, desc, precio, stock, disp, foto))
        db().commit(); flash("Producto guardado.", "ok")
        return redirect(url_for("admin"))
    return render_template("producto_form.html", p=p)

@app.route("/admin/producto/<int:pid>/eliminar", methods=["POST"])
@login_required("Staff")
def producto_eliminar(pid):
    db().execute("DELETE FROM productos WHERE id=?", (pid,)); db().commit()
    flash("Producto eliminado.", "ok"); return redirect(url_for("admin"))

@app.route("/admin/pedidos")
@login_required("Staff")
def admin_pedidos():
    peds = db().execute("SELECT p.*,u.nombre cliente FROM pedidos p JOIN usuarios u ON u.id=p.usuario_id ORDER BY p.id DESC").fetchall()
    ing = db().execute("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM pedidos WHERE estado!='Cancelado'").fetchone()
    return render_template("admin_pedidos.html", pedidos=peds, ingresos=ing, estados=["Pendiente", "En preparación", "Listo", "Entregado", "Cancelado"])

ESTADOS = ["Pendiente", "En preparación", "Listo", "Entregado", "Cancelado"]
ROLES = ("Estudiante", "Trabajador", "Admin")

def mov(con, pid, nombre, tipo, cant, nota, quien):
    con.execute("INSERT INTO movimientos(producto_id,producto,tipo,cantidad,fecha,usuario,nota) VALUES(?,?,?,?,?,?,?)",
                (pid, nombre, tipo, cant, datetime.now().strftime("%d/%m/%Y %H:%M"), quien, nota))

def notificar(con, uid, msg):
    con.execute("INSERT INTO notificaciones(usuario_id,mensaje,fecha) VALUES(?,?,?)", (uid, msg, datetime.now().strftime("%d/%m/%Y %H:%M")))

@app.route("/admin/pedidos/<int:pid>/estado", methods=["POST"])
@login_required("Staff")
def pedido_estado(pid):
    est = request.form.get("estado"); con = db()
    o = con.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()
    if not o or est not in ESTADOS: abort(400)
    if o["estado"] == "Cancelado":
        flash("Un pedido cancelado no se puede reactivar.", "error")
    elif est != o["estado"]:
        con.execute("UPDATE pedidos SET estado=? WHERE id=?", (est, pid))
        if est == "Cancelado":
            for d in con.execute("SELECT * FROM detalle WHERE pedido_id=?", (pid,)).fetchall():
                con.execute("UPDATE productos SET stock=stock+? WHERE id=?", (d["cantidad"], d["producto_id"]))
                mov(con, d["producto_id"], d["nombre"], "Devolución", d["cantidad"], f"Cancelación {o['ref']}", g.user["nombre"])
            notificar(con, o["usuario_id"], f"Tu pedido {o['ref']} fue cancelado. Las unidades volvieron al inventario.")
        else:
            notificar(con, o["usuario_id"], f"Tu pedido {o['ref']} ahora está: {est}.")
        con.commit(); flash("Estado actualizado.", "ok")
    return redirect(url_for("admin_pedidos"))

@app.route("/admin/inventario", methods=["GET", "POST"])
@login_required("Staff")
def inventario():
    con = db()
    if request.method == "POST":
        try: pid = int(request.form["producto"]); cant = int(request.form["cantidad"]); tipo = request.form["tipo"]
        except (ValueError, KeyError): abort(400)
        p = con.execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone()
        if not p or cant <= 0 or tipo not in ("Entrada", "Salida"): flash("Datos inválidos.", "error")
        elif tipo == "Salida" and cant > p["stock"]: flash(f"No puedes sacar más de {p['stock']} unidades de {p['nombre']}.", "error")
        else:
            con.execute("UPDATE productos SET stock=stock+? WHERE id=?", (cant if tipo == "Entrada" else -cant, pid))
            mov(con, pid, p["nombre"], tipo, cant, request.form.get("nota", "").strip(), g.user["nombre"])
            con.commit(); flash("Movimiento registrado.", "ok")
        return redirect(url_for("inventario"))
    return render_template("admin_inventario.html", productos=con.execute("SELECT * FROM productos ORDER BY nombre").fetchall(),
                           movs=con.execute("SELECT * FROM movimientos ORDER BY id DESC LIMIT 50").fetchall())

@app.route("/admin/reportes")
@login_required("Admin")
def reportes():
    hoy = datetime.now().date()
    desde = request.args.get("desde") or (hoy - timedelta(days=6)).isoformat()
    hasta = request.args.get("hasta") or hoy.isoformat()
    if desde > hasta: desde, hasta = hasta, desde
    modo = "semanal" if request.args.get("modo") == "semanal" else "diario"
    grp = "strftime('%Y-%m-%d',fecha_iso)" if modo == "diario" else "'Semana ' || strftime('%Y-%W',fecha_iso)"
    con = db()
    filas = con.execute(f"SELECT {grp} periodo, COUNT(*) ventas, SUM(total) ingresos FROM pedidos WHERE estado!='Cancelado' AND date(fecha_iso) BETWEEN ? AND ? GROUP BY periodo ORDER BY periodo", (desde, hasta)).fetchall()
    top = con.execute("SELECT d.nombre, SUM(d.cantidad) cant, SUM(d.cantidad*d.precio) ing FROM detalle d JOIN pedidos p ON p.id=d.pedido_id WHERE p.estado!='Cancelado' AND date(p.fecha_iso) BETWEEN ? AND ? GROUP BY d.nombre ORDER BY cant DESC LIMIT 5", (desde, hasta)).fetchall()
    return render_template("admin_reportes.html", filas=filas, top=top, desde=desde, hasta=hasta, modo=modo,
                           total=sum(f["ingresos"] for f in filas), n=sum(f["ventas"] for f in filas))

@app.route("/admin/usuarios", methods=["GET", "POST"])
@login_required("Admin")
def usuarios():
    con = db()
    if request.method == "POST":
        n, u, p, r = (request.form.get(k, "").strip() for k in ("nombre", "username", "password", "rol"))
        if not n or not u or len(p) < 4 or r not in ROLES: flash("Completa todos los campos (contraseña mínimo 4 caracteres).", "error")
        else:
            try: con.execute("INSERT INTO usuarios(nombre,username,password_hash,rol) VALUES(?,?,?,?)", (n, u, sha(p), r)); con.commit(); flash("Usuario creado.", "ok")
            except sqlite3.IntegrityError: flash("Ese usuario ya existe.", "error")
        return redirect(url_for("usuarios"))
    return render_template("admin_usuarios.html", usuarios=con.execute("SELECT * FROM usuarios ORDER BY id").fetchall(), roles=ROLES)

@app.route("/admin/usuarios/<int:uid>", methods=["POST"])
@login_required("Admin")
def usuario_editar(uid):
    r = request.form.get("rol"); act = 1 if request.form.get("activo") else 0
    if r not in ROLES: abort(400)
    if uid == g.user["id"] and (r != "Admin" or not act): flash("No puedes quitarte tu propio rol de Admin ni desactivarte.", "error")
    else: db().execute("UPDATE usuarios SET rol=?,activo=? WHERE id=?", (r, act, uid)); db().commit(); flash("Usuario actualizado.", "ok")
    return redirect(url_for("usuarios"))

@app.route("/notificaciones")
@login_required("Estudiante")
def notificaciones():
    con = db(); ns = con.execute("SELECT * FROM notificaciones WHERE usuario_id=? ORDER BY id DESC LIMIT 50", (g.user["id"],)).fetchall()
    con.execute("UPDATE notificaciones SET leida=1 WHERE usuario_id=?", (g.user["id"],)); con.commit()
    return render_template("notificaciones.html", ns=ns)


init_db()
if __name__ == "__main__":
    app.run(debug=True)
