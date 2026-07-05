FROM python:3.11-slim

# Terminal loglarının anında ekrana düşmesini sağlar
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --preload: uygulamayı worker'lar çoğaltılmadan ÖNCE tek sefer yükler,
# böylece db.create_all() 4 worker tarafından aynı anda çalıştırılıp çakışmaz
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "run:app"]