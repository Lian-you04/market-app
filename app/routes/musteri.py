from flask import Blueprint, request, jsonify, session
from app import db, socketio
from app.models import Urun, Siparis, SiparisDetay, Musteri, Market, Kullanici, FavoriUrun
from app.security import role_required

musteri_bp = Blueprint("musteri", __name__)


def aktif_musteri_getir():
    kullanici_id = session.get("kullanici_id")
    if not kullanici_id:
        return None
    return Musteri.query.filter_by(kullanici_id=kullanici_id).first()


def siparis_json(s):
    kalemler = [{
        "urun_id": d.urun_id,
        "ad": d.urun.ad if d.urun else "Silinmiş Ürün",
        "adet": d.adet,
        "birim_fiyat": float(d.birim_fiyat)
    } for d in s.detaylar]

    return {
        "id": s.id,
        "durum": s.durum,
        "odeme_yontemi": s.odeme_yontemi,
        "teslimat_yontemi": s.teslimat_yontemi,
        "toplam_tutar": float(s.toplam_tutar),
        "tarih": s.olusturma_tarihi.strftime("%d.%m.%Y %H:%M") if s.olusturma_tarihi else "",
        "detaylar": kalemler
    }


@musteri_bp.route("/market-durum", methods=["GET"])
def market_durum_ogren():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        m = Market.query.get_or_404(market_id)

        return jsonify({
            "ad": m.ad,
            "adres": m.adres,
            "harita_url": m.adres,
            "aktif": m.aktif,
            "min_siparis_tutari": float(m.min_siparis_tutari),
            "maks_teslimat_km": float(m.maks_teslimat_km),
            "konum_lat": float(m.konum_lat),
            "konum_lon": float(m.konum_lon)
        }), 200
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/kategoriler", methods=["GET"])
def kategoriler_listele():
    return jsonify([
        {"id": "et_tavuk", "ad": "🥩 Et & Tavuk", "resim": "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=200&q=80"},
        {"id": "meyve_sebze", "ad": "🍅 Meyve & Sebze", "resim": "https://images.unsplash.com/photo-1610348725531-843dff563e2c?auto=format&fit=crop&w=200&q=80"},
        {"id": "sut_kahvaltilik", "ad": "🧀 Süt & Kahvaltı", "resim": "https://images.unsplash.com/photo-1628088062854-d1870b4553da?auto=format&fit=crop&w=200&q=80"},
        {"id": "aburcubur", "ad": "🍫 Aburcubur", "resim": "https://images.unsplash.com/photo-1606312619070-d48b4c652a52?auto=format&fit=crop&w=200&q=80"},
        {"id": "icecek", "ad": "🥤 İçecekler", "resim": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=200&q=80"},
        {"id": "ekmek_firin", "ad": "🍞 Ekmek & Fırın", "resim": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=200&q=80"},
        {"id": "tatlilar", "ad": "🍰 Tatlılar", "resim": "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=200&q=80"},
        {"id": "temizlik", "ad": "🧼 Temizlik", "resim": "https://images.unsplash.com/photo-1563453392212-326f5e854473?auto=format&fit=crop&w=200&q=80"},
        {"id": "kozmetik", "ad": "🧴 Kozmetik", "resim": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=200&q=80"},
        {"id": "dondurma", "ad": "🍦 Dondurma", "resim": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?auto=format&fit=crop&w=200&q=80"},
        {"id": "evcil_hayvan_mamasi", "ad": "🐾 Evcil Hayvan Maması", "resim": "https://images.unsplash.com/photo-1589924691995-400dc9ecc119?auto=format&fit=crop&w=200&q=80"},
        {"id": "elektronik", "ad": "🔌 Elektronik", "resim": "https://images.unsplash.com/photo-1498049794561-7780e7231661?auto=format&fit=crop&w=200&q=80"}
    ])

@musteri_bp.route("/urunler", methods=["GET"])
def urunleri_getir():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        kategori = request.args.get("kategori")

        query = Urun.query.filter_by(market_id=market_id, aktif=True)

        if kategori:
            query = query.filter_by(kategori=kategori)

        urunler = query.all()

        favori_ids = set()
        musteri = aktif_musteri_getir()

        if musteri:
            favori_ids = {
                f.urun_id for f in FavoriUrun.query.filter_by(musteri_id=musteri.id).all()
            }

        return jsonify([{
            "id": u.id,
            "ad": u.ad,
            "aciklama": u.aciklama,
            "fiyat": float(u.fiyat),
            "resim_url": u.resim_url,
            "max_alinabilir_adet": u.stok_adet,
            "stok_durumu": "var" if u.stok_adet > 0 else "tukendi",
            "favori": u.id in favori_ids
        } for u in urunler]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/profil", methods=["GET"])
@role_required("musteri")
def profil_getir():
    try:
        kullanici_id = session.get("kullanici_id")
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        kullanici = Kullanici.query.get(kullanici_id)

        parcalar = (musteri.ad_soyad or "").split(" ", 1)
        ad = parcalar[0] if len(parcalar) > 0 else ""
        soyad = parcalar[1] if len(parcalar) > 1 else ""

        return jsonify({
            "email": kullanici.email if kullanici else "",
            "ad": ad,
            "soyad": soyad,
            "ad_soyad": musteri.ad_soyad,
            "telefon": musteri.telefon,
            "adres_tarifi": musteri.adres,
            "adres": musteri.adres
        }), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/profil", methods=["PUT"])
@role_required("musteri")
def profil_guncelle():
    try:
        data = request.get_json(silent=True) or {}
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        ad = data.get("ad", "").strip()
        soyad = data.get("soyad", "").strip()
        ad_soyad = data.get("ad_soyad", "").strip()
        telefon = data.get("telefon", "").strip().replace(" ", "")
        adres_tarifi = data.get("adres_tarifi", data.get("adres", "")).strip()

        if ad or soyad:
            ad_soyad = f"{ad} {soyad}".strip()

        if not ad_soyad:
            return jsonify({"hata": "Ad ve soyad boş olamaz!"}), 400

        if not telefon:
            return jsonify({"hata": "Telefon boş olamaz!"}), 400

        if not telefon.startswith("+90"):
            telefon = "+90" + telefon.lstrip("0")

        if not adres_tarifi:
            return jsonify({"hata": "Adres tarifi boş olamaz!"}), 400

        musteri.ad_soyad = ad_soyad
        musteri.telefon = telefon
        musteri.adres = adres_tarifi

        db.session.commit()

        return jsonify({"mesaj": "Profil bilgileriniz güncellendi."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/siparisler", methods=["GET"])
@role_required("musteri")
def musteri_siparislerini_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        siparisler = Siparis.query.filter_by(musteri_id=musteri.id).order_by(
            Siparis.olusturma_tarihi.desc()
        ).all()

        return jsonify([siparis_json(s) for s in siparisler]), 200

    except Exception as e:
        return jsonify({"hata": f"Siparişler çekilemedi: {str(e)}"}), 500


@musteri_bp.route("/siparisler/gecmis", methods=["GET"])
@role_required("musteri")
def gecmis_siparisleri_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        siparisler = Siparis.query.filter(
            Siparis.musteri_id == musteri.id,
            Siparis.durum.in_(["teslim_edildi", "iptal"])
        ).order_by(Siparis.olusturma_tarihi.desc()).all()

        return jsonify([siparis_json(s) for s in siparisler]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/siparisler/aktif", methods=["GET"])
@role_required("musteri")
def aktif_siparisleri_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        siparisler = Siparis.query.filter(
            Siparis.musteri_id == musteri.id,
            Siparis.durum.notin_(["teslim_edildi", "iptal"])
        ).order_by(Siparis.olusturma_tarihi.desc()).all()

        return jsonify([siparis_json(s) for s in siparisler]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/siparisler/<int:siparis_id>/iptal", methods=["POST"])
@role_required("musteri")
def musteri_siparis_iptal(siparis_id):
    try:
        musteri = aktif_musteri_getir()
        siparis = Siparis.query.get_or_404(siparis_id)

        if not musteri or siparis.musteri_id != musteri.id:
            return jsonify({"hata": "Bu siparişi iptal etme yetkiniz yok!"}), 403

        if siparis.durum != "bekliyor":
            return jsonify({
                "hata": "Hazırlanmaya başlanmış sipariş iptal edilemez. Lütfen bakkalı arayın."
            }), 400

        siparis.durum = "iptal"

        for detay in siparis.detaylar:
            if detay.urun:
                detay.urun.stok_adet += detay.adet
                if detay.urun.stok_adet > 0:
                    detay.urun.aktif = True

        db.session.commit()

        socketio.emit("siparis_durumu_degisti", {
            "siparis_id": siparis.id,
            "yeni_durum": "iptal"
        })

        return jsonify({
            "mesaj": "Siparişiniz iptal edildi ve stoklar iade edildi."
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/favoriler", methods=["GET"])
@role_required("musteri")
def favorileri_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        favoriler = FavoriUrun.query.filter_by(musteri_id=musteri.id).all()

        return jsonify([{
            "urun_id": f.urun.id,
            "ad": f.urun.ad,
            "aciklama": f.urun.aciklama,
            "fiyat": float(f.urun.fiyat),
            "resim_url": f.urun.resim_url,
            "stok_adet": f.urun.stok_adet,
            "max_alinabilir_adet": f.urun.stok_adet,
            "stok_durumu": "var" if f.urun.stok_adet > 0 else "tukendi",
            "aktif": f.urun.aktif
        } for f in favoriler if f.urun]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/favoriler/<int:urun_id>", methods=["POST"])
@musteri_bp.route("/favori/<int:urun_id>", methods=["POST"])
@role_required("musteri")
def favori_ekle(urun_id):
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        urun = Urun.query.get_or_404(urun_id)

        mevcut = FavoriUrun.query.filter_by(
            musteri_id=musteri.id,
            urun_id=urun.id
        ).first()

        if mevcut:
            return jsonify({
                "mesaj": "Ürün zaten favorilerinizde.",
                "favori": True
            }), 200

        db.session.add(FavoriUrun(
            musteri_id=musteri.id,
            urun_id=urun.id
        ))

        db.session.commit()

        return jsonify({
            "mesaj": "Ürün favorilere eklendi.",
            "favori": True
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/favoriler/<int:urun_id>", methods=["DELETE"])
@musteri_bp.route("/favori/<int:urun_id>", methods=["DELETE"])
@role_required("musteri")
def favori_sil(urun_id):
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        favori = FavoriUrun.query.filter_by(
            musteri_id=musteri.id,
            urun_id=urun_id
        ).first()

        if favori:
            db.session.delete(favori)
            db.session.commit()

        return jsonify({
            "mesaj": "Ürün favorilerden çıkarıldı.",
            "favori": False
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/siparis", methods=["POST"])
@role_required("musteri")
def siparis_olustur():
    try:
        kullanici_id = session.get("kullanici_id")
        data = request.get_json(silent=True) or {}
        market_id = data.get("market_id", 1)

        market = Market.query.get_or_404(market_id)

        if not market.aktif:
            return jsonify({"hata": "Bakkal şu an siparişe kapalıdır!"}), 400

        musteri = aktif_musteri_getir()

        if not musteri:
            kullanici = Kullanici.query.get(kullanici_id)

            musteri = Musteri(
                kullanici_id=kullanici_id,
                ad_soyad=kullanici.email.split("@")[0].capitalize(),
                telefon="+905320000000",
                adres="Antakya Merkez / Hatay"
            )

            db.session.add(musteri)
            db.session.flush()

        istenen_kalemler = data.get("urunler", [])

        if not istenen_kalemler:
            return jsonify({"hata": "Sepetiniz boş!"}), 400

        kontrol_edilmis_kalemler = []

        for kalem in istenen_kalemler:
            urun = Urun.query.get(kalem.get("urun_id"))

            if not urun or not urun.aktif or urun.market_id != int(market_id):
                return jsonify({
                    "hata": f"Ürün bulunamadı veya artık satışta değil (id: {kalem.get('urun_id')})"
                }), 400

            adet = int(kalem.get("adet", 0))

            if adet <= 0:
                return jsonify({"hata": f"'{urun.ad}' için geçersiz adet!"}), 400

            if urun.stok_adet < adet:
                return jsonify({
                    "hata": f"'{urun.ad}' için yeterli stok yok! Mevcut stok: {urun.stok_adet}"
                }), 400

            kontrol_edilmis_kalemler.append((urun, adet))

        yeni_siparis = Siparis(
            market_id=market_id,
            musteri_id=musteri.id,
            durum="bekliyor",
            odeme_yontemi=data.get("odeme_yontemi", "nakit"),
            teslimat_yontemi="adrese_teslim",
            siparis_notu=data.get("not", ""),
            toplam_tutar=0.0
        )

        db.session.add(yeni_siparis)
        db.session.flush()

        toplam = 0.0

        for urun, adet in kontrol_edilmis_kalemler:
            fiyat = float(urun.fiyat)
            toplam += fiyat * adet

            db.session.add(SiparisDetay(
                siparis_id=yeni_siparis.id,
                urun_id=urun.id,
                adet=adet,
                birim_fiyat=fiyat
            ))

            urun.stok_adet -= adet

            if urun.stok_adet <= 0:
                urun.aktif = False

        yeni_siparis.toplam_tutar = toplam

        db.session.commit()

        socketio.emit("yeni_siparis_geldi", {
            "market_id": market_id,
            "siparis_id": yeni_siparis.id
        })

        return jsonify({
            "mesaj": "Siparişiniz başarıyla alındı!",
            "id": yeni_siparis.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Sipariş hatası: {str(e)}"}), 500