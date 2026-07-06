import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()
socketio = SocketIO()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "gizli-ve-guvenli-anahtar-12345")

    db_user = os.environ.get("DB_USER", "root")
    db_pass = os.environ.get("DB_PASSWORD", "root")
    db_host = os.environ.get("DB_HOST", "db")
    db_name = os.environ.get("DB_NAME", "market_siparis")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    db.init_app(app)
    
    # YENİ EKLEME: Canlı Socket motorumuzu Flask uygulamasına bağlıyoruz
    socketio.init_app(app, cors_allowed_origins="*", async_mode="eventlet")

    # API Blueprints
    from app.routes.market import market_bp
    from app.routes.musteri import musteri_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(market_bp, url_prefix="/api/market")
    app.register_blueprint(musteri_bp, url_prefix="/api/musteri")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/login")
    def login_sayfasi():
        return render_template("login.html")

    @app.route("/register")
    def register_sayfasi():
        return render_template("register.html")

    @app.route("/market")
    def market_sayfasi():
        return render_template("market.html")

    @app.route("/")
    @app.route("/musteri")
    def musteri_sayfasi():
        return render_template("musteri.html")

    return app