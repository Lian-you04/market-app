from flask import Blueprint, request, jsonify, session
from app import db
from app.models import Kullanici, Market, Musteri, Kurye

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    sifre = data.get("sifre")
    rol = data.get("rol")

    if not all([email, sifre, rol]):
        return jsonify({"hata": "E-posta, şifre ve rol zorunludur"}), 400

    if Kullanici.query.filter_by(email=email).first():
        return jsonify({"hata": "Bu e-posta adresi zaten kayıtlı!"}), 400

    try:
        yeni_kullanici = Kullanici(email=email, rol=rol)
        yeni_kullanici.sifre_belirle(sifre)
        db.session.add(yeni_kullanici)
        db.session.flush()

        if rol == "market":
            profil = Market(
                kullanici_id=yeni_kullanici.id,
                ad=data.get("ad", "Yeni Market"),
                adres=data.get("adres"),
                telefon=data.get("telefon"),
                konum_lat=float(data.get("konum_lat", 36.2000)),
                konum_lon=float(data.get("konum_lon", 36.1500)),
                maks_teslimat_km=float(data.get("yaricap_km", 5.0)),
                resim_url=data.get("resim_url", "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80")
            )
        elif rol == "musteri":
            profil = Musteri(
                kullanici_id=yeni_kullanici.id,
                ad_soyad=data.get("ad", "Yeni Müşteri"),
                telefon=data.get("telefon", ""),
                adres=data.get("adres"),
                konum_lat=float(data.get("konum_lat", 36.1950)),
                konum_lon=float(data.get("konum_lon", 36.1450))
            )
        elif rol == "kurye":
            profil = Kurye(
                kullanici_id=yeni_kullanici.id,
                ad_soyad=data.get("ad", "Yeni Kurye"),
                telefon=data.get("telefon", ""),
                konum_lat=float(data.get("konum_lat", 36.1980)),
                konum_lon=float(data.get("konum_lon", 36.1480)),
                calisma_yaricap_km=float(data.get("yaricap_km", 7.0)),
                durum="musait"
            )
        else:
            db.session.rollback()
            return jsonify({"hata": "Geçersiz rol seçildi"}), 400

        db.session.add(profil)
        db.session.commit()

        return jsonify({"mesaj": "Kayıt başarılı, giriş yapabilirsiniz.", "kullanici_id": yeni_kullanici.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": "Kayıt oluşturulamadı.", "detay": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    sifre = data.get("sifre")

    kullanici = Kullanici.query.filter_by(email=email, aktif=True).first()

    if not kullanici or not kullanici.sifre_kontrol(sifre):
        return jsonify({"hata": "E-posta veya şifre hatalı!"}), 401

    profil_id = None
    profil_ad = ""
    if kullanici.rol == "market" and kullanici.market:
        profil_id = kullanici.market.id
        profil_ad = kullanici.market.ad
    elif kullanici.rol == "musteri" and kullanici.musteri:
        profil_id = kullanici.musteri.id
        profil_ad = kullanici.musteri.ad_soyad
    elif kullanici.rol == "kurye" and kullanici.kurye:
        profil_id = kullanici.kurye.id
        profil_ad = kullanici.kurye.ad_soyad

    session["kullanici_id"] = kullanici.id
    session["rol"] = kullanici.rol
    session["profil_id"] = profil_id

    return jsonify({
        "mesaj": "Giriş başarılı",
        "kullanici": {
            "id": kullanici.id,
            "email": kullanici.email,
            "rol": kullanici.rol,
            "profil_id": profil_id,
            "profil_ad": profil_ad
        }
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mesaj": "Oturum kapatıldı"})