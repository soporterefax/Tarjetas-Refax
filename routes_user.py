from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from auth import token_required
from database import ClienteB2B, Usuario, cifrar_secreto, db
from utils import get_card_url, get_qr_api_url


user_bp = Blueprint("user", __name__, url_prefix="/api/user")


def _usuario_actual():
    auth_user = request.auth_user

    if auth_user.get("rol") == "admin":
        return None, (
            jsonify({
                "error": "Esta ruta corresponde a usuarios"
            }),
            403
        )

    usuario = db.session.get(
        Usuario,
        auth_user.get("user_id")
    )

    if not usuario:
        return None, (
            jsonify({
                "error": "Usuario no encontrado"
            }),
            404
        )

    return usuario, None


# =====================================
# MI TARJETA
# =====================================

@user_bp.get("/mi-tarjeta")
@token_required
def mi_tarjeta():

    usuario, error = _usuario_actual()

    if error:
        return error

    data = usuario.to_public_dict()

    data["card_url"] = get_card_url(
        usuario.public_id
    )

    data["qr_url"] = get_qr_api_url(
        usuario.public_id
    )

    data["debe_cambiar_password"] = (
        usuario.debe_cambiar_password
    )

    return jsonify(data)


# =====================================
# CAMBIAR CONTRASEÑA
# =====================================

@user_bp.post("/cambiar-password")
@token_required
def cambiar_password():

    usuario, error = _usuario_actual()

    if error:
        return error

    data = request.get_json(
        silent=True
    ) or {}

    password_actual = str(
        data.get(
            "password_actual",
            ""
        )
    ).strip()

    password_nueva = str(
        data.get(
            "password_nueva",
            ""
        )
    ).strip()

    password_confirmacion = str(
        data.get(
            "password_confirmacion",
            ""
        )
    ).strip()

    # ==============================
    # VALIDACIONES
    # ==============================

    if not password_actual:
        return jsonify({
            "error": "Ingresa tu contraseña actual"
        }), 400

    if not password_nueva:
        return jsonify({
            "error": "Ingresa una nueva contraseña"
        }), 400

    if not password_confirmacion:
        return jsonify({
            "error": "Confirma la nueva contraseña"
        }), 400

    if password_nueva != password_confirmacion:
        return jsonify({
            "error": "Las nuevas contraseñas no coinciden"
        }), 400

    if not check_password_hash(
        usuario.password_hash,
        password_actual
    ):
        return jsonify({
            "error": "La contraseña actual es incorrecta"
        }), 400

    # Evitar reutilizar la misma contraseña
    if check_password_hash(
        usuario.password_hash,
        password_nueva
    ):
        return jsonify({
            "error": (
                "La nueva contraseña debe ser "
                "diferente a la contraseña actual"
            )
        }), 400

    # Reglas mínimas de seguridad
    if len(password_nueva) < 8:
        return jsonify({
            "error": (
                "La nueva contraseña debe tener "
                "como mínimo 8 caracteres"
            )
        }), 400

    # ==============================
    # GUARDAR NUEVA CONTRASEÑA
    # ==============================

    usuario.password_hash = (
        generate_password_hash(
            password_nueva
        )
    )

    usuario.debe_cambiar_password = False

    db.session.commit()

    return jsonify({
        "ok": True,
        "mensaje": "Contraseña actualizada correctamente",
        "debe_cambiar_password": False
    })


# =====================================
# CLIENTES B2B
# =====================================

@user_bp.get("/clientes-b2b")
@token_required
def listar_clientes_b2b():

    usuario, error = _usuario_actual()

    if error:
        return error

    if usuario.tipo_usuario != "B2B":
        return jsonify({
            "error": "Disponible solo para usuarios B2B"
        }), 403

    clientes = (
        ClienteB2B.query
        .filter_by(
            usuario_id=usuario.id
        )
        .order_by(
            ClienteB2B.id.asc()
        )
        .all()
    )

    return jsonify([
        c.to_private_dict()
        for c in clientes
    ])


@user_bp.post("/clientes-b2b")
@token_required
def crear_cliente_b2b():

    usuario, error = _usuario_actual()

    if error:
        return error

    if usuario.tipo_usuario != "B2B":
        return jsonify({
            "error": "Disponible solo para usuarios B2B"
        }), 403

    data = request.get_json(
        silent=True
    ) or {}

    ruc = str(
        data.get(
            "ruc",
            ""
        )
    ).strip()

    usuario_cliente = str(
        data.get(
            "usuario",
            ""
        )
    ).strip()

    contrasena = str(
        data.get(
            "contrasena",
            ""
        )
    ).strip()

    if not all([
        ruc,
        usuario_cliente,
        contrasena
    ]):
        return jsonify({
            "error": "Completa RUC, usuario y contraseña"
        }), 400

    cliente = ClienteB2B(
        usuario_id=usuario.id,
        ruc=ruc,
        usuario_cliente=usuario_cliente,
        password_cifrada=cifrar_secreto(
            contrasena
        ),
    )

    db.session.add(
        cliente
    )

    db.session.commit()

    return jsonify(
        cliente.to_private_dict()
    ), 201


@user_bp.put("/clientes-b2b/<int:cliente_id>")
@token_required
def editar_cliente_b2b(cliente_id):

    usuario, error = _usuario_actual()

    if error:
        return error

    if usuario.tipo_usuario != "B2B":
        return jsonify({
            "error": "Disponible solo para usuarios B2B"
        }), 403

    cliente = (
        ClienteB2B.query
        .filter_by(
            id=cliente_id,
            usuario_id=usuario.id
        )
        .first()
    )

    if not cliente:
        return jsonify({
            "error": "Cliente no encontrado"
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    ruc = str(
        data.get(
            "ruc",
            cliente.ruc
        )
    ).strip()

    usuario_cliente = str(
        data.get(
            "usuario",
            cliente.usuario_cliente
        )
    ).strip()

    contrasena = str(
        data.get(
            "contrasena",
            ""
        )
    ).strip()

    if not ruc or not usuario_cliente:
        return jsonify({
            "error": "RUC y usuario son obligatorios"
        }), 400

    cliente.ruc = ruc
    cliente.usuario_cliente = usuario_cliente

    if contrasena:
        cliente.password_cifrada = (
            cifrar_secreto(
                contrasena
            )
        )

    db.session.commit()

    return jsonify(
        cliente.to_private_dict()
    )


@user_bp.delete("/clientes-b2b/<int:cliente_id>")
@token_required
def eliminar_cliente_b2b(cliente_id):

    usuario, error = _usuario_actual()

    if error:
        return error

    if usuario.tipo_usuario != "B2B":
        return jsonify({
            "error": "Disponible solo para usuarios B2B"
        }), 403

    cliente = (
        ClienteB2B.query
        .filter_by(
            id=cliente_id,
            usuario_id=usuario.id
        )
        .first()
    )

    if not cliente:
        return jsonify({
            "error": "Cliente no encontrado"
        }), 404

    db.session.delete(
        cliente
    )

    db.session.commit()

    return jsonify({
        "ok": True
    })