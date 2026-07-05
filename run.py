from app import create_app, db
from app.models import Market, Musteri, Kurye

app = create_app()


def demo_verisi_olustur():
    """İlk çalıştırmada demo market/müşteri/kurye kaydı oluşturur (id=1)."""
    if not Market.query.get(1):
        db.session.add(Market(id=1, ad="Köşebaşı Market", adres="Antakya, Hatay", telefon="0000000000"))
    if not Musteri.query.get(1):
        db.session.add(Musteri(id=1, ad_soyad="Demo Müşteri", telefon="0000000000", adres="Antakya"))
    if not Kurye.query.get(1):
        db.session.add(Kurye(id=1, ad_soyad="Onur K.", telefon="0000000000", durum="musait"))
    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # tablolar yoksa olustur
        demo_verisi_olustur()
    app.run(host="0.0.0.0", port=5000, debug=True)