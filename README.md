# Market Sipariş Sistemi (MVP)

Market sahibi, müşteri ve kurye rollerini içeren, kapıda ödemeli (nakit/kart)
basit bir sipariş uygulaması iskeleti. Flask + MySQL, DairySense'teki stack
ile aynı mantıkla kurulmuştur.

## Resetlemek için önce 

```bash
docker compose down
```

## Çalıştırmak için

```bash
docker compose up --build
```

Uygulama `http://localhost:5001` üzerinde ayağa kalkar.
Sağlık kontrolü: `GET /health`

## Klasör yapısı

```
market_siparis/
├── app/
│   ├── __init__.py        # Flask app factory, blueprint kaydı
│   ├── models.py           # 7 tablo: Market, Urun, Musteri, Kurye,
│   │                        Siparis, SiparisDetay, NakitTahsilat
│   └── routes/
│       ├── market.py        # market paneli endpoint'leri
│       ├── musteri.py        # müşteri uygulaması endpoint'leri
│       └── kurye.py          # kurye uygulaması endpoint'leri
├── run.py                   # başlangıç noktası, tabloları oluşturur
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## Örnek akış (uçtan uca test)

1. Market ürün ekler:
   `POST /api/market/urunler` → `{"market_id":1,"ad":"Süt","fiyat":25}`

2. Müşteri ürünleri görür:
   `GET /api/musteri/urunler?market_id=1`

3. Müşteri sipariş verir:
   `POST /api/musteri/siparis`
   ```json
   {
     "market_id": 1,
     "musteri_id": 1,
     "odeme_yontemi": "nakit",
     "urunler": [{"urun_id": 1, "adet": 2}]
   }
   ```

4. Market siparişi görür ve kurye atar:
   `GET /api/market/siparisler?market_id=1&durum=bekliyor`
   `PUT /api/market/siparisler/1/durum` → `{"durum":"onaylandi"}`
   `POST /api/market/siparisler/1/kurye-ata` → `{"kurye_id":1}`

5. Kurye siparişi görür, yola çıkar, teslim eder:
   `GET /api/kurye/atanan-siparisler?kurye_id=1`
   `PUT /api/kurye/siparis/1/durum` → `{"durum":"yolda"}`
   `PUT /api/kurye/siparis/1/durum` → `{"durum":"teslim_edildi"}`

6. Nakit ödemeyse kurye tahsilatı kaydeder:
   `POST /api/kurye/nakit-tahsilat` → `{"kurye_id":1,"siparis_id":1,"tutar":50}`
   `GET /api/kurye/gun-sonu-ozet?kurye_id=1`

## Sırada ne var (henüz eklenmedi)

- Kullanıcı girişi / kimlik doğrulama (JWT ya da session)
- Gerçek zamanlı bildirim (Flask-SocketIO ya da polling)
- Market/müşteri/kurye arayüzleri (bu sadece backend API)
- Kurye başına Banabikurye gibi harici bir platform entegrasyonu (opsiyonel)

