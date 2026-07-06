from app import create_app, db, socketio
import os

app = create_app()

with app.app_context():
    # Tabloları oluştur (yoksa). Market hesabı burada OLUŞTURULMUYOR.
    # Market/bakkal hesabı yönetimi tamamen bakkal_ekle.py'ye ait —
    # tek bir yerden, tek bir şekilde kontrol edilsin diye.
    db.create_all()

if __name__ == "__main__":
    debug_modu = os.environ.get("FLASK_DEBUG", "0") == "1"
    socketio.run(app, host="0.0.0.0", port=5000, debug=debug_modu)