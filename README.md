# Market Sipariş Sistemi (MVP)

Market sahibi ve müşteri rollerini içeren, kapıda ödemeli (nakit/kart)
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

Uygulama `http://localhost:5002` üzerinde ayağa kalkar.
Sağlık kontrolü: `GET /health`

## Klasör yapısı

```
market_siparis/
├── app/
│   ├── __init__.py      
│   ├── models.py         
│   │                       
│   └── routes/
│       ├── auth.py        
│       ├── market.py        
│       └── musteri.py         
│
├── templates/
│   ├── login.html 
│   ├── market.html
│   ├── musteri.html
│   └── register.html                     
│
├── gitignore                  
├── bakkal_ekle.py
├── docker-compose.yml
├── Dockerfile
├── readme
├── requirements.txt
└── run.py
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

4. Market siparişi teslim eder veya iptal eder

## Sırada ne var (henüz eklenmedi)

- Kullanıcı girişi / kimlik doğrulama (JWT ya da session)
- Gerçek zamanlı bildirim (Flask-SocketIO ya da polling)
- Market/müşteri arayüzleri (bu sadece backend API)