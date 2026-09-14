import os
import secrets

from flask import (
    Flask,
    jsonify,
    render_template,
    send_from_directory
)
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

    app.config["SECRET_KEY"] = (
        os.environ.get("SECRET_KEY")
        or secrets.token_hex(32)
    )

    app.config["APP_BOOT_ID"] = secrets.token_hex(16)

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False

    db_user = os.environ.get("DB_USER", "root")
    db_pass = os.environ.get("DB_PASSWORD", "root")
    db_host = os.environ.get("DB_HOST", "db")
    db_name = os.environ.get("DB_NAME", "market_siparis")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_pass}@"
        f"{db_host}/{db_name}"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280
    }

    db.init_app(app)

    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="eventlet"
    )

    from app.security import role_required

    from app.routes.auth import auth_bp
    from app.routes.market import market_bp
    from app.routes.musteri import musteri_bp

    app.register_blueprint(
        auth_bp,
        url_prefix="/api/auth"
    )

    app.register_blueprint(
        musteri_bp,
        url_prefix="/api/musteri"
    )

    app.register_blueprint(
        market_bp,
        url_prefix="/api/market"
    )

    @app.after_request
    def disable_cache(response):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/service-worker.js")
    def service_worker():
        return send_from_directory(
            app.static_folder,
            "service-worker.js",
            mimetype="application/javascript"
        )

    @app.route("/manifest.webmanifest")
    def pwa_manifest():
        from app.models import Market

        market = db.session.get(Market, 1)

        market_adi = (
            str(market.ad).strip()
            if market and market.ad
            else "Market"
        )

        response = jsonify({
            "name": market_adi,
            "short_name": market_adi,
            "id": "/musteri",
            "lang": "tr",
            "start_url": "/musteri",
            "scope": "/",
            "display": "standalone",
            "theme_color": "#FF7B00",
            "background_color": "#F8FAFC",
            "description": (
                f"{market_adi} müşteri uygulaması"
            ),
            "icons": [
                {
                    "src": "/static/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any"
                },
                {
                    "src": "/static/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable"
                }
            ]
        })

        response.headers["Content-Type"] = (
            "application/manifest+json"
        )

        return response

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