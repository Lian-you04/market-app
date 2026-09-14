from flask import Blueprint, request, jsonify, session
from sqlalchemy import or_
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_DOWN,
    ROUND_HALF_UP
)
from datetime import timezone
from zoneinfo import ZoneInfo
from app import db, socketio
from app.models import Urun, Siparis, SiparisDetay, Musteri, Market, Kullanici, FavoriUrun, Yorum
from app.security import role_required

musteri_bp = Blueprint("musteri", __name__)

def siparis_miktarini_hazirla(deger):
    try:
        miktar = Decimal(str(deger))

        if not miktar.is_finite() or miktar <= 0:
            raise ValueError(
                "Sipariş miktarı pozitif bir sayı olmalıdır."
            )

        return miktar.quantize(
            Decimal("0.000001"),
            rounding=ROUND_DOWN
        )

    except (InvalidOperation, TypeError, ValueError) as hata:
        raise ValueError(
            "Geçerli bir sipariş miktarı girilmelidir."
        ) from hata

def siparis_tutarini_hazirla(deger):
    try:
        tutar = Decimal(str(deger))

        if not tutar.is_finite() or tutar <= 0:
            raise ValueError(
                "Sipariş tutarı pozitif bir sayı olmalıdır."
            )

        tutar = tutar.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        if tutar > Decimal("99999999.99"):
            raise ValueError(
                "Sipariş tutarı izin verilen sınırı aşıyor."
            )

        return tutar

    except (InvalidOperation, TypeError, ValueError) as hata:
        raise ValueError(
            "Geçerli bir sipariş tutarı girilmelidir."
        ) from hata

def tutar_icin_kg_miktari_hazirla(
    hedef_tutar,
    kg_fiyati,
    stok
):
    if kg_fiyati <= 0:
        raise ValueError(
            "Kilogram fiyatı sıfırdan büyük olmalıdır."
        )

    if stok < 0:
        raise ValueError(
            "Stok negatif olamaz."
        )

    if hedef_tutar > kg_fiyati * stok:
        raise ValueError(
            "İstenen tutar mevcut stok değerini aşıyor."
        )

    miktar = (
        hedef_tutar / kg_fiyati
    ).quantize(
        Decimal("0.000001"),
        rounding=ROUND_DOWN
    )

    if miktar <= 0:
        raise ValueError(
            "İstenen tutar geçerli bir kilogram miktarı oluşturmuyor."
        )

    return miktar

ISTANBUL_SAAT_DILIMI = ZoneInfo("Europe/Istanbul")


def aktif_musteri_getir():
    kullanici_id = session.get("kullanici_id")
    if not kullanici_id:
        return None
    return Musteri.query.filter_by(kullanici_id=kullanici_id).first()


def siparis_json(s):
    kalemler = [{
        "urun_id": d.urun_id,
        "ad": d.urun.ad if d.urun else "Silinmiş Ürün",
        "adet": float(d.adet),
        "satis_hesaplama_turu": d.satis_hesaplama_turu,
        "birim_fiyat": float(d.birim_fiyat),
        "satir_toplam": float(d.satir_tutari)
    } for d in s.detaylar]

    siparis_zamani_utc = s.olusturma_tarihi

    if (
        siparis_zamani_utc
        and siparis_zamani_utc.tzinfo is None
    ):
        siparis_zamani_utc = siparis_zamani_utc.replace(
            tzinfo=timezone.utc
        )

    siparis_zamani_istanbul = (
        siparis_zamani_utc.astimezone(
            ISTANBUL_SAAT_DILIMI
        )
        if siparis_zamani_utc
        else None
    )

    karar_zamani_istanbul = None

    if s.karar_tarihi:
        karar_zamani_utc = s.karar_tarihi

        if karar_zamani_utc.tzinfo is None:
            karar_zamani_utc = karar_zamani_utc.replace(
                tzinfo=timezone.utc
            )

        karar_zamani_istanbul = (
            karar_zamani_utc.astimezone(
                ISTANBUL_SAAT_DILIMI
            )
        )

    return {
        "id": s.id,
        "durum": s.durum,
        "karar_tarihi": (
            karar_zamani_istanbul.isoformat()
            if karar_zamani_istanbul
            else None
        ),
        "karar_saati": (
            karar_zamani_istanbul.strftime("%H:%M")
            if karar_zamani_istanbul
            else None
        ),
        "red_sebebi": s.red_sebebi,
        "siparis_notu": s.siparis_notu,
        "odeme_yontemi": s.odeme_yontemi,
        "teslimat_yontemi": s.teslimat_yontemi,
        "toplam_tutar": float(s.toplam_tutar),
        "tarih": (
            siparis_zamani_istanbul.strftime(
                "%d.%m.%Y %H:%M"
            )
            if siparis_zamani_istanbul
            else ""
        ),
        "detaylar": kalemler
    }


@musteri_bp.route("/market-durum", methods=["GET"])
def market_durum_ogren():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        market = Market.query.get_or_404(market_id)

        return jsonify({
            "ad": market.ad,
            "aktif": market.aktif,
            "min_siparis_tutari": float(market.min_siparis_tutari)
        }), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/kategoriler", methods=["GET"])
def kategoriler_listele():
    return jsonify([
        {
            "id": "et_tavuk",
            "ad": "🥩 Et & Tavuk",
            "resim": "/static/category-images/et-tavuk.jpg"
        },
        {
            "id": "meyve_sebze",
            "ad": "🍅 Meyve & Sebze",
            "resim": "/static/category-images/meyve-sebze.jpg"
        },
        {
            "id": "sut_kahvaltilik",
            "ad": "🧀 Süt & Kahvaltı",
            "resim": "/static/category-images/sut-kahvaltilik.jpg"
        },
        {
            "id": "aburcubur",
            "ad": "🍫 Aburcubur",
            "resim": "/static/category-images/aburcubur.jpg"
        },
        {
            "id": "icecek",
            "ad": "🥤 İçecekler",
            "resim": "/static/category-images/icecek.jpg"
        },
        {
            "id": "ekmek_firin",
            "ad": "🍞 Ekmek & Fırın",
            "resim": "/static/category-images/ekmek-firin.jpg"
        },
        {
            "id": "tatlilar",
            "ad": "🍰 Tatlılar",
            "resim": "/static/category-images/tatlilar.jpg"
        },
        {
            "id": "temizlik",
            "ad": "🧼 Temizlik",
            "resim": "/static/category-images/temizlik.jpg"
        },
        {
            "id": "kozmetik",
            "ad": "🧴 Kozmetik",
            "resim": "/static/category-images/kozmetik.jpg"
        },
        {
            "id": "dondurma",
            "ad": "🍦 Dondurma",
            "resim": "/static/category-images/dondurma.jpg"
        },
        {
            "id": "evcil_hayvan_mamasi",
            "ad": "🐾 Evcil Hayvan Maması",
            "resim": "/static/category-images/evcil-hayvan-mamasi.jpg"
        },
        {
            "id": "elektronik",
            "ad": "🔌 Elektronik",
            "resim": "/static/category-images/elektronik.jpg"
        }
    ])


@musteri_bp.route("/urunler", methods=["GET"])
def urunleri_getir():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        kategori = request.args.get("kategori")

        query = Urun.query.filter(
            Urun.market_id == market_id,
            or_(
                Urun.aktif.is_(True),
                Urun.stok_adet <= 0
            )
        )

        if kategori:
            query = query.filter_by(kategori=kategori)

        urunler = query.all()

        favori_ids = set()
        musteri = aktif_musteri_getir()

        if musteri:
            favori_ids = {
                f.urun_id
                for f in FavoriUrun.query.filter_by(
                    musteri_id=musteri.id
                ).all()
            }

        return jsonify([{
            "id": u.id,
            "ad": u.ad,
            "aciklama": u.aciklama,
            "fiyat": float(u.fiyat),
            "resim_url": u.resim_url,
            "satis_hesaplama_turu": (
                u.satis_hesaplama_turu
            ),
            "max_alinabilir_adet": float(u.stok_adet),
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
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

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
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

        ad = data.get("ad", "").strip()
        soyad = data.get("soyad", "").strip()
        ad_soyad = data.get("ad_soyad", "").strip()
        telefon = data.get("telefon", "").strip().replace(" ", "")
        adres_tarifi = data.get(
            "adres_tarifi",
            data.get("adres", "")
        ).strip()

        if ad or soyad:
            ad_soyad = f"{ad} {soyad}".strip()

        if not ad_soyad:
            return jsonify({
                "hata": "Ad ve soyad boş olamaz!"
            }), 400

        if not telefon:
            return jsonify({
                "hata": "Telefon boş olamaz!"
            }), 400

        if not telefon.startswith("+90"):
            telefon = "+90" + telefon.lstrip("0")

        if not adres_tarifi:
            return jsonify({
                "hata": "Adres tarifi boş olamaz!"
            }), 400

        musteri.ad_soyad = ad_soyad
        musteri.telefon = telefon
        musteri.adres = adres_tarifi

        db.session.commit()

        socketio.emit(
            "musteri_bilgileri_guncellendi",
            {
                "musteri_id": musteri.id
            }
        )

        return jsonify({
            "mesaj": "Profil bilgileriniz güncellendi."
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/siparisler", methods=["GET"])
@role_required("musteri")
def musteri_siparislerini_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

        siparisler = Siparis.query.filter_by(
            musteri_id=musteri.id
        ).order_by(
            Siparis.olusturma_tarihi.desc()
        ).all()

        return jsonify([
            siparis_json(s)
            for s in siparisler
        ]), 200

    except Exception as e:
        return jsonify({
            "hata": f"Siparişler çekilemedi: {str(e)}"
        }), 500


@musteri_bp.route("/siparisler/gecmis", methods=["GET"])
@role_required("musteri")
def gecmis_siparisleri_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

        siparisler = Siparis.query.filter(
            Siparis.musteri_id == musteri.id,
            Siparis.durum.in_([
                "onaylandi",
                "reddedildi",
            ])
        ).order_by(
            Siparis.olusturma_tarihi.desc()
        ).all()

        return jsonify([
            siparis_json(s)
            for s in siparisler
        ]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route(
    "/siparisler/<int:siparis_id>/tekrar",
    methods=["POST"]
)
@role_required("musteri")
def siparisi_tekrarla(siparis_id):
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({
                "hata": "Müşteri profili bulunamadı."
            }), 404

        eski_siparis = Siparis.query.get_or_404(siparis_id)

        if eski_siparis.musteri_id != musteri.id:
            return jsonify({
                "hata": "Bu sipariş size ait değil."
            }), 403

        sepete_eklenecekler = []
        eklenemeyenler = []

        for detay in eski_siparis.detaylar:
            urun = detay.urun

            if not urun:
                eklenemeyenler.append("Silinmiş ürün")
                continue

            if not urun.aktif or urun.stok_adet <= 0:
                eklenemeyenler.append(urun.ad)
                continue

            satis_turu = (
                urun.satis_hesaplama_turu
                or "adet"
            )

            eski_satis_turu = (
                detay.satis_hesaplama_turu
                or "adet"
            )

            if eski_satis_turu != satis_turu:
                eklenemeyenler.append(
                    f"{urun.ad}: satış biçimi değişmiş; "
                    "yeniden seçilmelidir"
                )
                continue

            hedef_tutar = None

            if satis_turu == "tutar":
                hedef_tutar = detay.satir_toplami

                if hedef_tutar is None:
                    hedef_tutar = (
                        detay.birim_fiyat
                        * detay.adet
                    )

                try:
                    eklenecek_adet = (
                        tutar_icin_kg_miktari_hazirla(
                            hedef_tutar,
                            urun.fiyat,
                            urun.stok_adet
                        )
                    )

                except ValueError:
                    eklenemeyenler.append(
                        f"{urun.ad}: güncel fiyat ve stok "
                        "eski hedef tutarı karşılamıyor"
                    )
                    continue

            else:
                eklenecek_adet = min(
                    detay.adet,
                    urun.stok_adet
                )

            sepete_eklenecekler.append({
                "urun_id": urun.id,
                "ad": urun.ad,
                "adet": float(eklenecek_adet),
                "tutar": (
                    float(hedef_tutar)
                    if hedef_tutar is not None
                    else None
                ),
                "fiyat": float(urun.fiyat),
                "satis_hesaplama_turu": (
                    urun.satis_hesaplama_turu
                ),
                "resim_url": urun.resim_url,
                "max_alinabilir_adet": float(
                    urun.stok_adet
                )
            })

            if (
                satis_turu != "tutar"
                and eklenecek_adet < detay.adet
            ):
                eklenemeyenler.append(
                    f"{urun.ad}: yalnızca "
                    f"{eklenecek_adet} adet stokta"
                )

        if not sepete_eklenecekler:
            return jsonify({
                "hata": (
                    "Bu siparişte tekrar sepete "
                    "eklenebilecek ürün bulunamadı."
                ),
                "eklenemeyenler": eklenemeyenler
            }), 400

        return jsonify({
            "mesaj": "Uygun ürünler sepete eklenmeye hazır.",
            "urunler": sepete_eklenecekler,
            "eklenemeyenler": eklenemeyenler
        }), 200

    except Exception as e:
        return jsonify({
            "hata": f"Sipariş tekrarlanamadı: {str(e)}"
        }), 500


@musteri_bp.route("/siparisler/aktif", methods=["GET"])
@role_required("musteri")
def aktif_siparisleri_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

        siparisler = Siparis.query.filter(
            Siparis.musteri_id == musteri.id,
            Siparis.durum == "bekliyor"
        ).order_by(
            Siparis.olusturma_tarihi.desc()
        ).all()

        return jsonify([
            siparis_json(s)
            for s in siparisler
        ]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/favoriler", methods=["GET"])
@role_required("musteri")
def favorileri_getir():
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

        favoriler = FavoriUrun.query.filter_by(
            musteri_id=musteri.id
        ).all()

        return jsonify([{
            "urun_id": f.urun.id,
            "ad": f.urun.ad,
            "aciklama": f.urun.aciklama,
            "fiyat": float(f.urun.fiyat),
            "resim_url": f.urun.resim_url,
            "satis_hesaplama_turu": (
                f.urun.satis_hesaplama_turu
            ),
            "stok_adet": float(f.urun.stok_adet),
            "max_alinabilir_adet": float(f.urun.stok_adet),
            "stok_durumu": (
                "var"
                if f.urun.stok_adet > 0
                else "tukendi"
            ),
            "aktif": f.urun.aktif
        } for f in favoriler if f.urun]), 200

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route(
    "/favoriler/<int:urun_id>",
    methods=["POST"]
)
@musteri_bp.route(
    "/favori/<int:urun_id>",
    methods=["POST"]
)
@role_required("musteri")
def favori_ekle(urun_id):
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

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

        db.session.add(
            FavoriUrun(
                musteri_id=musteri.id,
                urun_id=urun.id
            )
        )

        db.session.commit()

        return jsonify({
            "mesaj": "Ürün favorilere eklendi.",
            "favori": True
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route(
    "/favoriler/<int:urun_id>",
    methods=["DELETE"]
)
@musteri_bp.route(
    "/favori/<int:urun_id>",
    methods=["DELETE"]
)
@role_required("musteri")
def favori_sil(urun_id):
    try:
        musteri = aktif_musteri_getir()

        if not musteri:
            return jsonify({
                "hata": "Müşteri profili bulunamadı!"
            }), 404

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
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "hata": "Geçersiz sipariş verisi!"
            }), 400
        
        try:
            market_id = int(data.get("market_id", 1))
        except (TypeError, ValueError):
            return jsonify({
                "hata": "Geçersiz market kimliği!"
            }), 400

        if market_id <= 0:
            return jsonify({
                "hata": "Geçersiz market kimliği!"
            }), 400

        market = Market.query.get_or_404(market_id)

        if not market.aktif:
            return jsonify({
                "hata": "Bakkal şu an siparişe kapalıdır!"
            }), 400

        odeme_yontemi = data.get(
            "odeme_yontemi",
            "nakit"
        )

        izin_verilen_odeme_yontemleri = {
            "nakit",
            "kart"
        }

        if odeme_yontemi not in izin_verilen_odeme_yontemleri:
            return jsonify({
                "hata": "Geçersiz ödeme yöntemi!"
            }), 400

        musteri = aktif_musteri_getir()

        if not musteri:
            kullanici = Kullanici.query.get(kullanici_id)

            if not kullanici:
                return jsonify({
                    "hata": "Kullanıcı hesabı bulunamadı!"
                }), 404

            musteri = Musteri(
                kullanici_id=kullanici_id,
                ad_soyad=kullanici.email.split("@")[0].capitalize(),
                telefon="+905320000000",
                adres="Antakya Merkez / Hatay"
            )

            db.session.add(musteri)
            db.session.flush()

        istenen_kalemler = data.get("urunler", [])

        if not isinstance(istenen_kalemler, list):
            return jsonify({
                "hata": "Ürünler listesi geçersiz!"
            }), 400

        if not istenen_kalemler:
            return jsonify({
                "hata": "Sepetiniz boş!"
            }), 400

        urun_adetleri = {}

        for kalem in istenen_kalemler:
            if not isinstance(kalem, dict):
                return jsonify({
                    "hata": "Geçersiz sepet verisi!"
                }), 400

            try:
                urun_id = int(kalem.get("urun_id"))

                ham_miktar = kalem.get("adet")

                if (
                    ham_miktar in (None, "")
                    and "tutar" in kalem
                ):
                    ham_miktar = kalem.get("tutar")

                adet = siparis_miktarini_hazirla(
                    ham_miktar
                )

            except (TypeError, ValueError):
                return jsonify({
                    "hata": (
                        "Ürün kimliği veya adet "
                        "bilgisi geçersiz!"
                    )
                }), 400

            if adet <= 0:
                return jsonify({
                    "hata": (
                        "Ürün adedi sıfırdan "
                        "büyük olmalıdır!"
                    )
                }), 400

            urun_adetleri[urun_id] = (
                urun_adetleri.get(urun_id, 0) + adet
            )

        kontrol_edilmis_kalemler = []

        satir_toplamlari = {}

        for urun_id in sorted(urun_adetleri):
            toplam_adet = urun_adetleri[urun_id]
            urun = (
                Urun.query
                .filter_by(id=urun_id)
                .with_for_update()
                .first()
            )

            if (
                not urun
                or not urun.aktif
                or urun.market_id != market_id
            ):
                return jsonify({
                    "hata": (
                        "Ürün bulunamadı veya artık satışta değil "
                        f"(id: {urun_id})"
                    )
                }), 400

            satis_turu = (
                urun.satis_hesaplama_turu
                or "adet"
            )

            if satis_turu == "adet":
                if (
                    toplam_adet
                    != toplam_adet.to_integral_value()
                ):
                    return jsonify({
                        "hata": (
                            f"'{urun.ad}' adetle satılıyor; "
                            "küsuratlı miktar kullanılamaz."
                        )
                    }), 400

                toplam_adet = (
                    toplam_adet.to_integral_value()
                )

            elif satis_turu == "kg":
                yarim_kg_adimi = (
                    toplam_adet / Decimal("0.5")
                )

                if (
                    yarim_kg_adimi
                    != yarim_kg_adimi.to_integral_value()
                ):
                    return jsonify({
                        "hata": (
                            f"'{urun.ad}' ürünü için miktar "
                            "0,5 kg adımlarıyla seçilmelidir."
                        )
                    }), 400

            elif satis_turu == "tutar":
                hedef_tutar = (
                    siparis_tutarini_hazirla(
                        toplam_adet
                    )
                )

                toplam_adet = (
                    tutar_icin_kg_miktari_hazirla(
                        hedef_tutar,
                        urun.fiyat,
                        urun.stok_adet
                    )
                )

                satir_toplamlari[urun.id] = (
                    hedef_tutar
                )

            else:
                return jsonify({
                    "hata": (
                        f"'{urun.ad}' için geçersiz "
                        "satış biçimi."
                    )
                }), 400

            if urun.id not in satir_toplamlari:
                satir_toplamlari[urun.id] = (
                    urun.fiyat * toplam_adet
                )

            if urun.stok_adet < toplam_adet:
                return jsonify({
                    "hata": (
                        f"'{urun.ad}' için yeterli stok yok! "
                        f"İstenen: {toplam_adet}, "
                        f"mevcut stok: {urun.stok_adet}"
                    )
                }), 400

            kontrol_edilmis_kalemler.append(
                (urun, toplam_adet)
            )

        toplam = sum(
            satir_toplamlari[urun.id]
            for urun, adet in kontrol_edilmis_kalemler
        )

        minimum_tutar = (
            market.min_siparis_tutari or 0
        )

        if toplam < minimum_tutar:
            return jsonify({
                "hata": (
                    f"Minimum sipariş tutarı "
                    f"{minimum_tutar:.2f} TL'dir. "
                    f"Sepet toplamınız {toplam:.2f} TL."
                )
            }), 400

        siparis_notu = data.get("not", "")

        if not isinstance(siparis_notu, str):
            return jsonify({
                "hata": "Sipariş notu metin olmalıdır!"
            }), 400

        siparis_notu = siparis_notu.strip()

        if len(siparis_notu) > 500:
            return jsonify({
                "hata": "Sipariş notu en fazla 500 karakter olabilir!"
            }), 400

        yeni_siparis = Siparis(
            market_id=market_id,
            musteri_id=musteri.id,
            durum="bekliyor",
            odeme_yontemi=odeme_yontemi,
            teslimat_yontemi="adrese_teslim",
            siparis_notu=siparis_notu,
            toplam_tutar=toplam
        )

        db.session.add(yeni_siparis)
        db.session.flush()

        for urun, adet in kontrol_edilmis_kalemler:
            fiyat = urun.fiyat

            db.session.add(
                SiparisDetay(
                    siparis_id=yeni_siparis.id,
                    urun_id=urun.id,
                    adet=adet,
                    birim_fiyat=fiyat,
                    satis_hesaplama_turu=urun.satis_hesaplama_turu,
                    satir_toplami=(
                        satir_toplamlari[urun.id]
                    )
                )
            )

            urun.stok_adet = max(
                0,
                urun.stok_adet - adet
            )

            urun.aktif = urun.stok_adet > 0

        yeni_siparis.toplam_tutar = toplam

        db.session.commit()

        for urun, adet in kontrol_edilmis_kalemler:
            socketio.emit("urun_degisikligi", {
                "market_id": market_id,
                "urun_id": urun.id,
                "stok_adet": float(urun.stok_adet),
                "stok_durumu": (
                    "var"
                    if urun.stok_adet > 0
                    else "tukendi"
                )
            })

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

        return jsonify({
            "hata": f"Sipariş hatası: {str(e)}"
        }), 500


@musteri_bp.route("/yorum_ekle", methods=["POST"])
@role_required("musteri")
def yorum_ekle():
    try:
        data = request.get_json(silent=True) or {}
        
        # O an giriş yapmış olan müşteriyi buluyoruz
        musteri = aktif_musteri_getir()
        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        market_id = data.get("market_id")
        siparis_id = data.get("siparis_id")
        puan = data.get("puan")
        yorum_metni = data.get("yorum_metni", "")

        if not market_id or not puan:
            return jsonify({"hata": "Market ID ve puan zorunludur."}), 400

        try:
            puan = int(puan)
            if puan < 1 or puan > 5:
                raise ValueError
        except ValueError:
            return jsonify({"hata": "Puan 1 ile 5 arasında olmalıdır."}), 400

        # İsteğe bağlı güvenlik kontrolü: Eğer sipariş ID gönderilmişse, bu sipariş gerçekten bu müşteriye mi ait?
        if siparis_id:
            siparis = Siparis.query.get(siparis_id)
            if not siparis or siparis.musteri_id != musteri.id:
                return jsonify({"hata": "Geçersiz sipariş kimliği!"}), 403

        # Yorumu veritabanına ekle
        yeni_yorum = Yorum(
            market_id=market_id,
            musteri_id=musteri.id,
            siparis_id=siparis_id,
            puan=puan,
            yorum_metni=str(yorum_metni).strip()
        )
        
        db.session.add(yeni_yorum)
        db.session.commit()

        # 🔥 ŞOV KISMI: Market paneline (kasa) anlık bildirim fırlat
        socketio.emit("yeni_yorum_geldi", {"market_id": market_id})

        return jsonify({"mesaj": "Yorumunuz başarıyla gönderildi."}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Yorum kaydedilemedi: {str(e)}"}), 500