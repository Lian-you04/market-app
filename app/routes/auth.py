from flask import Blueprint, request, jsonify, session, current_app
from app import db
from app.models import Kullanici, Market, Musteri

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(silent=True) or {}

        email = data.get("email", "").strip().lower()
        sifre = data.get("sifre", "")
        ad_soyad = data.get("ad_soyad", "").strip() or "Yeni Müşteri"
        telefon = data.get("telefon", "05000000000").strip()
        adres = data.get("adres", "Antakya / Hatay").strip()

        if not email or "@" not in email:
            return jsonify({"hata": "Geçerli bir e-posta adresi giriniz!"}), 400

        if not sifre or len(sifre) < 6:
            return jsonify({"hata": "Şifre en az 6 karakter olmalıdır!"}), 400

        if Kullanici.query.filter_by(email=email).first():
            return jsonify({"hata": "Bu e-posta adresi zaten kullanımda!"}), 409

        yeni_kullanici = Kullanici(email=email, rol="musteri", aktif=True)
        yeni_kullanici.sifre_belirle(sifre)

        db.session.add(yeni_kullanici)
        db.session.flush()

        yeni_musteri = Musteri(
            kullanici_id=yeni_kullanici.id,
            ad_soyad=ad_soyad,
            telefon=telefon,
            adres=adres
        )

        db.session.add(yeni_musteri)
        db.session.commit()

        return jsonify({"mesaj": "Kayıt başarılı! Şimdi giriş yapabilirsiniz."}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Kayıt hatası: {str(e)}"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.json or {}

        email = data.get("email", "").strip().lower()
        sifre = data.get("sifre", "")

        kullanici = Kullanici.query.filter_by(email=email, aktif=True).first()

        sifre_gecerli = False

        if kullanici:
            if hasattr(kullanici, "sifre_kontrol"):
                sifre_gecerli = kullanici.sifre_kontrol(sifre)
            elif hasattr(kullanici, "sifre_dogrula"):
                sifre_gecerli = kullanici.sifre_dogrula(sifre)

        if not kullanici or not sifre_gecerli:
            return jsonify({"hata": "E-posta adresi veya şifre hatalı!"}), 401

        session.clear()
        session["kullanici_id"] = kullanici.id
        session["rol"] = kullanici.rol
        session["boot_id"] = current_app.config["APP_BOOT_ID"]

        if kullanici.rol == "market":
            market = (
                kullanici.market[0]
                if isinstance(kullanici.market, list) and kullanici.market
                else kullanici.market
            )
            session["market_id"] = market.id if market else 1

        elif kullanici.rol == "musteri":
            musteri = (
                kullanici.musteri[0]
                if isinstance(kullanici.musteri, list) and kullanici.musteri
                else kullanici.musteri
            )

            if musteri:
                session["musteri_id"] = musteri.id

        return jsonify({
            "mesaj": "Giriş başarılı!",
            "rol": kullanici.rol,
            "yonlendir": "/market" if kullanici.rol == "market" else "/musteri"
        }), 200

    except Exception as e:
        return jsonify({"hata": f"Giriş hatası: {str(e)}"}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mesaj": "Çıkış yapıldı!"}), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    kullanici_id = session.get("kullanici_id")

    if session.get("boot_id") != current_app.config.get("APP_BOOT_ID"):
        session.clear()
        return jsonify({"hata": "Oturum süresi doldu. Lütfen tekrar giriş yapın."}), 401

    if not kullanici_id:
        return jsonify({"hata": "Oturum açık değil"}), 401

    kullanici = Kullanici.query.get(kullanici_id)

    if not kullanici or not kullanici.aktif:
        session.clear()
        return jsonify({"hata": "Oturum geçersiz. Lütfen tekrar giriş yapın."}), 401

    profil_adi = kullanici.email

    if kullanici.rol == "market":
        market = (
            kullanici.market[0]
            if isinstance(kullanici.market, list) and kullanici.market
            else kullanici.market
        )
        profil_adi = market.ad if market else "Köşebaşı Market"

    elif kullanici.rol == "musteri":
        musteri = (
            kullanici.musteri[0]
            if isinstance(kullanici.musteri, list) and kullanici.musteri
            else kullanici.musteri
        )
        profil_adi = musteri.ad_soyad if musteri else kullanici.email.split("@")[0].capitalize()

    return jsonify({
        "id": kullanici.id,
        "email": kullanici.email,
        "rol": kullanici.rol,
        "profil_adi": profil_adi,
        "kullanici": {
            "id": kullanici.id,
            "email": kullanici.email,
            "rol": kullanici.rol,
            "ad": profil_adi
        }
    }), 200