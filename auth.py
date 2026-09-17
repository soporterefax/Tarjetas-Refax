import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash

from database import Usuario


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "A123456$")
TOKEN_HOURS = int(os.environ.get("TOKEN_HOURS", "8"))


def _token_secret():
    return current_app.config["SECRET_KEY"]


def crear_token(payload):
    now = datetime.now(timezone.utc)

    data = {
        **payload,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_HOURS),
    }

    return jwt.encode(
        data,
        _token_secret(),
        algorithm="HS256"
    )


def _leer_token():
    auth_header = request.headers.get(
        "Authorization",
        ""
    )

    if not auth_header.startswith("Bearer "):
        return None

    return auth_header.split(
        " ",
        1
    )[1].strip()


def token_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        token = _leer_token()

        if not token:
            return jsonify({
                "error": "Token requerido"
            }), 401

        try:
            auth_user = jwt.decode(
                token,
                _token_secret(),
                algorithms=["HS256"]
            )

        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "La sesión ha expirado"
            }), 401

        except jwt.InvalidTokenError:
            return jsonify({
                "error": "Token inválido"
            }), 401

        # ==============================
        # VALIDAR USUARIO BLOQUEADO
        # ==============================

        if auth_user.get("rol") != "admin":
            usuario = Usuario.query.get(
                auth_user.get("user_id")
            )

            if not usuario:
                return jsonify({
                    "error": "Usuario no encontrado"
                }), 401

            if not usuario.activo:
                return jsonify({
                    "error": (
                        "Tu acceso se encuentra bloqueado. "
                        "Comunícate con el administrador."
                    )
                }), 403

        request.auth_user = auth_user

        return view(
            *args,
            **kwargs
        )

    return wrapped_view


def admin_required(view):
    @wraps(view)
    @token_required
    def wrapped_view(*args, **kwargs):

        if request.auth_user.get("rol") != "admin":
            return jsonify({
                "error": "Acceso solo para administradores"
            }), 403

        return view(
            *args,
            **kwargs
        )

    return wrapped_view


# =====================================
# LOGIN
# =====================================

@auth_bp.post("/login")
def login():

    data = request.get_json(
        silent=True
    ) or {}

    username = str(
        data.get(
            "username",
            ""
        )
    ).lower().strip()

    password = str(
        data.get(
            "password",
            ""
        )
    ).strip()

    if not username or not password:
        return jsonify({
            "error": (
                "Usuario y contraseña "
                "son obligatorios"
            )
        }), 400

    # ==============================
    # LOGIN ADMIN
    # ==============================

    if (
        username == ADMIN_USER
        and
        password == ADMIN_PASSWORD
    ):

        token = crear_token({
            "username": ADMIN_USER,
            "rol": "admin"
        })

        return jsonify({
            "token": token,
            "rol": "admin",
            "username": ADMIN_USER,
            "debe_cambiar_password": False,
        })

    # ==============================
    # LOGIN USUARIO
    # ==============================

    usuario = Usuario.query.filter_by(
        username=username
    ).first()

    if not usuario:
        return jsonify({
            "error": "Usuario o contraseña incorrectos"
        }), 401

    # Usuario bloqueado
    if not usuario.activo:
        return jsonify({
            "error": (
                "Tu acceso se encuentra bloqueado. "
                "Comunícate con el administrador."
            )
        }), 403

    # Contraseña incorrecta
    if not check_password_hash(
        usuario.password_hash,
        password
    ):
        return jsonify({
            "error": "Usuario o contraseña incorrectos"
        }), 401

    token = crear_token({
        "user_id": usuario.id,
        "username": usuario.username,
        "rol": usuario.rol,
    })

    return jsonify({
        "token": token,
        "rol": usuario.rol,
        "username": usuario.username,
        "debe_cambiar_password": (
            usuario.debe_cambiar_password
        ),
        "usuario": usuario.to_public_dict(),
    })


# =====================================
# INFORMACIÓN DEL USUARIO ACTUAL
# =====================================

@auth_bp.get("/me")
@token_required
def me():

    auth_user = request.auth_user

    if auth_user.get("rol") == "admin":
        return jsonify({
            "username": ADMIN_USER,
            "rol": "admin",
            "debe_cambiar_password": False,
        })

    usuario = Usuario.query.get(
        auth_user.get("user_id")
    )

    if not usuario:
        return jsonify({
            "error": "Usuario no encontrado"
        }), 404

    if not usuario.activo:
        return jsonify({
            "error": (
                "Tu acceso se encuentra bloqueado. "
                "Comunícate con el administrador."
            )
        }), 403

    return jsonify({
        "username": usuario.username,
        "rol": usuario.rol,
        "debe_cambiar_password": (
            usuario.debe_cambiar_password
        ),
        "usuario": usuario.to_public_dict(),
    })