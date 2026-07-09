import os
import secrets

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()
socketio = SocketIO()


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )

    # -----------------------------
    # Güvenlik
    # -----------------------------
    app.config["SECRET_KEY"] = (
        os.environ.get("SECRET_KEY")
        or secrets.token_hex(32)
    )

    # Docker her yeniden başladığında yeni oturum kimliği üret.
    app.config["APP_BOOT_ID"] = secrets.token_hex(16)

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False

    # -----------------------------
    # Veritabanı
    # -----------------------------
    db_user = os.environ.get("DB_USER", "root")
    db_pass = os.environ.get("DB_PASSWORD", "root")
    db_host = os.environ.get("DB_HOST", "db")
    db_name = os.environ.get("DB_NAME", "market_siparis")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280
    }

    db.init_app(app)

    # -----------------------------
    # SocketIO
    # -----------------------------
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="eventlet"
    )

    # -----------------------------
    # Blueprintler
    # -----------------------------
    from app.security import role_required

    from app.routes.auth import auth_bp
    from app.routes.market import market_bp
    from app.routes.musteri import musteri_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(musteri_bp, url_prefix="/api/musteri")
    app.register_blueprint(market_bp, url_prefix="/api/market")

    # -----------------------------
    # Cache kapat
    # -----------------------------
    @app.after_request
    def disable_cache(response):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # -----------------------------
    # Sayfalar
    # -----------------------------
    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/login")
    def login():
        return render_template("login.html")

    @app.route("/register")
    def register():
        return render_template("register.html")

    @app.route("/")
    @app.route("/musteri")
    @role_required("musteri")
    def musteri():
        return render_template("musteri.html")

    @app.route("/market")
    @role_required("market")
    def market():
        return render_template("market.html")

    return app