import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from app import db, socketio
from app.models import Urun, Siparis, SiparisDetay, Market
from app.security import role_required

market_bp = Blueprint("market", __name__)
IZIN_VERILEN_UZANTILAR = {"png", "jpg", "jpeg", "webp"}


def resim_uzantisi_gonderilebilir_mi(dosya_adi):
    return "." in dosya_adi and dosya_adi.rsplit(".", 1)[1].lower() in IZIN_VERILEN_UZANTILAR


@market_bp.route("/durum", methods=["GET"])
@role_required("market")
def market_durum_getir():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        market = Market.query.get_or_404(market_id)

        return jsonify({
            "id": market.id,
            "ad": market.ad,
            "adres": market.adres,
            "aktif": market.aktif,
            "min_siparis_tutari": float(market.min_siparis_tutari),
            "maks_teslimat_km": float(market.maks_teslimat_km),
            "konum_lat": float(market.konum_lat),
            "konum_lon": float(market.konum_lon)
        }), 200
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/durum", methods=["PUT"])
@role_required("market")
def market_durum_guncelle():
    try:
        data = request.json or {}
        market_id = data.get("market_id", 1)
        market = Market.query.get_or_404(market_id)

        if "aktif" in data:
            market.aktif = bool(data["aktif"])
        if "min_siparis_tutari" in data:
            market.min_siparis_tutari = float(data["min_siparis_tutari"])
        if "maks_teslimat_km" in data:
            market.maks_teslimat_km = float(data["maks_teslimat_km"])
        if "konum_lat" in data:
            market.konum_lat = float(data["konum_lat"])
        if "konum_lon" in data:
            market.konum_lon = float(data["konum_lon"])
        if "adres" in data:
            market.adres = str(data["adres"]).strip()

        db.session.commit()

        socketio.emit("market_durumu_degisti", {
            "market_id": market.id,
            "aktif": market.aktif
        })

        return jsonify({
            "mesaj": "Market operasyon ve harita ayarları güncellendi.",
            "konum_lat": market.konum_lat,
            "konum_lon": market.konum_lon
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/urunler", methods=["POST"])
@role_required("market")
def urun_ekle():
    try:
        dosyalar = []

        if request.content_type and "multipart/form-data" in request.content_type:
            form_verisi = request.form
            dosyalar = request.files.getlist("resimler")

            if not dosyalar or all(d.filename == "" for d in dosyalar):
                tekli_dosya = request.files.get("resim")
                if tekli_dosya and tekli_dosya.filename != "":
                    dosyalar = [tekli_dosya]
        else:
            form_verisi = request.json or {}

        market_id = form_verisi.get("market_id", 1)
        ad = form_verisi.get("ad", "").strip()
        fiyat = form_verisi.get("fiyat")

        if not ad or fiyat is None:
            return jsonify({"hata": "Ürün Adı ve Fiyat alanları zorunludur!"}), 400

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

        resim_yolu = ",".join(kaydedilen_yollar) if kaydedilen_yollar else form_verisi.get(
            "resim_url",
            "https://images.unsplash.com/photo-1583258292688-d0213dc5a3a8?auto=format&fit=crop&w=300&q=80"
        )

        urun = Urun(
            market_id=int(market_id),
            ad=ad,
            aciklama=form_verisi.get("aciklama", "").strip(),
            fiyat=float(fiyat),
            stok_adet=int(form_verisi.get("stok_adet", 0)),
            kategori=form_verisi.get("kategori", "meyve_sebze"),
            resim_url=resim_yolu,
            aktif=True
        )

        db.session.add(urun)
        db.session.commit()

        return jsonify({
            "id": urun.id,
            "resim_url": resim_yolu,
            "mesaj": "Ürün başarıyla eklendi"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Ürün eklenemedi: {str(e)}"}), 500


@market_bp.route("/urunler/<int:urun_id>", methods=["PUT"])
@role_required("market")
def urun_guncelle(urun_id):
    try:
        urun = Urun.query.get_or_404(urun_id)
        data = request.json or {}

        if "fiyat" in data:
            urun.fiyat = float(data["fiyat"])

        if "stok_adet" in data:
            yeni_stok = int(data["stok_adet"])
            urun.stok_adet = yeni_stok
            urun.aktif = yeni_stok > 0

        if "aktif" in data:
            urun.aktif = bool(data["aktif"])

        if "ad" in data:
            urun.ad = str(data["ad"])

        if "aciklama" in data:
            urun.aciklama = str(data["aciklama"])

        if "kategori" in data:
            urun.kategori = str(data["kategori"])

        db.session.commit()

        return jsonify({
            "mesaj": "Ürün güncellendi",
            "stok": urun.stok_adet,
            "aktif": urun.aktif
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/urunler", methods=["GET"])
@role_required("market")
def urunler_listele():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        urunler = Urun.query.filter_by(market_id=market_id).all()

        return jsonify([{
            "id": u.id,
            "ad": u.ad,
            "aciklama": u.aciklama,
            "fiyat": float(u.fiyat),
            "stok_adet": u.stok_adet,
            "kategori": u.kategori,
            "resim_url": u.resim_url,
            "aktif": u.aktif
        } for u in urunler]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/siparisler", methods=["GET"])
@role_required("market")
def siparisler_listele():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        # Kasa panelinde sadece aktif/anlık siparişler görünür.
        # Teslim edilen veya iptal edilen siparişler bu listeden düşer.
        siparisler = Siparis.query.filter(
            Siparis.market_id == market_id,
            Siparis.durum.notin_(["teslim_edildi", "iptal"])
        ).order_by(Siparis.olusturma_tarihi.desc()).all()

        sonuc = []

        for s in siparisler:
            kalemler = [{
                "detay_id": d.id,
                "ad": d.urun.ad if d.urun else "Silinmiş Ürün",
                "adet": d.adet,
                "birim_fiyat": float(d.birim_fiyat),
                "satir_toplam": float(d.birim_fiyat) * d.adet
            } for d in s.detaylar]

            sonuc.append({
                "id": s.id,
                "musteri_id": s.musteri_id,
                "musteri_ad": s.musteri.ad_soyad if s.musteri else "Misafir Müşteri",
                "musteri_tel": s.musteri.telefon if s.musteri else "",
                "durum": s.durum,
                "odeme_yontemi": s.odeme_yontemi,
                "teslimat_yontemi": s.teslimat_yontemi,
                "siparis_notu": s.siparis_notu,
                "toplam_tutar": float(s.toplam_tutar),
                "detaylar": kalemler
            })

        return jsonify(sonuc), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/siparisler/<int:siparis_id>/detay/<int:detay_id>", methods=["PUT"])
@role_required("market")
def siparis_kalem_duzenle(siparis_id, detay_id):
    try:
        siparis = Siparis.query.get_or_404(siparis_id)

        if siparis.durum in ["teslim_edildi", "iptal"]:
            return jsonify({
                "hata": "Tamamlanmış sipariş düzenlenemez."
            }), 400

        detay = SiparisDetay.query.get_or_404(detay_id)

        if detay.siparis_id != siparis.id:
            return jsonify({"hata": "Sipariş kalemi bu siparişe ait değil."}), 400

        yeni_adet = int((request.json or {}).get("yeni_adet", 0))

        if yeni_adet < 0:
            return jsonify({"hata": "Adet negatif olamaz!"}), 400

        fark = detay.adet - yeni_adet

        if detay.urun:
            detay.urun.stok_adet += fark
            if detay.urun.stok_adet > 0:
                detay.urun.aktif = True

        if yeni_adet == 0:
            db.session.delete(detay)
        else:
            detay.adet = yeni_adet

        db.session.flush()

        siparis.toplam_tutar = sum(
            d.adet * float(d.birim_fiyat) for d in siparis.detaylar
        )

        db.session.commit()

        return jsonify({"mesaj": "Sipariş güncellendi."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/siparisler/<int:siparis_id>/durum", methods=["PUT"])
@role_required("market")
def siparis_durum_guncelle(siparis_id):
    try:
        siparis = Siparis.query.get_or_404(siparis_id)
        yeni_durum = (request.json or {}).get("durum")

        # Kasa panelinde sadece iki sonuç olabilir:
        # teslim_edildi = teslim edildi
        # iptal = teslim edilmedi / iptal
        izinli_durumlar = ["teslim_edildi", "iptal"]

        if yeni_durum not in izinli_durumlar:
            return jsonify({
                "hata": "Bu işlem için sadece 'teslim edildi' veya 'teslim edilmedi' seçilebilir."
            }), 400

        if siparis.durum in ["teslim_edildi", "iptal"]:
            return jsonify({
                "hata": "Tamamlanmış siparişin durumu tekrar değiştirilemez."
            }), 400

        if yeni_durum == "iptal":
            for detay in siparis.detaylar:
                if detay.urun:
                    detay.urun.stok_adet += detay.adet
                    if detay.urun.stok_adet > 0:
                        detay.urun.aktif = True

        siparis.durum = yeni_durum
        db.session.commit()

        socketio.emit("siparis_durumu_degisti", {
            "siparis_id": siparis.id,
            "yeni_durum": yeni_durum
        })

        return jsonify({
            "mesaj": "Sipariş durumu güncellendi.",
            "yeni_durum": yeni_durum
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500