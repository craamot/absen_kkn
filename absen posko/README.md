# Absensi QR Posko KKN — Flask + MySQL

## Struktur
```
absensi-kkn/
  app.py              backend Flask (semua endpoint API)
  schema.sql           skema database MySQL
  requirements.txt
  .env.example
  templates/index.html frontend (dilayani oleh Flask)
```

## 1. Siapkan database
```bash
mysql -u root -p < schema.sql
```
Ini membuat database `absensi_kkn` beserta tabel `members`, `sessions`, `attendance`, `settings`.

## 2. Siapkan environment Python
```bash
cd absensi-kkn
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```
Buka `.env` dan isi `DB_USER` / `DB_PASSWORD` sesuai MySQL kamu.

## 3. Jalankan
```bash
python app.py
```
Buka `http://localhost:5000` di laptop admin, dan `http://<IP-laptop>:5000` di HP anggota (pastikan satu jaringan WiFi posko).

## Alur pemakaian
1. **Panel Admin** — tambah nama anggota, atur jam batas hadir tepat waktu, klik "Buat sesi baru" untuk memunculkan QR hari itu.
2. **Scan Absen** — anggota buka halaman ini di HP, arahkan kamera ke QR di layar admin (atau unggah foto QR kalau kamera tak bisa diakses), pilih nama, konfirmasi.
3. **Rekap** — lihat siapa saja yang hadir per tanggal beserta status tepat waktu/terlambat/manual.

## Catatan keamanan untuk pemakaian nyata
File ini dibuat sederhana untuk kebutuhan posko KKN. Kalau mau dipakai lebih serius:
- Tambahkan login admin (Flask-Login / session) supaya tab Panel Admin tidak bisa diakses sembarang orang.
- Jalankan di belakang HTTPS kalau diakses lewat internet publik (kamera browser butuh HTTPS di banyak perangkat, kecuali diakses lewat `localhost` atau IP lokal jaringan WiFi yang sama).
- Ganti `FLASK_SECRET_KEY` dan jangan commit file `.env` ke Git.
