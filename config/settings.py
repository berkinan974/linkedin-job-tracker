# ============================================================
#  LinkedIn Job Tracker — Merkezi Ayarlar
# ============================================================
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# LinkedIn ilan başlıklarında emoji geçebiliyor (örn. 🤖); Windows konsolunun
# varsayılan kod sayfası (cp1254 vb.) bunları encode edemeyip programı
# UnicodeEncodeError ile çökertiyordu. stdout/stderr'i UTF-8'e zorla.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# --- LinkedIn Kimlik Bilgileri ---
LINKEDIN_EMAIL    = os.environ["LINKEDIN_EMAIL"]
LINKEDIN_PASSWORD = os.environ["LINKEDIN_PASSWORD"]

# --- AI (Claude) ---
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# --- Arama Kriterleri ---
SEARCH_JOBS = [
    # Signal Processing / Embedded / RF
    "Elektrik Elektronik Mühendisi",
    "Gömülü Sistemler Mühendisi",
    "Firmware Engineer",
    "Elektronik Tasarım Mühendisi",
    "Donanım Mühendisi",
    "STM32 Engineer",
    # Software / Backend / AI-ML
    "Software Engineer",
    "Backend Developer",
    "Yazılım Mühendisi",
    "Machine Learning Engineer",
    # Power Electronics / Hardware
    "Power Electronics Engineer",
    "Güç Elektroniği Mühendisi",
    # E-ticaret / Marketplace / SEO
    "E-ticaret Uzmanı",
    "E-ticaret Operasyon",
    "Dijital Pazarlama Uzmanı",
    "SEO Uzmanı",
    "Marketplace Uzmanı",
]

SEARCH_LOCATIONS = [
    "İzmir, Türkiye",
]

WORK_TYPES = [
    "remote",
    "hybrid",
    "on-site",
]

EXPERIENCE_LEVELS = [
    "internship",       # staj
    "entry_level",      # yeni mezun
    "associate",        # 1-3 yıl
]

# --- Genel Ayarlar ---
MAX_JOBS_PER_SEARCH = 50      # her aramada kaç ilan
MIN_MATCH_SCORE     = 40      # İzmir turu: 65+ sadece 5 ilan verdi, 40+ ~26 ilanlık havuz sağlıyor
APPLY_AUTOMATICALLY = True    # True yapınca otomatik başvuru açılır (dikkatli!)

# --- Dosya Yolları ---
DB_PATH             = "data/db/jobs.db"
CV_INPUT            = "data/cvs/CV_Adatip_v3.pdf"
CV_OUTPUT           = "data/cvs/"
COVER_LETTER_OUTPUT = "data/cover_letters/"
LOG_PATH            = "data/logs/app.log"

# --- CV Profilleri (statik, ilana göre seçilir — AI içerik değiştirmez) ---
# Her profil bir kategoriyi temsil eder. "keywords" ilan başlığı/açıklamasında
# aranır (case-insensitive); en çok eşleşen profil seçilir (bkz.
# cv_manager.select_cv_profile). Daha dar/spesifik profiller önce listelenir
# ki eşit skor durumunda geniş "comprehensive" profil yerine onlar kazansın.
CV_PROFILES = [
    {
        # Dar sinyal işleme / gömülü sistem / RF odaklı CV — yazılım/SaaS
        # içeriği bilinçli olarak dışarıda tutulmuş, saf donanım/sinyal
        # ilanlarında daha odaklı görünmesi için.
        "id": "signal_embedded",
        "keywords": [
            "sinyal işleme", "signal processing", "dsp", "rf", "wireless",
            "embedded", "gömülü sistem", "mmwave", "iletişim mühendisi",
            "communication engineer", "firmware", "beam scanning",
            "stm32", "mikrodenetleyici", "microcontroller",
        ],
        "cv_tr": "data/cvs/CV_SignalEmbedded_TR.pdf",
        "cv_en": "data/cvs/CV_SignalEmbedded_EN.pdf",
    },
    {
        # Güç elektroniği / devre / endüstriyel otomasyon ağırlıklı yedek CV.
        "id": "power_electronics",
        "keywords": [
            "power electronics", "güç elektroniği", "devre tasarım",
            "circuit design", "pcb", "hardware engineer", "donanım mühendisi",
            "elektrik mühendisi", "enerji sistemleri", "power systems",
            "high voltage", "yüksek gerilim", "industrial automation",
            "endüstriyel otomasyon", "plc",
        ],
        "cv_tr": "data/cvs/CV_PowerElectronics_TR.pdf",
        "cv_en": None,  # İngilizce versiyon henüz yok — EN ilanlarda bu profil atlanır
    },
    {
        # E-ticaret / marketplace / SEO / dijital pazarlama odaklı CV.
        "id": "ecommerce",
        "keywords": [
            "e-ticaret", "e-ticaret uzmanı", "e-commerce", "etsy", "marketplace",
            "pazaryeri", "seo", "dijital pazarlama", "digital marketing",
            "growth marketing", "ürün listeleme", "content optimization",
        ],
        "cv_tr": "data/cvs/CV_Ecommerce_TR.pdf",
        "cv_en": None,  # İngilizce versiyon henüz yok
    },
    {
        # Kapsamlı CV: sinyal işleme + gömülü sistem + yazılım/backend/AI
        # projelerinin (FleetSync SaaS dahil) tümünü içerir. Yukarıdaki dar
        # profillere uymayan genel yazılım/mühendislik ilanları için varsayılan.
        "id": "comprehensive",
        "keywords": [
            "software engineer", "yazılım mühendisi", "backend", "full stack",
            "fullstack", "python developer", "ai engineer", "ml engineer",
            "machine learning engineer", "data engineer", "data scientist",
        ],
        "cv_tr": "data/cvs/CV_Comprehensive_TR.pdf",
        "cv_en": "data/cvs/CV_Comprehensive_EN.pdf",
    },
]

# --- Opera Tarayıcı ---
OPERA_EXE = r"C:\Users\berki\AppData\Local\Programs\Opera\opera.exe"
# Otomasyona ayrılmış, kullanıcının canlı Opera profilinden bağımsız profil.
# Profil kilidi çakışması yaşanmasın diye (aynı profili iki process aynı anda
# açamaz) ayrı bir dizin kullanılır; ilk çalıştırmada otomatik LinkedIn girişi
# yapılıp bu profilde kalıcı olarak oturum açık kalır.
OPERA_PROFILE = r"C:\Users\berki\AppData\Roaming\Opera Software\Opera Automation"

# --- Otomasyon Penceresi ---
# İkinci ekranda (sol monitör) açılır, böylece ana ekran çalışmak için serbest kalır.
AUTOMATION_WINDOW_ARGS = ["--window-position=-1920,476", "--window-size=1920,1080"]
