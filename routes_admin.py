import os
import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from auth import admin_required
from database import Usuario, db, obtener_username
from utils import get_card_url, get_qr_api_url


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

EMPRESA_FIJA = "REFAX PERÚ"
WEB_FIJA = "https://www.refax.com/peru"

DEFAULT_USER_PASSWORD = os.environ.get(
    "DEFAULT_USER_PASSWORD",
    "A123456$"
)

TIPOS_VALIDOS = {
    "GNs",
    "B2B",
    "Administrativo"
}


# =====================================
# HELPERS
# =====================================

def _payload_usuario(usuario):
    data = usuario.to_admin_dict()

    data["card_url"] = get_card_url(
        usuario.public_id
    )

    data["qr_url"] = get_qr_api_url(
        usuario.public_id
    )

    return data


def _payload_acceso(usuario):
    return {
        "id": usuario.id,
        "public_id": usuario.public_id,
        "username": usuario.username,
        "nombre": usuario.nombre,
        "correo": usuario.correo,
        "tipo_usuario": usuario.tipo_usuario,
        "activo": usuario.activo,
        "debe_cambiar_password": usuario.debe_cambiar_password,
        "estado_password": (
            "Temporal"
            if usuario.debe_cambiar_password
            else "Cambiada"
        ),
    }


def _normalizar(data, actual=None):

    tipo = str(
        data.get(
            "tipo_usuario",
            getattr(
                actual,
                "tipo_usuario",
                "Administrativo"
            )
        )
    ).strip()

    nombre = str(
        data.get(
            "nombre",
            getattr(
                actual,
                "nombre",
                ""
            )
        )
    ).strip()

    celular = str(
        data.get(
            "celular",
            getattr(
                actual,
                "celular",
                ""
            )
        )
    ).strip()

    correo = str(
        data.get(
            "correo",
            getattr(
                actual,
                "correo",
                ""
            )
        )
    ).lower().strip()

    cargo = str(
        data.get(
            "cargo",
            getattr(
                actual,
                "cargo",
                ""
            )
        )
    ).strip()

    atencion_web = str(
        data.get(
            "atencion_web",
            getattr(
                actual,
                "atencion_web",
                ""
            )
            or ""
        )
    ).strip()

    if tipo not in TIPOS_VALIDOS:
        return None, "Selecciona un tipo de usuario válido"

    if not nombre or not celular or not correo:
        return None, (
            "Nombre, celular y correo "
            "son obligatorios"
        )

    if tipo == "Administrativo" and not cargo:
        return None, (
            "El cargo es obligatorio "
            "para usuarios Administrativos"
        )

    if tipo == "B2B" and not atencion_web:
        return None, (
            "Atención web es obligatoria "
            "para usuarios B2B"
        )

    # Campos según tipo
    if tipo == "B2B":
        cargo = "Ejecutivo Web"

    elif tipo == "GNs":
        cargo = ""
        atencion_web = ""

    elif tipo == "Administrativo":
        atencion_web = ""

    return {
        "tipo_usuario": tipo,
        "nombre": nombre,
        "cargo": cargo,
        "celular": celular,
        "correo": correo,
        "atencion_web": atencion_web,
    }, None


# =====================================
# GESTIÓN DE TARJETAS
# =====================================

@admin_bp.get("/usuarios")
@admin_required
def listar_usuarios():

    usuarios = (
        Usuario.query
        .order_by(
            Usuario.id.desc()
        )
        .all()
    )

    return jsonify([
        _payload_usuario(usuario)
        for usuario in usuarios
    ])


@admin_bp.post("/usuarios")
@admin_required
def registrar():

    data = request.get_json(
        silent=True
    ) or {}

    valores, error = _normalizar(
        data
    )

    if error:
        return jsonify({
            "error": error
        }), 400

    usuario = Usuario(
        public_id=uuid.uuid4().hex[:12],
        empresa=EMPRESA_FIJA,
        web=WEB_FIJA,

        username=obtener_username(
            valores["correo"]
        ),

        password_hash=generate_password_hash(
            DEFAULT_USER_PASSWORD
        ),

        rol="usuario",

        activo=True,

        debe_cambiar_password=True,

        **valores,
    )

    try:

        db.session.add(
            usuario
        )

        db.session.commit()

    except IntegrityError:

        db.session.rollback()

        return jsonify({
            "error": (
                "Ya existe un usuario "
                "con ese correo/username"
            )
        }), 409

    return jsonify(
        _payload_usuario(
            usuario
        )
    ), 201


@admin_bp.put("/usuarios/<public_id>")
@admin_required
def editar(public_id):

    usuario = (
        Usuario.query
        .filter_by(
            public_id=public_id
        )
        .first()
    )

    if not usuario:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    valores, error = _normalizar(
        data,
        usuario
    )

    if error:
        return jsonify({
            "error": error
        }), 400

    for campo, valor in valores.items():
        setattr(
            usuario,
            campo,
            valor
        )

    usuario.username = obtener_username(
        usuario.correo
    )

    try:

        db.session.commit()

    except IntegrityError:

        db.session.rollback()

        return jsonify({
            "error": (
                "Ese correo/username "
                "ya está en uso"
            )
        }), 409

    return jsonify(
        _payload_usuario(
            usuario
        )
    )


@admin_bp.delete("/usuarios/<public_id>")
@admin_required
def eliminar(public_id):

    usuario = (
        Usuario.query
        .filter_by(
            public_id=public_id
        )
        .first()
    )

    if not usuario:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    db.session.delete(
        usuario
    )

    db.session.commit()

    return jsonify({
        "ok": True
    })


# =====================================
# GESTIÓN DE ACCESOS
# =====================================

@admin_bp.get("/accesos")
@admin_required
def listar_accesos():

    usuarios = (
        Usuario.query
        .order_by(
            Usuario.nombre.asc()
        )
        .all()
    )

    return jsonify([
        _payload_acceso(
            usuario
        )
        for usuario in usuarios
    ])


# =====================================
# BLOQUEAR USUARIO
# =====================================

@admin_bp.post("/usuarios/<public_id>/bloquear")
@admin_required
def bloquear_usuario(public_id):

    usuario = (
        Usuario.query
        .filter_by(
            public_id=public_id
        )
        .first()
    )

    if not usuario:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    usuario.activo = False

    db.session.commit()

    return jsonify({
        "ok": True,
        "activo": False,
        "mensaje": "Usuario bloqueado correctamente"
    })


# =====================================
# DESBLOQUEAR USUARIO
# =====================================

@admin_bp.post("/usuarios/<public_id>/desbloquear")
@admin_required
def desbloquear_usuario(public_id):

    usuario = (
        Usuario.query
        .filter_by(
            public_id=public_id
        )
        .first()
    )

    if not usuario:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    usuario.activo = True

    db.session.commit()

    return jsonify({
        "ok": True,
        "activo": True,
        "mensaje": "Usuario desbloqueado correctamente"
    })


# =====================================
# RESET A CONTRASEÑA INICIAL
# =====================================

@admin_bp.post(
    "/usuarios/<public_id>/reset-password"
)
@admin_required
def reset_password(public_id):

    usuario = (
        Usuario.query
        .filter_by(
            public_id=public_id
        )
        .first()
    )

    if not usuario:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    usuario.password_hash = (
        generate_password_hash(
            DEFAULT_USER_PASSWORD
        )
    )

    usuario.debe_cambiar_password = True

    db.session.commit()

    return jsonify({
        "ok": True,
        "mensaje": "Contraseña restablecida correctamente",
        "password_temporal": DEFAULT_USER_PASSWORD,
        "debe_cambiar_password": True,
    })


# =====================================
# ADMIN ASIGNA NUEVA CONTRASEÑA
# =====================================

@admin_bp.post(
    "/usuarios/<public_id>/cambiar-password"
)
@admin_required
def cambiar_password_usuario(public_id):

    usuario = (
        Usuario.query
        .filter_by(
            public_id=public_id
        )
        .first()
    )

    if not usuario:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    nueva_password = str(
        data.get(
            "password_nueva",
            ""
        )
    ).strip()

    confirmacion = str(
        data.get(
            "password_confirmacion",
            ""
        )
    ).strip()

    if not nueva_password:
        return jsonify({
            "error": "Ingresa una nueva contraseña"
        }), 400

    if not confirmacion:
        return jsonify({
            "error": "Confirma la nueva contraseña"
        }), 400

    if nueva_password != confirmacion:
        return jsonify({
            "error": "Las contraseñas no coinciden"
        }), 400

    if len(nueva_password) < 8:
        return jsonify({
            "error": (
                "La contraseña debe tener "
                "como mínimo 8 caracteres"
            )
        }), 400

    usuario.password_hash = (
        generate_password_hash(
            nueva_password
        )
    )

    # La contraseña asignada por admin se considera temporal
    usuario.debe_cambiar_password = True

    db.session.commit()

    return jsonify({
        "ok": True,
        "mensaje": (
            "Contraseña actualizada correctamente"
        ),
        "debe_cambiar_password": True,
    })