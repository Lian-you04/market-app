import math
from flask import Blueprint, request, jsonify
from app import db
from app.models import Urun, Siparis, Kurye, Market

market_bp = Blueprint("market", __name__)

def mesafe_hesapla(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2): return 999.0
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

@market_bp.route("/kuryeler", methods=["GET"])
def kuryeleri_listele():
    market_id = request.args.get("market_id", type=int)
    kuryeler = Kurye.query.all()
    
    # Market belirtilmişse mesafeye göre filtrele
    if market_id:
        market = Market.query.get(market_id)
        if market:
            uygun_kuryeler = []
            for k in kuryeler:
                msf = mesafe_hesapla(market.konum_lat, market.konum_lon, k.konum_lat, k.konum_lon)
                # Kuryenin kendi çalışma yarıçapı marketi kapsıyorsa listeye ekle
                if msf <= k.calisma_yaricap_km:
                    uygun_kuryeler.append({"id": k.id, "ad_soyad": k.ad_soyad, "durum": k.durum, "mesafe_km": round(msf, 1)})
            return jsonify(uygun_kuryeler)

    return jsonify([{"id": k.id, "ad_soyad": k.ad_soyad, "durum": k.durum} for k in kuryeler])

@market_bp.route("/urunler", methods=["POST"])
def urun_ekle():
    data = request.json
    try:
        urun = Urun(
            market_id=data["market_id"], ad=data["ad"], aciklama=data.get("aciklama", ""),
            fiyat=data["fiyat"], stok_adet=data.get("stok_adet", 0),
            kategori=data.get("kategori", "yeni_urunler"),
            resim_url=data.get("resim_url", "https://images.unsplash.com/photo-1583258292688-d0213dc5a3a8?auto=format&fit=crop&w=300&q=80")
        )
        db.session.add(urun)
        db.session.commit()
        return jsonify({"id": urun.id, "mesaj": "Ürün eklendi"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500

@market_bp.route("/urunler", methods=["GET"])
def urunler_listele():
    market_id = request.args.get("market_id", type=int)
    urunler = Urun.query.filter_by(market_id=market_id).all() if market_id else Urun.query.all()
    return jsonify([{
        "id": u.id, "ad": u.ad, "aciklama": u.aciklama, "fiyat": float(u.fiyat),
        "stok_adet": u.stok_adet, "kategori": u.kategori, "resim_url": u.resim_url, "aktif": u.aktif
    } for u in urunler])

@market_bp.route("/siparisler", methods=["GET"])
def siparisler_listele():
    market_id = request.args.get("market_id", type=int)
    durum = request.args.get("durum")
    query = Siparis.query
    if market_id: query = query.filter_by(market_id=market_id)
    if durum: query = query.filter_by(durum=durum)
    siparisler = query.order_by(Siparis.olusturma_tarihi.desc()).all()
    return jsonify([{
        "id": s.id, "musteri_id": s.musteri_id, "durum": s.durum,
        "odeme_yontemi": s.odeme_yontemi, "toplam_tutar": float(s.toplam_tutar), "kurye_id": s.kurye_id
    } for s in siparisler])

@market_bp.route("/siparisler/<int:siparis_id>/durum", methods=["PUT"])
def siparis_durum_guncelle(siparis_id):
    siparis = Siparis.query.get_or_404(siparis_id)
    yeni_durum = request.json.get("durum")
    if siparis.durum in ["iptal", "teslim_edildi"] and yeni_durum == "iptal":
        return jsonify({"hata": "Tamamlanmış sipariş iptal edilemez!"}), 400

    try:
        if yeni_durum == "iptal" and siparis.durum != "iptal":
            for detay in siparis.detaylar:
                if detay.urun: detay.urun.stok_adet += detay.adet
            if siparis.kurye_id and siparis.durum != "yolda":
                k = Kurye.query.get(siparis.kurye_id)
                if k: k.durum = "musait"
        siparis.durum = yeni_durum
        db.session.commit()
        return jsonify({"mesaj": "Guncellendi"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500

@market_bp.route("/siparisler/<int:siparis_id>/kurye-ata", methods=["POST"])
def kurye_ata(siparis_id):
    siparis = Siparis.query.get_or_404(siparis_id)
    kurye_id = request.json.get("kurye_id")
    try:
        kurye = Kurye.query.get_or_404(kurye_id)
        siparis.kurye_id = kurye.id
        siparis.durum = "hazirlaniyor"
        kurye.durum = "mesgul"
        db.session.commit()
        return jsonify({"mesaj": f"Kurye {kurye.ad_soyad} atandı"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500