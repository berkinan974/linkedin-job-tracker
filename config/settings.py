# ============================================================
#  LinkedIn Job Tracker — Merkezi Ayarlar
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

# --- LinkedIn Kimlik Bilgileri ---
LINKEDIN_EMAIL    = os.environ["LINKEDIN_EMAIL"]
LINKEDIN_PASSWORD = os.environ["LINKEDIN_PASSWORD"]

# --- AI (Claude) ---
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# --- Arama Kriterleri ---
SEARCH_JOBS = [
    "Elektrik Elektronik Mühendisi",
    "Gömülü Sistemler Mühendisi",
    "Firmware Engineer",
    "Elektronik Tasarım Mühendisi",
    "Donanım Mühendisi",
    "STM32 Engineer",
]

SEARCH_LOCATIONS = [
    "İzmir, Türkiye",
    "İstanbul, Türkiye",
    "Ankara, Türkiye",
    "Türkiye",          # uzaktan ilanlar için
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
MIN_MATCH_SCORE     = 0       # yüzde kaç eşleşme olursa başvuru yapılsın
APPLY_AUTOMATICALLY = True    # True yapınca otomatik başvuru açılır (dikkatli!)

# --- Dosya Yolları ---
DB_PATH             = "data/db/jobs.db"
CV_INPUT            = "data/cvs/CV_Adatip_v3.pdf"
CV_OUTPUT           = "data/cvs/"
COVER_LETTER_OUTPUT = "data/cover_letters/"
LOG_PATH            = "data/logs/app.log"

# --- Opera Tarayıcı (mevcut profil ile LinkedIn girişi gerekmez) ---
OPERA_EXE     = r"C:\Users\berki\AppData\Local\Programs\Opera\opera.exe"
OPERA_PROFILE = r"C:\Users\berki\AppData\Roaming\Opera Software\Opera Stable"
