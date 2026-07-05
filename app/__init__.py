import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # Session / Çerez güvenliği için zorunlu anahtar
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "gizli-ve-guvenli-anahtar-12345")

    db_user = os.environ.get("DB_USER", "root")
    db_pass = os.environ.get("DB_PASSWORD", "root")
    db_host = os.environ.get("DB_HOST", "db")
    db_name = os.environ.get("DB_NAME", "market_siparis")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # --- İŞTE EKSİK OLAN VE HATAYI ÇÖZEN BLOK BURASI ---
    # Uygulama başlarken tüm modelleri tanı ve veritabanında eksik tabloları yarat!
    with app.app_context():
        from app import models
        db.create_all()
    # ----------------------------------------------------

    from app.routes.market import market_bp
    from app.routes.musteri import musteri_bp
    from app.routes.kurye import kurye_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(market_bp, url_prefix="/api/market")
    app.register_blueprint(musteri_bp, url_prefix="/api/musteri")
    app.register_blueprint(kurye_bp, url_prefix="/api/kurye")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/login")
    def login_sayfasi():
        return render_template("login.html")

    @app.route("/market")
    def market_sayfasi():
        return render_template("market.html")

    @app.route("/")
    @app.route("/musteri")
    def musteri_sayfasi():
        return render_template("musteri.html")

    @app.route("/kurye")
    def kurye_sayfasi():
        return render_template("kurye.html")

    return app