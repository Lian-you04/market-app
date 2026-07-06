from flask import Blueprint, request, jsonify, session
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

        # 🔒 Basit validasyon
        if not email or "@" not in email:
            return jsonify({"hata": "Geçerli bir e-posta adresi giriniz!"}), 400

        if not sifre or len(sifre) < 6:
            return jsonify({"hata": "Şifre en az 6 karakter olmalıdır!"}), 400

        if Kullanici.query.filter_by(email=email).first():
            return jsonify({"hata": "Bu e-posta adresi zaten kullanımda!"}), 409

        # 🔒 NOT: rol artık client'tan alınmıyor.
        # Bu sistemde marketler bakkal_ekle.py ile elle oluşturuluyor.
        # /register üzerinden HERKES sadece "musteri" olarak kaydolur.
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
        email = data.get("email", "").strip()
        sifre = data.get("sifre", "")

        kullanici = Kullanici.query.filter_by(email=email, aktif=True).first()

        # Şifre kontrolü (Hem sifre_kontrol hem sifre_dogrula destekli zırh)
        sifre_gecerli = False
        if kullanici:
            if hasattr(kullanici, "sifre_kontrol"):
                sifre_gecerli = kullanici.sifre_kontrol(sifre)
            elif hasattr(kullanici, "sifre_dogrula"):
                sifre_gecerli = kullanici.sifre_dogrula(sifre)

        if not kullanici or not sifre_gecerli:
            return jsonify({"hata": "E-posta adresi veya şifre hatalı!"}), 401

        # Oturum çerezlerini doldur
        session.clear()
        session["kullanici_id"] = kullanici.id
        session["rol"] = kullanici.rol

        # 🚀 ÇÖZÜM BURADA: Market veya Müşteri ID'sini güvenle yakala (Liste gelse bile patlamaz!)
        if kullanici.rol == "market":
            market = None
            if isinstance(kullanici.market, list):
                market = kullanici.market[0] if len(kullanici.market) > 0 else None
            else:
                market = kullanici.market
            
            # Eğer bakkalın dükkanı yoksa ID olarak 1 ata
            session["market_id"] = market.id if market else 1
        
        elif kullanici.rol == "musteri":
            musteri = None
            if isinstance(kullanici.musteri, list):
                musteri = kullanici.musteri[0] if len(kullanici.musteri) > 0 else None
            else:
                musteri = kullanici.musteri
            
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
    if not kullanici_id:
        return jsonify({"hata": "Oturum açık değil"}), 401

    kullanici = Kullanici.query.get(kullanici_id)
    if not kullanici:
        return jsonify({"hata": "Kullanıcı bulunamadı"}), 404

    profil_adi = kullanici.email
    if kullanici.rol == "market":
        m = kullanici.market[0] if isinstance(kullanici.market, list) and kullanici.market else kullanici.market
        profil_adi = m.ad if m else "Köşebaşı Market"
    elif kullanici.rol == "musteri":
        m = kullanici.musteri[0] if isinstance(kullanici.musteri, list) and kullanici.musteri else kullanici.musteri
        profil_adi = m.ad_soyad if m else kullanici.email.split("@")[0].capitalize()

    return jsonify({
        "id": kullanici.id,
        "email": kullanici.email,
        "rol": kullanici.rol,
        "profil_adi": profil_adi
    }), 200