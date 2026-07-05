import math
from flask import Blueprint, request, jsonify
from app import db
from app.models import Urun, Siparis, SiparisDetay, Market, Musteri

musteri_bp = Blueprint("musteri", __name__)

def mesafe_hesapla(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2): return 999.0
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

@musteri_bp.route("/kategoriler", methods=["GET"])
def kategoriler():
    """Görseldeki gibi resimli ve şık market kategorileri."""
    return jsonify([
        {"id": "yeni_urunler", "ad": "Yeni Ürünler", "ikon": "🔔", "resim": "https://images.unsplash.com/photo-1578916171728-46686eac8d58?auto=format&fit=crop&w=150&q=80"},
        {"id": "et_tavuk", "ad": "Et, Tavuk & Şarküteri", "ikon": "🥩", "resim": "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=150&q=80"},
        {"id": "meyve_sebze", "ad": "Meyve & Sebze", "ikon": "🍅", "resim": "https://images.unsplash.com/photo-1610348725531-843dff563e2c?auto=format&fit=crop&w=150&q=80"},
        {"id": "sut_kahvaltilik", "ad": "Süt & Kahvaltılık", "ikon": "🧀", "resim": "https://images.unsplash.com/photo-1486297678162-eb2a19b0a32d?auto=format&fit=crop&w=150&q=80"},
        {"id": "atistirmalik", "ad": "Atıştırmalık & Çerez", "ikon": "chips", "resim": "https://images.unsplash.com/photo-1566478989037-eec170784d0b?auto=format&fit=crop&w=150&q=80"},
        {"id": "icecek", "ad": "İçecekler", "ikon": "🥤", "resim": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=150&q=80"},
        {"id": "ekmek_pastane", "ad": "Ekmek & Pastane", "ikon": "🍞", "resim": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=150&q=80"},
        {"id": "temizlik", "ad": "Temizlik & Hijyen", "ikon": "🧼", "resim": "https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&w=150&q=80"}
    ])

@musteri_bp.route("/yakindaki-marketler", methods=["GET"])
def yakindaki_marketler():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"hata": "Müşteri konumu (lat/lon) zorunlu."}), 400

    marketler = Market.query.filter_by(aktif=True).all()
    uygunlar = []
    for m in marketler:
        mesafe = mesafe_hesapla(lat, lon, m.konum_lat, m.konum_lon)
        # Sadece marketin kendi belirlediği maksimum teslimat km içerisindeyse listele!
        if mesafe <= m.maks_teslimat_km:
            uygunlar.append({
                "id": m.id, "ad": m.ad, "adres": m.adres,
                "resim_url": m.resim_url, "mesafe_km": round(mesafe, 1),
                "min_siparis_tutari": float(m.min_siparis_tutari)
            })
    uygunlar.sort(key=lambda x: x["mesafe_km"])
    return jsonify(uygunlar)

@musteri_bp.route("/urunler", methods=["GET"])
def urunler_listele():
    market_id = request.args.get("market_id", type=int)
    kategori = request.args.get("kategori")
    if not market_id: return jsonify({"hata": "market_id gerekli"}), 400

    query = Urun.query.filter_by(market_id=market_id, aktif=True)
    if kategori: query = query.filter_by(kategori=kategori)

    sonuc = []
    for u in query.all():
        stok_durumu = "tukendi" if u.stok_adet <= 0 else "kritik_stok" if u.stok_adet <= 5 else "stokta_var"
        etiket = "Tükendi" if u.stok_adet <= 0 else f"Son {u.stok_adet} Ürün!" if u.stok_adet <= 5 else None
        sonuc.append({
            "id": u.id, "ad": u.ad, "aciklama": u.aciklama, "fiyat": float(u.fiyat),
            "kategori": u.kategori, "resim_url": u.resim_url,
            "stok_durumu": stok_durumu, "etiket": etiket, "max_alinabilir_adet": u.stok_adet
        })
    return jsonify(sonuc)

@musteri_bp.route("/siparis", methods=["POST"])
def siparis_olustur():
    data = request.json
    if not data.get("urunler"): return jsonify({"hata": "Sepet boş"}), 400

    try:
        siparis = Siparis(
            market_id=data["market_id"], musteri_id=data["musteri_id"],
            odeme_yontemi=data.get("odeme_yontemi", "nakit"), durum="bekliyor"
        )
        db.session.add(siparis)
        db.session.flush()

        toplam = 0
        for k in data["urunler"]:
            u = Urun.query.get_or_404(k["urun_id"])
            adet = int(k["adet"])
            if u.stok_adet < adet:
                db.session.rollback()
                return jsonify({"hata": f"'{u.ad}' için yetersiz stok! Kalan: {u.stok_adet}"}), 400
            u.stok_adet -= adet
            db.session.add(SiparisDetay(siparis_id=siparis.id, urun_id=u.id, adet=adet, birim_fiyat=u.fiyat))
            toplam += float(u.fiyat) * adet

        siparis.toplam_tutar = toplam
        db.session.commit()
        return jsonify({"id": siparis.id, "toplam_tutar": toplam, "durum": siparis.durum}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": "Sipariş hatası", "detay": str(e)}), 500

@musteri_bp.route("/siparis/<int:siparis_id>", methods=["GET"])
def siparis_durumu(siparis_id):
    s = Siparis.query.get_or_404(siparis_id)
    return jsonify({"id": s.id, "durum": s.durum, "kurye_id": s.kurye_id, "toplam_tutar": float(s.toplam_tutar), "odeme_yontemi": s.odeme_yontemi})