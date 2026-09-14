from app import create_app, db, socketio
from sqlalchemy import inspect, text
import os

app = create_app()

def eksik_siparis_sutunlarini_ekle():
    inspector = inspect(db.engine)

    mevcut_sutunlar = {
        sutun["name"]
        for sutun in inspector.get_columns("siparisler")
    }

    with db.engine.begin() as connection:
        if "karar_tarihi" not in mevcut_sutunlar:
            connection.execute(text(
                "ALTER TABLE siparisler "
                "ADD COLUMN karar_tarihi DATETIME NULL"
            ))

        if "red_sebebi" not in mevcut_sutunlar:
            connection.execute(text(
                "ALTER TABLE siparisler "
                "ADD COLUMN red_sebebi TEXT NULL"
            ))


def eksik_satis_sutunlarini_ekle():
    with db.engine.begin() as connection:
        inspector = inspect(connection)

        urun_sutunlari = {
            sutun["name"]
            for sutun in inspector.get_columns("urunler")
        }

        detay_sutunlari = {
            sutun["name"]
            for sutun in inspector.get_columns(
                "siparis_detaylari"
            )
        }

        if "satis_hesaplama_turu" not in urun_sutunlari:
            connection.execute(text(
                "ALTER TABLE urunler "
                "ADD COLUMN satis_hesaplama_turu "
                "VARCHAR(20) NOT NULL DEFAULT 'adet'"
            ))

        if "satis_hesaplama_turu" not in detay_sutunlari:
            connection.execute(text(
                "ALTER TABLE siparis_detaylari "
                "ADD COLUMN satis_hesaplama_turu "
                "VARCHAR(20) NOT NULL DEFAULT 'adet'"
            ))

        if "satir_toplami" not in detay_sutunlari:
            connection.execute(text(
                "ALTER TABLE siparis_detaylari "
                "ADD COLUMN satir_toplami DECIMAL(10, 2) NULL"
            ))

        connection.execute(text(
            "UPDATE siparis_detaylari "
            "SET satir_toplami = birim_fiyat * adet "
            "WHERE satir_toplami IS NULL "
            "AND satis_hesaplama_turu = 'adet'"
        ))


def miktar_sutun_tiplerini_guncelle():
    with db.engine.begin() as connection:
        inspector = inspect(connection)

        urun_sutunlari = {
            sutun["name"]: sutun
            for sutun in inspector.get_columns("urunler")
        }

        detay_sutunlari = {
            sutun["name"]: sutun
            for sutun in inspector.get_columns(
                "siparis_detaylari"
            )
        }

        stok_tipi = str(
            urun_sutunlari["stok_adet"]["type"]
        ).upper()

        if (
            "DECIMAL" not in stok_tipi
            and "NUMERIC" not in stok_tipi
        ):
            connection.execute(text(
                "ALTER TABLE urunler "
                "MODIFY COLUMN stok_adet "
                "DECIMAL(16, 6) NULL DEFAULT 0"
            ))

        adet_tipi = str(
            detay_sutunlari["adet"]["type"]
        ).upper()

        if (
            "DECIMAL" not in adet_tipi
            and "NUMERIC" not in adet_tipi
        ):
            connection.execute(text(
                "ALTER TABLE siparis_detaylari "
                "MODIFY COLUMN adet "
                "DECIMAL(16, 6) NOT NULL"
            ))


with app.app_context():
    db.create_all()
    eksik_siparis_sutunlarini_ekle()
    eksik_satis_sutunlarini_ekle()
    miktar_sutun_tiplerini_guncelle()


if __name__ == "__main__":
    debug_modu = os.environ.get("FLASK_DEBUG", "0") == "1"

    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=debug_modu
    )