import os

from flask import Flask, jsonify
from flask_cors import CORS

from auth import auth_bp
from database import init_db
from routes_admin import admin_bp
from routes_public import public_bp
from routes_user import user_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-azure")

    init_db(app)

    allowed_origins = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS",
            "http://127.0.0.1:5500,http://localhost:5500"
        ).split(",")
        if origin.strip()
    ]
    CORS(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(public_bp)

    @app.get("/")
    def home():
        return jsonify({
            "name": "Tarjetas REFAX API",
            "status": "ok",
        })

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
