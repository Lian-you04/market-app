# bakkal_ekle.py - Sadece Sistem Yöneticisi (Sen) Terminalden Çalıştırabilir!
from app import create_app, db
from app.models import Kullanici, Market

app = create_app()

with app.app_context():
    email = "ahmetamca@kosebasimarket.com"
    sifre = "HatayBakkal2026!"
    dükkan_adi = "Nihat Market"

    # Daha önce eklenmiş mi?
    mevcut = Kullanici.query.filter_by(email=email).first()
    if mevcut:
        print("⚠️ Bu bakkal hesabı zaten mevcut!")
    else:
        kullanici = Kullanici(email=email, rol="market", aktif=True)
        kullanici.sifre_belirle(sifre)
        db.session.add(kullanici)
        db.session.flush()

        market = Market(
            kullanici_id=kullanici.id,
            ad=dükkan_adi,
            adres="Sümerler Mah. Antakya/Hatay",
            telefon="05551234567"
        )
        db.session.add(market)
        db.session.commit()
        print(f"🎉 Bakkal hesabı oluşturuldu! Giriş: {email} | Şifre: {sifre}")