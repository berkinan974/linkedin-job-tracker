"""
LinkedIn Job Tracker — Otomatik Pipeline
─────────────────────────────────────────
Sırasıyla çalıştırır:
  1. Scraper   — LinkedIn'den iş ilanlarını çek
  2. Analyzer  — AI ile analiz et + Windows bildirimi
  3. CV Mgr    — Yüksek skorlu ilanlar için CV üret
  4. Cover Ltr — Kapak mektubu üret

Başvuru (applicator) otomasyona dahil DEĞİL — manuel onay gerektirir.

Kullanım:
    py run_pipeline.py
    py run_pipeline.py --skip-scrape   (scraper'ı atla, sadece analiz)
    py run_pipeline.py --skip-fetch    (açıklama çekmeyi atla)
"""

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from loguru import logger

# Log dosyası
LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger.add(str(log_file), rotation="10 MB", encoding="utf-8")

SKIP_SCRAPE = "--skip-scrape" in sys.argv
SKIP_FETCH  = "--skip-fetch"  in sys.argv


def step(name: str):
    line = "─" * 50
    print(f"\n{line}")
    print(f"  {name}")
    print(f"{line}")
    logger.info(f"Adim basladi: {name}")


async def run_scraper():
    step("Adim 1/4 — Scraper")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from scraper.linkedin_scraper import LinkedInScraper
        await LinkedInScraper(headless=False).run()
        logger.success("Scraper tamamlandi.")
    except Exception as e:
        logger.error(f"Scraper hatasi: {e}")
        raise


async def run_analyzer():
    step("Adim 2/4 — Analyzer + Bildirim")
    try:
        from analyzer.job_analyzer import run as analyze_run
        await analyze_run(skip_fetch=SKIP_FETCH)
        logger.success("Analyzer tamamlandi.")
    except Exception as e:
        logger.error(f"Analyzer hatasi: {e}")
        raise


def run_cv_manager():
    step("Adim 3/4 — CV Manager")
    try:
        from cv_manager.cv_generator import run as cv_run
        cv_run()
        logger.success("CV Manager tamamlandi.")
    except Exception as e:
        logger.warning(f"CV Manager hatasi (devam ediliyor): {e}")


def run_cover_letter():
    step("Adim 4/4 — Cover Letter")
    try:
        from cover_letter.cover_letter_generator import run as cl_run
        cl_run()
        logger.success("Cover Letter tamamlandi.")
    except Exception as e:
        logger.warning(f"Cover Letter hatasi (devam ediliyor): {e}")


async def main():
    start = datetime.now()
    print(f"\n{'='*50}")
    print(f"  LinkedIn Pipeline Basladi — {start.strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*50}")

    try:
        if not SKIP_SCRAPE:
            await run_scraper()
        else:
            print("\n[--skip-scrape] Scraper atlandi.")

        await run_analyzer()
        run_cv_manager()
        run_cover_letter()

    except KeyboardInterrupt:
        print("\n\nPipeline kullanici tarafindan durduruldu.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Pipeline beklenmedik hata: {e}")
        print(f"\n[HATA] Pipeline durdu: {e}")
        sys.exit(1)

    elapsed = (datetime.now() - start).seconds
    mins, secs = divmod(elapsed, 60)
    print(f"\n{'='*50}")
    print(f"  Pipeline tamamlandi! Sure: {mins}d {secs}s")
    print(f"  Log: {log_file}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
