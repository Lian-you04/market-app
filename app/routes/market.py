import os
import uuid
import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, request, jsonify, current_app

from app import db, socketio
from app.models import (
    Urun,
    Siparis,
    SiparisDetay,
    FavoriUrun,
    Market
)
from app.security import role_required


market_bp = Blueprint("market", __name__)

ISTANBUL_SAAT_DILIMI = ZoneInfo("Europe/Istanbul")


def istanbul_tarih_araligini_utc_yap(
    baslangic_tarihi,
    bitis_tarihi
):
    baslangic_istanbul = datetime.combine(
        baslangic_tarihi,
        time.min,
        tzinfo=ISTANBUL_SAAT_DILIMI
    )

    bitis_istanbul = datetime.combine(
        bitis_tarihi,
        time.min,
        tzinfo=ISTANBUL_SAAT_DILIMI
    )

    baslangic_utc = (
        baslangic_istanbul
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    bitis_utc = (
        bitis_istanbul
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    return baslangic_utc, bitis_utc

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

@market_bp.route("/dashboard-ozet", methods=["GET"])
@role_required("market")
def dashboard_ozet_getir():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        bugun_istanbul = datetime.now(
            ISTANBUL_SAAT_DILIMI
        ).date()

        yarin_istanbul = bugun_istanbul + timedelta(days=1)

        gun_baslangici_utc, gun_bitisi_utc = (
            istanbul_tarih_araligini_utc_yap(
                bugun_istanbul,
                yarin_istanbul
            )
        )

        bugunku_siparisler = Siparis.query.filter(
            Siparis.market_id == market_id,
            Siparis.olusturma_tarihi >= gun_baslangici_utc,
            Siparis.olusturma_tarihi < gun_bitisi_utc
        ).all()

        bugunku_siparis_sayisi = len(bugunku_siparisler)

        bekleyen_siparis_sayisi = sum(
            1
            for siparis in bugunku_siparisler
            if siparis.durum not in ["teslim_edildi", "iptal"]
        )

        tamamlanan_siparisler = [
            siparis
            for siparis in bugunku_siparisler
            if siparis.durum == "teslim_edildi"
        ]

        tamamlanan_siparis_sayisi = len(
            tamamlanan_siparisler
        )

        bugunku_ciro = sum(
            float(siparis.toplam_tutar)
            for siparis in tamamlanan_siparisler
        )

        return jsonify({
            "bugunku_siparis": bugunku_siparis_sayisi,
            "bekleyen_siparis": bekleyen_siparis_sayisi,
            "tamamlanan_siparis": tamamlanan_siparis_sayisi,
            "bugunku_ciro": round(bugunku_ciro, 2)
        }), 200

    except Exception as e:
        return jsonify({
            "hata": f"Dashboard bilgileri alınamadı: {str(e)}"
        }), 500

@market_bp.route("/dashboard-grafik", methods=["GET"])
@role_required("market")
def dashboard_grafik_getir():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        donem = request.args.get(
            "donem",
            "haftalik"
        ).strip().lower()

        bugun_istanbul = datetime.now(
            ISTANBUL_SAAT_DILIMI
        ).date()

        labels = []
        veriler = []

        if donem == "gunluk":
            donem_baslangic_tarihi = bugun_istanbul
            donem_bitis_tarihi = (
                bugun_istanbul + timedelta(days=1)
            )
            ciro_basligi = "Bugünkü Ciro"

            gun_baslangici_utc, gun_bitisi_utc = (
                istanbul_tarih_araligini_utc_yap(
                    donem_baslangic_tarihi,
                    donem_bitis_tarihi
                )
            )

            siparisler = Siparis.query.filter(
                Siparis.market_id == market_id,
                Siparis.olusturma_tarihi >= gun_baslangici_utc,
                Siparis.olusturma_tarihi < gun_bitisi_utc
            ).all()

            for saat in range(0, 24, 3):
                saat_bitisi = saat + 3
                adet = 0

                for siparis in siparisler:
                    siparis_utc = (
                        siparis.olusturma_tarihi
                        .replace(tzinfo=timezone.utc)
                    )

                    siparis_istanbul = siparis_utc.astimezone(
                        ISTANBUL_SAAT_DILIMI
                    )

                    if saat <= siparis_istanbul.hour < saat_bitisi:
                        adet += 1

                labels.append(
                    f"{saat:02d}:00–{saat_bitisi:02d}:00"
                )
                veriler.append(adet)

        elif donem == "haftalik":
            donem_baslangic_tarihi = (
                bugun_istanbul - timedelta(days=6)
            )
            donem_bitis_tarihi = (
                bugun_istanbul + timedelta(days=1)
            )
            ciro_basligi = "Haftalık Ciro"

            for gun_farki in range(6, -1, -1):
                tarih = (
                    bugun_istanbul
                    - timedelta(days=gun_farki)
                )

                sonraki_tarih = tarih + timedelta(days=1)

                baslangic_utc, bitis_utc = (
                    istanbul_tarih_araligini_utc_yap(
                        tarih,
                        sonraki_tarih
                    )
                )

                adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                labels.append(tarih.strftime("%d.%m"))
                veriler.append(adet)

        elif donem == "aylik":
            donem_baslangic_tarihi = (
                bugun_istanbul.replace(day=1)
            )
            donem_bitis_tarihi = (
                bugun_istanbul + timedelta(days=1)
            )
            ciro_basligi = "Aylık Ciro"

            hafta_numarasi = 1
            hafta_baslangici = donem_baslangic_tarihi

            while hafta_baslangici <= bugun_istanbul:
                hafta_bitisi = min(
                    hafta_baslangici + timedelta(days=7),
                    donem_bitis_tarihi
                )

                baslangic_utc, bitis_utc = (
                    istanbul_tarih_araligini_utc_yap(
                        hafta_baslangici,
                        hafta_bitisi
                    )
                )

                adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                labels.append(
                    f"{hafta_numarasi}. Hafta"
                )
                veriler.append(adet)

                hafta_numarasi += 1
                hafta_baslangici += timedelta(days=7)

        elif donem == "yillik":
            yil = bugun_istanbul.year

            donem_baslangic_tarihi = (
                bugun_istanbul.replace(
                    month=1,
                    day=1
                )
            )

            donem_bitis_tarihi = (
                bugun_istanbul.replace(
                    year=yil + 1,
                    month=1,
                    day=1
                )
            )
            ciro_basligi = "Yıllık Ciro"

            ay_isimleri = [
                "Oca",
                "Şub",
                "Mar",
                "Nis",
                "May",
                "Haz",
                "Tem",
                "Ağu",
                "Eyl",
                "Eki",
                "Kas",
                "Ara"
            ]

            for ay in range(1, 13):
                ay_baslangici = datetime(
                    yil,
                    ay,
                    1
                ).date()

                if ay == 12:
                    sonraki_ay_baslangici = datetime(
                        yil + 1,
                        1,
                        1
                    ).date()
                else:
                    sonraki_ay_baslangici = datetime(
                        yil,
                        ay + 1,
                        1
                    ).date()

                baslangic_utc, bitis_utc = (
                    istanbul_tarih_araligini_utc_yap(
                        ay_baslangici,
                        sonraki_ay_baslangici
                    )
                )

                adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                labels.append(ay_isimleri[ay - 1])
                veriler.append(adet)

        else:
            return jsonify({
                "hata": "Geçersiz grafik dönemi!"
            }), 400

        ciro_baslangici_utc, ciro_bitisi_utc = (
            istanbul_tarih_araligini_utc_yap(
                donem_baslangic_tarihi,
                donem_bitis_tarihi
            )
        )

        donem_cirosu = (
            db.session.query(
                db.func.coalesce(
                    db.func.sum(Siparis.toplam_tutar),
                    0
                )
            )
            .filter(
                Siparis.market_id == market_id,
                Siparis.durum == "teslim_edildi",
                Siparis.olusturma_tarihi >= ciro_baslangici_utc,
                Siparis.olusturma_tarihi < ciro_bitisi_utc
            )
            .scalar()
        )

        return jsonify({
            "donem": donem,
            "labels": labels,
            "veriler": veriler,
            "ciro": round(float(donem_cirosu or 0), 2),
            "ciro_basligi": ciro_basligi
        }), 200

    except Exception as e:
        return jsonify({
            "hata": f"Grafik bilgileri alınamadı: {str(e)}"
        }), 500

@market_bp.route("/dashboard-en-cok-satanlar", methods=["GET"])
@role_required("market")
def dashboard_en_cok_satanlar_getir():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        sonuclar = (
            db.session.query(
                Urun.id,
                Urun.ad,
                Urun.resim_url,
                db.func.sum(SiparisDetay.adet).label("toplam_adet")
            )
            .join(
                SiparisDetay,
                SiparisDetay.urun_id == Urun.id
            )
            .join(
                Siparis,
                Siparis.id == SiparisDetay.siparis_id
            )
            .filter(
                Urun.market_id == market_id,
                Siparis.market_id == market_id,
                Siparis.durum == "teslim_edildi"
            )
            .group_by(
                Urun.id,
                Urun.ad,
                Urun.resim_url
            )
            .order_by(
                db.func.sum(SiparisDetay.adet).desc(),
                Urun.id.asc()
            )
            .limit(5)
            .all()
        )

        return jsonify([
            {
                "urun_id": urun_id,
                "ad": ad,
                "resim_url": resim_url,
                "toplam_adet": int(toplam_adet or 0)
            }
            for urun_id, ad, resim_url, toplam_adet in sonuclar
        ]), 200

    except Exception as e:
        return jsonify({
            "hata": f"En çok satan ürünler alınamadı: {str(e)}"
        }), 500

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

            if not dosyalar or all(
                dosya.filename == ""
                for dosya in dosyalar
            ):
                tekli_dosya = request.files.get("resim")

                if (
                    tekli_dosya
                    and tekli_dosya.filename != ""
                ):
                    dosyalar = [tekli_dosya]

        else:
            form_verisi = (
                request.get_json(silent=True)
                or {}
            )

        market_id = int(
            form_verisi.get("market_id", 1)
        )

        if market_id <= 0:
            return jsonify({
                "hata": "Geçerli bir market seçilmelidir."
            }), 400

        market = Market.query.get(market_id)

        if not market:
            return jsonify({
                "hata": "Market bulunamadı."
            }), 404

        ad = str(
            form_verisi.get("ad", "")
        ).strip()

        fiyat_degeri = form_verisi.get("fiyat")

        if not ad:
            return jsonify({
                "hata": "Ürün adı zorunludur."
            }), 400

        if fiyat_degeri in (None, ""):
            return jsonify({
                "hata": "Ürün fiyatı zorunludur."
            }), 400

        fiyat = float(fiyat_degeri)

        stok_degeri = form_verisi.get(
            "stok_adet",
            0
        )

        if stok_degeri in (None, ""):
            stok_degeri = 0

        stok_adet = int(stok_degeri)

        if fiyat < 0:
            return jsonify({
                "hata": "Ürün fiyatı negatif olamaz."
            }), 400

        if stok_adet < 0:
            return jsonify({
                "hata": "Stok adedi negatif olamaz."
            }), 400

        kaydedilen_yollar = []

        if dosyalar:
            yukleme_klasoru = os.path.join(
                current_app.static_folder,
                "uploads"
            )

            os.makedirs(
                yukleme_klasoru,
                exist_ok=True
            )

            for dosya in dosyalar:
                if (
                    dosya
                    and dosya.filename != ""
                    and resim_uzantisi_gonderilebilir_mi(
                        dosya.filename
                    )
                ):
                    uzanti = (
                        dosya.filename
                        .rsplit(".", 1)[1]
                        .lower()
                    )

                    guvenli_isim = (
                        f"{uuid.uuid4().hex}.{uzanti}"
                    )

                    dosya.save(
                        os.path.join(
                            yukleme_klasoru,
                            guvenli_isim
                        )
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
            else (
                form_verisi.get("resim_url")
                or varsayilan_resim
            )
        )

        kategori = str(
            form_verisi.get(
                "kategori",
                "meyve_sebze"
            )
        ).strip()

        if not kategori:
            kategori = "meyve_sebze"

        urun = Urun(
            market_id=market_id,
            ad=ad,
            aciklama=str(
                form_verisi.get(
                    "aciklama",
                    ""
                )
            ).strip(),
            fiyat=fiyat,
            stok_adet=stok_adet,
            kategori=kategori,
            resim_url=resim_yolu,
            aktif=stok_adet > 0
        )

        db.session.add(urun)
        db.session.commit()

        socketio.emit(
            "urun_degisikligi",
            {
                "market_id": urun.market_id,
                "urun_id": urun.id,
                "islem": "eklendi"
            }
        )
        
        return jsonify({
            "id": urun.id,
            "ad": urun.ad,
            "fiyat": float(urun.fiyat),
            "stok_adet": urun.stok_adet,
            "aktif": urun.aktif,
            "resim_url": resim_yolu,
            "mesaj": "Ürün başarıyla eklendi."
        }), 201

    except (TypeError, ValueError):
        db.session.rollback()

        return jsonify({
            "hata": (
                "Fiyat ve stok alanları "
                "geçerli bir sayı olmalıdır."
            )
        }), 400

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "hata": f"Ürün eklenemedi: {str(e)}"
        }), 500

@market_bp.route(
    "/urunler/<int:urun_id>",
    methods=["PUT"]
)
@role_required("market")
def urun_guncelle(urun_id):
    yuklenen_dosya_yollari = []

    try:
        urun = Urun.query.get_or_404(urun_id)

        orijinal_resim_yollari = [
            resim.strip()
            for resim in (
                urun.resim_url or ""
            ).split(",")
            if resim.strip()
        ]

        korunacak_resim_yollari = list(
            orijinal_resim_yollari
        )

        resim_listesi_gonderildi = False

        multipart_mi = (
            request.content_type
            and "multipart/form-data"
            in request.content_type
        )

        if multipart_mi:
            data = request.form.to_dict()

            dosyalar = [
                dosya
                for dosya in request.files.getlist(
                    "resimler"
                )
                if dosya and dosya.filename
            ]

            ham_mevcut_resimler = data.get(
                "mevcut_resimler"
            )

            if ham_mevcut_resimler is not None:
                resim_listesi_gonderildi = True

                try:
                    gelen_resim_listesi = json.loads(
                        ham_mevcut_resimler or "[]"
                    )
                except (TypeError, ValueError):
                    return jsonify({
                        "hata": (
                            "Mevcut görsel listesi "
                            "geçerli değil."
                        )
                    }), 400

                if not isinstance(
                    gelen_resim_listesi,
                    list
                ):
                    return jsonify({
                        "hata": (
                            "Mevcut görsel listesi "
                            "dizi olmalıdır."
                        )
                    }), 400

                korunacak_resim_yollari = []

                for resim_yolu in (
                    gelen_resim_listesi
                ):
                    if not isinstance(
                        resim_yolu,
                        str
                    ):
                        continue

                    temiz_yol = resim_yolu.strip()

                    if (
                        temiz_yol
                        and temiz_yol
                        in orijinal_resim_yollari
                        and temiz_yol
                        not in korunacak_resim_yollari
                    ):
                        korunacak_resim_yollari.append(
                            temiz_yol
                        )

        else:
            data = request.get_json(
                silent=True
            )
            dosyalar = []

        if not isinstance(data, dict):
            return jsonify({
                "hata": (
                    "Geçerli bir JSON veya form verisi "
                    "gönderilmelidir."
                )
            }), 400

        if any(
            not resim_uzantisi_gonderilebilir_mi(
                dosya.filename
            )
            for dosya in dosyalar
        ):
            return jsonify({
                "hata": (
                    "Sadece PNG, JPG, JPEG ve WEBP "
                    "formatları yüklenebilir."
                )
            }), 400

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
            ham_aktif = data["aktif"]

            if isinstance(ham_aktif, bool):
                yeni_aktif = ham_aktif

            elif isinstance(ham_aktif, str):
                aktif_metni = (
                    ham_aktif.strip().lower()
                )

                if aktif_metni == "true":
                    yeni_aktif = True

                elif aktif_metni == "false":
                    yeni_aktif = False

                else:
                    return jsonify({
                        "hata": (
                            "Aktif alanı true veya false "
                            "olmalıdır."
                        )
                    }), 400

            else:
                return jsonify({
                    "hata": (
                        "Aktif alanı true veya false "
                        "olmalıdır."
                    )
                }), 400

            if (
                yeni_aktif
                and urun.stok_adet <= 0
            ):
                return jsonify({
                    "hata": (
                        "Stok adedi 0 olan ürün "
                        "satışa açılamaz."
                    )
                }), 400

            urun.aktif = yeni_aktif

        if "ad" in data:
            yeni_ad = str(data["ad"]).strip()

            if not yeni_ad:
                return jsonify({
                    "hata": "Ürün adı boş olamaz."
                }), 400

            urun.ad = yeni_ad

        if "aciklama" in data:
            urun.aciklama = (
                ""
                if data["aciklama"] is None
                else str(data["aciklama"]).strip()
            )

        if "kategori" in data:
            yeni_kategori = str(
                data["kategori"]
            ).strip()

            if not yeni_kategori:
                return jsonify({
                    "hata": "Kategori boş olamaz."
                }), 400

            urun.kategori = yeni_kategori

        yeni_resim_yollari = []

        if dosyalar:
            yukleme_klasoru = os.path.join(
                current_app.static_folder,
                "uploads"
            )

            os.makedirs(
                yukleme_klasoru,
                exist_ok=True
            )

            for dosya in dosyalar:
                uzanti = (
                    dosya.filename
                    .rsplit(".", 1)[1]
                    .lower()
                )

                guvenli_isim = (
                    f"{uuid.uuid4().hex}.{uzanti}"
                )

                dosya_sistem_yolu = os.path.join(
                    yukleme_klasoru,
                    guvenli_isim
                )

                dosya.save(
                    dosya_sistem_yolu
                )

                yuklenen_dosya_yollari.append(
                    dosya_sistem_yolu
                )

                yeni_resim_yollari.append(
                    f"/static/uploads/{guvenli_isim}"
                )

        if (
            resim_listesi_gonderildi
            or yeni_resim_yollari
        ):
            urun.resim_url = ",".join(
                korunacak_resim_yollari
                + yeni_resim_yollari
            )

        db.session.commit()

        socketio.emit(
            "urun_degisikligi",
            {
                "market_id": urun.market_id,
                "urun_id": urun.id,
                "islem": "guncellendi"
            }
        )

        return jsonify({
            "mesaj": "Ürün güncellendi.",
            "id": urun.id,
            "ad": urun.ad,
            "fiyat": float(urun.fiyat),
            "stok_adet": urun.stok_adet,
            "kategori": urun.kategori,
            "resim_url": urun.resim_url,
            "aktif": urun.aktif
        }), 200

    except (TypeError, ValueError):
        db.session.rollback()

        for dosya_yolu in yuklenen_dosya_yollari:
            if os.path.exists(dosya_yolu):
                os.remove(dosya_yolu)

        return jsonify({
            "hata": (
                "Fiyat ve stok alanları "
                "geçerli bir sayı olmalıdır."
            )
        }), 400

    except Exception as e:
        db.session.rollback()

        for dosya_yolu in yuklenen_dosya_yollari:
            if os.path.exists(dosya_yolu):
                os.remove(dosya_yolu)

        return jsonify({
            "hata": str(e)
        }), 500
        
@market_bp.route(
    "/urunler/<int:urun_id>",
    methods=["DELETE"]
)
@role_required("market")
def urun_sil(urun_id):
    try:
        market_id = request.args.get(
            "market_id",
            1,
            type=int
        )

        urun = Urun.query.filter_by(
            id=urun_id,
            market_id=market_id
        ).first()

        if not urun:
            return jsonify({
                "hata": "Ürün bulunamadı."
            }), 404

        urun_market_id = urun.market_id

        siparis_detayi_var_mi = (
            SiparisDetay.query
            .filter_by(urun_id=urun.id)
            .first()
        )

        if siparis_detayi_var_mi:
            urun.aktif = False
            urun.stok_adet = 0

            db.session.commit()

            socketio.emit(
                "urun_degisikligi",
                {
                    "market_id": urun_market_id,
                    "urun_id": urun.id,
                    "islem": "silindi"
                }
            )

            return jsonify({
                "mesaj": (
                    "Ürün geçmiş siparişlerde kullanıldığı "
                    "için satıştan kaldırıldı."
                ),
                "silindi": False,
                "aktif": False,
                "urun_id": urun.id
            }), 200

        FavoriUrun.query.filter_by(
            urun_id=urun.id
        ).delete(
            synchronize_session=False
        )

        db.session.delete(urun)
        db.session.commit()

        socketio.emit(
            "urun_degisikligi",
            {
                "market_id": urun.market_id,
                "urun_id": urun.id,
                "islem": "silindi"
            }
        )

        return jsonify({
            "mesaj": "Ürün başarıyla silindi.",
            "silindi": True,
            "urun_id": urun_id
        }), 200

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "hata": f"Ürün silinemedi: {str(e)}"
        }), 500

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
        gunluk_sira_haritalari = {}

        for siparis in siparisler:
            siparis_zamani_utc = (
                siparis.olusturma_tarihi
                .replace(tzinfo=timezone.utc)
            )

            siparis_zamani_istanbul = (
                siparis_zamani_utc.astimezone(
                    ISTANBUL_SAAT_DILIMI
                )
            )

            siparis_gunu = siparis_zamani_istanbul.date()

            if siparis_gunu not in gunluk_sira_haritalari:
                sonraki_gun = (
                    siparis_gunu + timedelta(days=1)
                )

                gun_baslangici_utc, gun_bitisi_utc = (
                    istanbul_tarih_araligini_utc_yap(
                        siparis_gunu,
                        sonraki_gun
                    )
                )

                gunun_siparis_idleri = (
                    db.session.query(Siparis.id)
                    .filter(
                        Siparis.market_id == market_id,
                        Siparis.olusturma_tarihi
                        >= gun_baslangici_utc,
                        Siparis.olusturma_tarihi
                        < gun_bitisi_utc
                    )
                    .order_by(
                        Siparis.olusturma_tarihi.asc(),
                        Siparis.id.asc()
                    )
                    .all()
                )

                gunluk_sira_haritalari[siparis_gunu] = {
                    siparis_id: sira_no
                    for sira_no, (siparis_id,) in enumerate(
                        gunun_siparis_idleri,
                        start=1
                    )
                }

            gunluk_sira_no = (
                gunluk_sira_haritalari[siparis_gunu]
                .get(siparis.id, 0)
            )

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
                "gunluk_sira_no": gunluk_sira_no,
                "siparis_tarihi": siparis_gunu.isoformat(),
                "musteri_id": siparis.musteri_id,
                "musteri_ad": (
                    siparis.musteri.ad_soyad
                    if siparis.musteri
                    else "Misafir Müşteri"
                ),
                "musteri_adres": (
                    siparis.musteri.adres
                    if siparis.musteri
                    else ""
                ),
                "musteri_tel": (
                    siparis.musteri.telefon
                    if siparis.musteri
                    else ""
                ),
                "durum": siparis.durum,
                "odeme_yontemi": siparis.odeme_yontemi,
                "teslimat_yontemi": siparis.teslimat_yontemi,
                "olusturma_tarihi": (
                    siparis_zamani_istanbul.isoformat()
                ),
                "olusturma_saati": (
                    siparis_zamani_istanbul.strftime("%H:%M")
                ),
                "siparis_notu": siparis.siparis_notu,
                "toplam_tutar": float(siparis.toplam_tutar),
                "detaylar": kalemler
            })

        return jsonify(sonuc), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500

@market_bp.route(
    "/siparisler/<int:siparis_id>/durum",
    methods=["PUT"]
)
@role_required("market")
def siparis_durum_guncelle(siparis_id):
    try:
        siparis = Siparis.query.get_or_404(siparis_id)
        market_id = siparis.market_id
        stok_degisikligi_urun_idleri = set()    
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
                    stok_degisikligi_urun_idleri.add(detay.urun.id)

        siparis.durum = yeni_durum

        db.session.commit()

        socketio.emit("siparis_durumu_degisti", {
            "siparis_id": siparis.id,
            "market_id": market_id,
            "yeni_durum": yeni_durum
        })

        for urun_id in stok_degisikligi_urun_idleri:
            socketio.emit(
                "urun_degisikligi",
                {
                    "market_id": market_id,
                    "urun_id": urun_id,
                    "islem": "stok_guncellendi"
                }
            )

        return jsonify({
            "mesaj": "Sipariş durumu güncellendi.",
            "yeni_durum": yeni_durum
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500
    
    