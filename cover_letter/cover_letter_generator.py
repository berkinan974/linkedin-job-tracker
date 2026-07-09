"""
Cover Letter Generator
──────────────────────
Her iş ilanı için AI ile Türkçe ön yazı üretir,
ardından humanizer ile doğal bir dile dönüştürür.
"""

import sqlite3
import re
from pathlib import Path
from datetime import datetime

import anthropic
from loguru import logger
from rich.console import Console

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import (
    ANTHROPIC_API_KEY, DB_PATH,
    CV_OUTPUT, COVER_LETTER_OUTPUT, MIN_MATCH_SCORE
)

console = Console()
client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

CV_PROFILE = """
Ad: Berk İnan
Bölüm: Elektrik-Elektronik Mühendisliği, Yaşar Üniversitesi (%100 İngilizce), Mayıs 2025 mezunu
Konum: İzmir/Bornova
İletişim: +90 538 074 00 09 | berkinan974@gmail.com
Deneyim: FrikElektronik — Gömülü Sistemler & Donanım Stajyeri (STM32, firmware, devre tasarımı)
Beceriler: Python, MATLAB, STM32, Arduino C/C++, Proteus, Siemens S7-1500, Communication Protocols, Machine Learning
Sertifikalar: STM32, MATLAB Onramp, Simulink Onramp, Simulink Fundamentals, Simscape Onramp, Core Signal Processing Techniques in MATLAB
Sosyal: Amerikan Futbolu (Türkiye Şampiyonu), Gelişim Proje Topluluğu Denetim Kurulu Başkanı
Dil: Türkçe (ana dil), İngilizce (intermediate), Ukraynaca (başlangıç)
"""


# ─── 1. Adım: Ham Cover Letter ────────────────────────────────────────────────

def _generate_raw(job: dict) -> str:
    prompt = f"""Sen bir kariyer danışmanısın. Aşağıdaki iş ilanı için Türkçe bir ön yazı (cover letter) yaz.

## Aday Profili
{CV_PROFILE}

## İş İlanı
Pozisyon : {job['title']}
Şirket   : {job['company']}
Beceriler: {job.get('required_skills', '')}
Açıklama :
{(job.get('description') or '')[:1500]}

## Kurallar
- Konu satırı: "Başvuru: [Pozisyon Adı] | Berk İnan"
- Selamlama: "Merhaba," veya "Sayın İlgili,"
- 3 paragraf: (1) neden bu pozisyon ilgini çekiyor, (2) ilanla örtüşen 2-3 somut beceri/deneyim, (3) kapanış
- İlk cümlede asla "Ben ... 'ım/im" veya isim kullanma — CV'de zaten var
- Doğrudan konuya gir: pozisyona olan ilginle başla
- İmza: Ad, telefon, email
- Samimi ve özgüvenli ama kibar bir ton
- Maksimum 200 kelime
- Sadece ön yazı metnini döndür, başka hiçbir şey yazma"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


# ─── 2. Adım: Humanizer ───────────────────────────────────────────────────────

def _humanize(text: str) -> str:
    prompt = f"""Aşağıdaki AI tarafından yazılmış Türkçe ön yazıyı daha doğal ve insan yazısı gibi yeniden yaz.

Kurallar:
- Tüm teknik terimler, isimler, iletişim bilgileri aynen kalsın
- Cümle uzunluklarını çeşitlendir — kısa ve uzun cümleler karıştır
- "Ayrıca", "Bunun yanı sıra", "Öte yandan" gibi resmi bağlaçlar yerine daha sade geçişler kullan
- Zaman zaman belirsizlik tonu ekle ("sanırım", "bence", "inanıyorum ki")
- Tek tip uzun paragrafları kır
- Abartılı iddialı ifadeleri yumuşat
- Uydurma bilgi ekleme, sadece metni yeniden yaz
- Sadece yeniden yazılmış metni döndür, yorum ekleme

Metin:
{text}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


# ─── Veritabanı ───────────────────────────────────────────────────────────────

def get_jobs() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, company, description, required_skills, match_score
        FROM jobs
        WHERE status IN ('analyzed', 'cv_ready') AND match_score >= ?
        ORDER BY match_score DESC
    """, (MIN_MATCH_SCORE,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_cover_letter_done(job_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE jobs SET status = 'cover_letter_ready' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


# ─── Tek İlan İçin Üret ───────────────────────────────────────────────────────

def generate_for_job(job: dict, save: bool = True) -> str:
    """Tek bir ilan için cover letter üretir ve döndürür."""
    raw       = _generate_raw(job)
    humanized = _humanize(raw)

    if save:
        Path(COVER_LETTER_OUTPUT).mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[^\w\-]', '_', f"{job['company']}_{job['title']}")
        safe = re.sub(r'_+', '_', safe).strip('_')[:50]
        out_path = Path(COVER_LETTER_OUTPUT) / f"CL_{safe}.txt"
        out_path.write_text(humanized, encoding="utf-8")
        logger.info(f"Cover letter kaydedildi: {out_path}")

    return humanized


# ─── Ana Akış ─────────────────────────────────────────────────────────────────

def run():
    Path(COVER_LETTER_OUTPUT).mkdir(parents=True, exist_ok=True)
    jobs = get_jobs()

    if not jobs:
        console.print(f"[yellow]Eslesme skoru >= {MIN_MATCH_SCORE} olan ilan yok.[/yellow]")
        return

    console.print(f"\n[bold cyan]{len(jobs)} ilan icin on yazi uretiliyor...[/bold cyan]\n")

    for job in jobs:
        console.print(f"  -> {job['title']} @ {job['company']} (Skor: {job['match_score']:.0f})")
        text = generate_for_job(job, save=True)
        mark_cover_letter_done(job["id"])
        console.print(f"    [green]OK[/green]")
        console.print(f"    [dim]{text[:120]}...[/dim]\n")

    console.print(f"[bold green]OK {len(jobs)} on yazi uretildi -> {COVER_LETTER_OUTPUT}[/bold green]")


if __name__ == "__main__":
    run()
