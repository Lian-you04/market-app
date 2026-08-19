# Market Sipariş Sistemi

Market sahipleri ile müşterileri buluşturan, gerçek zamanlı sipariş ve stok yönetimi sunan Flask tabanlı market uygulaması.

Uygulama; market yönetim paneli, müşteri alışveriş ekranı, canlı sipariş bildirimleri, ürün ve stok yönetimi ile market ayarlarını tek bir sistemde birleştirir.

## Teknolojiler

- Python 3.11
- Flask
- Flask-SQLAlchemy
- MySQL
- Flask-SocketIO
- Docker
- Docker Compose
- HTML
- CSS
- JavaScript

## Uygulamayı çalıştırma

Çalışan container'ları durdurmak için:

    docker compose down

Uygulamayı build ederek başlatmak için:

    docker compose up --build

Uygulama şu adreste çalışır:

    http://localhost:5002

Sağlık kontrolü:

    GET /health

## Kullanıcı rolleri

### Market sahibi

- Dashboard ve dönemsel ciro grafikleri
- Günlük, haftalık, aylık ve yıllık satış verileri
- En çok satan ilk 5 ürün
- Canlı sipariş bildirimleri
- Sipariş teslim etme ve iptal etme
- Ürün ekleme, güncelleme ve silme
- Ürün fotoğrafı ekleme ve silme
- Ürün detaylarını görüntüleme
- Kategori yönetimi
- Stok yönetimi
- Satışta olan ve tükenen ürünleri ayrı görüntüleme
- Ürünleri ad, fiyat ve stok miktarına göre sıralama
- Market adı, telefon ve adres bilgilerini güncelleme
- Minimum sipariş tutarı belirleme
- Marketi online siparişlere açma veya kapatma
- Açık ve koyu tema seçimi
- Bildirim sesi açma veya kapatma
- Bildirim sesi türü ve ses seviyesi ayarlama

### Müşteri

- Market ürünlerini görüntüleme
- Kategoriye göre ürün filtreleme
- Ürün detaylarını ve fotoğraflarını görüntüleme
- Ürünleri sepete ekleme
- Nakit veya kart ile ödeme seçme
- Adrese teslim veya gel-al seçimi
- Sipariş notu ekleme
- Sipariş verme
- Sipariş durumunu canlı takip etme
- Marketin açık veya kapalı durumunu canlı görme
- Ürün ve stok değişikliklerini sayfa yenilemeden görme

## Gerçek zamanlı özellikler

Uygulamada Flask-SocketIO kullanılmaktadır.

Aşağıdaki işlemler Socket.IO ile canlı olarak güncellenir:

- Yeni sipariş bildirimi
- Sipariş durumunun değişmesi
- Ürün ve stok değişiklikleri
- Marketin online veya offline durumu
- Müşteri tarafındaki ürün listesi
- Dashboard satış ve ciro verileri
- Market adı değişikliği

## Sipariş durumları

    bekliyor
    hazirlaniyor
    yolda
    teslim_edildi
    iptal

## Zaman dilimi

Sipariş tarihleri, saatleri ve dashboard grafik verileri İstanbul zaman dilimi esas alınarak gösterilir.

## Temel API uçları

### Market API

    GET    /api/market/durum
    PUT    /api/market/durum

    GET    /api/market/urunler
    POST   /api/market/urunler
    PUT    /api/market/urunler/<urun_id>
    DELETE /api/market/urunler/<urun_id>

    GET    /api/market/siparisler
    GET    /api/market/dashboard-grafik

### Müşteri API

    GET  /api/musteri/urunler
    GET  /api/musteri/kategoriler
    GET  /api/musteri/market-durum
    POST /api/musteri/siparis

## Örnek sipariş verisi

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

## Proje klasör yapısı

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
    │   ├── css/
    │   │   └── style.css
    │   └── uploads/
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

## Uçtan uca örnek akış

1. Market sahibi sisteme giriş yapar.
2. Ürün ekler veya mevcut ürünlerini günceller.
3. Müşteri market ürünlerini görüntüler.
4. Müşteri sepete ürün ekleyerek sipariş verir.
5. Market paneline canlı sipariş bildirimi gelir.
6. Sipariş verildiğinde ürün stoğu otomatik azalır.
7. Sipariş iptal edilirse ilgili stok müşteriye ve markete canlı olarak iade edilir.
8. Market siparişi teslim eder veya iptal eder.
9. Dashboard üzerindeki ciro, sipariş ve satış verileri güncellenir.

## Geliştirme planı

- Raporlar bölümünün genişletilmesi
- Yorumlar bölümünün tamamlanması
- Otomatik test kapsamının artırılması
- Veritabanı migration yapısının eklenmesi
- Production ortamı için güvenlik ve deployment düzenlemeleri