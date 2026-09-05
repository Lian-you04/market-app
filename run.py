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


with app.app_context():
    db.create_all()
    eksik_siparis_sutunlarini_ekle()


if __name__ == "__main__":
    debug_modu = os.environ.get("FLASK_DEBUG", "0") == "1"

    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=debug_modu
    )