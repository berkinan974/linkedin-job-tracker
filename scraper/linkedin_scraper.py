"""
LinkedIn İş İlanı Toplayıcı
────────────────────────────
Playwright kullanarak LinkedIn'den iş ilanlarını çeker,
filtreler ve veritabanına kaydeder.
"""

import asyncio
import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import (
    LINKEDIN_EMAIL, LINKEDIN_PASSWORD,
    SEARCH_JOBS, SEARCH_LOCATIONS, WORK_TYPES,
    EXPERIENCE_LEVELS, MAX_JOBS_PER_SEARCH, DB_PATH,
    OPERA_EXE, OPERA_PROFILE, AUTOMATION_WINDOW_ARGS,
)

console = Console()


# ─── Veritabanı ──────────────────────────────────────────────────────────────

def init_db():
    """Veritabanı tablolarını oluştur."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.execute("PRAGMA encoding='UTF-8'")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            linkedin_id     TEXT UNIQUE,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            work_type       TEXT,
            experience      TEXT,
            description     TEXT,
            required_skills TEXT,
            match_score     REAL DEFAULT 0,
            status          TEXT DEFAULT 'new',
            applied_at      TEXT,
            url             TEXT,
            search_keyword  TEXT,
            search_location TEXT,
            scraped_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Eski DB'lere sütun ekle (varsa hata vermez)
    for col in [
        "search_keyword TEXT", "search_location TEXT",
        "feedback_status TEXT DEFAULT 'waiting'",
        "feedback_note TEXT", "interview_date TEXT",
    ]:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col}")
        except Exception:
            pass
    conn.commit()
    conn.close()
    logger.info("Veritabanı hazır.")


def save_job(job: dict):
    """Bir ilanı veritabanına kaydet (zaten varsa güncelleme yapma)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO jobs
                (linkedin_id, title, company, location, work_type, experience,
                 description, url, search_keyword, search_location)
            VALUES
                (:linkedin_id, :title, :company, :location, :work_type, :experience,
                 :description, :url, :search_keyword, :search_location)
        """, job)
        conn.commit()
    finally:
        conn.close()


# ─── Scraper ─────────────────────────────────────────────────────────────────

class LinkedInScraper:

    def __init__(self, headless: bool = False):
        """
        headless=False → tarayıcıyı görerek çalıştır (debug için iyi)
        headless=True  → arka planda çalıştır
        """
        self.headless = headless
        self.browser  = None
        self.page     = None

    # ── Giriş ────────────────────────────────────────────────────────────────

    async def login(self):
        """LinkedIn hesabına giriş yap."""
        logger.info("LinkedIn'e giriş yapılıyor...")
        await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
        await self.page.fill("#username", LINKEDIN_EMAIL)
        await self.page.fill("#password", LINKEDIN_PASSWORD)
        await self.page.click('[type="submit"]')
        await self.page.wait_for_timeout(3000)

        if "feed" in self.page.url or "checkpoint" in self.page.url:
            logger.success("Giriş başarılı.")
        else:
            logger.error("Giriş başarısız! E-posta/şifre kontrol et.")
            raise RuntimeError("LinkedIn girişi başarısız.")

    # ── Arama ─────────────────────────────────────────────────────────────────

    async def search_jobs(self, keyword: str, location: str) -> list[dict]:
        self._current_keyword  = keyword
        self._current_location = location
        """Belirli bir anahtar kelime + konum için iş ilanı ara."""
        jobs = []
        seen_ids = set()
        start = 0  # LinkedIn sayfalama parametresi (her sayfada 25 ilan)

        params_base = (
            f"keywords={keyword.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20').replace(',', '%2C')}"
            f"&f_WT=1,2,3"
            f"&f_E=1,2,3"
            f"&f_LF=f_AL"   # Sadece Easy Apply ilanları
            f"&sortBy=DD"
        )

        logger.info(f"Araniyor: '{keyword}' — {location}")

        while len(jobs) < MAX_JOBS_PER_SEARCH:
            url = f"https://www.linkedin.com/jobs/search/?{params_base}&start={start}"
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000)

            # Sayfayı aşağı kaydır — lazy load için
            await self._scroll_job_list()

            cards = await self.page.query_selector_all(".job-card-container, [data-job-id]")
            if not cards:
                logger.warning("İlan kartı bulunamadı, sayfa yapısı değişmiş olabilir.")
                break

            new_found = 0
            for card in cards:
                job = await self._parse_card(card)
                if job and job["linkedin_id"] and job["url"] and job["linkedin_id"] not in seen_ids:
                    seen_ids.add(job["linkedin_id"])
                    jobs.append(job)
                    new_found += 1
                    if len(jobs) >= MAX_JOBS_PER_SEARCH:
                        break

            logger.info(f"  start={start} → {new_found} yeni ilan (toplam: {len(jobs)})")

            # Yeni ilan gelmediyse dur
            if new_found == 0:
                break

            start += 25  # sonraki sayfa
            await asyncio.sleep(2)

        logger.info(f"  → {len(jobs)} ilan bulundu.")
        return jobs

    # ── Kart Ayrıştırma ───────────────────────────────────────────────────────

    async def _parse_card(self, card) -> dict | None:
        """İlan kartından temel bilgileri çek."""
        try:
            linkedin_id = await card.get_attribute("data-job-id") or ""
            title_el    = await card.query_selector(".job-card-list__title, .job-card-container__link")
            company_el  = await card.query_selector(".job-card-container__company-name, .artdeco-entity-lockup__subtitle")
            location_el = await card.query_selector(".job-card-container__metadata-item")
            link_el     = await card.query_selector("a[href*='/jobs/view/']")

            title    = (await title_el.inner_text()).strip()    if title_el    else "—"
            company  = (await company_el.inner_text()).strip()  if company_el  else "—"
            location = (await location_el.inner_text()).strip() if location_el else "—"
            url      = await link_el.get_attribute("href")      if link_el     else ""
            if url and not url.startswith("http"):
                url = "https://www.linkedin.com" + url

            return {
                "linkedin_id":     linkedin_id,
                "title":           title,
                "company":         company,
                "location":        location,
                "work_type":       self._detect_work_type(location),
                "experience":      "",
                "description":     "",
                "url":             url,
                "search_keyword":  self._current_keyword,
                "search_location": self._current_location,
            }
        except Exception as e:
            logger.warning(f"Kart ayrıştırma hatası: {e}")
            return None

    # ── Scroll ────────────────────────────────────────────────────────────────

    async def _scroll_job_list(self):
        """Sol paneldeki iş listesini aşağı kaydırarak tüm kartları yükle."""
        # Önce liste panelini bul
        list_panel = await self.page.query_selector(".jobs-search-results-list, .scaffold-layout__list")
        if list_panel:
            # Paneli yavaşça aşağı kaydır
            for _ in range(6):
                await list_panel.evaluate("el => el.scrollBy(0, 500)")
                await self.page.wait_for_timeout(400)
        else:
            # Panel bulunamazsa sayfanın tamamını kaydır
            for _ in range(6):
                await self.page.evaluate("window.scrollBy(0, 600)")
                await self.page.wait_for_timeout(400)
        # En üste dön
        await self.page.wait_for_timeout(500)

    # ── İlan Detayı ───────────────────────────────────────────────────────────

    async def fetch_description(self, job_url: str) -> str:
        """İlanın tam açıklamasını çek (AI analizi için gerekli)."""
        try:
            await self.page.goto(job_url, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(1500)
            desc_el = await self.page.query_selector(".jobs-description__content, .job-view-layout")
            if desc_el:
                return (await desc_el.inner_text()).strip()
        except PlaywrightTimeout:
            logger.warning(f"Timeout: {job_url}")
        return ""

    # ── Yardımcı ──────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_work_type(location_text: str) -> str:
        text = location_text.lower()
        if "remote" in text or "uzaktan" in text:
            return "remote"
        if "hybrid" in text or "hibrit" in text:
            return "hybrid"
        return "on-site"

    # ── Ana Akış ──────────────────────────────────────────────────────────────

    async def run(self):
        """Tüm arama kombinasyonlarını tara ve veritabanına kaydet."""
        init_db()

        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=OPERA_PROFILE,
                executable_path=OPERA_EXE,
                headless=self.headless,
                slow_mo=50,
                args=AUTOMATION_WINDOW_ARGS,
                viewport={"width": 1280, "height": 800},
            )
            for old_page in context.pages:
                await old_page.close()
            self.page = await context.new_page()
            self.browser = context

            # Profil zaten giriş yapılıysa login atla
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000)
            if "feed" not in self.page.url:
                await self.login()

            total_saved = 0
            for keyword in SEARCH_JOBS:
                for location in SEARCH_LOCATIONS:
                    jobs = await self.search_jobs(keyword, location)
                    for job in jobs:
                        save_job(job)
                        total_saved += 1
                    await asyncio.sleep(3)   # sunucuya nazik ol

            await context.close()

        console.print(f"\n[bold green]✓ Toplam {total_saved} ilan veritabanına kaydedildi.[/bold green]")


# ─── Çalıştır ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(LinkedInScraper(headless=False).run())
