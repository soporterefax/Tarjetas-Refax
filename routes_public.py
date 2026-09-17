from io import BytesIO

import qrcode
from flask import Blueprint, jsonify, send_file

from database import Usuario
from utils import get_card_url


public_bp = Blueprint("public", __name__, url_prefix="/api")


@public_bp.get("/tarjeta/<public_id>")
def tarjeta_publica(public_id):
    usuario = Usuario.query.filter_by(public_id=public_id).first()
    if not usuario:
        return jsonify({"error": "Tarjeta no encontrada"}), 404
    return jsonify(usuario.to_public_dict())


@public_bp.get("/qr/<public_id>.png")
def qr(public_id):
    usuario = Usuario.query.filter_by(public_id=public_id).first()
    if not usuario:
        return jsonify({"error": "Tarjeta no encontrada"}), 404

    image = qrcode.make(get_card_url(public_id))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="image/png",
        as_attachment=False,
        download_name=f"{public_id}.png",
        max_age=300,
    )
