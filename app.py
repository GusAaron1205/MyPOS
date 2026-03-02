from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import os
from datetime import datetime, timedelta
import webbrowser
import threading
import uuid
import zipfile
import shutil
import tempfile
import requests
import sys
import hashlib

# ----------------------------
# APP Y VERSION
# ----------------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

VERSION_APP = "1.0.0"

def version_to_tuple(v):
    return tuple(map(int, v.split(".")))

# ----------------------------
# FUNCIONES DE ACTUALIZACIÓN
# ----------------------------

def calcular_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for bloque in iter(lambda: f.read(4096), b""):
            sha256.update(bloque)
    return sha256.hexdigest()


def descargar_y_actualizar(url_zip, url_hash):
    backup_dir = os.path.join(os.getcwd(), "backup_temp")

    try:
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, "update.zip")

        # -------------------------
        # 1️⃣ Descargar ZIP
        # -------------------------
        r = requests.get(url_zip, timeout=20)
        r.raise_for_status()

        with open(zip_path, "wb") as f:
            f.write(r.content)

        # -------------------------
        # 2️⃣ Descargar HASH
        # -------------------------
        r_hash = requests.get(url_hash, timeout=10)
        r_hash.raise_for_status()
        hash_online = r_hash.text.strip()

        hash_local = calcular_sha256(zip_path)

        if hash_local != hash_online:
            return False, "El archivo está corrupto o fue modificado."

        # -------------------------
        # 3️⃣ Crear BACKUP
        # -------------------------
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

        os.makedirs(backup_dir)

        for item in os.listdir(os.getcwd()):

            # Excluir archivos que no deben copiarse
            if item in ["backup_temp", "__pycache__"]:
                continue

            # Si es ejecutable en Windows, no copiarlo
            if item.endswith(".exe"):
                continue

            origen = os.path.join(os.getcwd(), item)
            destino = os.path.join(backup_dir, item)

            if os.path.isdir(origen):
                shutil.copytree(origen, destino)
            else:
                shutil.copy2(origen, destino)

        # -------------------------
        # 4️⃣ Extraer UPDATE
        # -------------------------
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)

        contenido = os.listdir(tmp_dir)
        contenido.remove("update.zip")

        carpeta_update = os.path.join(tmp_dir, contenido[0])

        # -------------------------
        # 5️⃣ Reemplazar archivos
        # -------------------------
        for item in os.listdir(carpeta_update):
            origen = os.path.join(carpeta_update, item)
            destino = os.path.join(os.getcwd(), item)

            if os.path.isdir(origen):
                if os.path.exists(destino):
                    shutil.rmtree(destino)
                shutil.copytree(origen, destino)
            else:
                shutil.copy2(origen, destino)

        shutil.rmtree(tmp_dir)
        shutil.rmtree(backup_dir)

        return True, "Actualización instalada correctamente"

    except Exception as e:

        # -------------------------
        # 6️⃣ RESTAURAR BACKUP
        # -------------------------
        if os.path.exists(backup_dir):
            for item in os.listdir(backup_dir):
                origen = os.path.join(backup_dir, item)
                destino = os.path.join(os.getcwd(), item)

                if os.path.isdir(destino):
                    shutil.rmtree(destino)
                elif os.path.exists(destino):
                    os.remove(destino)

                if os.path.isdir(origen):
                    shutil.copytree(origen, destino)
                else:
                    shutil.copy2(origen, destino)

            shutil.rmtree(backup_dir)

        return False, f"Error y restaurado backup: {str(e)}"

# ----------------------------
# ENDPOINTS DE ACTUALIZACIÓN
# ----------------------------
@app.route("/check_update")
def check_update():
    try:
        url = "https://raw.githubusercontent.com/GusAaron1205/MyPOS/main/version.txt"
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        latest_version = response.text.strip()

        # Validar formato de versión
        try:
            latest_tuple = tuple(map(int, latest_version.split(".")))
        except ValueError:
            return jsonify({"update": False, "error": f"Formato de versión inválido: '{latest_version}'"})

        if version_to_tuple(VERSION_APP) < latest_tuple:
            return jsonify({
    "update": True,
    "latest_version": latest_version,
    "url_zip": "https://raw.githubusercontent.com/GusAaron1205/MyPOS/main/update.zip",
    "url_hash": "https://raw.githubusercontent.com/GusAaron1205/MyPOS/main/update_hash.txt"
})
        else:
            return jsonify({"update": False, "latest_version": latest_version})

    except requests.exceptions.RequestException as e:
        return jsonify({"update": False, "error": f"No se pudo obtener versión online: {e}"})

#-------------------------------------
#UPDATE
#-------------------------------------

@app.route("/update", methods=["POST"])
def update():
    try:
        data = request.json
        url_zip = data.get("url_zip")
        url_hash = data.get("url_hash")

        if not url_zip or not url_hash:
            return jsonify({"success": False, "error": "Faltan URLs"})

        success, msg = descargar_y_actualizar(url_zip, url_hash)

        if success:
            os.execv(sys.executable, [sys.executable] + sys.argv)

        return jsonify({"success": success, "message": msg})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ----------------------------
# RUTA BASE DE DATOS
# ----------------------------
BASE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "MiPOS")
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, "database.db")
print("BASE_DIR:", BASE_DIR)
print("DB_PATH:", DB_PATH)

# ----------------------------
# CONEXIÓN A BASE DE DATOS
# ----------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def obtener_id_equipo():
    return str(uuid.getnode())

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version")
    version = cursor.fetchone()[0]

    # ==============================
    # VERSION 1 - CREACIÓN INICIAL
    # ==============================
    if version == 0:

        conn.execute("""
            CREATE TABLE licencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT NOT NULL,
                equipo_id TEXT NOT NULL,
                fecha_activacion TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                contraseña TEXT NOT NULL,
                rol TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                precio_compra REAL NOT NULL,
                precio_venta REAL NOT NULL,
                stock INTEGER NOT NULL,
                merma_mes INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usuario_id INTEGER,
                total REAL,
                recibido REAL,
                cambio REAL,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)

        conn.execute("""
            CREATE TABLE detalle_venta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id INTEGER NOT NULL,
                producto_id INTEGER,
                nombre_producto TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                precio_unitario REAL NOT NULL,
                FOREIGN KEY(venta_id) REFERENCES ventas(id)
            )
        """)

        conn.execute("""
            INSERT INTO usuarios(nombre, contraseña, rol)
            VALUES (?, ?, ?)
        """, ("admin", "1234", "admin"))

        conn.execute("PRAGMA user_version = 1")
        version = 1

    # ==============================
    # VERSION 2 - AGREGAR DESCUENTO
    # ==============================
    if version < 2:
        try:
            conn.execute("ALTER TABLE ventas ADD COLUMN descuento REAL DEFAULT 0")
        except:
            pass
        conn.execute("PRAGMA user_version = 2")
        version = 2

    # ==============================
    # VERSION 3 - CÓDIGO DE BARRAS
    # ==============================
    if version < 3:
        try:
            conn.execute("ALTER TABLE productos ADD COLUMN codigo_barras TEXT")
        except:
            pass
        conn.execute("PRAGMA user_version = 3")
        version = 3

    conn.commit()
    conn.close()

# ----------------------------
# VERIFICAR LICENCIA
# ----------------------------
def licencia_activa():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT equipo_id FROM licencia LIMIT 1")
    resultado = cursor.fetchone()

    conn.close()

    if resultado is None:
        return False

    equipo_actual = obtener_id_equipo()

    return resultado["equipo_id"] == equipo_actual


CLAVE_SECRETA = "GUS_POS_2026"

def validar_clave(clave):
    try:
        texto = clave + CLAVE_SECRETA
        hash_generado = hashlib.sha256(texto.encode()).hexdigest()

        # Regla secreta: hash debe terminar en "00"
        return hash_generado.endswith("00")
    except:
        return False

def activar_licencia(clave):
    equipo_id = obtener_id_equipo()

    conn = get_db_connection()

    # Opcional pero recomendable: borrar licencia anterior
    conn.execute("DELETE FROM licencia")

    conn.execute("""
        INSERT INTO licencia (clave, equipo_id, fecha_activacion)
        VALUES (?, ?, datetime('now'))
    """, (clave, equipo_id))

    conn.commit()
    conn.close()
#-------------------------------
# Activasion
#-------------------------------

@app.route("/activar", methods=["GET", "POST"])
def activar():
    if request.method == "POST":
        clave = request.form["clave"]

        if validar_clave(clave):
            activar_licencia(clave)
            return redirect("/")
        else:
            return render_template("activar.html", error="Clave inválida")

    return render_template("activar.html")

# ----------------------------
# LOGIN
# ----------------------------

@app.route("/", methods=["GET", "POST"])
def login():

    if not licencia_activa():
        return redirect("/activar")

    if request.method == "POST":
        nombre = request.form["nombre"]
        contraseña = request.form["contraseña"]
        conn = get_db_connection()
        usuario = conn.execute("SELECT * FROM usuarios WHERE nombre=? AND contraseña=?",
                               (nombre, contraseña)).fetchone()
        conn.close()
        if usuario:
            session["usuario_id"] = usuario["id"]
            session["rol"] = usuario["rol"]
            session["nombre"] = usuario["nombre"]
            return redirect("/ventas")
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

# ----------------------------
# VENTAS
# ----------------------------
@app.route("/ventas")
def ventas():
    if "usuario_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    productos = conn.execute("SELECT * FROM productos").fetchall()
    conn.close()
    return render_template("ventas.html", productos=productos)

# ----------------------------
# BÚSQUEDA DE PRODUCTOS (para la barra)
# ----------------------------
@app.route("/buscar_productos")
def buscar_productos():
    q = request.args.get("q", "")
    conn = get_db_connection()
    productos = conn.execute(
        "SELECT id, nombre, precio_venta FROM productos WHERE nombre LIKE ?",
        (f"%{q}%",)
    ).fetchall()
    conn.close()
    resultado = [{"id": p["id"], "nombre": p["nombre"], "precio_venta": p["precio_venta"]} for p in productos]
    return jsonify(resultado)

# ----------------------------
# REGISTRAR VENTA FINAL
# ----------------------------
@app.route("/vender", methods=["POST"])
def vender_lista():
    productos = request.json.get("detalles", [])
    recibido = float(request.json.get("recibido", 0))

    if not productos:
        return jsonify({"error": "No hay productos para vender"}), 400

    conn = get_db_connection()
    total = 0

    # ==============================
    # CALCULAR TOTAL DESDE BD
    # ==============================

    for p in productos:
        producto_db = conn.execute(
            "SELECT stock, precio_venta, nombre FROM productos WHERE id=?",
            (p["id"],)
        ).fetchone()

        if not producto_db:
            conn.close()
            return jsonify({"error": "Producto no encontrado"}), 400

        if p["cantidad"] > producto_db["stock"]:
            conn.close()
            return jsonify({"error": "Stock insuficiente"}), 400

        total += producto_db["precio_venta"] * p["cantidad"]

    # ==============================
    # VALIDAR DINERO SUFICIENTE
    # ==============================

    if recibido < total:
        conn.close()
        return jsonify({
            "error": f"Dinero insuficiente. Total: ${total:.2f}"
        }), 400

    cambio = recibido - total

    # ==============================
    # INSERTAR VENTA
    # ==============================

    conn.execute(
        """
        INSERT INTO ventas (usuario_id, total, recibido, cambio)
        VALUES (?, ?, ?, ?)
        """,
        (session["usuario_id"], total, recibido, cambio)
    )

    venta_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ==============================
    # INSERTAR DETALLES Y ACTUALIZAR STOCK
    # ==============================

    for p in productos:
        producto_db = conn.execute(
            "SELECT stock, precio_venta, nombre FROM productos WHERE id=?",
            (p["id"],)
        ).fetchone()

        precio_unitario = producto_db["precio_venta"]

        conn.execute(
            """
            INSERT INTO detalle_venta
            (venta_id, producto_id, nombre_producto, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                venta_id,
                p["id"],
                producto_db["nombre"],  # SNAPSHOT DEL NOMBRE
                p["cantidad"],
                precio_unitario
            )
        )

        nuevo_stock = producto_db["stock"] - p["cantidad"]

        conn.execute(
            "UPDATE productos SET stock=? WHERE id=?",
            (nuevo_stock, p["id"])
        )

    conn.commit()
    conn.close()

    return jsonify({
        "venta_id": venta_id,
        "total": total,
        "recibido": recibido,
        "cambio": cambio
    })

# ----------------------------
# INVENTARIO
# ----------------------------
@app.route("/inventario")
def inventario():
    if "usuario_id" not in session or session["rol"] != "admin":
        return redirect("/")
    conn = get_db_connection()
    productos = conn.execute("SELECT * FROM productos").fetchall()
    conn.close()
    return render_template("inventario.html", productos=productos)

@app.route("/agregar_producto", methods=["POST"])
def agregar_producto():
    nombre = request.form["nombre"]
    stock = int(request.form["stock"])
    precio_compra = float(request.form["precio_compra"])
    precio_venta = float(request.form["precio_venta"])

    conn = get_db_connection()

    producto_existente = conn.execute(
        "SELECT id, stock FROM productos WHERE nombre = ?",
        (nombre,)
    ).fetchone()

    if producto_existente:
        nuevo_stock = producto_existente["stock"] + stock
        conn.execute(
            "UPDATE productos SET stock=?, precio_compra=?, precio_venta=? WHERE id=?",
            (nuevo_stock, precio_compra, precio_venta, producto_existente["id"])
        )
    else:
        conn.execute(
            "INSERT INTO productos(nombre, stock, precio_compra, precio_venta) VALUES (?, ?, ?, ?)",
            (nombre, stock, precio_compra, precio_venta)
        )

    conn.commit()
    conn.close()

    return redirect("/inventario")

@app.route("/actualizar_stock/<int:id>", methods=["POST"])
def actualizar_stock(id):
    cantidad = int(request.form["cantidad"])
    accion = request.form["accion"]

    if cantidad <= 0:
        return redirect("/inventario")

    conn = get_db_connection()

    producto = conn.execute(
        "SELECT stock, merma_mes FROM productos WHERE id=?",
        (id,)
    ).fetchone()

    if producto:
        stock_actual = producto["stock"]
        merma_actual = producto["merma_mes"]

        if accion == "sumar":
            nuevo_stock = stock_actual + cantidad
            nueva_merma = merma_actual

        elif accion == "merma":
            nuevo_stock = max(0, stock_actual - cantidad)
            nueva_merma = merma_actual + cantidad

        conn.execute(
            "UPDATE productos SET stock=?, merma_mes=? WHERE id=?",
            (nuevo_stock, nueva_merma, id)
        )

        conn.commit()

    conn.close()
    return redirect("/inventario")


@app.route("/eliminar_producto/<int:id>", methods=["POST"])
def eliminar_producto(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM productos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/inventario")

# ----------------------------
# HISTORIAL
# ----------------------------

@app.route("/historial")
def historial():
    if "usuario_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    ventas = conn.execute("SELECT * FROM ventas ORDER BY fecha DESC").fetchall()
    conn.close()
    return render_template("historial.html", ventas=ventas)

# ----------------------------
# TICKET
#-----------------------------
# ----------------------------
# VER DETALLE TICKET (JSON)
# ----------------------------
@app.route("/ticket/<int:venta_id>")
def ticket(venta_id):
    if "usuario_id" not in session:
        return jsonify({"error": "No autorizado"}), 403

    conn = get_db_connection()
    # Detalles de la venta
    detalles = conn.execute("""
    SELECT nombre_producto AS nombre,
           cantidad,
           precio_unitario,
           (precio_unitario * cantidad) AS total
    FROM detalle_venta
    WHERE venta_id = ?
""", (venta_id,)).fetchall()

    # Información de la venta: monto recibido y cambio
    venta_info = conn.execute("""
        SELECT recibido, cambio
        FROM ventas
        WHERE id = ?
    """, (venta_id,)).fetchone()
    conn.close()

    # Convertir detalles a lista de dicts
    resultado = [
        {
            "nombre": d["nombre"],
            "cantidad": d["cantidad"],
            "precio_unitario": d["precio_unitario"],
            "total": d["total"]
        } for d in detalles
    ]

    # Agregar info de recibido y cambio
    response = {
        "detalles": resultado,
        "recibido": venta_info["recibido"] if venta_info else 0,
        "cambio": venta_info["cambio"] if venta_info else 0
    }

    return jsonify(response)

# ----------------------------
# FINANZAS
# ----------------------------
from datetime import datetime, timedelta

@app.route("/finanzas")
def finanzas():
    if "usuario_id" not in session or session["rol"] != "admin":
        return redirect("/")

    periodo = request.args.get("periodo", "diario")  # diario, semanal, mensual, anual

    conn = get_db_connection()
    
    # Fecha límite según periodo
    ahora = datetime.now()
    if periodo == "diario":
        inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semanal":
        inicio = ahora - timedelta(days=ahora.weekday())  # lunes de esta semana
        inicio = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "mensual":
        inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "anual":
        inicio = ahora.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        inicio = datetime.min

    # Ventas en el periodo
    ventas = conn.execute("""
        SELECT dv.cantidad, p.precio_compra, p.precio_venta, p.merma_mes
        FROM detalle_venta dv
        JOIN productos p ON dv.producto_id = p.id
        JOIN ventas v ON dv.venta_id = v.id
        WHERE v.fecha >= ?
    """, (inicio,)).fetchall()

    # Calcular ganancias y dinero invertido
    dinero_invertido = 0
    ganancias = 0
    mermas = 0

    for v in ventas:
        dinero_invertido += v["precio_compra"] * v["cantidad"]
        ganancias += (v["precio_venta"] - v["precio_compra"]) * v["cantidad"]
        mermas += v["merma_mes"]  # asumimos que merma_mes se acumula

    conn.close()

    return render_template("finanzas.html",
                           dinero_invertido=dinero_invertido,
                           ganancias=ganancias,
                           mermas=mermas,
                           periodo=periodo)



# ----------------------------
# SALIR
# ----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ----------------------------
# EJECUCIÓN
# ----------------------------
def abrir_navegador():
    webbrowser.open("http://127.0.0.1:5500")

if __name__ == "__main__":

    init_db()

    threading.Timer(1.5, abrir_navegador).start()
    app.run(debug=False, port=5500)