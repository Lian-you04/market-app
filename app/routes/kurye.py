from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app import db
from app.models import Siparis, NakitTahsilat, Kurye

kurye_bp = Blueprint("kurye", __name__)


@kurye_bp.route("/atanan-siparisler", methods=["GET"])
def atanan_siparisler():
    kurye_id = request.args.get("kurye_id", type=int)
    if not kurye_id:
        return jsonify({"hata": "kurye_id gerekli"}), 400

    siparisler = (
        Siparis.query.filter_by(kurye_id=kurye_id)
        .filter(Siparis.durum.in_(["hazirlaniyor", "yolda"]))
        .all()
    )
    return jsonify([
        {
            "id": s.id,
            "durum": s.durum,
            "odeme_yontemi": s.odeme_yontemi,
            "toplam_tutar": float(s.toplam_tutar),
            "musteri_id": s.musteri_id,
        }
        for s in siparisler
    ])


@kurye_bp.route("/siparis/<int:siparis_id>/durum", methods=["PUT"])
def siparis_durum_guncelle(siparis_id):
    siparis = Siparis.query.get_or_404(siparis_id)
    yeni_durum = request.json.get("durum")

    if yeni_durum not in ("yolda", "teslim_edildi"):
        return jsonify({"hata": "Kurye sadece 'yolda' ya da 'teslim_edildi' yapabilir"}), 400

    # Çift işlem koruması: Sipariş zaten teslim edildiyse tekrar işlem yapmasın
    if siparis.durum == "teslim_edildi":
        return jsonify({"hata": "Bu sipariş zaten teslim edilmiş!"}), 400

    try:
        siparis.durum = yeni_durum

        if yeni_durum == "teslim_edildi":
            # 1. Kuryeyi müsait duruma getir
            if siparis.kurye_id:
                kurye = Kurye.query.get(siparis.kurye_id)
                if kurye:
                    kurye.durum = "musait"

            # 2. OTOMASYON: Ödeme yöntemi nakit ise otomatik tahsilat kaydı oluştur
            if siparis.odeme_yontemi == "nakit" and siparis.kurye_id:
                # Daha önce bu sipariş için tahsilat oluşmuş mu diye garanti kontrolü
                mevcut_tahsilat = NakitTahsilat.query.filter_by(siparis_id=siparis.id).first()
                if not mevcut_tahsilat:
                    yeni_tahsilat = NakitTahsilat(
                        kurye_id=siparis.kurye_id,
                        siparis_id=siparis.id,
                        tutar=siparis.toplam_tutar,
                        tarih=datetime.now(timezone.utc),
                        markete_teslim_edildi=False,
                    )
                    db.session.add(yeni_tahsilat)

        db.session.commit()
        return jsonify({"mesaj": f"Siparis '{yeni_durum}' olarak güncellendi"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": "Sipariş durumu güncellenirken bir hata oluştu.", "detay": str(e)}), 500


@kurye_bp.route("/nakit-tahsilat", methods=["POST"])
def nakit_tahsilat_kaydet():
    """
    Not: Kurye siparişi 'teslim_edildi' yaptığında nakit tahsilat otomatik oluşur.
    Ancak manuel ekleme gerekirse diye bu endpoint korunmuş ve hatalara karşı güçlendirilmiştir.
    """
    data = request.json
    if not all(k in data for k in ("kurye_id", "siparis_id", "tutar")):
        return jsonify({"hata": "kurye_id, siparis_id ve tutar alanları zorunludur"}), 400

    try:
        tahsilat = NakitTahsilat(
            kurye_id=data["kurye_id"],
            siparis_id=data["siparis_id"],
            tutar=data["tutar"],
            tarih=datetime.now(timezone.utc),
            markete_teslim_edildi=False,
        )
        db.session.add(tahsilat)
        db.session.commit()
        return jsonify({"id": tahsilat.id, "mesaj": "Nakit tahsilat kaydedildi"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"hata": "Tahsilat kaydedilemedi.", "detay": str(e)}), 500


@kurye_bp.route("/gun-sonu-ozet", methods=["GET"])
def gun_sonu_ozet():
    kurye_id = request.args.get("kurye_id", type=int)
    if not kurye_id:
        return jsonify({"hata": "kurye_id gerekli"}), 400

    bugun = datetime.now(timezone.utc).date()
    tahsilatlar = (
        NakitTahsilat.query.filter_by(kurye_id=kurye_id)
        .filter(db.func.date(NakitTahsilat.tarih) == bugun)
        .all()
    )

    toplam = sum(float(t.tutar) for t in tahsilatlar)
    teslim_edilmeyen = sum(
        float(t.tutar) for t in tahsilatlar if not t.markete_teslim_edildi
    )

    return jsonify({
        "toplam_toplanan": toplam,
        "markete_teslim_edilmeyen": teslim_edilmeyen,
        "islem_sayisi": len(tahsilatlar),
    })