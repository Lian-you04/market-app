import os
import uuid

from flask import Blueprint, request, jsonify, current_app

from app import db, socketio
from app.models import Urun, Siparis, SiparisDetay, Market
from app.security import role_required


market_bp = Blueprint("market", __name__)

IZIN_VERILEN_UZANTILAR = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def resim_uzantisi_gonderilebilir_mi(dosya_adi):
    return (
        "." in dosya_adi
        and dosya_adi.rsplit(".", 1)[1].lower() in IZIN_VERILEN_UZANTILAR
    )


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
            "min_siparis_tutari": float(market.min_siparis_tutari)
        }), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/durum", methods=["PUT"])
@role_required("market")
def market_durum_guncelle():
    try:
        data = request.get_json(silent=True) or {}
        market_id = data.get("market_id", 1)

        market = Market.query.get_or_404(market_id)

        if "aktif" in data:
            market.aktif = bool(data["aktif"])

        if "min_siparis_tutari" in data:
            yeni_limit = float(data["min_siparis_tutari"])

            if yeni_limit < 0:
                return jsonify({
                    "hata": "Minimum sipariş tutarı negatif olamaz."
                }), 400

            market.min_siparis_tutari = yeni_limit

        db.session.commit()

        socketio.emit("market_durumu_degisti", {
            "market_id": market.id,
            "aktif": market.aktif,
            "min_siparis_tutari": float(market.min_siparis_tutari)
        })

        return jsonify({
            "mesaj": "Market ayarları güncellendi.",
            "aktif": market.aktif,
            "min_siparis_tutari": float(market.min_siparis_tutari)
        }), 200

    except (TypeError, ValueError):
        db.session.rollback()

        return jsonify({
            "hata": "Minimum sipariş tutarı geçerli bir sayı olmalıdır."
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/urunler", methods=["POST"])
@role_required("market")
def urun_ekle():
    try:
        dosyalar = []

        if (
            request.content_type
            and "multipart/form-data" in request.content_type
        ):
            form_verisi = request.form
            dosyalar = request.files.getlist("resimler")

            if not dosyalar or all(d.filename == "" for d in dosyalar):
                tekli_dosya = request.files.get("resim")

                if tekli_dosya and tekli_dosya.filename != "":
                    dosyalar = [tekli_dosya]

        else:
            form_verisi = request.get_json(silent=True) or {}

        market_id = form_verisi.get("market_id", 1)
        ad = form_verisi.get("ad", "").strip()
        fiyat = form_verisi.get("fiyat")

        if not ad or fiyat is None:
            return jsonify({
                "hata": "Ürün Adı ve Fiyat alanları zorunludur!"
            }), 400

        kaydedilen_yollar = []

        if dosyalar:
            yukleme_klasoru = os.path.join(
                current_app.static_folder,
                "uploads"
            )

            os.makedirs(yukleme_klasoru, exist_ok=True)

            for dosya in dosyalar:
                if (
                    dosya
                    and dosya.filename != ""
                    and resim_uzantisi_gonderilebilir_mi(dosya.filename)
                ):
                    uzanti = dosya.filename.rsplit(".", 1)[1].lower()
                    guvenli_isim = f"{uuid.uuid4().hex}.{uzanti}"

                    dosya.save(
                        os.path.join(yukleme_klasoru, guvenli_isim)
                    )

                    kaydedilen_yollar.append(
                        f"/static/uploads/{guvenli_isim}"
                    )

        varsayilan_resim = (
            "https://images.unsplash.com/"
            "photo-1583258292688-d0213dc5a3a8"
            "?auto=format&fit=crop&w=300&q=80"
        )

        resim_yolu = (
            ",".join(kaydedilen_yollar)
            if kaydedilen_yollar
            else form_verisi.get("resim_url", varsayilan_resim)
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

    except (TypeError, ValueError):
        db.session.rollback()

        return jsonify({
            "hata": "Fiyat ve stok alanları geçerli bir sayı olmalıdır."
        }), 400

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "hata": f"Ürün eklenemedi: {str(e)}"
        }), 500


@market_bp.route("/urunler/<int:urun_id>", methods=["PUT"])
@role_required("market")
def urun_guncelle(urun_id):
    try:
        urun = Urun.query.get_or_404(urun_id)
        data = request.get_json(silent=True) or {}

        if "fiyat" in data:
            yeni_fiyat = float(data["fiyat"])

            if yeni_fiyat < 0:
                return jsonify({
                    "hata": "Ürün fiyatı negatif olamaz."
                }), 400

            urun.fiyat = yeni_fiyat

        if "stok_adet" in data:
            yeni_stok = int(data["stok_adet"])

            if yeni_stok < 0:
                return jsonify({
                    "hata": "Stok adedi negatif olamaz."
                }), 400

            urun.stok_adet = yeni_stok
            urun.aktif = yeni_stok > 0

        if "aktif" in data:
            urun.aktif = bool(data["aktif"])

        if "ad" in data:
            yeni_ad = str(data["ad"]).strip()

            if not yeni_ad:
                return jsonify({
                    "hata": "Ürün adı boş olamaz."
                }), 400

            urun.ad = yeni_ad

        if "aciklama" in data:
            urun.aciklama = str(data["aciklama"]).strip()

        if "kategori" in data:
            urun.kategori = str(data["kategori"]).strip()

        db.session.commit()

        return jsonify({
            "mesaj": "Ürün güncellendi",
            "stok": urun.stok_adet,
            "aktif": urun.aktif
        }), 200

    except (TypeError, ValueError):
        db.session.rollback()

        return jsonify({
            "hata": "Fiyat ve stok alanları geçerli bir sayı olmalıdır."
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/urunler", methods=["GET"])
@role_required("market")
def urunler_listele():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        urunler = Urun.query.filter_by(
            market_id=market_id
        ).order_by(
            Urun.id.desc()
        ).all()

        return jsonify([
            {
                "id": urun.id,
                "ad": urun.ad,
                "aciklama": urun.aciklama,
                "fiyat": float(urun.fiyat),
                "stok_adet": urun.stok_adet,
                "kategori": urun.kategori,
                "resim_url": urun.resim_url,
                "aktif": urun.aktif
            }
            for urun in urunler
        ]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/siparisler", methods=["GET"])
@role_required("market")
def siparisler_listele():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        siparisler = Siparis.query.filter(
            Siparis.market_id == market_id,
            Siparis.durum.notin_(["teslim_edildi", "iptal"])
        ).order_by(
            Siparis.olusturma_tarihi.desc()
        ).all()

        sonuc = []

        for siparis in siparisler:
            kalemler = [
                {
                    "detay_id": detay.id,
                    "ad": (
                        detay.urun.ad
                        if detay.urun
                        else "Silinmiş Ürün"
                    ),
                    "adet": detay.adet,
                    "birim_fiyat": float(detay.birim_fiyat),
                    "satir_toplam": (
                        float(detay.birim_fiyat) * detay.adet
                    )
                }
                for detay in siparis.detaylar
            ]

            sonuc.append({
                "id": siparis.id,
                "musteri_id": siparis.musteri_id,
                "musteri_ad": (
                    siparis.musteri.ad_soyad
                    if siparis.musteri
                    else "Misafir Müşteri"
                ),
                "musteri_tel": (
                    siparis.musteri.telefon
                    if siparis.musteri
                    else ""
                ),
                "durum": siparis.durum,
                "odeme_yontemi": siparis.odeme_yontemi,
                "teslimat_yontemi": siparis.teslimat_yontemi,
                "siparis_notu": siparis.siparis_notu,
                "toplam_tutar": float(siparis.toplam_tutar),
                "detaylar": kalemler
            })

        return jsonify(sonuc), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500
    
@market_bp.route(
    "/siparisler/<int:siparis_id>/detay/<int:detay_id>",
    methods=["PUT"]
)
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
            return jsonify({
                "hata": "Sipariş kalemi bu siparişe ait değil."
            }), 400

        data = request.get_json(silent=True) or {}
        yeni_adet = int(data.get("yeni_adet", 0))

        if yeni_adet < 0:
            return jsonify({
                "hata": "Adet negatif olamaz."
            }), 400

        eski_adet = detay.adet
        fark = eski_adet - yeni_adet

        if detay.urun:
            detay.urun.stok_adet += fark
            detay.urun.aktif = detay.urun.stok_adet > 0

        if yeni_adet == 0:
            db.session.delete(detay)
        else:
            detay.adet = yeni_adet

        db.session.flush()

        kalan_detaylar = SiparisDetay.query.filter_by(
            siparis_id=siparis.id
        ).all()

        siparis.toplam_tutar = sum(
            detay.adet * float(detay.birim_fiyat)
            for detay in kalan_detaylar
        )

        db.session.commit()

        return jsonify({
            "mesaj": "Sipariş kalemi güncellendi.",
            "toplam_tutar": float(siparis.toplam_tutar)
        }), 200

    except (TypeError, ValueError):
        db.session.rollback()

        return jsonify({
            "hata": "Yeni adet geçerli bir tam sayı olmalıdır."
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@market_bp.route(
    "/siparisler/<int:siparis_id>/durum",
    methods=["PUT"]
)
@role_required("market")
def siparis_durum_guncelle(siparis_id):
    try:
        siparis = Siparis.query.get_or_404(siparis_id)
        data = request.get_json(silent=True) or {}
        yeni_durum = data.get("durum")

        izinli_durumlar = {
            "teslim_edildi",
            "iptal"
        }

        if yeni_durum not in izinli_durumlar:
            return jsonify({
                "hata": (
                    "Sipariş yalnızca teslim edildi "
                    "veya iptal edildi olarak işaretlenebilir."
                )
            }), 400

        if siparis.durum in ["teslim_edildi", "iptal"]:
            return jsonify({
                "hata": (
                    "Tamamlanmış siparişin durumu "
                    "tekrar değiştirilemez."
                )
            }), 400

        if yeni_durum == "iptal":
            for detay in siparis.detaylar:
                if detay.urun:
                    detay.urun.stok_adet += detay.adet
                    detay.urun.aktif = detay.urun.stok_adet > 0

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
    
    