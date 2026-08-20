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
    Market,
    Musteri,
    Yorum
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
        market_id = request.args.get(
            "market_id",
            1,
            type=int
        )

        market = Market.query.get_or_404(market_id)

        return jsonify({
            "id": market.id,
            "ad": market.ad,
            "telefon": market.telefon,
            "adres": market.adres,
            "aktif": market.aktif,
            "min_siparis_tutari": float(
                market.min_siparis_tutari
            )
        }), 200

    except Exception as e:
        return jsonify({
            "hata": str(e)
        }), 500


@market_bp.route("/durum", methods=["PUT"])
@role_required("market")
def market_durum_guncelle():
    try:
        data = request.get_json(
            silent=True
        )

        if not isinstance(data, dict):
            return jsonify({
                "hata": (
                    "Geçerli bir JSON verisi "
                    "gönderilmelidir."
                )
            }), 400

        market_id = int(
            data.get("market_id", 1)
        )

        market = Market.query.get_or_404(
            market_id
        )

        yeni_ad = market.ad
        yeni_telefon = market.telefon
        yeni_adres = market.adres
        yeni_aktif = market.aktif
        yeni_minimum_tutar = (
            float(market.min_siparis_tutari)
        )

        if "ad" in data:
            yeni_ad = str(
                data["ad"]
            ).strip()

            if not yeni_ad:
                return jsonify({
                    "hata": (
                        "Market adı boş olamaz."
                    )
                }), 400

        if "telefon" in data:
            yeni_telefon = str(
                data["telefon"]
            ).strip()

            if not yeni_telefon:
                return jsonify({
                    "hata": (
                        "Telefon alanı boş olamaz."
                    )
                }), 400

        if "adres" in data:
            yeni_adres = str(
                data["adres"]
            ).strip()

            if not yeni_adres:
                return jsonify({
                    "hata": (
                        "Adres alanı boş olamaz."
                    )
                }), 400

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
                            "Aktif alanı true veya "
                            "false olmalıdır."
                        )
                    }), 400

            else:
                return jsonify({
                    "hata": (
                        "Aktif alanı true veya "
                        "false olmalıdır."
                    )
                }), 400

        if "min_siparis_tutari" in data:
            yeni_minimum_tutar = float(
                data["min_siparis_tutari"]
            )

            if yeni_minimum_tutar < 0:
                return jsonify({
                    "hata": (
                        "Minimum sipariş tutarı "
                        "negatif olamaz."
                    )
                }), 400

        market.ad = yeni_ad
        market.telefon = yeni_telefon
        market.adres = yeni_adres
        market.aktif = yeni_aktif
        market.min_siparis_tutari = (
            yeni_minimum_tutar
        )

        db.session.commit()

        socketio.emit(
            "market_durumu_degisti",
            {
                "market_id": market.id,
                "ad": market.ad,
                "telefon": market.telefon,
                "adres": market.adres,
                "aktif": market.aktif,
                "min_siparis_tutari": float(
                    market.min_siparis_tutari
                )
            }
        )

        return jsonify({
            "mesaj": (
                "Market ayarları güncellendi."
            ),
            "id": market.id,
            "ad": market.ad,
            "telefon": market.telefon,
            "adres": market.adres,
            "aktif": market.aktif,
            "min_siparis_tutari": float(
                market.min_siparis_tutari
            )
        }), 200

    except (TypeError, ValueError):
        db.session.rollback()

        return jsonify({
            "hata": (
                "Market ayarlarında geçersiz "
                "bir veri bulundu."
            )
        }), 400

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "hata": str(e)
        }), 500

@market_bp.route(
    "/dashboard-ozet",
    methods=["GET"]
)
@role_required("market")
def dashboard_ozet_getir():
    try:
        market_id = request.args.get(
            "market_id",
            1,
            type=int
        )

        donem = request.args.get(
            "donem",
            "gunluk"
        ).lower()

        izin_verilen_donemler = {
            "gunluk",
            "haftalik",
            "aylik",
            "yillik"
        }

        if donem not in izin_verilen_donemler:
            return jsonify({
                "hata": "Geçersiz dönem bilgisi."
            }), 400

        bugun_istanbul = datetime.now(
            ISTANBUL_SAAT_DILIMI
        ).date()

        if donem == "gunluk":
            donem_baslangici = bugun_istanbul
            donem_bitisi = (
                bugun_istanbul
                + timedelta(days=1)
            )

            siparis_basligi = (
                "Bugünkü Sipariş"
            )
            ciro_basligi = "Bugünkü Ciro"

        elif donem == "haftalik":
            donem_baslangici = (
                bugun_istanbul
                - timedelta(
                    days=bugun_istanbul.weekday()
                )
            )

            donem_bitisi = (
                donem_baslangici
                + timedelta(days=7)
            )

            siparis_basligi = (
                "Haftalık Sipariş"
            )
            ciro_basligi = "Haftalık Ciro"

        elif donem == "aylik":
            donem_baslangici = (
                bugun_istanbul.replace(day=1)
            )

            if donem_baslangici.month == 12:
                donem_bitisi = (
                    donem_baslangici.replace(
                        year=donem_baslangici.year + 1,
                        month=1
                    )
                )
            else:
                donem_bitisi = (
                    donem_baslangici.replace(
                        month=donem_baslangici.month + 1
                    )
                )

            siparis_basligi = (
                "Aylık Sipariş"
            )
            ciro_basligi = "Aylık Ciro"

        else:
            donem_baslangici = (
                bugun_istanbul.replace(
                    month=1,
                    day=1
                )
            )

            donem_bitisi = (
                donem_baslangici.replace(
                    year=donem_baslangici.year + 1
                )
            )

            siparis_basligi = (
                "Yıllık Sipariş"
            )
            ciro_basligi = "Yıllık Ciro"

        baslangic_utc, bitis_utc = (
            istanbul_tarih_araligini_utc_yap(
                donem_baslangici,
                donem_bitisi
            )
        )

        siparisler = Siparis.query.filter(
            Siparis.market_id == market_id,
            Siparis.olusturma_tarihi >= baslangic_utc,
            Siparis.olusturma_tarihi < bitis_utc
        ).all()

        tamamlanan_siparisler = [
            siparis
            for siparis in siparisler
            if siparis.durum == "teslim_edildi"
        ]

        iptal_edilen_siparisler = [
            siparis
            for siparis in siparisler
            if siparis.durum == "iptal"
        ]

        bekleyen_siparisler = [
            siparis
            for siparis in siparisler
            if siparis.durum not in [
                "teslim_edildi",
                "iptal"
            ]
        ]

        ciro = sum(
            float(siparis.toplam_tutar)
            for siparis in tamamlanan_siparisler
        )

        return jsonify({
            "donem": donem,
            "donem_baslangici": (
                donem_baslangici.isoformat()
            ),
            "donem_bitisi": (
                donem_bitisi.isoformat()
            ),
            "siparis_basligi": siparis_basligi,
            "ciro_basligi": ciro_basligi,
            "donem_siparis": len(siparisler),
            "tamamlanan_siparis": len(
                tamamlanan_siparisler
            ),
            "iptal_edilen_siparis": len(
                iptal_edilen_siparisler
            ),
            "bekleyen_siparis": len(
                bekleyen_siparisler
            ),
            "ciro": round(ciro, 2)
        }), 200

    except Exception as e:
        return jsonify({
            "hata": (
                "Dashboard bilgileri alınamadı: "
                f"{str(e)}"
            )
        }), 500

@market_bp.route("/dashboard-grafik", methods=["GET"])
@role_required("market")
def dashboard_grafik_getir():
    try:
        market_id = request.args.get(
            "market_id",
            1,
            type=int
        )

        donem = request.args.get(
            "donem",
            "haftalik"
        ).strip().lower()

        bugun_istanbul = datetime.now(
            ISTANBUL_SAAT_DILIMI
        ).date()

        labels = []
        tamamlanan_veriler = []
        iptal_veriler = []

        if donem == "gunluk":
            donem_baslangic_tarihi = (
                bugun_istanbul
            )

            donem_bitis_tarihi = (
                bugun_istanbul
                + timedelta(days=1)
            )

            ciro_basligi = "Bugünkü Ciro"

            baslangic_utc, bitis_utc = (
                istanbul_tarih_araligini_utc_yap(
                    donem_baslangic_tarihi,
                    donem_bitis_tarihi
                )
            )

            siparisler = Siparis.query.filter(
                Siparis.market_id == market_id,
                Siparis.olusturma_tarihi >= baslangic_utc,
                Siparis.olusturma_tarihi < bitis_utc
            ).all()

            for saat in range(0, 24, 3):
                saat_bitisi = saat + 3
                tamamlanan_adet = 0
                iptal_adet = 0

                for siparis in siparisler:
                    siparis_utc = (
                        siparis.olusturma_tarihi
                        .replace(tzinfo=timezone.utc)
                    )

                    siparis_istanbul = (
                        siparis_utc.astimezone(
                            ISTANBUL_SAAT_DILIMI
                        )
                    )

                    if not (
                        saat
                        <= siparis_istanbul.hour
                        < saat_bitisi
                    ):
                        continue

                    if siparis.durum == "teslim_edildi":
                        tamamlanan_adet += 1

                    elif siparis.durum == "iptal":
                        iptal_adet += 1

                labels.append(
                    f"{saat:02d}:00–{saat_bitisi:02d}:00"
                )

                tamamlanan_veriler.append(
                    tamamlanan_adet
                )

                iptal_veriler.append(
                    iptal_adet
                )

        elif donem == "haftalik":
            donem_baslangic_tarihi = (
                bugun_istanbul
                - timedelta(days=6)
            )

            donem_bitis_tarihi = (
                bugun_istanbul
                + timedelta(days=1)
            )

            ciro_basligi = "Haftalık Ciro"

            for gun_farki in range(6, -1, -1):
                tarih = (
                    bugun_istanbul
                    - timedelta(days=gun_farki)
                )

                sonraki_tarih = (
                    tarih + timedelta(days=1)
                )

                baslangic_utc, bitis_utc = (
                    istanbul_tarih_araligini_utc_yap(
                        tarih,
                        sonraki_tarih
                    )
                )

                tamamlanan_adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.durum == "teslim_edildi",
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                iptal_adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.durum == "iptal",
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                labels.append(
                    tarih.strftime("%d.%m")
                )

                tamamlanan_veriler.append(
                    tamamlanan_adet
                )

                iptal_veriler.append(
                    iptal_adet
                )

        elif donem == "aylik":
            donem_baslangic_tarihi = (
                bugun_istanbul.replace(day=1)
            )

            donem_bitis_tarihi = (
                bugun_istanbul
                + timedelta(days=1)
            )

            ciro_basligi = "Aylık Ciro"

            hafta_numarasi = 1
            hafta_baslangici = (
                donem_baslangic_tarihi
            )

            while (
                hafta_baslangici
                <= bugun_istanbul
            ):
                hafta_bitisi = min(
                    hafta_baslangici
                    + timedelta(days=7),
                    donem_bitis_tarihi
                )

                baslangic_utc, bitis_utc = (
                    istanbul_tarih_araligini_utc_yap(
                        hafta_baslangici,
                        hafta_bitisi
                    )
                )

                tamamlanan_adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.durum == "teslim_edildi",
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                iptal_adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.durum == "iptal",
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                labels.append(
                    f"{hafta_numarasi}. Hafta"
                )

                tamamlanan_veriler.append(
                    tamamlanan_adet
                )

                iptal_veriler.append(
                    iptal_adet
                )

                hafta_numarasi += 1
                hafta_baslangici += (
                    timedelta(days=7)
                )

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

                tamamlanan_adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.durum == "teslim_edildi",
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                iptal_adet = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.durum == "iptal",
                    Siparis.olusturma_tarihi >= baslangic_utc,
                    Siparis.olusturma_tarihi < bitis_utc
                ).count()

                labels.append(
                    ay_isimleri[ay - 1]
                )

                tamamlanan_veriler.append(
                    tamamlanan_adet
                )

                iptal_veriler.append(
                    iptal_adet
                )

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
                    db.func.sum(
                        Siparis.toplam_tutar
                    ),
                    0
                )
            )
            .filter(
                Siparis.market_id == market_id,
                Siparis.durum == "teslim_edildi",
                Siparis.olusturma_tarihi
                >= ciro_baslangici_utc,
                Siparis.olusturma_tarihi
                < ciro_bitisi_utc
            )
            .scalar()
        )

        birlesik_veriler = [
            tamamlanan + iptal
            for tamamlanan, iptal in zip(
                tamamlanan_veriler,
                iptal_veriler
            )
        ]

        return jsonify({
            "donem": donem,
            "labels": labels,

            "veriler": birlesik_veriler,

            "tamamlanan_veriler": (
                tamamlanan_veriler
            ),

            "iptal_veriler": (
                iptal_veriler
            ),

            "tamamlanan_toplam": sum(
                tamamlanan_veriler
            ),

            "iptal_edilen_toplam": sum(
                iptal_veriler
            ),

            "ciro": round(
                float(donem_cirosu or 0),
                2
            ),

            "ciro_basligi": ciro_basligi
        }), 200

    except Exception as e:
        return jsonify({
            "hata": (
                "Grafik bilgileri alınamadı: "
                f"{str(e)}"
            )
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


@market_bp.route(
    "/siparisler",
    methods=["GET"]
)
@role_required("market")
def siparisler_listele():
    try:
        market_id = request.args.get(
            "market_id",
            1,
            type=int
        )

        gorunum = request.args.get(
            "gorunum",
            "aktif"
        ).strip().lower()

        if gorunum not in [
            "aktif",
            "gecmis"
        ]:
            return jsonify({
                "hata": (
                    "Geçersiz sipariş görünümü."
                )
            }), 400

        siparis_sorgusu = Siparis.query.filter(
            Siparis.market_id == market_id
        )

        if gorunum == "gecmis":
            siparis_sorgusu = siparis_sorgusu.filter(
                Siparis.durum.in_([
                    "teslim_edildi",
                    "iptal"
                ])
            )
        else:
            siparis_sorgusu = siparis_sorgusu.filter(
                Siparis.durum.notin_([
                    "teslim_edildi",
                    "iptal"
                ])
            )

        siparisler = siparis_sorgusu.order_by(
            Siparis.olusturma_tarihi.desc()
        ).all()

        sonuc = []
        gunluk_sira_haritalari = {}

        for siparis in siparisler:
            siparis_zamani_utc = (
                siparis.olusturma_tarihi
                .replace(
                    tzinfo=timezone.utc
                )
            )

            siparis_zamani_istanbul = (
                siparis_zamani_utc.astimezone(
                    ISTANBUL_SAAT_DILIMI
                )
            )

            siparis_gunu = (
                siparis_zamani_istanbul.date()
            )

            if (
                siparis_gunu
                not in gunluk_sira_haritalari
            ):
                sonraki_gun = (
                    siparis_gunu
                    + timedelta(days=1)
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

                gunluk_sira_haritalari[
                    siparis_gunu
                ] = {
                    siparis_id: sira_no
                    for sira_no, (siparis_id,)
                    in enumerate(
                        gunun_siparis_idleri,
                        start=1
                    )
                }

            gunluk_sira_no = (
                gunluk_sira_haritalari[
                    siparis_gunu
                ].get(
                    siparis.id,
                    0
                )
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
                    "birim_fiyat": float(
                        detay.birim_fiyat
                    ),
                    "satir_toplam": (
                        float(
                            detay.birim_fiyat
                        )
                        * detay.adet
                    )
                }
                for detay in siparis.detaylar
            ]

            sonuc.append({
                "id": siparis.id,
                "gunluk_sira_no": (
                    gunluk_sira_no
                ),
                "siparis_tarihi": (
                    siparis_gunu.isoformat()
                ),
                "musteri_id": (
                    siparis.musteri_id
                ),
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
                "odeme_yontemi": (
                    siparis.odeme_yontemi
                ),
                "teslimat_yontemi": (
                    siparis.teslimat_yontemi
                ),
                "olusturma_tarihi": (
                    siparis_zamani_istanbul
                    .isoformat()
                ),
                "olusturma_saati": (
                    siparis_zamani_istanbul
                    .strftime("%H:%M")
                ),
                "siparis_notu": (
                    siparis.siparis_notu
                ),
                "toplam_tutar": float(
                    siparis.toplam_tutar
                ),
                "detaylar": kalemler
            })

        return jsonify(sonuc), 200

    except Exception as e:
        return jsonify({
            "hata": str(e)
        }), 500

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


@market_bp.route("/musteriler", methods=["GET"])
@role_required("market")
def musteriler_listele():
    try:
        market_id = request.args.get(
            "market_id",
            1,
            type=int
        )

        musteriler = Musteri.query.order_by(
            Musteri.ad_soyad.asc()
        ).all()

        sonuc = []

        for musteri in musteriler:
            siparis_sayisi = Siparis.query.filter_by(
                market_id=market_id,
                musteri_id=musteri.id
            ).count()

            sonuc.append({
                "id": musteri.id,
                "ad_soyad": musteri.ad_soyad,
                "telefon": musteri.telefon,
                "adres": musteri.adres,
                "siparis_sayisi": siparis_sayisi
            })

        return jsonify(sonuc), 200

    except Exception as e:
        return jsonify({
            "hata": f"Müşteriler alınamadı: {str(e)}"
        }), 500
    
@market_bp.route(
    "/musteriler/<int:musteri_id>/siparisler",
    methods=["GET"]
)
@role_required("market")
def musteri_siparisleri_getir(musteri_id):
    try:
        market_id = request.args.get(
            "market_id",
            1,
            type=int
        )

        musteri = Musteri.query.get_or_404(musteri_id)

        siparisler = Siparis.query.filter_by(
            market_id=market_id,
            musteri_id=musteri_id
        ).order_by(
            Siparis.olusturma_tarihi.desc()
        ).all()

        sonuc = []

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

            kalemler = [
                {
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
                "tarih": siparis_zamani_istanbul.strftime(
                    "%d.%m.%Y %H:%M"
                ),
                "durum": siparis.durum,
                "toplam_tutar": float(siparis.toplam_tutar),
                "detaylar": kalemler
            })

        return jsonify({
            "musteri": {
                "id": musteri.id,
                "ad_soyad": musteri.ad_soyad,
                "telefon": musteri.telefon,
                "adres": musteri.adres
            },
            "siparisler": sonuc
        }), 200

    except Exception as e:
        return jsonify({
            "hata": f"Müşteri siparişleri alınamadı: {str(e)}"
        }), 500


@market_bp.route("/yorumlar", methods=["GET"])
@role_required("market")
def yorumlar_listele():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        
        # Yorumları en yeniden en eskiye doğru sıralayarak çekiyoruz
        yorumlar = Yorum.query.filter_by(market_id=market_id).order_by(Yorum.olusturma_tarihi.desc()).all()
        
        sonuc = []
        for y in yorumlar:
            # Zamanı Türkiye saatine çeviriyoruz
            yorum_zamani_utc = y.olusturma_tarihi.replace(tzinfo=timezone.utc)
            yorum_zamani_istanbul = yorum_zamani_utc.astimezone(ISTANBUL_SAAT_DILIMI)
            
            sonuc.append({
                "id": y.id,
                "musteri_ad": y.musteri.ad_soyad if y.musteri else "İsimsiz Müşteri",
                "puan": y.puan,
                "yorum_metni": y.yorum_metni or "",
                "tarih": yorum_zamani_istanbul.strftime("%d.%m.%Y %H:%M"),
                "okundu_mu": y.okundu_mu,
                "siparis_id": y.siparis_id
            })
            
        return jsonify(sonuc), 200
        
    except Exception as e:
        return jsonify({"hata": f"Yorumlar alınamadı: {str(e)}"}), 500

@market_bp.route("/yorumlar/<int:yorum_id>/okundu", methods=["PUT"])
@role_required("market")
def yorum_okundu_isaretle(yorum_id):
    try:
        market_id = request.args.get("market_id", 1, type=int)
        yorum = Yorum.query.filter_by(id=yorum_id, market_id=market_id).first()
        
        if not yorum:
            return jsonify({"hata": "Yorum bulunamadı."}), 404
            
        yorum.okundu_mu = True
        db.session.commit()
        
        return jsonify({"mesaj": "Yorum okundu olarak işaretlendi.", "id": yorum.id}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500

# MÜŞTERİ YORUM YAPMA ROTASI (Hem test etmek hem de canlı bildirim atmak için)
@market_bp.route("/yorumlar", methods=["POST"])
def yorum_ekle():
    try:
        data = request.get_json(silent=True) or {}
        market_id = data.get("market_id", 1)
        musteri_id = data.get("musteri_id")
        puan = data.get("puan")
        yorum_metni = data.get("yorum_metni", "")
        siparis_id = data.get("siparis_id") # Hangi siparişe yapıldığı (opsiyonel)

        if not musteri_id or not puan:
            return jsonify({"hata": "Müşteri ID ve puan (yıldız) zorunludur."}), 400

        yeni_yorum = Yorum(
            market_id=market_id,
            musteri_id=musteri_id,
            siparis_id=siparis_id,
            puan=int(puan),
            yorum_metni=str(yorum_metni).strip()
        )
        
        db.session.add(yeni_yorum)
        db.session.commit()

        
        socketio.emit("yeni_yorum_geldi", {"market_id": market_id})

        return jsonify({"mesaj": "Yorum başarıyla eklendi.", "id": yeni_yorum.id}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@market_bp.route("/raporlar", methods=["GET"])
@role_required("market")
def raporlari_getir():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        
        # Zaman sınırlarını belirliyoruz (Bugün ve Bu Ay)
        bugun_istanbul = datetime.now(ISTANBUL_SAAT_DILIMI).date()
        ay_baslangic_tarihi = bugun_istanbul.replace(day=1)

        bugun_baslangic, _ = istanbul_tarih_araligini_utc_yap(
            bugun_istanbul,
            bugun_istanbul + timedelta(days=1)
        )

        ay_baslangic, _ = istanbul_tarih_araligini_utc_yap(
            ay_baslangic_tarihi,
            bugun_istanbul + timedelta(days=1)
        )

        siparisler = Siparis.query.filter_by(market_id=market_id).all()
        
        # --- 1. FİNANSAL VE GENEL METRİKLER ---
        ciro_toplam = 0
        ciro_bugun = 0
        ciro_bu_ay = 0
        siparis_sayisi_tamamlanan = 0
        siparis_sayisi_iptal = 0
        
        for s in siparisler:
            # Sadece başarıyla teslim edilenleri ciroya sayıyoruz
            if s.durum == "teslim_edildi":
                ciro_toplam += float(s.toplam_tutar)
                siparis_sayisi_tamamlanan += 1
                
                if s.olusturma_tarihi >= bugun_baslangic:
                    ciro_bugun += float(s.toplam_tutar)
                if s.olusturma_tarihi >= ay_baslangic:
                    ciro_bu_ay += float(s.toplam_tutar)
            elif s.durum == "iptal":
                siparis_sayisi_iptal += 1

        toplam_islem = siparis_sayisi_tamamlanan + siparis_sayisi_iptal
        iptal_orani = (siparis_sayisi_iptal / toplam_islem * 100) if toplam_islem > 0 else 0
        ortalama_sepet = (ciro_toplam / siparis_sayisi_tamamlanan) if siparis_sayisi_tamamlanan > 0 else 0

        # --- 2. KATEGORİ VE ÜRÜN BAZLI ANALİZ ---
        kategori_satis = {}
        urun_satis = {}
        
        # Hangi ürünlerin ne kadar sattığını bulmak için teslim edilen sipariş detaylarını geziyoruz
        teslim_edilen_idleri = [s.id for s in siparisler if s.durum == "teslim_edildi"]
        detaylar = SiparisDetay.query.filter(SiparisDetay.siparis_id.in_(teslim_edilen_idleri)).all() if teslim_edilen_idleri else []

        for d in detaylar:
            if d.urun:
                # Kategori cirosunu topla
                kat = d.urun.kategori
                kategori_satis[kat] = kategori_satis.get(kat, 0) + float(d.birim_fiyat * d.adet)
                
                # Ürün bazlı satış adetlerini ve ciroyu topla
                uid = d.urun.id
                if uid not in urun_satis:
                    urun_satis[uid] = {"ad": d.urun.ad, "adet": 0, "ciro": 0}
                urun_satis[uid]["adet"] += d.adet
                urun_satis[uid]["ciro"] += float(d.birim_fiyat * d.adet)

        # En çok satan ilk 10 ürünü büyükten küçüğe sırala
        en_cok_satanlar = sorted(urun_satis.values(), key=lambda x: x["adet"], reverse=True)[:10]

        # Kategorileri getirdikleri ciroya göre büyükten küçüğe sırala
        kategori_sirali = [{"kategori": k, "ciro": v} for k, v in sorted(kategori_satis.items(), key=lambda item: item[1], reverse=True)]

        # --- 3. OPERASYONEL METRİKLER (KRİTİK STOK UYARISI) ---
        # Stoğu 5 ve altına düşen aktif ürünler
        kritik_stok_urunleri = Urun.query.filter_by(market_id=market_id, aktif=True).filter(Urun.stok_adet <= 5).all()
        kritik_stok = [{"id": u.id, "ad": u.ad, "stok": u.stok_adet} for u in kritik_stok_urunleri]

        # --- 4. MÜŞTERİ MEMNUNİYETİ ---
        musteri_sayisi = Musteri.query.count()
        yorumlar = Yorum.query.filter_by(market_id=market_id).all()
        ortalama_puan = sum(y.puan for y in yorumlar) / len(yorumlar) if yorumlar else 0

        # Tüm veriyi paketleyip HTML/JS'ye gönderiyoruz
        return jsonify({
            "finans": {
                "ciro_bugun": ciro_bugun,
                "ciro_bu_ay": ciro_bu_ay,
                "ciro_toplam": ciro_toplam,
                "ortalama_sepet": ortalama_sepet
            },
            "operasyon": {
                "tamamlanan_siparis": siparis_sayisi_tamamlanan,
                "iptal_siparis": siparis_sayisi_iptal,
                "iptal_orani": iptal_orani,
                "toplam_musteri": musteri_sayisi,
                "ortalama_puan": round(ortalama_puan, 1)
            },
            "kategoriler": kategori_sirali,
            "en_cok_satanlar": en_cok_satanlar,
            "kritik_stok": kritik_stok
        }), 200

    except Exception as e:
        return jsonify({"hata": f"Raporlar oluşturulamadı: {str(e)}"}), 500

@market_bp.route("/raporlar/genel-bakis", methods=["GET"])
@role_required("market")
def rapor_genel_bakis():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        bugun_istanbul = datetime.now(ISTANBUL_SAAT_DILIMI).date()
        dun_istanbul = bugun_istanbul - timedelta(days=1)

        bugun_baslangic_utc, bugun_bitis_utc = istanbul_tarih_araligini_utc_yap(
            bugun_istanbul,
            bugun_istanbul + timedelta(days=1)
        )

        dun_baslangic_utc, dun_bitis_utc = istanbul_tarih_araligini_utc_yap(
            dun_istanbul,
            bugun_istanbul
        )

        bu_ay_baslangici = bugun_istanbul.replace(day=1)

        if bu_ay_baslangici.month == 1:
            gecen_ay_baslangici = bu_ay_baslangici.replace(
                year=bu_ay_baslangici.year - 1,
                month=12
            )
        else:
            gecen_ay_baslangici = bu_ay_baslangici.replace(
                month=bu_ay_baslangici.month - 1
            )

        bu_ay_baslangic_utc, bu_ay_bitis_utc = istanbul_tarih_araligini_utc_yap(
            bu_ay_baslangici,
            bugun_istanbul + timedelta(days=1)
        )

        gecen_ay_baslangic_utc, gecen_ay_bitis_utc = istanbul_tarih_araligini_utc_yap(
            gecen_ay_baslangici,
            bu_ay_baslangici
        )

        def donem_metrikleri(baslangic_utc, bitis_utc):
            siparisler = Siparis.query.filter(
                Siparis.market_id == market_id,
                Siparis.olusturma_tarihi >= baslangic_utc,
                Siparis.olusturma_tarihi < bitis_utc
            ).all()

            teslim_edilenler = [
                s for s in siparisler if s.durum == "teslim_edildi"
            ]

            iptal_edilenler = [
                s for s in siparisler if s.durum == "iptal"
            ]

            ciro = sum(float(s.toplam_tutar) for s in teslim_edilenler)

            tamamlanmis_islem = len(teslim_edilenler) + len(iptal_edilenler)

            iptal_orani = (
                len(iptal_edilenler) / tamamlanmis_islem * 100
                if tamamlanmis_islem > 0
                else 0
            )

            ortalama_sepet = (
                ciro / len(teslim_edilenler)
                if teslim_edilenler
                else 0
            )

            return {
                "ciro": ciro,
                "iptal_orani": iptal_orani,
                "ortalama_sepet": ortalama_sepet
            }

        def yuzde_degisim(simdi, once):
            if once == 0:
                return 100.0 if simdi > 0 else 0.0

            return round((simdi - once) / once * 100, 1)

        bugun_metrik = donem_metrikleri(bugun_baslangic_utc, bugun_bitis_utc)
        dun_metrik = donem_metrikleri(dun_baslangic_utc, dun_bitis_utc)
        bu_ay_metrik = donem_metrikleri(bu_ay_baslangic_utc, bu_ay_bitis_utc)
        gecen_ay_metrik = donem_metrikleri(gecen_ay_baslangic_utc, gecen_ay_bitis_utc)

        # Son 7 günün ciro sparkline verisi
        sparkline = []

        for gun_farki in range(6, -1, -1):
            tarih = bugun_istanbul - timedelta(days=gun_farki)
            sonraki_tarih = tarih + timedelta(days=1)

            gun_baslangic_utc, gun_bitis_utc = istanbul_tarih_araligini_utc_yap(
                tarih,
                sonraki_tarih
            )

            gun_cirosu = db.session.query(
                db.func.coalesce(db.func.sum(Siparis.toplam_tutar), 0)
            ).filter(
                Siparis.market_id == market_id,
                Siparis.durum == "teslim_edildi",
                Siparis.olusturma_tarihi >= gun_baslangic_utc,
                Siparis.olusturma_tarihi < gun_bitis_utc
            ).scalar()

            sparkline.append(float(gun_cirosu or 0))

        # Sipariş durum dağılımı (tüm zamanlar)
        durum_sayilari = {
            "bekliyor": 0,
            "hazirlaniyor": 0,
            "yolda": 0,
            "teslim_edildi": 0,
            "iptal": 0
        }

        durum_sonuclari = db.session.query(
            Siparis.durum,
            db.func.count(Siparis.id)
        ).filter(
            Siparis.market_id == market_id
        ).group_by(Siparis.durum).all()

        for durum, adet in durum_sonuclari:
            if durum in durum_sayilari:
                durum_sayilari[durum] = adet
            else:
                durum_sayilari[durum] = adet

        return jsonify({
            "ciro_bugun": bugun_metrik["ciro"],
            "ciro_bugun_trend": yuzde_degisim(
                bugun_metrik["ciro"], dun_metrik["ciro"]
            ),
            "ciro_bu_ay": bu_ay_metrik["ciro"],
            "ciro_bu_ay_trend": yuzde_degisim(
                bu_ay_metrik["ciro"], gecen_ay_metrik["ciro"]
            ),
            "ortalama_sepet": bu_ay_metrik["ortalama_sepet"],
            "ortalama_sepet_trend": yuzde_degisim(
                bu_ay_metrik["ortalama_sepet"], gecen_ay_metrik["ortalama_sepet"]
            ),
            "iptal_orani": bu_ay_metrik["iptal_orani"],
            "iptal_orani_trend": yuzde_degisim(
                bu_ay_metrik["iptal_orani"], gecen_ay_metrik["iptal_orani"]
            ),
            "sparkline_7gun": sparkline,
            "durum_dagilimi": durum_sayilari
        }), 200

    except Exception as e:
        return jsonify({
            "hata": f"Genel bakış raporu alınamadı: {str(e)}"
        }), 500

@market_bp.route("/raporlar/satis-analizi", methods=["GET"])
@role_required("market")
def rapor_satis_analizi():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        donem = request.args.get(
            "donem",
            "haftalik"
        ).strip().lower()

        izin_verilen_donemler = {
            "gunluk",
            "haftalik",
            "aylik",
            "yillik"
        }

        if donem not in izin_verilen_donemler:
            donem = "haftalik"

        bugun_istanbul = datetime.now(ISTANBUL_SAAT_DILIMI).date()

        labels = []
        ciro_veriler = []
        siparis_veriler = []

        def gun_araligi_topla(tarih, sonraki_tarih):
            baslangic_utc, bitis_utc = istanbul_tarih_araligini_utc_yap(
                tarih,
                sonraki_tarih
            )

            teslim_edilenler = Siparis.query.filter(
                Siparis.market_id == market_id,
                Siparis.durum == "teslim_edildi",
                Siparis.olusturma_tarihi >= baslangic_utc,
                Siparis.olusturma_tarihi < bitis_utc
            ).all()

            ciro = sum(float(s.toplam_tutar) for s in teslim_edilenler)

            tum_siparis_sayisi = Siparis.query.filter(
                Siparis.market_id == market_id,
                Siparis.olusturma_tarihi >= baslangic_utc,
                Siparis.olusturma_tarihi < bitis_utc
            ).count()

            return ciro, tum_siparis_sayisi

        if donem == "gunluk":
            for saat in range(0, 24, 3):
                saat_bitisi = saat + 3
                gun_baslangic_utc, gun_bitis_utc = istanbul_tarih_araligini_utc_yap(
                    bugun_istanbul,
                    bugun_istanbul + timedelta(days=1)
                )

                teslim_edilenler = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.durum == "teslim_edildi",
                    Siparis.olusturma_tarihi >= gun_baslangic_utc,
                    Siparis.olusturma_tarihi < gun_bitis_utc
                ).all()

                tum_siparisler = Siparis.query.filter(
                    Siparis.market_id == market_id,
                    Siparis.olusturma_tarihi >= gun_baslangic_utc,
                    Siparis.olusturma_tarihi < gun_bitis_utc
                ).all()

                saat_cirosu = 0
                saat_siparis_sayisi = 0

                for s in tum_siparisler:
                    s_utc = s.olusturma_tarihi.replace(tzinfo=timezone.utc)
                    s_istanbul = s_utc.astimezone(ISTANBUL_SAAT_DILIMI)

                    if saat <= s_istanbul.hour < saat_bitisi:
                        saat_siparis_sayisi += 1

                        if s.durum == "teslim_edildi":
                            saat_cirosu += float(s.toplam_tutar)

                labels.append(f"{saat:02d}:00")
                ciro_veriler.append(saat_cirosu)
                siparis_veriler.append(saat_siparis_sayisi)

        elif donem == "haftalik":
            for gun_farki in range(6, -1, -1):
                tarih = bugun_istanbul - timedelta(days=gun_farki)
                ciro, siparis_sayisi = gun_araligi_topla(tarih, tarih + timedelta(days=1))

                labels.append(tarih.strftime("%d.%m"))
                ciro_veriler.append(ciro)
                siparis_veriler.append(siparis_sayisi)

        elif donem == "aylik":
            ay_baslangici = bugun_istanbul.replace(day=1)
            hafta_numarasi = 1
            hafta_baslangici = ay_baslangici

            while hafta_baslangici <= bugun_istanbul:
                hafta_bitisi = min(
                    hafta_baslangici + timedelta(days=7),
                    bugun_istanbul + timedelta(days=1)
                )

                ciro, siparis_sayisi = gun_araligi_topla(hafta_baslangici, hafta_bitisi)

                labels.append(f"{hafta_numarasi}. Hafta")
                ciro_veriler.append(ciro)
                siparis_veriler.append(siparis_sayisi)

                hafta_numarasi += 1
                hafta_baslangici += timedelta(days=7)

        else:
            yil = bugun_istanbul.year
            ay_isimleri = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

            for ay in range(1, 13):
                ay_baslangici = datetime(yil, ay, 1).date()

                if ay == 12:
                    sonraki_ay_baslangici = datetime(yil + 1, 1, 1).date()
                else:
                    sonraki_ay_baslangici = datetime(yil, ay + 1, 1).date()

                ciro, siparis_sayisi = gun_araligi_topla(ay_baslangici, sonraki_ay_baslangici)

                labels.append(ay_isimleri[ay - 1])
                ciro_veriler.append(ciro)
                siparis_veriler.append(siparis_sayisi)

        # Ödeme ve teslimat yöntemi dağılımı (teslim edilen siparişler üzerinden)
        odeme_dagilimi = dict(
            db.session.query(
                Siparis.odeme_yontemi,
                db.func.count(Siparis.id)
            ).filter(
                Siparis.market_id == market_id,
                Siparis.durum == "teslim_edildi"
            ).group_by(Siparis.odeme_yontemi).all()
        )

        teslimat_dagilimi = dict(
            db.session.query(
                Siparis.teslimat_yontemi,
                db.func.count(Siparis.id)
            ).filter(
                Siparis.market_id == market_id,
                Siparis.durum == "teslim_edildi"
            ).group_by(Siparis.teslimat_yontemi).all()
        )

        return jsonify({
            "donem": donem,
            "labels": labels,
            "ciro_veriler": ciro_veriler,
            "siparis_veriler": siparis_veriler,
            "odeme_dagilimi": odeme_dagilimi,
            "teslimat_dagilimi": teslimat_dagilimi
        }), 200

    except Exception as e:
        return jsonify({
            "hata": f"Satış analizi raporu alınamadı: {str(e)}"
        }), 500

@market_bp.route("/raporlar/urun-kategori", methods=["GET"])
@role_required("market")
def rapor_urun_kategori():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        teslim_edilen_id_sorgusu = db.session.query(Siparis.id).filter(
            Siparis.market_id == market_id,
            Siparis.durum == "teslim_edildi"
        )

        teslim_edilen_idler = [
            satir[0] for satir in teslim_edilen_id_sorgusu.all()
        ]

        detaylar = (
            SiparisDetay.query
            .filter(SiparisDetay.siparis_id.in_(teslim_edilen_idler))
            .all()
            if teslim_edilen_idler
            else []
        )

        kategori_satis = {}
        urun_satis = {}

        for d in detaylar:
            if not d.urun:
                continue

            kat = d.urun.kategori
            satir_toplam = float(d.birim_fiyat) * d.adet

            if kat not in kategori_satis:
                kategori_satis[kat] = {"ciro": 0, "adet": 0}

            kategori_satis[kat]["ciro"] += satir_toplam
            kategori_satis[kat]["adet"] += d.adet

            uid = d.urun.id

            if uid not in urun_satis:
                urun_satis[uid] = {
                    "id": uid,
                    "ad": d.urun.ad,
                    "adet": 0,
                    "ciro": 0
                }

            urun_satis[uid]["adet"] += d.adet
            urun_satis[uid]["ciro"] += satir_toplam

        kategori_sirali = [
            {"kategori": k, "ciro": v["ciro"], "adet": v["adet"]}
            for k, v in sorted(
                kategori_satis.items(),
                key=lambda item: item[1]["ciro"],
                reverse=True
            )
        ]

        en_cok_satanlar = sorted(
            urun_satis.values(),
            key=lambda x: x["adet"],
            reverse=True
        )[:10]

        satilan_urun_idleri = set(urun_satis.keys())

        hic_satilmayanlar = Urun.query.filter(
            Urun.market_id == market_id,
            Urun.aktif == True,
            ~Urun.id.in_(satilan_urun_idleri) if satilan_urun_idleri else True
        ).order_by(Urun.ad.asc()).limit(10).all()

        hic_satilmayan_liste = [
            {"id": u.id, "ad": u.ad, "stok": u.stok_adet}
            for u in hic_satilmayanlar
        ]

        return jsonify({
            "kategoriler": kategori_sirali,
            "en_cok_satanlar": en_cok_satanlar,
            "hic_satilmayanlar": hic_satilmayan_liste
        }), 200

    except Exception as e:
        return jsonify({
            "hata": f"Ürün & kategori raporu alınamadı: {str(e)}"
        }), 500

@market_bp.route("/raporlar/musteriler", methods=["GET"])
@role_required("market")
def rapor_musteriler():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        # Sadece teslim edilen siparişler üzerinden müşteri analizi
        siparisler = Siparis.query.filter_by(market_id=market_id, durum="teslim_edildi").all()

        musteri_analiz = {}
        for s in siparisler:
            mid = s.musteri_id
            if mid not in musteri_analiz:
                musteri_analiz[mid] = {
                    "id": mid,
                    "ad": s.musteri.ad_soyad if s.musteri else "İsimsiz",
                    "siparis_sayisi": 0,
                    "toplam_ciro": 0,
                    "son_siparis_tarihi": s.olusturma_tarihi
                }
            
            musteri_analiz[mid]["siparis_sayisi"] += 1
            musteri_analiz[mid]["toplam_ciro"] += float(s.toplam_tutar)
            
            if s.olusturma_tarihi > musteri_analiz[mid]["son_siparis_tarihi"]:
                musteri_analiz[mid]["son_siparis_tarihi"] = s.olusturma_tarihi

        # En sadık / çok harcayan 10 müşteri (ciroya göre büyükten küçüğe)
        en_iyi_musteriler = sorted(musteri_analiz.values(), key=lambda x: x["toplam_ciro"], reverse=True)[:10]

        # Tarih formatlaması
        for m in en_iyi_musteriler:
            if m["son_siparis_tarihi"]:
                m["son_siparis_tarihi"] = m["son_siparis_tarihi"].strftime("%d.%m.%Y")

        toplam_aktif_musteri = len(musteri_analiz)
        
        # Sadece 1 sipariş verip bir daha gelmeyenler (Sadakat Oranı ölçümü için)
        tek_siparisli_sayisi = sum(1 for m in musteri_analiz.values() if m["siparis_sayisi"] == 1)

        return jsonify({
            "toplam_aktif_musteri": toplam_aktif_musteri,
            "tek_siparisli_sayisi": tek_siparisli_sayisi,
            "en_iyi_musteriler": en_iyi_musteriler
        }), 200

    except Exception as e:
        return jsonify({"hata": f"Müşteri raporu alınamadı: {str(e)}"}), 500

@market_bp.route("/raporlar/stok", methods=["GET"])
@role_required("market")
def rapor_stok():
    try:
        market_id = request.args.get("market_id", 1, type=int)

        tum_urunler = Urun.query.filter_by(market_id=market_id).all()

        toplam_cesit = len(tum_urunler)
        toplam_stok_adedi = sum(u.stok_adet for u in tum_urunler)
        
        # Stokların toplam ciro/satış potansiyeli veya maliyet değeri (Fiyat * Stok Adedi)
        toplam_envanter_degeri = sum(float(u.fiyat) * u.stok_adet for u in tum_urunler if u.aktif)

        # Durumlarına göre ürünleri ayıralım
        tukenenler = []
        kritik_stoklar = []
        normal_stoklar = []

        for u in tum_urunler:
            veri = {
                "id": u.id,
                "ad": u.ad,
                "kategori": u.kategori,
                "fiyat": float(u.fiyat),
                "stok": u.stok_adet,
                "aktif": u.aktif
            }
            if u.stok_adet <= 0 or not u.aktif:
                tukenenler.append(veri)
            elif u.stok_adet <= 5:
                kritik_stoklar.append(veri)
            else:
                normal_stoklar.append(veri)

        return jsonify({
            "toplam_cesit": toplam_cesit,
            "toplam_stok_adedi": toplam_stok_adedi,
            "toplam_envanter_degeri": toplam_envanter_degeri,
            "tukenen_sayisi": len(tukenenler),
            "kritik_sayisi": len(kritik_stoklar),
            "tukenenler": tukenenler,
            "kritik_stoklar": kritik_stoklar
        }), 200

    except Exception as e:
        return jsonify({"hata": f"Stok raporu alınamadı: {str(e)}"}), 500