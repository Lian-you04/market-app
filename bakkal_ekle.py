# bakkal_ekle.py - Sadece sistem yöneticisi terminalden çalıştırır.

from app import create_app, db
from app.models import Kullanici, Market

app = create_app()

with app.app_context():
    email = "ahmetamca@kosebasimarket.com"
    sifre = "HatayBakkal2026!"
    dukkan_adi = "Köşebaşı Mahalle Bakkalı"

    mevcut_market_sayisi = Market.query.count()

    if mevcut_market_sayisi > 0:
        print("⚠️ Sistemde zaten bir bakkal/market var. İkinci market oluşturulamaz.")
    else:
        mevcut_kullanici = Kullanici.query.filter_by(email=email).first()

        if mevcut_kullanici:
            print("⚠️ Bu e-posta adresi zaten kullanılıyor.")
        else:
            kullanici = Kullanici(
                email=email,
                rol="market",
                aktif=True
            )
            kullanici.sifre_belirle(sifre)

            db.session.add(kullanici)
            db.session.flush()

            market = Market(
                kullanici_id=kullanici.id,
                ad=dukkan_adi,
                adres="https://maps.app.goo.gl/CPR7e1GN8gCaBfLs6",
                telefon="05551234567"
            )

            db.session.add(market)
            db.session.commit()

            print("🎉 Tek bakkal hesabı oluşturuldu.")
            print(f"Giriş e-postası: {email}")
            print(f"Şifre: {sifre}")
            print(f"Market konumu: {market.adres}")
            print(f"Koordinat: {market.konum_lat}, {market.konum_lon}")