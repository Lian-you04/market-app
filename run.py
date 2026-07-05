from app import db, create_app

app = create_app()

# Gunicorn işçileri paralel ayağa kalkmadan hemen önce, 
# ana master işlem üzerinden tabloları ve seed verilerini güvenle tek bir kez kuruyoruz:
with app.app_context():
    from app import models
    db.create_all()

    # 1. Varsayılan Market Yoksa Ekle
    if not models.Market.query.get(1):
        db.session.add(models.Market(
            id=1, ad="Köşebaşı Market (Merkez Şube)", adres="Antakya / Hatay",
            telefon="0532 000 00 00", konum_lat=36.2000, konum_lon=36.1500, maks_teslimat_km=15.0, aktif=True
        ))

    # 2. Varsayılan Müşteri Yoksa Ekle
    if not models.Musteri.query.get(1):
        db.session.add(models.Musteri(
            id=1, ad_soyad="Varsayılan Mahalle Müşterisi", telefon="0500 000 00 00",
            adres="Antakya Merkez", konum_lat=36.1950, konum_lon=36.1450
        ))

    # 3. Varsayılan Kurye Yoksa Ekle
    if not models.Kurye.query.get(1):
        db.session.add(models.Kurye(
            id=1, ad_soyad="Ahmet Kurye (Express)", telefon="0544 000 00 00",
            durum="musait", konum_lat=36.1980, konum_lon=36.1480, calisma_yaricap_km=10.0
        ))

    try:
        db.session.commit()
        print("Sistem başlangıç verileri (Seed Data) başarıyla yüklendi!")
    except Exception as e:
        db.session.rollback()
        print(f"Başlangıç verisi yükleme hatası: {str(e)}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)