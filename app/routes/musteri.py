from flask import Blueprint, request, jsonify, session
from app import db,socketio
from app.models import Urun, Siparis, SiparisDetay, Musteri, Market,Kullanici

musteri_bp = Blueprint("musteri", __name__)

# YENİ ROTA: Müşteri dükkânın o an açık olup olmadığını ve min tutarını öğrenebilsin
# YENİ ROTA: Müşteri bakkalın harita konumunu ve servis yarıçapını öğrensin
@musteri_bp.route("/market-durum", methods=["GET"])
def market_durum_ogren():
    try:
        market_id = request.args.get("market_id", 1, type=int)
        m = Market.query.get_or_404(market_id)
        return jsonify({
            "ad": m.ad,
            "adres": m.adres,
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
        {"id": "yeni_urunler", "ad": "🔔 Yeni Ürünler", "resim": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=200&q=80"},
        {"id": "et_tavuk", "ad": "🥩 Et & Şarküteri", "resim": "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=200&q=80"},
        {"id": "meyve_sebze", "ad": "🍅 Meyve & Sebze", "resim": "https://images.unsplash.com/photo-1610348725531-843dff563e2c?auto=format&fit=crop&w=200&q=80"},
        {"id": "sut_kahvaltilik", "ad": "🧀 Süt & Kahvaltı", "resim": "https://images.unsplash.com/photo-1628088062854-d1870b4553da?auto=format&fit=crop&w=200&q=80"},
        {"id": "atistirmalik", "ad": "🍟 Atıştırmalık", "resim": "https://images.unsplash.com/photo-1599490659213-e2b9527bd087?auto=format&fit=crop&w=200&q=80"},
        {"id": "icecek", "ad": "🥤 İçecekler", "resim": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=200&q=80"},
        {"id": "ekmek_pastane", "ad": "🍞 Ekmek & Pastane", "resim": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=200&q=80"},
        {"id": "temizlik", "ad": "🧼 Temizlik", "resim": "https://images.unsplash.com/photo-1585816019848-7314a1a6b0c9?auto=format&fit=crop&w=200&q=80"}
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
        return jsonify([{
            "id": u.id,
            "ad": u.ad,
            "aciklama": u.aciklama,
            "fiyat": float(u.fiyat),
            "resim_url": u.resim_url,
            "max_alinabilir_adet": u.stok_adet,
            "stok_durumu": "var" if u.stok_adet > 0 else "tukendi"
        } for u in urunler])
    except Exception as e:
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/siparisler", methods=["GET"])
def musteri_siparislerini_getir():
    try:
        kullanici_id = session.get("kullanici_id")
        if not kullanici_id:
            return jsonify({"hata": "Oturum açmanız gerekiyor!"}), 401

        musteri = Musteri.query.filter_by(kullanici_id=kullanici_id).first()
        if not musteri:
            return jsonify({"hata": "Müşteri profili bulunamadı!"}), 404

        siparisler = Siparis.query.filter_by(musteri_id=musteri.id).order_by(Siparis.olusturma_tarihi.desc()).all()

        sonuc = []
        for s in siparisler:
            kalemler = [{
                "ad": d.urun.ad if d.urun else "Silinmiş Ürün",
                "adet": d.adet,
                "birim_fiyat": float(d.birim_fiyat)
            } for d in s.detaylar]

            sonuc.append({
                "id": s.id,
                "durum": s.durum,
                "odeme_yontemi": s.odeme_yontemi,
                "teslimat_yontemi": s.teslimat_yontemi,
                "toplam_tutar": float(s.toplam_tutar),
                "tarih": s.olusturma_tarihi.strftime("%d.%m.%Y %H:%M") if s.olusturma_tarihi else "",
                "detaylar": kalemler
            })

        return jsonify(sonuc), 200
    except Exception as e:
        return jsonify({"hata": f"Siparişler çekilemedi: {str(e)}"}), 500


# YENİ ROTA: Müşteri henüz poşetlenmemiş (bekliyor) siparişini iptal edebilsin
@musteri_bp.route("/siparisler/<int:siparis_id>/iptal", methods=["POST"])
def musteri_siparis_iptal(siparis_id):
    try:
        kullanici_id = session.get("kullanici_id")
        musteri = Musteri.query.filter_by(kullanici_id=kullanici_id).first() if kullanici_id else None
        
        siparis = Siparis.query.get_or_404(siparis_id)
        if not musteri or siparis.musteri_id != musteri.id:
            return jsonify({"hata": "Bu siparişi iptal etme yetkiniz yok!"}), 403

        if siparis.durum != "bekliyor":
            return jsonify({"hata": "Hazırlanmaya başlanmış veya yola çıkmış sipariş iptal edilemez. Lütfen bakkalı arayın."}), 400

        siparis.durum = "iptal"
        # Stokları geri koy
        for detay in siparis.detaylar:
            if detay.urun:
                detay.urun.stok_adet += detay.adet
                if detay.urun.stok_adet > 0: detay.urun.aktif = True

        db.session.commit()
        return jsonify({"mesaj": "Siparişiniz iptal edildi ve stoklar iade edildi."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": str(e)}), 500


@musteri_bp.route("/siparis", methods=["POST"])
def siparis_olustur():
    try:
        kullanici_id = session.get("kullanici_id")

        # 🔒 DÜZELTME: Oturum yoksa artık otomatik bir kullanıcıya atanmıyor.
        # Eskiden buradaki bypass, oturum açmamış herhangi birinin en son
        # kayıt olan müşteri hesabı üzerinden sipariş vermesine izin veriyordu.
        if not kullanici_id:
            return jsonify({"hata": "Lütfen sipariş vermek için önce giriş yapın!"}), 401

        data = request.get_json(silent=True) or {}
        market_id = data.get("market_id", 1)

        # Müşteri Profilini Bul veya Otomatik Tanımla
        musteri = Musteri.query.filter_by(kullanici_id=kullanici_id).first()
        if not musteri:
            kullanici = Kullanici.query.get(kullanici_id)
            musteri = Musteri(
                kullanici_id=kullanici_id,
                ad_soyad=kullanici.email.split("@")[0].capitalize(),
                telefon="05320000000",
                adres="Antakya Merkez / Hatay"
            )
            db.session.add(musteri)
            db.session.flush()

        # Sipariş kalemlerini önce kontrol et (stok yeterli mi?)
        istenen_kalemler = data.get("urunler", [])
        if not istenen_kalemler:
            return jsonify({"hata": "Sepetiniz boş!"}), 400

        kontrol_edilmis_kalemler = []
        for kalem in istenen_kalemler:
            urun = Urun.query.get(kalem.get("urun_id"))
            if not urun or not urun.aktif:
                return jsonify({"hata": f"Ürün bulunamadı veya artık satışta değil (id: {kalem.get('urun_id')})"}), 400

            adet = int(kalem.get("adet", 0))
            if adet <= 0:
                return jsonify({"hata": f"'{urun.ad}' için geçersiz adet!"}), 400

            # 🔒 DÜZELTME: Stok yetersizse sipariş sessizce kabul edilmiyor, reddediliyor.
            if urun.stok_adet < adet:
                return jsonify({
                    "hata": f"'{urun.ad}' için yeterli stok yok! Mevcut stok: {urun.stok_adet}"
                }), 400

            kontrol_edilmis_kalemler.append((urun, adet))

        # Sipariş Kaydı
        yeni_siparis = Siparis(
            market_id=market_id,
            musteri_id=musteri.id,
            durum="bekliyor",
            odeme_yontemi=data.get("odeme_yontemi", "nakit"),
            teslimat_yontemi=data.get("teslimat_yontemi", "adrese_teslim"),
            siparis_notu=data.get("not", ""),
            toplam_tutar=0.0
        )
        db.session.add(yeni_siparis)
        db.session.flush()

        toplam = 0.0
        for urun, adet in kontrol_edilmis_kalemler:
            fiyat = float(urun.fiyat)
            toplam += fiyat * adet
            detay = SiparisDetay(
                siparis_id=yeni_siparis.id,
                urun_id=urun.id,
                adet=adet,
                birim_fiyat=fiyat
            )
            db.session.add(detay)
            urun.stok_adet -= adet
            if urun.stok_adet <= 0:
                urun.aktif = False

        yeni_siparis.toplam_tutar = toplam
        db.session.commit()

        # Canlı Sinyal
        socketio.emit("yeni_siparis_geldi", {"market_id": market_id, "siparis_id": yeni_siparis.id})

        return jsonify({"mesaj": "Siparişiniz başarıyla alındı!", "id": yeni_siparis.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": f"Sipariş hatası: {str(e)}"}), 500