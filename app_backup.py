import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

import qrcode
from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "usuarios.db")
QR_DIR = os.path.join(BASE_DIR, "static", "qr")

EMPRESA_FIJA = "REFAX PERÚ"
WEB_FIJA = "https://www.refax.com/peru"

APP_BASE_URL = os.environ.get("APP_BASE_URL", "").rstrip("/")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "A123456$")
DEFAULT_USER_PASSWORD = os.environ.get("DEFAULT_USER_PASSWORD", "A123456$")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esta-clave-segura")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def obtener_username(correo):
    return correo.split("@")[0].lower().strip()


def get_card_url(public_id):
    if APP_BASE_URL:
        return f"{APP_BASE_URL}{url_for('tarjeta_publica', public_id=public_id)}"
    return url_for("tarjeta_publica", public_id=public_id, _external=True)


def crear_qr(public_id):
    card_url = get_card_url(public_id)
    qr_filename = f"{public_id}.png"
    qr_path = os.path.join(QR_DIR, qr_filename)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(card_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="#111827", back_color="white")
    image.save(qr_path)
    return qr_filename


def init_db():
    os.makedirs(QR_DIR, exist_ok=True)

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                cargo TEXT NOT NULL,
                empresa TEXT NOT NULL,
                celular TEXT NOT NULL,
                correo TEXT NOT NULL,
                web TEXT NOT NULL,
                qr_filename TEXT NOT NULL,
                creado_en TEXT NOT NULL
            )
            """
        )

        columnas = [col["name"] for col in connection.execute("PRAGMA table_info(usuarios)").fetchall()]

        if "username" not in columnas:
            connection.execute("ALTER TABLE usuarios ADD COLUMN username TEXT")

        if "password_hash" not in columnas:
            connection.execute("ALTER TABLE usuarios ADD COLUMN password_hash TEXT")

        if "rol" not in columnas:
            connection.execute("ALTER TABLE usuarios ADD COLUMN rol TEXT DEFAULT 'usuario'")

        usuarios = connection.execute("SELECT * FROM usuarios").fetchall()

        for usuario in usuarios:
            username = usuario["username"] or obtener_username(usuario["correo"])
            password_hash = usuario["password_hash"] or generate_password_hash(DEFAULT_USER_PASSWORD)
            rol = usuario["rol"] or "usuario"

            connection.execute(
                """
                UPDATE usuarios
                SET username = ?, password_hash = ?, rol = ?
                WHERE id = ?
                """,
                (username, password_hash, rol, usuario["id"]),
            )


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin") and not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin"):
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").lower().strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USER and password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            session["username"] = ADMIN_USER
            return redirect(url_for("admin_panel"))

        with get_connection() as connection:
            usuario = connection.execute(
                "SELECT * FROM usuarios WHERE username = ?",
                (username,),
            ).fetchone()

        if usuario and check_password_hash(usuario["password_hash"], password):
            session.clear()
            session["user_id"] = usuario["id"]
            session["username"] = usuario["username"]
            return redirect(url_for("mi_tarjeta"))

        error = "Usuario o contraseña incorrectos."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@admin_required
def admin_panel():
    with get_connection() as connection:
        usuarios = connection.execute(
            "SELECT * FROM usuarios ORDER BY id DESC"
        ).fetchall()

    return render_template(
        "index.html",
        usuarios=usuarios,
        empresa=EMPRESA_FIJA,
        web=WEB_FIJA,
    )


@app.route("/registrar", methods=["POST"])
@admin_required
def registrar():
    required_fields = ["nombre", "cargo", "celular", "correo"]
    form_data = {field: request.form.get(field, "").strip() for field in required_fields}

    if any(not value for value in form_data.values()):
        return redirect(url_for("admin_panel"))

    public_id = uuid.uuid4().hex[:12]
    qr_filename = crear_qr(public_id)
    username = obtener_username(form_data["correo"])
    password_hash = generate_password_hash(DEFAULT_USER_PASSWORD)

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO usuarios (
                public_id, nombre, cargo, empresa, celular, correo, web,
                qr_filename, creado_en, username, password_hash, rol
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                public_id,
                form_data["nombre"],
                form_data["cargo"],
                EMPRESA_FIJA,
                form_data["celular"],
                form_data["correo"],
                WEB_FIJA,
                qr_filename,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                username,
                password_hash,
                "usuario",
            ),
        )

    return redirect(url_for("admin_panel"))


@app.route("/editar/<public_id>", methods=["GET", "POST"])
@admin_required
def editar(public_id):
    with get_connection() as connection:
        usuario = connection.execute(
            "SELECT * FROM usuarios WHERE public_id = ?",
            (public_id,),
        ).fetchone()

    if usuario is None:
        abort(404)

    if request.method == "POST":
        required_fields = ["nombre", "cargo", "celular", "correo"]
        form_data = {field: request.form.get(field, "").strip() for field in required_fields}

        if any(not value for value in form_data.values()):
            return render_template(
                "editar.html",
                usuario=usuario,
                empresa=EMPRESA_FIJA,
                web=WEB_FIJA,
                error="Completa todos los campos.",
            )

        username = obtener_username(form_data["correo"])

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE usuarios
                SET nombre = ?, cargo = ?, celular = ?, correo = ?, username = ?
                WHERE public_id = ?
                """,
                (
                    form_data["nombre"],
                    form_data["cargo"],
                    form_data["celular"],
                    form_data["correo"],
                    username,
                    public_id,
                ),
            )

        return redirect(url_for("admin_panel"))

    return render_template(
        "editar.html",
        usuario=usuario,
        empresa=EMPRESA_FIJA,
        web=WEB_FIJA,
        error=None,
    )


@app.route("/eliminar/<public_id>", methods=["POST"])
@admin_required
def eliminar(public_id):
    with get_connection() as connection:
        usuario = connection.execute(
            "SELECT * FROM usuarios WHERE public_id = ?",
            (public_id,),
        ).fetchone()

        if usuario is None:
            abort(404)

        connection.execute("DELETE FROM usuarios WHERE public_id = ?", (public_id,))

    qr_path = os.path.join(QR_DIR, usuario["qr_filename"])
    if os.path.exists(qr_path):
        os.remove(qr_path)

    return redirect(url_for("admin_panel"))


@app.route("/regenerar-qr/<public_id>", methods=["POST"])
@admin_required
def regenerar_qr(public_id):
    with get_connection() as connection:
        usuario = connection.execute(
            "SELECT * FROM usuarios WHERE public_id = ?",
            (public_id,),
        ).fetchone()

        if usuario is None:
            abort(404)

        qr_filename = crear_qr(public_id)
        connection.execute(
            "UPDATE usuarios SET qr_filename = ? WHERE public_id = ?",
            (qr_filename, public_id),
        )

    return redirect(url_for("admin_panel"))


@app.route("/mi-tarjeta")
@login_required
def mi_tarjeta():
    if session.get("is_admin"):
        return redirect(url_for("admin_panel"))

    with get_connection() as connection:
        usuario = connection.execute(
            "SELECT * FROM usuarios WHERE id = ?",
            (session["user_id"],),
        ).fetchone()

    if usuario is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("dashboard_usuario.html", usuario=usuario)


@app.route("/tarjeta/<public_id>")
def tarjeta_publica(public_id):
    with get_connection() as connection:
        usuario = connection.execute(
            "SELECT * FROM usuarios WHERE public_id = ?",
            (public_id,),
        ).fetchone()

    if usuario is None:
        abort(404)

    return render_template("tarjeta.html", usuario=usuario)


@app.route("/qr/<filename>")
@login_required
def descargar_qr(filename):
    if session.get("is_admin"):
        return send_from_directory(QR_DIR, filename, as_attachment=True)

    with get_connection() as connection:
        usuario = connection.execute(
            "SELECT * FROM usuarios WHERE id = ?",
            (session["user_id"],),
        ).fetchone()

    if usuario is None or usuario["qr_filename"] != filename:
        abort(403)

    return send_from_directory(QR_DIR, filename, as_attachment=True)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))