# Eczane Borç Takip Sistemi — Kurulum Kılavuzu

Bu doküman uygulamayı sıfırdan kurmak için gereken tüm adımları açıklar.

---

## 1. Gereksinimler

- Python 3.11+
- Google hesabı (Google Workspace değil, kişisel hesap da çalışır)
- GitHub hesabı
- Streamlit Cloud hesabı (ücretsiz, [share.streamlit.io](https://share.streamlit.io))

---

## 2. Google Cloud Projesi Oluşturma

### 2.1 Proje Oluştur

1. [console.cloud.google.com](https://console.cloud.google.com) adresine gidin.
2. Sol üstten **"Proje Seç"** → **"Yeni Proje"** tıklayın.
3. Proje adı: `eczane-borc-takip` (ya da istediğiniz bir ad).
4. **Oluştur** tıklayın.

### 2.2 Google Sheets API'yi Etkinleştir

1. **APIs & Services** → **Library** bölümüne gidin.
2. **"Google Sheets API"** arayın → **Enable** tıklayın.
3. Aynı şekilde **"Google Drive API"** arayın → **Enable** tıklayın.

### 2.3 Service Account Oluştur

1. **APIs & Services** → **Credentials** bölümüne gidin.
2. **"Create Credentials"** → **"Service Account"** seçin.
3. Servis hesabı adı: `eczane-sheets-sa` (ya da istediğiniz bir ad).
4. **Done** tıklayın.
5. Oluşturulan servis hesabına tıklayın → **"Keys"** sekmesi.
6. **"Add Key"** → **"Create new key"** → **JSON** formatı seçin.
7. İndirilen `.json` dosyasını güvenli bir yerde saklayın.
   > ⚠️ Bu dosyayı GitHub'a ya da herhangi bir herkese açık ortama yüklemeyin.

---

## 3. Google Sheets Spreadsheet Oluşturma

1. [sheets.google.com](https://sheets.google.com) adresinde yeni bir Spreadsheet oluşturun.
2. Adı: `Eczane Borç Takip` (ya da istediğiniz bir ad).
3. Spreadsheet URL'sinden ID'yi kopyalayın:
   ```
   https://docs.google.com/spreadsheets/d/BURASI_SPREADSHEET_ID/edit
   ```

4. Sol alttaki sheet sekmesine sağ tıklayın → **Rename** → `CARILER` yapın.
5. Sırasıyla şu isimlerde 3 sheet daha ekleyin:
   - `KULLANICILAR`
   - `ILACLAR`
   - `BORC_HAREKET`

### 3.1 Servis Hesabına Erişim Ver

1. Spreadsheet'in sağ üst köşesinden **"Paylaş"** tıklayın.
2. Servis hesabı e-postasını girin (`.json` dosyasındaki `client_email` değeri).
   ```
   eczane-sheets-sa@your-project.iam.gserviceaccount.com
   ```
3. **"Düzenleyici"** yetkisi verin → **Gönder**.

---

## 4. Sheet Başlıklarını Oluşturma

Uygulama ilk çalıştığında başlıkları otomatik oluşturur.  
Ancak manuel olarak da ekleyebilirsiniz:

### CARILER (A1:D1)
```
Cari ID | Cari Adı | Durum | Oluşturulma Tarihi
```

### KULLANICILAR (A1:G1)
```
User ID | Kullanıcı Adı | Şifre Hash | Cari ID | Rol | Reset Şifre | Oluşturulma Tarihi
```

### ILACLAR (A1:D1)
```
İlaç ID | İlaç Adı | Durum | Oluşturulma Tarihi
```

### BORC_HAREKET (A1:N1)
```
Belge No | Kalem No | Borç Veren Cari ID | İlaç ID | Lot Tarihi | Birim Alış Fiyatı | Toplam Miktar | Borç Alan Cari ID | Kalem Miktarı | Oluşturan User ID | Oluşturulma Tarihi | Durum | Silen User ID | Silinme Tarihi
```

---

## 5. İlk Admin Hesabını Oluşturma

İlk Admin hesabı **manuel olarak Google Sheets'e** girilmelidir.

### 5.1 Şifre Hash'i Oluşturma

Python kullanarak bcrypt hash oluşturun. Terminal'de:

```bash
pip install bcrypt
python -c "
import bcrypt
sifre = 'ilk_sifreniz_buraya'
hashed = bcrypt.hashpw(sifre.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(hashed)
"
```

Çıktı örneği:
```
$2b$12$AbCdEfGhIjKlMnOpQrStUuVwXyZ0123456789abcdefghijklmnopq
```

### 5.2 CARILER Sheet'ine Admin Carisini Ekle

`CARILER` sheet'inin 2. satırına:
```
1 | Ahmet Eczanesi | Aktif | 2026-01-01 00:00:00
```

### 5.3 KULLANICILAR Sheet'ine Admin Kullanıcısını Ekle

`KULLANICILAR` sheet'inin 2. satırına:
```
1 | admin | $2b$12$AbCdEfGhIjKlMnOpQrStUu... | 1 | ADMIN | | 2026-01-01 00:00:00
```

> **Önemli:** Rol alanına tam olarak `ADMIN` yazın (büyük harf).  
> `Reset Şifre` (F sütunu) boş bırakın.

---

## 6. GitHub Repository Oluşturma

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/KULLANICI_ADI/eczane-borc-takip.git
git push -u origin main
```

### .gitignore Dosyası

Proje kökünde `.gitignore` oluşturun:

```
.streamlit/secrets.toml
*.json
__pycache__/
*.pyc
.env
.DS_Store
```

---

## 7. Streamlit Cloud Deployment

1. [share.streamlit.io](https://share.streamlit.io) adresine gidin.
2. **"New app"** tıklayın.
3. GitHub reponuzu ve `app.py` dosyasını seçin.
4. **"Advanced settings"** → **"Secrets"** bölümüne tıklayın.
5. Aşağıdaki içeriği girin (kendi değerlerinizle doldurun):

```toml
spreadsheet_id = "BURAYA_SPREADSHEET_ID"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN RSA PRIVATE KEY-----\nKEY_CONTENT\n-----END RSA PRIVATE KEY-----\n"
client_email = "your-sa@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-sa%40your-project.iam.gserviceaccount.com"
universe_domain = "googleapis.com"
```

> **Not:** `private_key` alanındaki satır sonları `\n` olarak girilmelidir.  
> JSON dosyasından kopyalarken `\n` karakterlerini koruyun.

6. **"Deploy"** tıklayın.

---

## 8. Şifre Sıfırlama (Reset)

Bir kullanıcı şifresini unutursa:

1. Google Sheets'te `KULLANICILAR` sheet'ini açın.
2. İlgili kullanıcının satırında **F sütunu (Reset Şifre)** alanına geçici şifre yazın.
   ```
   Geçici123
   ```
3. Uygulama bir sonraki girişte bu şifreyi hash'ler ve F sütununu temizler.
4. Kullanıcı geçici şifreyle giriş yapar → **Profilim** ekranından kendi şifresini değiştirir.

---

## 9. Yerel Geliştirme Ortamı

```bash
# Bağımlılıkları kur
pip install -r requirements.txt

# Secrets dosyasını oluştur
mkdir -p .streamlit
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# secrets.toml dosyasını gerçek değerlerle doldurun

# Uygulamayı başlat
streamlit run app.py
```

---

## 10. Bilinen Kısıtlamalar

| Kısıtlama | Açıklama |
|-----------|----------|
| **Concurrency** | Google Sheets gerçek transaction desteği sunmaz. Aynı anda iki kullanıcı belge kaydederse teorik olarak belge numarası çakışması olabilir. Çakışma yazım sonrası tespit edilir ve kullanıcı tekrar denemesi istenir. |
| **Performans** | Yüzlerce binlik satır biriktiğinde Sheets okuma yavaşlayabilir. Bu durumda PostgreSQL gibi gerçek bir veritabanına geçiş önerilir. |
| **API Kota** | Google Sheets API'nin dakika başına istek sınırı vardır (100 req/100s). Az sayıda eşzamanlı kullanıcı için yeterlidir. |
| **Offline** | Sheets API kesintisinde uygulama çalışmaz. |

---

## 11. Bakım Notları

- **Sheets yapısını değiştirmeyin:** Kolon sırasını veya sheet isimlerini değiştirirseniz uygulama bozulur.
- **Servis hesabı credential'ını yenileyin:** JSON anahtarı süresi dolmadan yenileyin.
- **Yedek:** Google Sheets verilerini düzenli aralıklarla Excel olarak indirip yedekleyin.
