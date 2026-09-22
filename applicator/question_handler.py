"""
Soru Bankası — LinkedIn Easy Apply soru yönetimi
─────────────────────────────────────────────────
Cevap önceliği:
  1. Kural tabanlı (standart sorular)
  2. Kullanıcının bankaya girdiği cevap
  3. AI fallback (kullanıcı cevaplarını baz alarak)
  4. None → ilan atlanır, soru bankaya kaydedilir
"""

import json
import re
import sqlite3
from pathlib import Path

import anthropic

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import DB_PATH, ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

CV_PROFILE = """
Ad: Berk İnan
Bölüm: Elektrik-Elektronik Mühendisliği, Yaşar Üniversitesi (%100 İngilizce), Mayıs 2026 mezunu
Konum: İzmir/Bornova | Telefon: +90 538 074 00 09
Deneyim: Ermas Elektronik — Gömülü Sistemler & Donanım Stajyeri (STM32, firmware, devre tasarımı)
Beceriler: Python, MATLAB, STM32, Arduino C/C++, Proteus, Siemens S7-1500, Communication Protocols, ML
Dil: Türkçe (ana dil), İngilizce (B2), Ukraynaca (başlangıç)
Uyruk: T.C. vatandaşı | Çalışma izni: Türkiye'de tam yetkili | Askerlik: tecilli
"""

# ─── Kural Seti ───────────────────────────────────────────────────────────────
# Her kural: (anahtar kelimeler, TR cevap, EN cevap)
RULES: list[tuple[list[str], str, str]] = [
    (["çalışma izni", "work permit", "authorized to work", "çalışmaya yetkili",
      "yasal olarak", "legally authorized"], "Evet", "Yes"),
    (["türkiye vatandaş", "turkish citizen", "türk vatandaş",
      "vatandaşlık", "citizenship"], "Evet", "Yes"),
    (["vize sponsor", "visa sponsor", "sponsorship required"], "Hayır", "No"),
    (["askerlik", "military service", "military obligation"], "Tecilli", "Deferred"),
    (["uzaktan çalış", "remote work", "hibrit", "hybrid work"], "Evet", "Yes"),
    (["kaç yıl", "years of experience", "yıl deneyim",
      "how many years", "years relevant"], "0", "0"),
    (["eğitim seviyesi", "education level", "en yüksek eğitim",
      "highest education", "highest degree", "degree level"], "Lisans", "Bachelor's"),
    (["maaş beklenti", "salary expectation", "beklenen maaş",
      "expected salary", "desired salary", "maas", "ucret beklenti",
      "ücret beklenti", "net maaş", "gross salary", "brüt maaş"], "40000", "40000"),
    (["engellilik", "disability", "engelli"], "Hayır", "No"),
    (["location", "city", "şehir", "konum", "şehir adı", "bulunduğunuz şehir",
      "ikamet", "yaşadığınız", "hangi şehir"], "İzmir", "İzmir"),
    (["not ortalama", "gpa", "sınıf derece", "sinif derece", "lisans ortalama",
      "öğrenim görülen sınıf", "ogrenim gorulen sinif", "akademik ortalama",
      "mezuniyet ortalama", "4'lük", "4 luk"], "2.52", "2.52"),
    (["ösym sıralama", "osym sıralama", "osym siralama", "ösym siralama",
      "sıralama", "siralama", "yerleştiğiniz sıralama", "yerlestigi sıralama",
      "osym", "ösym"], "105653", "105653"),
    (["mezuniyet tarih", "mezuniyet ay", "mezun tarih", "graduation date",
      "when did you graduate", "ne zaman mezun"], "Mayıs 2026", "May 2026"),
    (["kaç dönem", "kac donem", "kac donem kaldigini", "dönem kaldı",
      "mezuniyetinize kac"], "0", "0"),
    (["haftada kaç gün", "haftada kac gun", "kaç gün çalışabilir",
      "kac gun calisabilir", "days per week", "haftada çalışma"], "5", "5"),
    (["elektronik harp", "electronic warfare", "savunma sistem", "defense system",
      "rf tasarım", "rf design", "mekanik tasarım", "mechanical design",
      "kontrol tasarım", "control design", "yazılım tasarım", "software design",
      "yüzey platform", "denizaltı", "submarine", "uçak", "aerospace",
      "radar", "sonar", "silah", "weapon", "askeri sistem", "military system"],
     "Hayır", "No"),
]


# ─── Yardımcılar ──────────────────────────────────────────────────────────────

_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().translate(_TR_MAP))


def _best_option(answer: str, options: list[str]) -> str | None:
    """Üretilen cevabı seçenekler listesindeki en yakın seçeneğe eşle."""
    if not options:
        return answer
    norm_ans = _norm(answer)
    # Tam eşleşme
    for opt in options:
        if _norm(opt) == norm_ans:
            return opt
    # İçerme
    for opt in options:
        if norm_ans in _norm(opt) or _norm(opt) in norm_ans:
            return opt
    return None


# ─── Veritabanı ───────────────────────────────────────────────────────────────

def init_question_bank():
    """question_bank ve application_log tablolarını oluştur (yoksa)."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS question_bank (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT    NOT NULL UNIQUE,
            question_type TEXT,
            options       TEXT,
            ai_answer     TEXT,
            user_answer   TEXT,
            times_seen    INTEGER DEFAULT 1,
            times_answered INTEGER DEFAULT 0,
            last_seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS application_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id        INTEGER NOT NULL,
            question_text TEXT,
            answer_given  TEXT,
            source        TEXT,
            logged_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def log_answer(job_id: int, question_text: str, answer: str | None, source: str):
    """Başvuru sırasında verilen cevabı application_log'a kaydet."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        INSERT INTO application_log (job_id, question_text, answer_given, source)
        VALUES (?, ?, ?, ?)
    """, (job_id, _norm(question_text), answer, source))
    conn.commit()
    conn.close()


def _find_in_bank(question_text: str) -> dict | None:
    norm = _norm(question_text)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    # Tam eşleşme (artık question_text normalize saklanıyor)
    row = conn.execute(
        "SELECT * FROM question_bank WHERE question_text = ?", (norm,)
    ).fetchone()

    if not row:
        # Kelime örtüşmesi — 3 veya daha fazla ortak kelime
        words = set(norm.split())
        for r in conn.execute("SELECT * FROM question_bank").fetchall():
            r_words = set(r["question_text"].split())
            if len(words & r_words) >= min(3, len(words)):
                row = r
                break

    conn.close()
    return dict(row) if row else None


def _save_to_bank(question_text: str, question_type: str,
                  options: list[str], answer: str | None, source: str):
    """Soruyu bankaya ekle ya da güncelle."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    norm = _norm(question_text)
    opts_json = json.dumps(options, ensure_ascii=False) if options else None

    # INSERT OR IGNORE — çakışmada sessizce geç, sonra UPDATE yap
    conn.execute("""
        INSERT OR IGNORE INTO question_bank
            (question_text, question_type, options, ai_answer, times_seen, times_answered)
        VALUES (?, ?, ?, ?, 1, ?)
    """, (
        norm,                                    # normalize edilmiş metin sakla
        question_type,
        opts_json,
        answer if source == "ai" else None,
        1 if answer else 0,
    ))

    # Zaten vardıysa güncelle
    conn.execute("""
        UPDATE question_bank
        SET times_seen    = times_seen + 1,
            last_seen_at  = CURRENT_TIMESTAMP,
            question_type = COALESCE(question_type, ?),
            options       = COALESCE(options, ?)
        WHERE question_text = ?
    """, (question_type, opts_json, norm))

    if answer and source == "ai":
        conn.execute(
            "UPDATE question_bank SET ai_answer = ?, times_answered = times_answered + 1 "
            "WHERE question_text = ?",
            (answer, norm)
        )
    elif answer and source in ("rule", "user"):
        conn.execute(
            "UPDATE question_bank SET times_answered = times_answered + 1 WHERE question_text = ?",
            (norm,)
        )

    conn.commit()
    conn.close()


def _get_user_context() -> str:
    """Bankadaki kullanıcı cevaplarını AI context'i olarak getir."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    rows = conn.execute(
        "SELECT question_text, user_answer FROM question_bank "
        "WHERE user_answer IS NOT NULL AND user_answer != ''"
    ).fetchall()
    conn.close()
    if not rows:
        return ""
    return "\n".join(f"- {r[0]}: {r[1]}" for r in rows)


def _get_job_description(job_id: int | None) -> str:
    """AI cevabını ilanın aradığı kriterlere göre hizalamak için açıklamayı getir."""
    if job_id is None:
        return ""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    row = conn.execute(
        "SELECT description FROM jobs WHERE id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return (row[0] or "")[:2000] if row else ""


# ─── Cevap Üretimi ────────────────────────────────────────────────────────────

def _rule_answer(question_text: str, options: list[str]) -> str | None:
    norm = _norm(question_text)
    for keywords, ans_tr, ans_en in RULES:
        if any(_norm(k) in norm for k in keywords):
            if not ans_tr:          # Boş kural → geç
                return None
            if options:
                result = _best_option(ans_tr, options) or _best_option(ans_en, options)
                return result
            return ans_tr
    return None


def _ai_answer(question_text: str, options: list[str], job_id: int | None = None) -> str | None:
    context = _get_user_context()
    context_block = (
        f"\n\nKullanicinin daha once verdigi cevaplar (baz al):\n{context}"
        if context else ""
    )
    job_desc = _get_job_description(job_id)
    job_block = f"\n\n## Ilan Aciklamasi (aranan kriterler)\n{job_desc}" if job_desc else ""
    opts_block = (
        "\n".join(f"- {o}" for o in options)
        if options else "Serbest metin giris"
    )
    prompt = (
        f"LinkedIn Easy Apply formunda su soru soruldu. "
        f"Adayin CV profiline ve ilanin aradigi kriterlere gore en uygun cevabi ver — "
        f"cevap adayin gercek CV'sinde karsiligi olan, dogru bir cevap olmali; "
        f"adayda olmayan bir deneyim/nitelik uydurma, sadece ilanin dilini/vurgusunu "
        f"yansitacak sekilde dogru bilgiyi ifade et.\n\n"
        f"## Aday Profili\n{CV_PROFILE}{context_block}{job_block}\n\n"
        f"## Soru\n{question_text}\n\n"
        f"## Secenekler\n{opts_block}\n\n"
        f"Sadece cevabi yaz. Secenekler varsa tam olarak bir secenegi yaz. "
        f"Baska hicbir sey yazma."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        if options:
            return _best_option(raw, options)
        return raw
    except Exception:
        return None


# ─── Ana Fonksiyon ────────────────────────────────────────────────────────────

def resolve(question_text: str, question_type: str, options: list[str],
            job_id: int | None = None) -> str | None:
    """
    Soru için cevap üret, bankaya ve application_log'a kaydet.
    Dönüş: cevap string | None (cevaplanamadı)
    """
    answer = None
    source = "none"

    # 1. Kural tabanlı
    answer = _rule_answer(question_text, options)
    if answer:
        source = "rule"

    # 2. Kullanıcı bankası
    if not answer:
        entry = _find_in_bank(question_text)
        if entry and entry.get("user_answer"):
            candidate = entry["user_answer"]
            answer = _best_option(candidate, options) if options else candidate
            if answer:
                source = "user"

    # 3. AI fallback — seçeneksiz sayısal/maaş alanlarda AI çağırma (kullanıcı dolduracak)
    _salary_kw = ("maaş", "salary", "ücret", "ucret", "wage", "compensation")
    _is_salary = any(k in _norm(question_text) for k in _salary_kw)
    if not answer and not ((question_type in ("number", "text") and not options) or _is_salary):
        answer = _ai_answer(question_text, options, job_id=job_id)
        if answer:
            source = "ai"

    # Bankaya kaydet
    _save_to_bank(question_text, question_type, options, answer, source)

    # Başvuru loguna kaydet (job_id verilmişse)
    if job_id is not None:
        log_answer(job_id, question_text, answer, source)

    return answer
