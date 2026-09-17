import os
from flask import request


FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5500").rstrip("/")


def get_card_url(public_id):
    return f"{FRONTEND_URL}/tarjeta.html?id={public_id}"


def get_qr_api_url(public_id):
    backend_url = os.environ.get("BACKEND_PUBLIC_URL", "").rstrip("/")
    if backend_url:
        return f"{backend_url}/api/qr/{public_id}.png"
    return f"{request.url_root.rstrip('/')}/api/qr/{public_id}.png"
