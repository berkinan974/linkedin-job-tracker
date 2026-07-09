"""
CV Manager — Canva Tasarımına Uygun
"""
import sqlite3
import json
import io
from pathlib import Path

import anthropic
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from loguru import logger
from rich.console import Console

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import ANTHROPIC_API_KEY, DB_PATH, CV_OUTPUT, MIN_MATCH_SCORE

console = Console()
client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── Fontlar ──────────────────────────────────────────────────────────────────
try:
    pdfmetrics.registerFont(TTFont("Arial",      "C:/Windows/Fonts/arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
    FONT_NORMAL = "Arial"
    FONT_BOLD   = "Arial-Bold"
except Exception:
    FONT_NORMAL = "Helvetica"
    FONT_BOLD   = "Helvetica-Bold"

# Profil fotoğrafı (data/photo.jpg koyarsan otomatik kullanılır)
PHOTO_PATH = str(Path(__file__).parent.parent / "data" / "photo.jpg")

# ─── Renkler ──────────────────────────────────────────────────────────────────
DARK       = colors.HexColor("#1a1a2e")
SECTION_BG = colors.HexColor("#eeeeee")
LINE_COLOR = colors.HexColor("#cccccc")
GRAY       = colors.HexColor("#555555")

# ─── Sabit CV Bilgileri ───────────────────────────────────────────────────────
CV_BASE = {
    "name":        "BERK İNAN",
    "phone":       "+90 538 074 00 09",
    "email":       "berkinan974@gmail.com",
    "address":     "İzmir/Bornova",
    "nationality": "T.C/Ukrainian",
    "birthdate":   "26.02.2002",
    "linkedin":    "linkedin.com/in/berk-inan1",
    "about": (
        "Elektrik-Elektronik Mühendisliği lisans mezunuyum. "
        "Hem donanım hem de yazılım alanlarında güçlü yetkinlikler kazanmak için hevesliyim. "
        "Eğitimimi tamamen İngilizce olarak tamamladım. Üniversite hayatım boyunca, teknik ve "
        "kişisel gelişimime katkı sağlayan ve profesyonel çalışma ortamlarına uyum sağlamama olanak "
        "tanıyan çeşitli alanlarda bulundum ve stajımı gerçekleştirdim. Küçük yaştan itibaren takım "
        "sporlarıyla ilgilendiğimden dolayı disiplinli, takım çalışmasına uyumlu, öğrenmeye istekli "
        "ve sürekli kendini geliştirmeye açık bir mühendisim. En önemlisi yapacağım işi kolay "
        "öğrenirim, en iyisini yapmak için uğraşırım."
    ),
    "experience": [
        {
            "company": "FrikElektronik",
            "role":    "Gömülü Sistemler & Donanım Stajyeri",
            "summary": (
                "FrikElektronik bünyesinde gömülü sistemler ve mikrodenetleyici tabanlı uygulamalar "
                "üzerine yürütülen ekip projelerinde ve saha uygulamalarında aktif görev aldım."
            ),
            "bullets": [
                ("Firmware Geliştirme",
                 "STM32 tabanlı uygulamalar için gömülü yazılım (firmware) kodlama ve hata ayıklama "
                 "(debugging) süreçlerinde yer aldım."),
                ("Devre Tasarımı ve Test",
                 "Mikrodenetleyici devrelerinin tasarım aşamalarına destek verdim ve prototip "
                 "testlerini gerçekleştirdim."),
                ("Donanım Üretimi ve Montajı",
                 "Üretim hattında manuel lehimleme, kablo hazırlığı ve temel donanım montaj "
                 "süreçlerini yürüterek; elektronik bileşenlerin yapısı ve pratik uygulamaları "
                 "konusunda teknik yetkinlik kazandım."),
            ],
        }
    ],
    "projects": [
        {
            "name": "Elektronik Devre Tasarımı: 555 Zamanlayıcı ve AC/DC Adaptör",
            "desc": (
                "Alternatif akımı (AC) verimli bir şekilde doğru akıma (DC) dönüştüren ve elektronik "
                "cihazlar için kararlı bir güç kaynağı sağlayan bir AC/DC adaptör devresi tasarladım."
            ),
        },
        {
            "name": "Makine Öğrenmesi ile Endüstriyel Motorlarda Titreşim Analizi",
            "desc": (
                "Bu projede endüstriyel motorlardaki rulman arızalarını titreşim verisiyle tespit "
                "etmeye çalıştım; iç bilezik, dış bilezik ve bilya hasarlarını ayırt edebilen bir "
                "sistem tasarladım. İlk başta FFT ile frekans analizi yaptım, ama durağan olmayan "
                "sinyallerde yetersiz kaldığını gördüm. Bunun üzerine Hilbert-Huang Transform'a "
                "geçtim ve doğruluk oldukça arttı. Makine öğrenmesi modeli için sensör verisinden "
                "özellik çıkarımı yapıp sınıflandırma algoritmaları uyguladım."
            ),
        },
        {
            "name": None,  # AI tarafından ilana göre üretilir
            "desc": None,
        },
    ],
    "certifications": [
        ("STM32 Sertifikası",                    "ST Microelectronics"),
        ("Core Signal Processing Techniques in MATLAB", "MathWorks"),
        ("Simulink Fundamentals",                "MathWorks"),
        ("Simscape Onramp",                      "MathWorks"),
        ("Simulink Onramp",                      "MathWorks"),
        ("MATLAB Onramp",                        "MathWorks"),
    ],
    "social": [
        "Yaşar Üniversitesi Amerikan Futbolu Takımı — 1x Türkiye Şampiyonluğu",
        "Profesyonel Amerikan Futbolu — 1x Türkiye Şampiyonluğu",
        "Gelişim Proje Topluluğu Denetim Kurulu Başkanlığı",
        "Voleybol Topluluğu Kurucu Üye",
    ],
    "education": [
        "Yaşar Üniversitesi (2021 – 2026)",
        "Elektrik-Elektronik Mühendisliği",
        "(%100 İngilizce)",
    ],
    "languages": [
        ("İngilizce", "B2"),
        ("Türkçe",    "Ana Dil"),
        ("Ukraynaca", "Başlangıç"),
    ],
    "skills": [
        "Python", "Proteus",
        "STM32/Cubelde Microcontroller",
        "Arduino C/C++",
        "Communication Protocols",
        "MATLAB",
        "Siemens S7-1500",
    ],
}

# ─── AI ile Özelleştirme ──────────────────────────────────────────────────────

def _job_context(job: dict) -> str:
    return (
        f"Pozisyon: {job['title']}\n"
        f"Şirket: {job['company']}\n"
        f"Aranan Beceriler: {job.get('required_skills', '')}\n"
        f"Açıklama: {(job.get('description') or '')[:1000]}"
    )


def _ai_json(job: dict) -> dict:
    prompt = f"""Sen bir kariyer danışmanısın.

## İş İlanı
{_job_context(job)}

## Mevcut Beceriler
Python, MATLAB, STM32, Arduino C/C++, Proteus, Siemens S7-1500, Communication Protocols, Machine Learning, Signal Processing

## Görevin
Yalnızca şu JSON'u döndür:
{{
  "skills": ["ilana en uygun 8 beceri"],
  "highlight_projects": ["1-2 proje adı"],
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    return json.loads(text)


def _ai_project(job: dict) -> tuple[str, str]:
    prompt = f"""Aşağıdaki iş ilanına uygun küçük bir kişisel proje yaz.

## İş İlanı
{_job_context(job)}

## Adayın Becerileri
Python, MATLAB, STM32, Arduino C/C++, Proteus, Siemens S7-1500, Communication Protocols

## Format
İlk satır: kısa proje başlığı (5-8 kelime, Türkçe)
Sonraki satırlar: TAM OLARAK 3 kısa cümle (toplam 300 karakteri kesinlikle geçme). Anlatım tarzı: birinci şahıs, geçmiş zaman, ne yapmak istediğini belirt, karşılaştığın teknik sorunu söyle, nasıl çözdüğünü anlat. Yüzde veya sayısal oran uydurma. Başka hiçbir şey yazma."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    lines = response.content[0].text.strip().splitlines()
    name = lines[0].strip()
    desc = " ".join(l.strip() for l in lines[1:] if l.strip())
    return name, desc


def customize_with_ai(job: dict) -> dict:
    fallback = {
        "about":                   CV_BASE["about"],
        "skills":                  CV_BASE["skills"],
        "highlight_projects":      [],
        "dynamic_project_name":    "Kişisel Teknik Proje",
        "dynamic_project_desc":    "STM32 ve Python kullanarak sensör verilerini işleyen küçük bir gömülü sistem uygulaması geliştirdim.",
    }

    try:
        result = _ai_json(job)
    except Exception as e:
        logger.warning(f"JSON çağrısı hatası: {e}")
        result = {}

    try:
        name, desc = _ai_project(job)
    except Exception as e:
        logger.warning(f"Proje çağrısı hatası: {e}")
        name, desc = fallback["dynamic_project_name"], fallback["dynamic_project_desc"]

    return {
        "about":                   CV_BASE["about"],
        "skills":               result.get("skills", CV_BASE["skills"]),
        "highlight_projects":   result.get("highlight_projects", []),
        "dynamic_project_name": name,
        "dynamic_project_desc":    desc,
    }

# ─── Yardımcılar ──────────────────────────────────────────────────────────────

def _circle_photo(path: str, size: float):
    try:
        from PIL import Image as PILImage, ImageDraw
        img = PILImage.open(path).convert("RGBA")
        side = min(img.size)
        left = (img.width  - side) // 2
        top  = (img.height - side) // 2
        img  = img.crop((left, top, left + side, top + side)).resize((200, 200))
        mask = PILImage.new("L", (200, 200), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 200, 200), fill=255)
        img.putalpha(mask)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Image(buf, width=size, height=size)
    except Exception:
        return None


def _section_header(title: str, s_h1, col_width: float):
    t = Table([[Paragraph(title, s_h1)]], colWidths=[col_width])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), SECTION_BG),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


# ─── PDF Oluşturma — Template Tabanlı ────────────────────────────────────────

def _wrap_text(text: str, max_w: float, fontsize: float) -> list[str]:
    """Metni max_w genişliğinde satırlara böl (Helvetica ölçümü, Arial için düzeltilmiş)."""
    import fitz
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if fitz.get_text_length(test, fontname="helv", fontsize=fontsize) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
# Orijinal CV (cv_original.pdf) tasarımını koruyarak sadece
# Beceriler (YETKINLIK) ve 3. Proje alanını değiştirir.

TEMPLATE_PATH    = str(Path(__file__).parent.parent / "data" / "cvs" / "CV_Adatip_v3.pdf")
TEMPLATE_PATH_EN = str(Path(__file__).parent.parent / "data" / "cvs" / "CV_Adatip_v3_EN.pdf")
ARIAL         = "C:/Windows/Fonts/arial.ttf"
ARIAL_BOLD    = "C:/Windows/Fonts/arialbd.ttf"

EN_ABOUT = (
    "I hold a bachelor's degree in Electrical & Electronics Engineering. "
    "I am passionate about developing strong competencies in both hardware and software. "
    "I completed my entire education in English. Throughout my university life, I participated in various "
    "activities and completed an internship that contributed to my technical and personal development "
    "and helped me adapt to professional work environments. "
    "Being involved in team sports from a young age, I am a disciplined, team-oriented engineer who is "
    "eager to learn and continuously improve. "
    "Most importantly, I pick up new skills quickly and always strive to deliver my best."
)

EN_SOCIAL = [
    "Yasar University American Football Team — 1x Turkey Championship",
    "Professional American Football — 1x Turkey Championship",
    "Development Projects Community — Board President",
    "Volleyball Community — Founding Member",
]

EN_EXP_COMPANY = "FrikElektronik  ·  Embedded Systems & Hardware Engineering Intern  ·  2024"
EN_EXP_SUMMARY = (
    "At FrikElektronik, I actively took part in team projects and field applications "
    "focused on embedded systems and microcontroller-based applications."
)
EN_EXP_BULLETS = [
    ("Firmware Development",
     "Took part in coding and debugging embedded firmware for STM32-based applications."),
    ("Circuit Design & Testing",
     "Supported the design stages of microcontroller circuits and carried out prototype testing."),
    ("Hardware Assembly",
     "Performed manual soldering, cable preparation, and PCB assembly on the production line."),
]


def build_pdf(job: dict, customized: dict, output_path: str):
    """
    cv_original.pdf'i template olarak kullanır.
    Sadece iki dinamik alan değiştirilir:
      1. YETKINLIK (beceriler listesi)
      2. 1. Proje (AI tarafından ilana göre üretilen dinamik proje)
    Geri kalan her şey orijinal tasarımda kalır.
    """
    import fitz

    doc  = fitz.open(TEMPLATE_PATH)
    page = doc[0]

    TMPL_COLOR = (26/255, 26/255, 46/255)
    PAGE_W     = 595.28

    # Sabit sınır değerleri — bu değerleri değiştirme
    HEADER_Y1   = 96.0   # HAKKIMDA gri bar y=96.7'de başlar
    PROJECT_Y1  = 449.0  # SERTiFiKALAR gri bar y=449.7'de başlar
    PROJ_LINE_H = 11.0   # Orijinal satır aralığı (pt)
    PROJ_MAX_W  = 469.0  # Arial için düzeltilmiş max genişlik

    ABOUT_Y_START = 115.0   # HAKKIMDA body text baseline başlangıcı
    ABOUT_LINE_H  = 11.0
    ABOUT_MAX_W   = 469.0
    ABOUT_Y_END   = 162.0   # İŞ DENEYİMİ barı başlamadan önce dur

    # ── 1. Dinamik alanları beyaza sil ────────────────────────────────────
    skills_rect       = fitz.Rect(388, 589,     549,      708)
    project_rect      = fitz.Rect(38,  390,     562,      PROJECT_Y1)
    header_rect       = fitz.Rect(0,   28,      PAGE_W,   HEADER_Y1)
    about_rect        = fitz.Rect(0,   HEADER_Y1, PAGE_W, ABOUT_Y_END)  # body text alanı
    social_lines_rect = fitz.Rect(38,  524,     562,      570)
    edu_rect          = fitz.Rect(38,  591,     210,      603)

    page.add_redact_annot(skills_rect,       fill=(1, 1, 1))
    page.add_redact_annot(project_rect,      fill=(1, 1, 1))
    page.add_redact_annot(header_rect,       fill=(1, 1, 1))
    page.add_redact_annot(about_rect,        fill=(1, 1, 1))
    page.add_redact_annot(social_lines_rect, fill=(1, 1, 1))
    page.add_redact_annot(edu_rect,          fill=(1, 1, 1))
    page.apply_redactions()

    # ── 2. Header: isim y=60, unvan y=72, line2 y=83, line3 y=92 ─────────
    name_w = fitz.get_text_length(CV_BASE["name"], fontname="helv", fontsize=22)
    page.insert_text(fitz.Point((PAGE_W - name_w) / 2 - 5, 60.0),
                     CV_BASE["name"],
                     fontsize=22, fontfile=ARIAL_BOLD, fontname="ArialBd", color=TMPL_COLOR)

    title_str = "Elektrik Elektronik Mühendisi"
    title_w   = fitz.get_text_length(title_str, fontname="helv", fontsize=9.5)
    page.insert_text(fitz.Point((PAGE_W - title_w) / 2, 72.0),
                     title_str,
                     fontsize=9.5, fontfile=ARIAL, fontname="Arial", color=TMPL_COLOR)

    line2   = f"{CV_BASE['address']}  |  {CV_BASE['phone']}"
    line2_w = fitz.get_text_length(line2, fontname="helv", fontsize=7.5)
    page.insert_text(fitz.Point((PAGE_W - line2_w) / 2, 83.0),
                     line2,
                     fontsize=7.5, fontfile=ARIAL, fontname="Arial", color=TMPL_COLOR)

    line3   = f"{CV_BASE['linkedin']}  |  {CV_BASE['email']}"
    line3_w = fitz.get_text_length(line3, fontname="helv", fontsize=7.5)
    page.insert_text(fitz.Point((PAGE_W - line3_w) / 2, 92.0),
                     line3,
                     fontsize=7.5, fontfile=ARIAL, fontname="Arial", color=TMPL_COLOR)

    # ── 3. HAKKIMDA gri bar (bar'dan SONRA yazı yazılır → ascender sorunu yok)
    page.draw_rect(fitz.Rect(34, 96.7, 561.3, 110.0), color=None, fill=(0.933, 0.933, 0.933))
    page.insert_text(fitz.Point(38, 104.5), "HAKKIMDA",
                     fontsize=10, fontfile=ARIAL_BOLD, fontname="ArialBd", color=TMPL_COLOR)

    # ── 3b. HAKKIMDA body text — bar'dan sonra yazıldığı için üstte render eder
    about_lines = _wrap_text(CV_BASE["about"], ABOUT_MAX_W, 8.0)
    y_about = ABOUT_Y_START
    for line in about_lines:
        if y_about >= ABOUT_Y_END:
            break
        page.insert_text(fitz.Point(38, y_about), line,
                         fontsize=8, fontfile=ARIAL, fontname="Arial", color=TMPL_COLOR)
        y_about += ABOUT_LINE_H

    # ── 2. Yeni becerileri yaz ────────────────────────────────────────────
    skills = [s.title() for s in customized.get("skills", CV_BASE["skills"])]
    y = 598.0   # baseline ≈ y0(591.4) + 7.5*0.82 ≈ 597.6
    TMPL_COLOR = (26/255, 26/255, 46/255)
    for skill in skills[:9]:
        page.insert_text(
            fitz.Point(390, y),
            skill,
            fontsize=7.5,
            fontfile=ARIAL,
            fontname="Arial",
            color=TMPL_COLOR,
        )
        y += 15.0   # orijinal satır aralığı (606.4-591.4=15)

    # ── 4. Dinamik projeyi yaz ────────────────────────────────────────────
    proj_name = customized.get("dynamic_project_name", "").replace("**", "").replace("#", "").strip()
    proj_desc = customized.get("dynamic_project_desc", "")

    # Başlık — bold 8pt, y=399
    page.insert_text(fitz.Point(40, 399), proj_name,
                     fontsize=8, fontfile=ARIAL_BOLD, fontname="ArialBd", color=TMPL_COLOR)

    # Açıklama — wrap_text + 11pt satır aralığı, max y=PROJECT_Y1
    desc_lines = _wrap_text(proj_desc, PROJ_MAX_W, 8)
    y_desc = 399 + PROJ_LINE_H
    for line in desc_lines:
        if y_desc >= PROJECT_Y1:
            break
        page.insert_text(fitz.Point(40, y_desc), line,
                         fontsize=8, fontfile=ARIAL, fontname="Arial", color=TMPL_COLOR)
        y_desc += PROJ_LINE_H

    # ── 5. Sosyal katılım girinti düzelt (x=48 → x=38) ───────────────────
    TMPL_COLOR = (26/255, 26/255, 46/255)
    y_s = 530.7
    for item in CV_BASE["social"]:
        page.insert_text(fitz.Point(38, y_s), f"- {item}",
                         fontsize=7.5, fontfile=ARIAL, fontname="Arial", color=TMPL_COLOR)
        y_s += 12.0

    # ── 5. Eğitim ilk satırını güncelle ──────────────────────────────────
    page.insert_text(fitz.Point(38, 597.7), CV_BASE["education"][0],
                     fontsize=7.5, fontfile=ARIAL, fontname="Arial", color=TMPL_COLOR)

    doc.save(output_path, deflate=True, garbage=4)
    doc.close()


def _ai_project_english(job: dict) -> tuple[str, str]:
    """İngilizce dinamik proje üret."""
    prompt = f"""Write a short personal project in English for a CV, targeting this job:

## Job
Position: {job['title']}
Company: {job['company']}
Skills needed: {job.get('required_skills', '')}

## Candidate skills
Python, MATLAB, STM32, Arduino C/C++, Signal Processing, Machine Learning

## Format
Line 1: short project title (5-8 words, no markdown)
Lines 2-4: exactly 3 sentences, first person past tense, max 270 chars total.
Return nothing else."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    lines = response.content[0].text.strip().splitlines()
    name = lines[0].strip().lstrip("*#-· ").strip()
    desc = " ".join(l.strip() for l in lines[1:] if l.strip())
    return name, desc


def customize_with_ai_english(job: dict) -> dict:
    """İngilizce CV için skills + dinamik proje üret."""
    fallback_name = "Real-time Signal Classification on Microcontroller"
    fallback_desc = (
        "I developed a signal classification pipeline using Python and scikit-learn to categorize "
        "sensor readings from an STM32-based device. I faced challenges with noisy input data and "
        "resolved them by applying a Butterworth filter before feature extraction."
    )
    try:
        result = _ai_json(job)
    except Exception as e:
        logger.warning(f"English JSON call error: {e}")
        result = {}
    try:
        name, desc = _ai_project_english(job)
    except Exception as e:
        logger.warning(f"English project call error: {e}")
        name, desc = fallback_name, fallback_desc

    return {
        "skills":               result.get("skills", CV_BASE["skills"]),
        "dynamic_project_name": name,
        "dynamic_project_desc": desc,
    }


def build_pdf_english(job: dict, customized: dict, output_path: str):
    """
    Türkçe CV_Adatip_v3.pdf'i direkt açar, TÜM Türkçe alanları
    orijinal koordinatlarda İngilizce'ye çevirir.
    Koordinatlar blocks.json analizinden — her şey template pozisyonuna göre.
    """
    import fitz

    doc  = fitz.open(TEMPLATE_PATH)   # orijinal Türkçe template
    page = doc[0]

    C  = (26/255, 26/255, 46/255)
    GR = (0.933, 0.933, 0.933)
    W  = 595.28

    def t(x, y, s, fs=8, bold=False):
        ff = ARIAL_BOLD if bold else ARIAL
        fn = "ArialBd"  if bold else "Arial"
        page.insert_text(fitz.Point(x, y), s,
                         fontsize=fs, fontfile=ff, fontname=fn, color=C)

    def bar(y0, h=13.3):
        page.draw_rect(fitz.Rect(34, y0, 561.3, y0 + h), color=None, fill=GR)

    def ww(x, y, content, max_w, fs=8, lh=11, y_max=9999):
        for line in _wrap_text(content, max_w, fs):
            if y >= y_max:
                break
            t(x, y, line, fs)
            y += lh
        return y

    # ── Tek seferlik redact: tüm Türkçe alanlar ───────────────────────────
    for rect in [
        (0,   28,    W,     96.0),   # header
        (0,   96.0,  W,     162.0),  # about
        (34,  163.5, 561.3, 280.9),  # İŞ DENEYİMİ bar + içerik
        (34,  280.9, 561.3, 390.0),  # PROJELER bar + proje 1 & 2
        (38,  390.0, 562,   449.0),  # 3. proje (dinamik)
        (34,  451.9, 561.3, 508.0),  # SERTİFİKALAR bar + içerik
        (34,  507.9, 561.3, 521.0),  # SOSYAL KATILIM bar
        (38,  524.0, 562,   570.0),  # sosyal içerik
        (34,  572.9, 561.3, 586.0),  # EĞİTİM DİL YETKİNLİK bar
        (38,  588.0, 385,   632.0),  # edu + lang içerik
        (38,  591.0, 210,   603.0),  # edu line1 (ayrıca)
        (388, 589.0, 549,   708.0),  # skills sütunu
        (34,  720.9, 561.3, 770.0),  # REFERANS bar + içerik
    ]:
        page.add_redact_annot(fitz.Rect(*rect), fill=(1, 1, 1))
    page.apply_redactions()

    # ── HEADER ────────────────────────────────────────────────────────────
    nw = fitz.get_text_length(CV_BASE["name"], fontname="helv", fontsize=22)
    t((W - nw) / 2 - 5, 60.0, CV_BASE["name"], fs=22, bold=True)
    title = "Electrical & Electronics Engineer"
    tw = fitz.get_text_length(title, fontname="helv", fontsize=9.5)
    t((W - tw) / 2, 72.0, title, fs=9.5)
    l2 = f"{CV_BASE['address']}  |  {CV_BASE['phone']}"
    t((W - fitz.get_text_length(l2, fontname="helv", fontsize=7.5)) / 2, 83.0, l2, fs=7.5)
    l3 = f"{CV_BASE['linkedin']}  |  {CV_BASE['email']}"
    t((W - fitz.get_text_length(l3, fontname="helv", fontsize=7.5)) / 2, 92.0, l3, fs=7.5)

    # ── ABOUT ─────────────────────────────────────────────────────────────
    bar(96.7, h=13.3)
    t(38, 104.5, "ABOUT", fs=10, bold=True)
    y = 115.0
    for line in _wrap_text(EN_ABOUT, 523, 8.0):
        if y >= 162.0:
            break
        t(38, y, line, fs=8)
        y += 11.0

    # ── WORK EXPERIENCE ───────────────────────────────────────────────────
    # Orijinal y: bar=163.5, company=180.2, summary=192.1, bullets=220.8
    bar(163.5)
    t(38, 171.3, "WORK EXPERIENCE", fs=10, bold=True)
    t(40, 186.4, EN_EXP_COMPANY, fs=8, bold=True)
    y = ww(40, 198.3, EN_EXP_SUMMARY, 515, fs=8, lh=10, y_max=222)
    y += 2
    for i, (bt, bd) in enumerate(EN_EXP_BULLETS):
        if y >= 278:
            break
        if i > 0:
            y += 4
        t(40, y, f"{bt}:", fs=7.5, bold=True)
        y += 9
        y = ww(48, y, bd, 505, fs=7.5, lh=9, y_max=285)

    # ── PROJECTS 1 & 2 ────────────────────────────────────────────────────
    # Orijinal y: bar=280.9, proje1 title=297.5, proje2 title=335.5
    bar(280.9)
    t(38, 288.7, "PROJECTS", fs=10, bold=True)
    t(40, 303.7, "Electronic Circuit Design: 555 Timer & AC/DC Adapter", fs=8, bold=True)
    ww(40, 314.7,
       "Designed a regulated AC-to-DC power supply providing stable DC output for electronic devices. "
       "Built and tested a 555-timer PWM signal generator circuit. "
       "Gained practical skills in analog circuit design, component selection, and lab measurement.",
       515, fs=8, lh=11, y_max=337)
    t(40, 341.7, "Machine Learning for Industrial Motor Vibration Analysis", fs=8, bold=True)
    ww(40, 352.7,
       "Built a bearing fault classifier using vibration sensor data from industrial motors. "
       "Switched from FFT to Hilbert-Huang Transform after finding FFT insufficient for "
       "non-stationary signals, improving accuracy. "
       "Applied supervised ML to distinguish inner race, outer race, and ball defects.",
       515, fs=8, lh=11, y_max=390)

    # ── 3rd PROJECT (dynamic) — template y0=391.8 → title baseline=399 ───
    proj_name = customized.get("dynamic_project_name", "").replace("**", "").replace("#", "").strip()
    proj_desc = customized.get("dynamic_project_desc", "")
    t(40, 391, proj_name, fs=8, bold=True)
    y_d = 402
    for line in _wrap_text(proj_desc, 515, 8):
        if y_d >= 449:
            break
        t(40, y_d, line, fs=8)
        y_d += 11

    # ── CERTIFICATIONS ────────────────────────────────────────────────────
    # Orijinal y: bar=451.9, içerik=469.5
    bar(451.9)
    t(38, 459.7, "CERTIFICATIONS", fs=10, bold=True)
    y = 475.7
    for cert in [
        "- STM32 Certificate (ST Microelectronics)  ·  Core Signal Processing Techniques in MATLAB (MathWorks)",
        "- Simulink Fundamentals (MathWorks)  ·  Simscape Onramp (MathWorks)",
        "- Simulink Onramp (MathWorks)  ·  MATLAB Onramp (MathWorks)",
    ]:
        if y >= 506:
            break
        y = ww(42, y, cert, 519, fs=8, lh=10, y_max=506)

    # ── ACTIVITIES ────────────────────────────────────────────────────────
    # Orijinal y: bar=507.9, içerik=523.9
    bar(507.9)
    t(38, 515.7, "ACTIVITIES", fs=10, bold=True)
    y_s = 530.7
    for item in EN_SOCIAL:
        t(38, y_s, f"- {item}", fs=7.5)
        y_s += 12.0

    # ── EDUCATION | LANGUAGES | SKILLS ────────────────────────────────────
    # Orijinal y: bar=572.9, içerik=591
    # Her başlığı kendi sütununun x konumunda ayrı yaz
    bar(572.9)
    t(38,  580.7, "EDUCATION",  fs=10, bold=True)
    t(214, 580.7, "LANGUAGES",  fs=10, bold=True)
    t(390, 580.7, "SKILLS",     fs=10, bold=True)

    # Education (sol — orijinal y: 590.9, 606.5, 621.5)
    t(38, 597.7, "Yasar University  (2021 - 2026)", fs=7.5)
    t(38, 612.3, "B.Sc. Electrical & Electronics Eng.", fs=7.5)
    t(38, 627.3, "(100% English-Medium)", fs=7.5)

    # Languages (orta — orijinal y: 591.5, 606.5, 621.5)
    t(214, 597.3, "English:   B2",       fs=7.5)
    t(214, 612.3, "Turkish:   Native",   fs=7.5)
    t(214, 627.3, "Ukrainian: Beginner", fs=7.5)

    # Skills (sağ — orijinal y0=591.2, satır aralığı=15)
    skills = [s.title() for s in customized.get("skills", CV_BASE["skills"])]
    y_sk = 598.0
    for sk in skills[:9]:
        t(390, y_sk, sk, fs=7.5)
        y_sk += 15.0

    # ── REFERENCES ────────────────────────────────────────────────────────
    # Orijinal y: bar=720.9, ref=742.4, dept=754.9
    bar(720.9)
    t(38, 728.7, "REFERENCES", fs=10, bold=True)
    t(40, 749.8, "\u00b7 Asst. Prof. Dr. Mahir Kutay", fs=9.5, bold=True)
    t(48, 761.9, "Yasar University, Electrical & Electronics Engineering", fs=9)

    doc.save(output_path, deflate=True, garbage=4)
    doc.close()


# ─── Veritabanı ───────────────────────────────────────────────────────────────

def get_analyzed_jobs() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, company, location, description, required_skills, match_score
        FROM jobs
        WHERE status IN ('analyzed', 'cv_ready') AND match_score >= ?
        ORDER BY match_score DESC
    """, (MIN_MATCH_SCORE,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_cv_ready(job_id: int, cv_path: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE jobs SET status = 'cv_ready' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


# ─── Ana Akış ─────────────────────────────────────────────────────────────────

def run():
    Path(CV_OUTPUT).mkdir(parents=True, exist_ok=True)
    jobs = get_analyzed_jobs()

    if not jobs:
        console.print(f"[yellow]Eslesme skoru >= {MIN_MATCH_SCORE} olan analiz edilmis ilan yok.[/yellow]")
        return

    console.print(f"\n[bold cyan]{len(jobs)} ilan icin CV ozellestiriliyor...[/bold cyan]\n")

    for job in jobs:
        import re
        raw = f"{job['company']}_{job['title']}"
        safe_name = re.sub(r'[^\w\-]', '_', raw.replace('\n', '').replace('\r', ''))
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')[:50]
        output_path = str(Path(CV_OUTPUT) / f"CV_{safe_name}.pdf")

        console.print(f"  -> {job['title']} @ {job['company']} (Skor: {job['match_score']:.0f})")

        customized = customize_with_ai(job)
        build_pdf(job, customized, output_path)
        mark_cv_ready(job["id"], output_path)

        console.print(f"    [green]OK {output_path}[/green]")

    console.print(f"\n[bold green]OK {len(jobs)} CV olusturuldu -> {CV_OUTPUT}[/bold green]")


if __name__ == "__main__":
    run()
