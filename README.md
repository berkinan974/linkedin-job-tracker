# LinkedIn Job Tracker

## Kurulum (ilk kez)

```bash
# 1. Sanal ortam oluştur
python -m venv venv
venv\Scripts\activate        # Windows

# 2. Paketleri yükle
pip install -r requirements.txt

# 3. Playwright tarayıcısını indir
playwright install chromium

# 4. Ayarları doldur
#    config/settings.py dosyasını aç:
#    - LINKEDIN_EMAIL    = "..."
#    - LINKEDIN_PASSWORD = "..."
#    - ANTHROPIC_API_KEY = "..."

# 5. CV'ni koy
#    Canva'dan PDF olarak export et
#    data/cvs/cv_original.pdf olarak kaydet
```

## Kullanım

```bash
python main.py         # menü
python main.py scrape  # iş ilanlarını topla
```
