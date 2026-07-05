import os
import math
import uuid
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Urun, Siparis, SiparisDetay, Kurye, Market

market_bp = Blueprint("market", __name__)

# İzin verilen resim uzantıları
IZIN_VERILEN_UZANTILAR = {"png", "jpg", "jpeg", "webp"}


def resim_uzantisi_gonderilebilir_mi(dosya_adi):
    return "." in dosya_adi and dosya_adi.rsplit(".", 1)[1].lower() in IZIN_VERILEN_UZANTILAR


def mesafe_hesapla(lat1, lon1, lat2, lon2):
    """İki koordinat arasındaki mesafeyi (km cinsinden) Haversine formülü ile hesaplar."""
    if None in (lat1, lon1, lat2, lon2):
        return 999.0
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


@market_bp.route("/kuryeler", methods=["GET"])
def kuryeleri_listele():
    try:
        market_id = request.args.get("market_id", type=int)
        kuryeler = Kurye.query.all()
        
        # Eğer market_id gönderildiyse, sadece marketin etrafındaki kapsama alanındaki kuryeleri getir
        if market_id:
            market = Market.query.get(market_id)
            if market:
                uygun_kuryeler = []
                for k in kuryeler:
                    msf = mesafe_hesapla(market.konum_lat, market.konum_lon, k.konum_lat, k.konum_lon)
                    if msf <= k.calisma_yaricap_km:
                        uygun_kuryeler.append({
                            "id": k.id,
                            "ad_soyad": k.ad_soyad,
                            "durum": k.durum,
                            "mesafe_km": round(msf, 1)
                        })
                return jsonify(uygun_kuryeler)

        return jsonify([{"id": k.id, "ad_soyad": k.ad_soyad, "durum": k.durum} for k in kuryeler])
    except Exception as e:
        return jsonify({"hata": f"Kuryeler yüklenirken hata oluştu: {str(e)}"}), 500


@market_bp.route("/urunler", methods=["POST"])
def urun_ekle():
    """
    Çoklu fotoğraf yüklemeyi ('resimler'), tekli yüklemeyi ('resim') 
    veya standart JSON içindeki 'resim_url' linkini kusursuz şekilde destekler.
    """
    try:
        dosyalar = []
        if request.content_type and "multipart/form-data" in request.content_type:
            form_verisi = request.form
            # Esnaf çoklu seçim yaptıysa 'resimler' anahtarından çek
            dosyalar = request.files.getlist("resimler")
            # Eğer 'resimler' boş geldiyse tekli 'resim' girdisine bak
            if not dosyalar or all(d.filename == '' for d in dosyalar):
                tekli_dosya = request.files.get("resim")
                if tekli_dosya and tekli_dosya.filename != '':
                    dosyalar = [tekli_dosya]
        else:
            form_verisi = request.json or {}

        market_id = form_verisi.get("market_id")
        ad = form_verisi.get("ad", "").strip()
        fiyat = form_verisi.get("fiyat")

        if not market_id or not ad or fiyat is None:
            return jsonify({"hata": "Market ID, Ürün Adı ve Fiyat alanları zorunludur!"}), 400

        # Fotoğrafları kaydetme
        kaydedilen_yollar = []
        if dosyalar:
            yukleme_klasoru = os.path.join(current_app.static_folder, "uploads")
            os.makedirs(yukleme_klasoru, exist_ok=True)

            for dosya in dosyalar:
                if dosya and dosya.filename != "" and resim_uzantisi_gonderilebilir_mi(dosya.filename):
                    uzanti = dosya.filename.rsplit(".", 1)[1].lower()
                    guvenli_isim = f"{uuid.uuid4().hex}.{uzanti}"
                    dosya.save(os.path.join(yukleme_klasoru, guvenli_isim))
                    kaydedilen_yollar.append(f"/static/uploads/{guvenli_isim}")

        # Eğer dosya yüklenmediyse formdaki URL'yi veya varsayılan resmi koy
        if kaydedilen_yollar:
            resim_yolu = ",".join(kaydedilen_yollar)
        else:
            resim_yolu = form_verisi.get("resim_url", "https://images.unsplash.com/photo-1583258292688-d0213dc5a3a8?auto=format&fit=crop&w=300&q=80")

        urun = Urun(
            market_id=int(market_id),
            ad=ad,
            aciklama=form_verisi.get("aciklama", "").strip(),
            fiyat=float(fiyat),
            stok_adet=int(form_verisi.get("stok_adet", 0)),
            kategori=form_verisi.get("kategori", "yeni_urunler"),
            resim_url=resim_yolu,
            aktif=True
        )
        db.session.add(urun)
        db.session.commit()
        return jsonify({"id": urun.id, "resim_url": resim_yolu, "mesaj": "Ürün başarıyla eklendi"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Ürün eklenemedi: {str(e)}"}), 500


@market_bp.route("/urunler/<int:urun_id>", methods=["PUT"])
def urun_guncelle(urun_id):
    try:
        urun = Urun.query.get_or_404(urun_id)
        data = request.json or {}
        
        if "fiyat" in data:
            urun.fiyat = float(data["fiyat"])
        if "stok_adet" in data:
            yeni_stok = int(data["stok_adet"])
            urun.stok_adet = yeni_stok
            # Stok 0'dan büyükse otomatik Satışta (aktif), 0 ise Tükendi (pasif) yap
            if yeni_stok > 0:
                urun.aktif = True
            else:
                urun.aktif = False

        if "aktif" in data:
            urun.aktif = bool(data["aktif"])
        if "ad" in data:
            urun.ad = str(data["ad"])
        if "aciklama" in data:
            urun.aciklama = str(data["aciklama"])
            
        db.session.commit()
        return jsonify({"mesaj": "Ürün başarıyla güncellendi", "stok": urun.stok_adet, "aktif": urun.aktif})
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Ürün güncellenemedi: {str(e)}"}), 500


@market_bp.route("/urunler", methods=["GET"])
def urunler_listele():
    try:
        market_id = request.args.get("market_id", type=int)
        query = Urun.query
        if market_id:
            query = query.filter_by(market_id=market_id)
        
        urunler = query.all()
        return jsonify([{
            "id": u.id,
            "ad": u.ad,
            "aciklama": u.aciklama,
            "fiyat": float(u.fiyat),
            "stok_adet": u.stok_adet,
            "kategori": u.kategori,
            "resim_url": u.resim_url,
            "aktif": u.aktif
        } for u in urunler])
    except Exception as e:
        return jsonify({"hata": f"Ürünler yüklenirken hata oluştu: {str(e)}"}), 500


@market_bp.route("/siparisler", methods=["GET"])
def siparisler_listele():
    try:
        market_id = request.args.get("market_id", type=int)
        durum = request.args.get("durum")
        query = Siparis.query
        
        if market_id:
            query = query.filter_by(market_id=market_id)
        if durum:
            query = query.filter_by(durum=durum)
            
        siparisler = query.order_by(Siparis.olusturma_tarihi.desc()).all()
        
        sonuc = []
        for s in siparisler:
            kalemler = []
            for d in s.detaylar:
                if d.urun:
                    kalemler.append({
                        "detay_id": d.id,  # Esnafın satır adedini düzenleyebilmesi için zorunlu!
                        "ad": d.urun.ad,
                        "adet": d.adet,
                        "birim_fiyat": float(d.birim_fiyat),
                        "satir_toplam": float(d.birim_fiyat) * d.adet
                    })
            
            sonuc.append({
                "id": s.id,
                "musteri_id": s.musteri_id,
                "durum": s.durum,
                "odeme_yontemi": s.odeme_yontemi,
                "toplam_tutar": float(s.toplam_tutar),
                "kurye_id": s.kurye_id,
                "detaylar": kalemler
            })
        return jsonify(sonuc)
    except Exception as e:
        return jsonify({"hata": f"Siparişler yüklenirken hata oluştu: {str(e)}"}), 500


@market_bp.route("/siparisler/<int:siparis_id>/detay/<int:detay_id>", methods=["PUT"])
def siparis_kalem_duzenle(siparis_id, detay_id):
    """
    Esnafın, rafta eksik ürün olduğunda sipariş kaleminin adedini değiştirmesini sağlar.
    Farkı stoğa iade eder ve siparişin yeni toplam tutarını hesaplar.
    """
    try:
        detay = SiparisDetay.query.get_or_404(detay_id)
        if detay.siparis_id != siparis_id:
            return jsonify({"hata": "Bu detay bu siparişe ait değil!"}), 400

        yeni_adet = int((request.json or {}).get("yeni_adet", 0))
        if yeni_adet < 0:
            return jsonify({"hata": "Adet 0'dan küçük olamaz!"}), 400

        eski_adet = detay.adet
        fark = eski_adet - yeni_adet

        # Rafta eksik çıktığı için iptal edilen adet kadarını stoğa geri iade et
        if detay.urun:
            detay.urun.stok_adet += fark
            if detay.urun.stok_adet > 0:
                detay.urun.aktif = True

        if yeni_adet == 0:
            db.session.delete(detay)
        else:
            detay.adet = yeni_adet

        db.session.flush()

        # Siparişin güncel toplam tutarını yeniden hesapla
        siparis = Siparis.query.get(siparis_id)
        siparis.toplam_tutar = sum(d.adet * float(d.birim_fiyat) for d in siparis.detaylar)
        
        db.session.commit()
        return jsonify({"mesaj": "Sipariş içeriği, stok ve toplam tutar başarıyla güncellendi."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Sipariş kalemi güncellenemedi: {str(e)}"}), 500


@market_bp.route("/siparisler/<int:siparis_id>/durum", methods=["PUT"])
def siparis_durum_guncelle(siparis_id):
    try:
        siparis = Siparis.query.get_or_404(siparis_id)
        yeni_durum = (request.json or {}).get("durum")
        
        if siparis.durum in ["iptal", "teslim_edildi"] and yeni_durum == "iptal":
            return jsonify({"hata": "Tamamlanmış veya zaten iptal edilmiş bir sipariş tekrar iptal edilemez!"}), 400

        # Eğer sipariş iptal edilirse, düşülmüş olan tüm stokları markete iade et
        if yeni_durum == "iptal" and siparis.durum != "iptal":
            for detay in siparis.detaylar:
                if detay.urun:
                    detay.urun.stok_adet += detay.adet
                    if detay.urun.stok_adet > 0:
                        detay.urun.aktif = True
            
            if siparis.kurye_id and siparis.durum != "yolda":
                kurye = Kurye.query.get(siparis.kurye_id)
                if kurye:
                    kurye.durum = "musait"

        siparis.durum = yeni_durum
        db.session.commit()
        return jsonify({"mesaj": f"Sipariş durumu '{yeni_durum}' olarak güncellendi"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Durum güncellenemedi: {str(e)}"}), 500


@market_bp.route("/siparisler/<int:siparis_id>/kurye-ata", methods=["POST"])
def kurye_ata(siparis_id):
    try:
        siparis = Siparis.query.get_or_404(siparis_id)
        kurye_id = (request.json or {}).get("kurye_id")
        
        kurye = Kurye.query.get_or_404(kurye_id)
        siparis.kurye_id = kurye.id
        siparis.durum = "hazirlaniyor"
        kurye.durum = "mesgul"
        
        db.session.commit()
        return jsonify({"mesaj": f"Kurye '{kurye.ad_soyad}' bu siparişe atandı"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Kurye ataması yapılamadı: {str(e)}"}), 500