from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

# 1. EN ÜST HİYERARŞİ: KULLANICILAR TABLOSU
class Kullanici(db.Model):
    __tablename__ = "kullanicilar"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    sifre_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False)  # 'market' veya 'musteri'
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    aktif = db.Column(db.Boolean, default=True) 

    def sifre_belirle(self, sifre):
        self.sifre_hash = generate_password_hash(sifre)

    def sifre_dogrula(self, sifre):
        return check_password_hash(self.sifre_hash, sifre)

    # 🚀 ÇÖZÜM BURADA: auth.py dosyası hata vermesin diye ikinci bir isim (alias) ekliyoruz!
    def sifre_kontrol(self, sifre):
        return check_password_hash(self.sifre_hash, sifre)


# 2. HİYERARŞİ: MARKETLER TABLOSU (kullanicilar tablosuna bağlı)
class Market(db.Model):
    __tablename__ = "marketler"
    id = db.Column(db.Integer, primary_key=True)
    kullanici_id = db.Column(db.Integer, db.ForeignKey("kullanicilar.id"), nullable=True)
    ad = db.Column(db.String(100), nullable=False)
    adres = db.Column(db.Text, nullable=False)
    telefon = db.Column(db.String(20), nullable=False)
    
    # Harita Koordinatları ve Servis Sınırları (Antakya/Hatay Merkezli)
    konum_lat = db.Column(db.Float, default=36.2000)
    konum_lon = db.Column(db.Float, default=36.1500)
    maks_teslimat_km = db.Column(db.Float, default=3.0)
    min_siparis_tutari = db.Column(db.Numeric(10, 2), default=50.00)
    aktif = db.Column(db.Boolean, default=True)

    kullanici = db.relationship("Kullanici", backref="market")
    urunler = db.relationship("Urun", backref="market", cascade="all, delete-orphan")


# 3. HİYERARŞİ: MÜŞTERİLER TABLOSU (kullanicilar tablosuna bağlı)
class Musteri(db.Model):
    __tablename__ = "musteriler"
    id = db.Column(db.Integer, primary_key=True)
    kullanici_id = db.Column(db.Integer, db.ForeignKey("kullanicilar.id"), nullable=True)
    ad_soyad = db.Column(db.String(100), nullable=False)
    telefon = db.Column(db.String(20), nullable=False)
    adres = db.Column(db.Text, nullable=False)
    konum_lat = db.Column(db.Float, default=36.1950)
    konum_lon = db.Column(db.Float, default=36.1450)

    kullanici = db.relationship("Kullanici", backref="musteri")


# 4. HİYERARŞİ: ÜRÜNLER TABLOSU (marketler tablosuna bağlı)
class Urun(db.Model):
    __tablename__ = "urunler"
    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey("marketler.id"), nullable=False)
    ad = db.Column(db.String(100), nullable=False)
    aciklama = db.Column(db.Text, nullable=True)
    fiyat = db.Column(db.Numeric(10, 2), nullable=False)
    stok_adet = db.Column(db.Integer, default=0)
    kategori = db.Column(db.String(50), nullable=False)
    resim_url = db.Column(db.Text, nullable=True)
    aktif = db.Column(db.Boolean, default=True)


# 5. HİYERARŞİ: SİPARİŞLER TABLOSU (marketler ve musteriler tablosuna bağlı)
class Siparis(db.Model):
    __tablename__ = "siparisler"
    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey("marketler.id"), nullable=False)
    musteri_id = db.Column(db.Integer, db.ForeignKey("musteriler.id"), nullable=False)
    durum = db.Column(db.String(20), default="bekliyor")  # bekliyor, hazirlaniyor, yolda, teslim_edildi, iptal
    odeme_yontemi = db.Column(db.String(20), nullable=False)  # nakit, kart
    teslimat_yontemi = db.Column(db.String(20), nullable=False)  # adrese_teslim, gel_al
    siparis_notu = db.Column(db.Text, nullable=True)
    toplam_tutar = db.Column(db.Numeric(10, 2), nullable=False)
    olusturma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    market = db.relationship("Market", backref="siparisler")
    musteri = db.relationship("Musteri", backref="siparisler")
    detaylar = db.relationship("SiparisDetay", backref="siparis", cascade="all, delete-orphan")


# 6. EN ALT HİYERARŞİ: SİPARİŞ DETAYLARI TABLOSU (siparisler ve urunler tablosuna bağlı)
class SiparisDetay(db.Model):
    __tablename__ = "siparis_detaylari"
    id = db.Column(db.Integer, primary_key=True)
    siparis_id = db.Column(db.Integer, db.ForeignKey("siparisler.id"), nullable=False)
    urun_id = db.Column(db.Integer, db.ForeignKey("urunler.id"), nullable=False)
    adet = db.Column(db.Integer, nullable=False)
    birim_fiyat = db.Column(db.Numeric(10, 2), nullable=False)

    urun = db.relationship("Urun")