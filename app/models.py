from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class Kullanici(db.Model):
    __tablename__ = "kullanici"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    sifre_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False)  # 'musteri', 'market', 'kurye'
    olusturma_tarihi = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    aktif = db.Column(db.Boolean, default=True)

    market = db.relationship("Market", backref="kullanici", uselist=False, cascade="all, delete-orphan")
    musteri = db.relationship("Musteri", backref="kullanici", uselist=False, cascade="all, delete-orphan")
    kurye = db.relationship("Kurye", backref="kullanici", uselist=False, cascade="all, delete-orphan")

    def sifre_belirle(self, sifre):
        self.sifre_hash = generate_password_hash(sifre)

    def sifre_kontrol(self, sifre):
        return check_password_hash(self.sifre_hash, sifre)


class Market(db.Model):
    __tablename__ = "market"

    id = db.Column(db.Integer, primary_key=True)
    kullanici_id = db.Column(db.Integer, db.ForeignKey("kullanici.id"), unique=True, nullable=True)
    ad = db.Column(db.String(120), nullable=False)
    adres = db.Column(db.String(255))
    telefon = db.Column(db.String(20))
    resim_url = db.Column(db.String(255), default="https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=400&q=80")
    
    konum_lat = db.Column(db.Float, default=36.2000)
    konum_lon = db.Column(db.Float, default=36.1500)
    maks_teslimat_km = db.Column(db.Float, default=5.0)  # Marketin maksimum servis yarıçapı
    
    min_siparis_tutari = db.Column(db.Numeric(10, 2), default=50.00)
    aktif = db.Column(db.Boolean, default=True)

    urunler = db.relationship("Urun", backref="market", lazy=True, cascade="all, delete-orphan")
    siparisler = db.relationship("Siparis", backref="market", lazy=True)


class Urun(db.Model):
    __tablename__ = "urun"

    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey("market.id"), nullable=False)
    ad = db.Column(db.String(120), nullable=False)
    aciklama = db.Column(db.String(255), default="")
    fiyat = db.Column(db.Numeric(10, 2), nullable=False)
    stok_adet = db.Column(db.Integer, default=0)
    kategori = db.Column(db.String(60), nullable=False)
    resim_url = db.Column(db.String(255), default="https://images.unsplash.com/photo-1583258292688-d0213dc5a3a8?auto=format&fit=crop&w=300&q=80")
    aktif = db.Column(db.Boolean, default=True)


class Musteri(db.Model):
    __tablename__ = "musteri"

    id = db.Column(db.Integer, primary_key=True)
    kullanici_id = db.Column(db.Integer, db.ForeignKey("kullanici.id"), unique=True, nullable=True)
    ad_soyad = db.Column(db.String(120), nullable=False)
    telefon = db.Column(db.String(20), nullable=False)
    adres = db.Column(db.String(255))
    konum_lat = db.Column(db.Float, default=36.1950)
    konum_lon = db.Column(db.Float, default=36.1450)

    siparisler = db.relationship("Siparis", backref="musteri", lazy=True)


class Kurye(db.Model):
    __tablename__ = "kurye"

    id = db.Column(db.Integer, primary_key=True)
    kullanici_id = db.Column(db.Integer, db.ForeignKey("kullanici.id"), unique=True, nullable=True)
    ad_soyad = db.Column(db.String(120), nullable=False)
    telefon = db.Column(db.String(20), nullable=False)
    durum = db.Column(db.String(20), default="musait")  # musait / mesgul
    
    # Kuryenin anlık konumu ve hizmet yarıçapı
    konum_lat = db.Column(db.Float, default=36.1980)
    konum_lon = db.Column(db.Float, default=36.1480)
    calisma_yaricap_km = db.Column(db.Float, default=7.0)

    siparisler = db.relationship("Siparis", backref="kurye", lazy=True)


class Siparis(db.Model):
    __tablename__ = "siparis"

    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey("market.id"), nullable=False)
    musteri_id = db.Column(db.Integer, db.ForeignKey("musteri.id"), nullable=False)
    kurye_id = db.Column(db.Integer, db.ForeignKey("kurye.id"), nullable=True)

    durum = db.Column(db.String(20), default="bekliyor")
    odeme_yontemi = db.Column(db.String(10), nullable=False)
    toplam_tutar = db.Column(db.Numeric(10, 2), default=0)
    olusturma_tarihi = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    detaylar = db.relationship("SiparisDetay", backref="siparis", lazy=True, cascade="all, delete-orphan")
    nakit_tahsilatlar = db.relationship("NakitTahsilat", backref="siparis", lazy=True, cascade="all, delete-orphan")


class SiparisDetay(db.Model):
    __tablename__ = "siparis_detay"

    id = db.Column(db.Integer, primary_key=True)
    siparis_id = db.Column(db.Integer, db.ForeignKey("siparis.id"), nullable=False)
    urun_id = db.Column(db.Integer, db.ForeignKey("urun.id"), nullable=False)
    adet = db.Column(db.Integer, nullable=False)
    birim_fiyat = db.Column(db.Numeric(10, 2), nullable=False)

    urun = db.relationship("Urun")


class NakitTahsilat(db.Model):
    __tablename__ = "nakit_tahsilat"

    id = db.Column(db.Integer, primary_key=True)
    kurye_id = db.Column(db.Integer, db.ForeignKey("kurye.id"), nullable=False)
    siparis_id = db.Column(db.Integer, db.ForeignKey("siparis.id"), nullable=False)
    tutar = db.Column(db.Numeric(10, 2), nullable=False)
    tarih = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    markete_teslim_edildi = db.Column(db.Boolean, default=False)