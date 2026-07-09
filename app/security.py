from functools import wraps
from flask import session, redirect, jsonify, request, current_app
from app.models import Kullanici


def _unauthorized():
    session.clear()
    if request.path.startswith("/api/"):
        return jsonify({"hata": "Oturum açmanız gerekiyor!"}), 401
    return redirect("/login")


def _forbidden(rol):
    if request.path.startswith("/api/"):
        return jsonify({"hata": "Bu işlem için yetkiniz yok!"}), 403

    if rol == "market":
        return redirect("/market")
    if rol == "musteri":
        return redirect("/musteri")

    session.clear()
    return redirect("/login")


def _aktif_kullanici_getir():
    kullanici_id = session.get("kullanici_id")
    boot_id = session.get("boot_id")

    if not kullanici_id:
        return None

    if boot_id != current_app.config.get("APP_BOOT_ID"):
        return None

    kullanici = Kullanici.query.get(kullanici_id)

    if not kullanici or not kullanici.aktif:
        return None

    return kullanici


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        kullanici = _aktif_kullanici_getir()

        if not kullanici:
            return _unauthorized()

        return f(*args, **kwargs)

    return wrapper


def role_required(*roller):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            kullanici = _aktif_kullanici_getir()

            if not kullanici:
                return _unauthorized()

            if kullanici.rol not in roller:
                return _forbidden(kullanici.rol)

            session["rol"] = kullanici.rol
            return f(*args, **kwargs)

        return wrapper

    return decorator