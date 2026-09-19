# Market Sipariş Sistemi

Market sahipleri ile müşterileri buluşturan, gerçek zamanlı sipariş, stok ve raporlama özelliklerine sahip Flask tabanlı market uygulaması.

Bu proje; market yönetim panelini, müşteri alışveriş ekranını, canlı sipariş bildirimlerini, ürün ve stok yönetimini, raporları ve PWA desteğini tek bir sistemde birleştirir.

## Özellikler

### Market paneli

* Dashboard ve satış özeti
* Günlük, haftalık, aylık ve yıllık raporlar
* Ciro, sipariş ve ortalama sepet istatistikleri
* En çok satan ürünler
* Müşteri ve stok raporları
* Canlı sipariş bildirimleri
* Siparişleri onaylama veya reddetme
* Ürün ekleme, güncelleme ve silme
* Ürün fotoğrafı ekleme
* Kategori yönetimi
* Stok yönetimi
* Ürünleri ad, fiyat ve stok miktarına göre sıralama
* Market adı, telefon ve adres bilgilerini güncelleme
* Minimum sipariş tutarı belirleme
* Marketi online siparişlere açma veya kapatma
* Açık/koyu tema seçimi
* Bildirim sesi ve ses seviyesi ayarları
* Günlük raporların İstanbul saat dilimine göre otomatik yenilenmesi

### Müşteri ekranı

* Market ürünlerini görüntüleme
* Kategoriye göre filtreleme
* Ürün detaylarını ve fotoğraflarını görüntüleme
* Ürünleri sepete ekleme
* Adet, kilogram ve tutar bazlı satış türleri
* Nakit veya kart ödeme tercihi
* Adrese teslim veya gel-al seçimi
* Sipariş notu ekleme
* Sipariş oluşturma
* Sipariş durumunu canlı takip etme
* Marketin açık/kapalı durumunu canlı görme
* Ürün ve stok değişikliklerini sayfa yenilemeden görme
* Stok azaldığında sepet miktarını otomatik güncelleme
* Sepet ve kategori sayfalarında yenileme sonrası mevcut sayfada kalma

## Satış türleri

Ürün bazında üç farklı satış türü desteklenir:

* `adet`: Tam sayı üzerinden ürün satışı
* `kg`: 0,5 kg adımlarıyla ağırlık bazlı satış
* `tutar`: Girilen TL tutarına göre yaklaşık miktar hesaplama

Satış türü kategoriye değil, doğrudan ürüne bağlıdır.

## Gerçek zamanlı özellikler

Uygulamada Flask-SocketIO kullanılmaktadır.

Aşağıdaki işlemler sayfa yenilenmeden güncellenir:

* Yeni sipariş bildirimi
* Sipariş durumunun değişmesi
* Ürün ve stok değişiklikleri
* Marketin online/offline durumu
* Müşteri tarafındaki ürün listesi
* Dashboard satış ve ciro verileri
* Market adı değişikliği

## Sipariş durumları

* `bekliyor`
* `onaylandi`
* `reddedildi`

## PWA desteği

Müşteri ekranı Progressive Web App özelliklerini destekler.

* Web App Manifest
* Service Worker
* Uygulama olarak yükleme desteği
* Mobil cihazlarda uygulama görünümü
* PWA ikonları
* Shell sayfası önbellekleme

PWA özellikleri localhost veya HTTPS üzerinden çalışır.

## Kullanılan teknolojiler

* Python 3.11
* Flask
* Flask-SQLAlchemy
* MySQL 8
* Flask-SocketIO
* Eventlet
* Docker
* Docker Compose
* HTML
* CSS
* JavaScript
* Progressive Web App

## Uygulamayı çalıştırma

### Gereksinimler

* Docker Desktop
* Git

### Kurulum

```bash
git clone https://github.com/Lian-you04/market-app.git
cd market-app
docker compose up -d --build
```

Container durumunu kontrol etmek için:

```bash
docker compose ps
```

Uygulama adresleri:

* Giriş: http://localhost:5002/login
* Müşteri ekranı: http://localhost:5002/musteri
* Market paneli: http://localhost:5002/market
* Sağlık kontrolü: http://localhost:5002/health

Uygulamayı durdurmak için:

```bash
docker compose down
```

## Zaman dilimi

Sipariş tarihleri, saatleri, raporlar ve dashboard grafiklerinde İstanbul zaman dilimi (`Europe/Istanbul`) kullanılır.

## Temel API uçları

### Kimlik doğrulama

```text
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/register
```

### Market API

```text
GET    /api/market/durum
PUT    /api/market/durum
GET    /api/market/urunler
POST   /api/market/urunler
PUT    /api/market/urunler/<urun_id>
DELETE /api/market/urunler/<urun_id>
GET    /api/market/siparisler
GET    /api/market/raporlar
GET    /api/market/raporlar/genel-bakis
GET    /api/market/raporlar/satis-analizi
GET    /api/market/raporlar/urun-kategori
GET    /api/market/raporlar/musteriler
GET    /api/market/raporlar/stok
```

### Müşteri API

```text
GET  /api/musteri/urunler
GET  /api/musteri/kategoriler
GET  /api/musteri/market-durum
POST /api/musteri/siparis
GET  /api/musteri/siparisler
```

## Örnek sipariş isteği

```json
{
  "market_id": 1,
  "musteri_id": 1,
  "odeme_yontemi": "nakit",
  "teslimat_yontemi": "adrese_teslim",
  "urunler": [
    {
      "urun_id": 1,
      "adet": 2
    }
  ],
  "siparis_notu": "Lütfen hızlı hazırlayın."
}
```

## Proje klasör yapısı

```text
market-app/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── security.py
│   └── routes/
│       ├── auth.py
│       ├── market.py
│       └── musteri.py
│
├── static/
│   ├── category-images/
│   ├── css/
│   ├── icons/
│   ├── uploads/
│   ├── manifest.webmanifest
│   └── service-worker.js
│
├── templates/
│   ├── login.html
│   ├── market.html
│   ├── musteri.html
│   └── register.html
│
├── .gitignore
├── bakkal_ekle.py
├── docker-compose.yml
├── Dockerfile
├── README.md
├── requirements.txt
└── run.py
```

## Uçtan uca örnek akış

1. Market sahibi sisteme giriş yapar.
2. Ürün ekler veya mevcut ürünlerini günceller.
3. Müşteri market ürünlerini görüntüler.
4. Müşteri ürünleri sepete ekler.
5. Müşteri sipariş oluşturur.
6. Market paneline canlı sipariş bildirimi gelir.
7. Market siparişi onaylar veya reddeder.
8. Onaylanan siparişte stok otomatik azalır.
9. Stok değişikliği müşteriye canlı olarak yansır.
10. Dashboard ve rapor verileri güncellenir.

## V1 durumu

Bu sürüm, temel müşteri alışverişi ve market yönetimi akışlarını içeren ilk kullanılabilir sürümdür.

Test edilen başlıca alanlar:

* Kullanıcı kaydı ve giriş
* Ürün ekleme, güncelleme ve silme
* Adet, kg ve tutar satış türleri
* Sepet işlemleri
* Sipariş oluşturma
* Sipariş onaylama ve reddetme
* Stok değişikliklerinin canlı yansıması
* Sayfa yenileme sonrası mevcut sekmede kalma
* Market raporları
* PWA manifest ve Service Worker
* Docker kurulumu
* MySQL veritabanı bağlantısı

## Gelecek geliştirmeler

* Otomatik test kapsamının genişletilmesi
* Formal migration yapısına geçiş
* Production güvenlik ayarlarının tamamlanması
* Otomatik veritabanı yedekleme
* Gelişmiş müşteri bildirimleri
* Ödeme altyapısı entegrasyonu
* Market paneli için gelişmiş mobil uyumluluk
* Raporlar için daha ayrıntılı filtreleme
* Kullanıcı geri bildirimlerine göre yeni özellikler

## Lisans

Bu proje şu anda kişisel geliştirme ve test amacıyla kullanılmaktadır.
