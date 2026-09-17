import base64
import hashlib
import os
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash


db = SQLAlchemy()

DEFAULT_USER_PASSWORD = os.environ.get(
    "DEFAULT_USER_PASSWORD",
    "A123456$"
)


def obtener_username(correo):
    return correo.split("@")[0].lower().strip()


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    public_id = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        index=True
    )

    tipo_usuario = db.Column(
        db.String(30),
        nullable=False,
        default="Administrativo",
        index=True
    )

    nombre = db.Column(
        db.String(150),
        nullable=False
    )

    cargo = db.Column(
        db.String(150),
        nullable=False,
        default=""
    )

    empresa = db.Column(
        db.String(150),
        nullable=False,
        default="REFAX PERÚ"
    )

    celular = db.Column(
        db.String(50),
        nullable=False
    )

    correo = db.Column(
        db.String(180),
        nullable=False
    )

    atencion_web = db.Column(
        db.String(150),
        nullable=True
    )

    web = db.Column(
        db.String(255),
        nullable=False,
        default="https://www.refax.com/peru"
    )

    creado_en = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    username = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    rol = db.Column(
        db.String(30),
        nullable=False,
        default="usuario"
    )

    # ==============================
    # CONTROL DE ACCESO
    # ==============================

    activo = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    debe_cambiar_password = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    # ==============================
    # CLIENTES B2B
    # ==============================

    clientes_b2b = db.relationship(
        "ClienteB2B",
        backref="usuario",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def to_public_dict(self):
        return {
            "public_id": self.public_id,
            "tipo_usuario": self.tipo_usuario,
            "nombre": self.nombre,
            "cargo": self.cargo,
            "empresa": self.empresa,
            "celular": self.celular,
            "correo": self.correo,
            "atencion_web": self.atencion_web or "",
            "web": self.web,
        }

    def to_admin_dict(self):
        data = self.to_public_dict()

        data.update({
            "id": self.id,
            "username": self.username,
            "rol": self.rol,
            "creado_en": (
                self.creado_en.isoformat()
                if self.creado_en
                else None
            ),
            "activo": self.activo,
            "debe_cambiar_password": self.debe_cambiar_password,
        })

        return data


class ClienteB2B(db.Model):
    __tablename__ = "clientes_b2b"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "usuarios.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    ruc = db.Column(
        db.String(20),
        nullable=False
    )

    usuario_cliente = db.Column(
        db.String(180),
        nullable=False
    )

    password_cifrada = db.Column(
        db.Text,
        nullable=False
    )

    creado_en = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    def to_private_dict(self):
        return {
            "id": self.id,
            "ruc": self.ruc,
            "usuario": self.usuario_cliente,
            "contrasena": descifrar_secreto(
                self.password_cifrada
            ),
        }


# =====================================
# CIFRADO DE CREDENCIALES B2B
# =====================================

def _fernet():

    raw = (
        os.environ.get("B2B_ENCRYPTION_KEY")
        or current_app.config.get(
            "SECRET_KEY",
            ""
        )
    )

    if not raw:
        raise RuntimeError(
            "Configura B2B_ENCRYPTION_KEY o SECRET_KEY"
        )

    try:
        return Fernet(
            raw.encode("utf-8")
        )

    except Exception:

        digest = hashlib.sha256(
            raw.encode("utf-8")
        ).digest()

        return Fernet(
            base64.urlsafe_b64encode(
                digest
            )
        )


def cifrar_secreto(valor):

    return (
        _fernet()
        .encrypt(
            str(valor).encode("utf-8")
        )
        .decode("utf-8")
    )


def descifrar_secreto(valor):

    try:

        return (
            _fernet()
            .decrypt(
                valor.encode("utf-8")
            )
            .decode("utf-8")
        )

    except (
        InvalidToken,
        AttributeError
    ):

        return ""


# =====================================
# MIGRACIONES
# =====================================

def _migrar_columnas_existentes():

    inspector = inspect(
        db.engine
    )

    if "usuarios" not in inspector.get_table_names():
        return

    columnas = {
        c["name"]
        for c in inspector.get_columns(
            "usuarios"
        )
    }

    cambios = []

    if "tipo_usuario" not in columnas:

        cambios.append(
            """
            ALTER TABLE usuarios
            ADD COLUMN tipo_usuario VARCHAR(30)
            NOT NULL DEFAULT 'Administrativo'
            """
        )

    if "atencion_web" not in columnas:

        cambios.append(
            """
            ALTER TABLE usuarios
            ADD COLUMN atencion_web VARCHAR(150)
            NULL
            """
        )

    if "activo" not in columnas:

        cambios.append(
            """
            ALTER TABLE usuarios
            ADD COLUMN activo BOOLEAN
            NOT NULL DEFAULT TRUE
            """
        )

    if "debe_cambiar_password" not in columnas:

        cambios.append(
            """
            ALTER TABLE usuarios
            ADD COLUMN debe_cambiar_password BOOLEAN
            NOT NULL DEFAULT TRUE
            """
        )

    if cambios:

        with db.engine.begin() as conn:

            for sql in cambios:

                conn.execute(
                    text(sql)
                )


# =====================================
# INICIALIZACIÓN DE BASE DE DATOS
# =====================================

def init_db(app):

    database_url = os.environ.get(
        "DATABASE_URL",
        "sqlite:///usuarios.db"
    )

    if database_url.startswith(
        "mysql://"
    ):

        database_url = database_url.replace(
            "mysql://",
            "mysql+pymysql://",
            1
        )

    app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = database_url

    app.config[
        "SQLALCHEMY_TRACK_MODIFICATIONS"
    ] = False

    engine_options = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # ==========================
    # SSL AZURE MYSQL
    # ==========================

    if database_url.startswith(
        "mysql"
    ):

        cert_path = os.path.join(
            os.path.dirname(__file__),
            "certs",
            "DigiCertGlobalRootG2.crt.pem"
        )

        if os.path.exists(
            cert_path
        ):

            engine_options[
                "connect_args"
            ] = {
                "ssl": {
                    "ca": cert_path
                }
            }

    app.config[
        "SQLALCHEMY_ENGINE_OPTIONS"
    ] = engine_options

    db.init_app(app)

    with app.app_context():

        # Crea tablas que todavía no existen.
        db.create_all()

        # Agrega columnas faltantes.
        _migrar_columnas_existentes()

        # Segunda ejecución para índices/tablas nuevas.
        db.create_all()


# =====================================
# CREACIÓN DE USUARIOS
# =====================================

def crear_usuario_desde_datos(
    public_id,
    nombre,
    cargo,
    celular,
    correo,
    empresa,
    web,
    tipo_usuario="Administrativo",
    atencion_web=""
):

    return Usuario(
        public_id=public_id,
        tipo_usuario=tipo_usuario,
        nombre=nombre,
        cargo=cargo,
        empresa=empresa,
        celular=celular,
        correo=correo,
        atencion_web=(
            atencion_web
            or None
        ),
        web=web,
        username=obtener_username(
            correo
        ),
        password_hash=generate_password_hash(
            DEFAULT_USER_PASSWORD
        ),
        rol="usuario",

        # Usuario habilitado inicialmente
        activo=True,

        # Primera contraseña = temporal
        debe_cambiar_password=True,
    )