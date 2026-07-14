"""
İş İlanı AI Analizörü
──────────────────────
Her ilanın açıklamasını Claude ile analiz eder:
- Aranan beceri/teknolojiler
- Deneyim seviyesi
- CV ile eşleşme skoru
- Başvuru tavsiyesi
"""

import asyncio
import sqlite3
import json
from pathlib import Path

import anthropic
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.progress import track

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import ANTHROPIC_API_KEY, DB_PATH, MIN_MATCH_SCORE, CV_PROFILES

console = Console()
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── CV Özeti (bir kez okunur) ────────────────────────────────────────────────

def load_cv_text() -> str:
    """
    3 statik CV profilinin (TR) metnini birleştirip döndürür, böylece AI eşleşme
    skorunu adayın tüm kategorilerdeki (Signal/Embedded, Software/AI, Power
    Electronics) toplam yetkinliğine göre hesaplar. CV seçimi ayrı bir adımda
    (cv_manager.select_cv_profile) yapılır — burası sadece skorlama içindir.
    """
    try:
        from pypdf import PdfReader
        parts = []
        for profile in CV_PROFILES:
            path = Path(__file__).parent.parent / profile["cv_tr"]
            if not path.exists():
                continue
            reader = PdfReader(str(path))
            parts.append("\n".join(page.extract_text() or "" for page in reader.pages))
        return "\n\n".join(parts).strip()
    except Exception as e:
        logger.warning(f"CV okunamadı: {e}")
        return "CV bilgisi yüklenemedi."


# ─── Veritabanı ───────────────────────────────────────────────────────────────

def get_unanalyzed_jobs() -> list[dict]:
    """Henüz analiz edilmemiş ilanları getir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, company, location, description, url
        FROM jobs
        WHERE status = 'new' AND description IS NOT NULL AND description != ''
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_jobs_without_description() -> list[dict]:
    """Açıklaması henüz çekilmemiş ilanları getir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, company, url
        FROM jobs
        WHERE (description IS NULL OR description = '') AND status = 'new'
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_job_analysis(job_id: int, skills: list, score: float, summary: str, advice: str):
    """Analiz sonuçlarını veritabanına kaydet."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs SET
            required_skills = ?,
            match_score     = ?,
            status          = 'analyzed'
        WHERE id = ?
    """, (json.dumps(skills, ensure_ascii=False), score, job_id))
    conn.commit()
    conn.close()


def save_description(job_id: int, description: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE jobs SET description = ? WHERE id = ?", (description, job_id))
    conn.commit()
    conn.close()


# ─── Metin Ayıklama ───────────────────────────────────────────────────────────

def _extract_job_section(body_text: str) -> str:
    """
    Sayfa metninden iş ilanı açıklama bölümünü çıkar.
    LinkedIn 'İş ilanı hakkında' başlığını kullanıyor.
    """
    markers = [
        "İş ilanı hakkında",
        "About the job",
        "Job description",
        "İş Tanımı",
        "Pozisyon Hakkında",
    ]
    stop_markers = [
        "Ulaşabileceğiniz kişiler",
        "Benzer iş ilanları",
        "Bu iş ilanını bildirin",
        "Kaydet",
        "Similar jobs",
        "Report this job",
    ]

    for marker in markers:
        idx = body_text.find(marker)
        if idx != -1:
            desc = body_text[idx + len(marker):].strip()
            # Durdurma noktasında kes
            for stop in stop_markers:
                stop_idx = desc.find(stop)
                if stop_idx != -1:
                    desc = desc[:stop_idx].strip()
            if len(desc) > 50:
                return desc[:5000]  # max 5000 karakter

    return ""


# ─── İlan Açıklaması Çekme ────────────────────────────────────────────────────

async def fetch_descriptions():
    """Açıklaması olmayan ilanları Playwright ile ziyaret edip açıklamayı çek."""
    from playwright.async_api import async_playwright
    from config.settings import LINKEDIN_EMAIL, LINKEDIN_PASSWORD

    jobs = get_jobs_without_description()
    if not jobs:
        logger.info("Tüm ilanların açıklaması zaten mevcut.")
        return

    logger.info(f"{len(jobs)} ilanın açıklaması çekilecek...")

    from config.settings import OPERA_EXE, OPERA_PROFILE, AUTOMATION_WINDOW_ARGS
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=OPERA_PROFILE,
            executable_path=OPERA_EXE,
            headless=False,
            slow_mo=30,
            args=AUTOMATION_WINDOW_ARGS,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # Profil giriş yapılıysa login atla
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        if "feed" not in page.url:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
            await page.fill("#username", LINKEDIN_EMAIL)
            await page.fill("#password", LINKEDIN_PASSWORD)
            await page.click('[type="submit"]')
            await page.wait_for_timeout(4000)

        for job in track(jobs, description="Açıklamalar çekiliyor..."):
            try:
                await page.goto(job["url"], wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                # Sayfanın tam metnini al ve "İş ilanı hakkında" bölümünü çıkar
                body_text = await page.inner_text("body")
                desc = _extract_job_section(body_text)

                if desc:
                    save_description(job["id"], desc)
                    logger.success(f"  ✓ {job['title']} — {job['company']} ({len(desc)} karakter)")
                else:
                    logger.warning(f"  ✗ Açıklama bulunamadı: {job['title']}")

                await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"  Hata ({job['title']}): {e}")

        await context.close()

    logger.info("Açıklamalar tamamlandı.")


# ─── AI Analiz ────────────────────────────────────────────────────────────────

def analyze_job_with_ai(job: dict, cv_text: str) -> dict:
    """Bir ilanı Claude ile analiz et, CV ile karşılaştır."""

    prompt = f"""Sen bir kariyer danışmanısın. Aşağıdaki iş ilanını ve adayın CV'sini analiz et.

## İş İlanı
Pozisyon: {job['title']}
Şirket: {job['company']}
Lokasyon: {job['location']}

Açıklama:
{job['description'][:3000]}

## Aday CV
{cv_text[:2000]}

## Görevin
Şu JSON formatında yanıt ver (başka hiçbir şey yazma):
{{
  "required_skills": ["skill1", "skill2", ...],
  "experience_level": "stajyer|yeni mezun|junior|mid|senior",
  "match_score": 0-100,
  "matching_points": ["uyuşan nokta 1", "uyuşan nokta 2"],
  "missing_points": ["eksik nokta 1", "eksik nokta 2"],
  "summary": "2-3 cümle özet",
  "apply_advice": "başvur|atla|önce hazırlan"
}}

match_score: Adayın bu ilana ne kadar uyduğu (0-100).
apply_advice: "başvur" (70+), "önce hazırlan" (50-69), "atla" (50 altı)"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # JSON'u parse et
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        return json.loads(text)
    except Exception as e:
        logger.warning(f"AI analiz hatası: {e}")
        return {
            "required_skills": [],
            "match_score": 0,
            "summary": "Analiz başarısız.",
            "apply_advice": "atla"
        }


# ─── Sonuç Tablosu ────────────────────────────────────────────────────────────

def show_results():
    """Analiz edilmiş ilanları tablo olarak göster."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, company, location, match_score, required_skills, status
        FROM jobs
        WHERE status = 'analyzed'
        ORDER BY match_score DESC
    """).fetchall()
    conn.close()

    table = Table(title="Analiz Sonuçları", show_lines=True)
    table.add_column("Skor", style="bold", width=6)
    table.add_column("Pozisyon", width=30)
    table.add_column("Şirket", width=25)
    table.add_column("Konum", width=15)
    table.add_column("Aranan Beceriler", width=40)

    for row in rows:
        score = row["match_score"] or 0
        skills = json.loads(row["required_skills"] or "[]")
        color = "green" if score >= 70 else "yellow" if score >= 50 else "red"
        table.add_row(
            f"[{color}]{score:.0f}[/{color}]",
            row["title"] or "—",
            row["company"] or "—",
            row["location"] or "—",
            ", ".join(skills[:5]),
        )

    console.print(table)


# ─── Ana Akış ─────────────────────────────────────────────────────────────────

async def run(skip_fetch: bool = False):
    if not skip_fetch:
        console.print("\n[bold cyan]Aşama 1: İlan açıklamaları çekiliyor...[/bold cyan]")
        await fetch_descriptions()
    else:
        console.print("\n[yellow]--skip-fetch: açıklama çekme adımı atlandı.[/yellow]")

    console.print("\n[bold cyan]Aşama 2: AI analizi yapılıyor...[/bold cyan]")
    cv_text = load_cv_text()
    if not cv_text or cv_text == "CV bilgisi yüklenemedi.":
        console.print("[red]CV okunamadı! CV_PROFILES içindeki TR dosyaları mevcut mu?[/red]")
        return

    jobs = get_unanalyzed_jobs()
    if not jobs:
        console.print("[yellow]Analiz edilecek ilan yok. Önce scraper'ı çalıştır.[/yellow]")
        return

    console.print(f"{len(jobs)} ilan analiz edilecek...")

    for job in track(jobs, description="AI analizi..."):
        result = analyze_job_with_ai(job, cv_text)
        update_job_analysis(
            job_id=job["id"],
            skills=result.get("required_skills", []),
            score=result.get("match_score", 0),
            summary=result.get("summary", ""),
            advice=result.get("apply_advice", "atla"),
        )

    console.print("\n[bold green]OK Analiz tamamlandi![/bold green]\n")
    show_results()

    # Windows bildirimi — score>=60 ilan varsa bildir
    try:
        from utils.notify import notify_high_score_jobs
        notify_high_score_jobs(min_score=60.0)
    except Exception:
        pass


if __name__ == "__main__":
    import sys
    skip_fetch = "--skip-fetch" in sys.argv
    asyncio.run(run(skip_fetch=skip_fetch))
