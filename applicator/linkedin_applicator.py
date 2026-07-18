"""
LinkedIn Otomatik Başvuru Modülü
─────────────────────────────────
cv_ready statüsündeki ilanlar için Easy Apply akışını otomatik yürütür.
Karmaşık metin soruları içeren ilanları güvenli biçimde atlar.
"""

import asyncio
import re
import sqlite3
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from loguru import logger
from rich.console import Console
from rich.table import Table

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import (
    LINKEDIN_EMAIL, LINKEDIN_PASSWORD,
    DB_PATH, CV_OUTPUT, APPLY_AUTOMATICALLY,
    MIN_MATCH_SCORE, OPERA_EXE, OPERA_PROFILE, AUTOMATION_WINDOW_ARGS,
)
from applicator.question_handler import resolve, init_question_bank, log_answer

console = Console()

# ─── Veritabanı ───────────────────────────────────────────────────────────────

def get_cv_ready_jobs() -> list[dict]:
    """Başvuru bekleyen (cv_ready) ilanları getir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, company, location, url, match_score
        FROM jobs
        WHERE status IN ('cv_ready', 'cover_letter_ready') AND match_score >= ?
        ORDER BY match_score DESC
    """, (MIN_MATCH_SCORE,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_applied(job_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs
        SET status = 'applied', applied_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (job_id,))
    conn.commit()
    conn.close()


def mark_skipped(job_id: int):
    """Karmaşık sorular nedeniyle atlanan ilanı işaretle (status değişmez, sadece log)."""
    pass  # status cv_ready kalır, bir sonraki çalıştırmada tekrar denenir


# ─── CV Dosyası Bulma ─────────────────────────────────────────────────────────

def find_cv_path(job: dict) -> str | None:
    """cv_manager ile aynı isimlendirme mantığını kullanarak CV dosyasını bul."""
    raw = f"{job['company']}_{job['title']}"
    safe_name = re.sub(r'[^\w\-]', '_', raw.replace('\n', '').replace('\r', ''))
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')[:50]
    path = Path(CV_OUTPUT) / f"CV_{safe_name}.pdf"
    if path.exists():
        return str(path.resolve())
    # Arama: şirket adıyla başlayan herhangi bir CV
    company_slug = re.sub(r'[^\w\-]', '_', job['company'])[:20].strip('_')
    matches = list(Path(CV_OUTPUT).glob(f"CV_{company_slug}*.pdf"))
    if matches:
        return str(matches[0].resolve())
    return None


# ─── Easy Apply İşleyici ──────────────────────────────────────────────────────

class LinkedInApplicator:

    PHONE = "05380740009"  # CV'deki telefon numarası

    def __init__(self, headless: bool = False, dry_run: bool = False, limit: int | None = None,
                 max_real_applications: int | None = None):
        self.headless = headless
        self.dry_run  = dry_run
        self.limit    = limit
        self.max_real_applications = max_real_applications
        self.page     = None
        self.results  = []   # (job, "applied" | "skipped" | "no_easy_apply" | "error")
        init_question_bank()

    # ── Giriş ─────────────────────────────────────────────────────────────────

    async def login(self):
        logger.info("LinkedIn'e giriş yapılıyor...")
        await self.page.goto(
            "https://www.linkedin.com/login",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await self.page.fill("#username", LINKEDIN_EMAIL)
        await self.page.fill("#password", LINKEDIN_PASSWORD)
        await self.page.click('[type="submit"]')
        await self.page.wait_for_timeout(4000)

        if "feed" in self.page.url or "checkpoint" in self.page.url:
            logger.success("Giriş başarılı.")
        else:
            raise RuntimeError("LinkedIn girişi başarısız! E-posta/şifre kontrol et.")

    # ── Tek İlana Başvur ──────────────────────────────────────────────────────

    async def apply_to_job(self, job: dict, cv_path: str | None) -> str:
        """
        Döndürür:
          "applied"        — başvuru tamamlandı
          "skipped"        — karmaşık soru nedeniyle atlandı
          "no_easy_apply"  — Easy Apply butonu yok
          "error"          — beklenmeyen hata
        """
        try:
            await self.page.goto(job["url"], wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000)
            url_before_click = self.page.url

            # Sayfa yüklenir yüklenmez limit kontrolü (buton gizlenmiş olabilir)
            if await self._check_daily_limit():
                return "daily_limit"

            # Easy Apply butonunu bul
            apply_btn = await self._find_easy_apply_button()
            if not apply_btn:
                logger.warning(f"  Easy Apply yok: {job['title']} @ {job['company']}")
                return "no_easy_apply"

            if self.dry_run:
                logger.info(f"  [DRY-RUN] Başvurulurdu: {job['title']} @ {job['company']}")
                return "applied"

            # Tıkla ve modalın açılmasını bekle
            await apply_btn.click()
            await self.page.wait_for_timeout(3000)

            # Günlük limit kontrolü
            if await self._check_daily_limit():
                return "daily_limit"

            # Bazı ilanlar (Ceipal, Greenhouse vb. üçüncü parti ATS) native modal
            # yerine tam sayfa yönlendirmesi yapıyor — bunları desteklemiyoruz,
            # sessizce "error" vermek yerine ayrı statüyle atla.
            modal = await self.page.query_selector(
                ".jobs-easy-apply-modal, [data-test-modal]"
            )
            if not modal and self.page.url != url_before_click:
                logger.info(
                    f"  Üçüncü parti ATS yönlendirmesi (native modal değil), atlanıyor: "
                    f"{job['title']} @ {job['company']} → {self.page.url}"
                )
                return "external_ats"

            # Modal adımlarını yönet
            result = await self._handle_modal(cv_path, job["id"])
            return result

        except PlaywrightTimeout:
            logger.warning(f"  Timeout: {job['title']}")
            return "error"
        except Exception as e:
            logger.warning(f"  Hata ({job['title']}): {e}")
            return "error"

    async def _check_daily_limit(self) -> bool:
        """Günlük Easy Apply limitine ulaşıldıysa True döner ve dialogu kapatır."""
        try:
            el = await self.page.query_selector("text=You reached today's Easy Apply limit")
            if not el:
                el = await self.page.query_selector("text=today's Easy Apply limit")
            if el:
                logger.warning("  Günlük Easy Apply limitine ulaşıldı! Durduruluyor.")
                got_it = await self.page.query_selector("button:has-text('Got it')")
                if got_it:
                    await got_it.click()
                return True
        except Exception:
            pass
        return False

    async def _find_easy_apply_button(self):
        """Sayfadaki Easy Apply / Kolay Başvur butonunu bul."""
        selectors = [
            "a[aria-label='Bu işe kolay başvuru yapın']",
            "a[aria-label*='kolay başvuru']",
            "a[href*='/apply/']",
            "button.jobs-apply-button",
            "button:has-text('Easy Apply')",
            "button:has-text('Kolay Başvur')",
        ]
        for sel in selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    return btn
            except Exception:
                continue
        return None

    # ── Modal Adımları ────────────────────────────────────────────────────────

    async def _get_modal_hash(self) -> str:
        """Modal içeriğinin hash'ini döner (takılma tespiti için)."""
        try:
            modal = await self.page.query_selector(
                ".jobs-easy-apply-modal, [data-test-modal], .artdeco-modal"
            )
            if modal:
                text = await modal.inner_text()
                return str(hash(text[:500]))
        except Exception:
            pass
        return ""

    async def _has_validation_errors(self) -> bool:
        """Formda doldurulmamış zorunlu alan hatası var mı?"""
        try:
            error_selectors = [
                ".artdeco-inline-feedback--error",
                "[data-test-form-builder-validation-error]",
                ".fb-form-element__error-text",
            ]
            for sel in error_selectors:
                els = await self.page.query_selector_all(sel)
                for el in els:
                    if await el.is_visible():
                        return True
            # Metin tabanlı hata kontrolü
            modal = await self.page.query_selector(
                ".jobs-easy-apply-modal, [data-test-modal], .artdeco-modal"
            )
            if modal:
                text = await modal.inner_text()
                if "Lütfen geçerli bir yanıt" in text or "Please enter a valid" in text:
                    return True
        except Exception:
            pass
        return False

    async def _handle_modal(self, cv_path: str | None, job_id: int | None = None) -> str:
        """
        Easy Apply modal adımlarını ilerle.
        Karmaşık metin sorusu çıkarsa 'skipped' döner.
        """
        max_steps = 25
        stuck_count = 0
        last_hash = ""

        for step in range(max_steps):
            await self.page.wait_for_timeout(2000)

            modal = await self.page.query_selector(
                ".jobs-easy-apply-modal, [data-test-modal]"
            )
            if not modal:
                logger.warning(
                    f"  Modal kapandı — beklenmedik durum. Sayfa URL: {self.page.url}"
                )
                try:
                    await self.page.screenshot(path="debug_modal.png", full_page=False)
                    logger.info("  Screenshot kaydedildi: debug_modal.png")
                except Exception:
                    pass
                return "error"

            # Tüm soruları cevapla (radio, dropdown, numeric, text)
            await self._answer_all_questions(job_id)

            # İletişim bilgilerini doldur (telefon vb.)
            await self._fill_contact_fields()

            # CV yükle (upload input varsa)
            if cv_path:
                await self._upload_cv(cv_path)

            # Cevaplanamayan essay sorusu varsa atla
            if await self._has_unanswerable_textarea():
                logger.info("  Cevaplanamayan essay sorusu, atlanıyor.")
                await self._close_modal()
                return "skipped"

            # Buton sırası: Submit > Review > Next
            submitted = await self._click_submit()
            if submitted:
                logger.success(f"  Başvuru gönderildi!")
                await self.page.wait_for_timeout(2000)
                # Onay ekranını kapat
                await self._close_modal()
                return "applied"

            reviewed = await self._click_review()
            if reviewed:
                await self.page.wait_for_timeout(1500)
                if await self._has_validation_errors():
                    logger.warning("  Cevaplanamayan zorunlu alan var (review), atlanıyor.")
                    await self._close_modal()
                    return "skipped"
                continue  # Review sonrası Submit bekliyoruz

            nexted = await self._click_next()
            if nexted:
                await self.page.wait_for_timeout(1500)
                # Validasyon hatası varsa → cevaplanamayan soru var, atla
                if await self._has_validation_errors():
                    logger.warning("  Cevaplanamayan zorunlu alan var, atlanıyor.")
                    await self._close_modal()
                    return "skipped"
                # Takılma tespiti: modal içeriği değişmedi mi?
                current_hash = await self._get_modal_hash()
                if current_hash and current_hash == last_hash:
                    stuck_count += 1
                    logger.warning(f"  Aynı adımda kaldı ({stuck_count}/3)")
                    if stuck_count >= 3:
                        logger.warning("  Form takıldı, atlanıyor.")
                        await self.page.screenshot(path="debug_modal.png", full_page=False)
                        await self._close_modal()
                        return "skipped"
                else:
                    stuck_count = 0
                    last_hash = current_hash
                continue

            # Son çare: sayfadaki herhangi bir görünür primary buton
            if await self._click_any_primary():
                continue

            # Hiçbir buton bulunamadı — screenshot al (modal açıkken) ve atla
            logger.warning("  İlerleme butonu bulunamadı, atlanıyor.")
            await self.page.screenshot(path="debug_modal.png", full_page=False)
            logger.info("  Screenshot kaydedildi: debug_modal.png")
            await self._close_modal()
            return "skipped"

        logger.warning("  Maksimum adım sayısına ulaşıldı, atlanıyor.")
        await self._close_modal()
        return "skipped"

    async def _has_unanswerable_textarea(self) -> bool:
        """Modal içinde cevaplanamayan (essay tipi) textarea varsa True döner."""
        modal = await self.page.query_selector(
            ".jobs-easy-apply-modal, [data-test-modal], .artdeco-modal"
        )
        if not modal:
            return False
        textareas = await modal.query_selector_all("textarea")
        for ta in textareas:
            if not await ta.is_visible():
                continue
            # Label'ını bul ve soru bankasına sor
            ta_id = await ta.get_attribute("id")
            label_el = None
            if ta_id:
                label_el = await modal.query_selector(f"label[for='{ta_id}']")
            question_text = (await label_el.inner_text()).strip() if label_el else ""
            placeholder = (await ta.get_attribute("placeholder") or "").lower()

            # Cover letter alanlarını atla
            skip_placeholders = ("", "cover letter", "ön yazı", "on yazi")
            skip_keywords = ("cover letter", "ön yazı")
            if placeholder in skip_placeholders:
                continue
            if any(k in question_text.lower() for k in skip_keywords):
                continue

            # Soru bankasında kullanıcı cevabı var mı?
            answer = resolve(question_text or placeholder, "textarea", [], job_id=None)
            if answer:
                current = (await ta.input_value()).strip()
                if not current:
                    await ta.fill(answer)
                continue

            # Cevap bulunamadı → essay sorusu, atla
            return True
        return False

    async def _answer_all_questions(self, job_id: int | None = None):
        """
        Modal içindeki form sorularını yakala ve yanıtla.
        Tüm sorgular modal scope'una kısıtlıdır — sayfa navigasyonu önlenir.
        """
        modal = await self.page.query_selector(
            ".jobs-easy-apply-modal, [data-test-modal], .artdeco-modal"
        )
        if not modal:
            return

        # ── Radio button grupları ────────────────────────────────────────────
        fieldsets = await modal.query_selector_all("fieldset")
        for fs in fieldsets:
            try:
                legend = await fs.query_selector(
                    "legend, span[data-test-form-builder-radio-button-form-component__title]"
                )
                if not legend:
                    continue
                question_text = (await legend.inner_text()).strip()
                if not question_text:
                    continue

                radios = await fs.query_selector_all("input[type='radio']")
                if not radios:
                    continue

                options: list[str] = []
                for rb in radios:
                    rb_id = await rb.get_attribute("id")
                    if rb_id:
                        lbl = await modal.query_selector(f"label[for='{rb_id}']")
                        if lbl:
                            options.append((await lbl.inner_text()).strip())

                answer = resolve(question_text, "radio", options, job_id=job_id)
                if not answer:
                    continue

                for rb in radios:
                    rb_id = await rb.get_attribute("id")
                    if not rb_id:
                        continue
                    lbl = await modal.query_selector(f"label[for='{rb_id}']")
                    if lbl and (await lbl.inner_text()).strip() == answer:
                        await lbl.click()
                        break
            except Exception:
                continue

        # ── Select (dropdown) soruları ───────────────────────────────────────
        selects = await modal.query_selector_all("select")
        for sel in selects:
            try:
                if not await sel.is_visible():
                    continue
                sel_id = await sel.get_attribute("id")
                label_el = None
                if sel_id:
                    label_el = await modal.query_selector(f"label[for='{sel_id}']")
                if not label_el:
                    continue
                question_text = (await label_el.inner_text()).strip()
                if not question_text:
                    continue

                opt_els = await sel.query_selector_all("option")
                options = []
                for o in opt_els:
                    val = await o.get_attribute("value")
                    txt = (await o.inner_text()).strip()
                    if val and txt:
                        options.append(txt)

                answer = resolve(question_text, "dropdown", options, job_id=job_id)
                if answer:
                    await sel.select_option(label=answer)
            except Exception:
                continue

        # ── Artdeco custom dropdown'lar (LinkedIn'e özgü) ────────────────────
        # Örnek: <div data-test-text-entity-list-form-select> veya
        #        <select class="artdeco-dropdown__trigger">
        artdeco_selects = await modal.query_selector_all(
            "select.artdeco-dropdown__trigger, "
            "[data-test-text-entity-list-form-select] select, "
            "select[data-live-search]"
        )
        for sel in artdeco_selects:
            try:
                if not await sel.is_visible():
                    continue
                current_val = await sel.evaluate("el => el.value")
                if current_val and current_val != "Select an option":
                    continue
                sel_id = await sel.get_attribute("id")
                label_el = None
                if sel_id:
                    label_el = await modal.query_selector(f"label[for='{sel_id}']")
                question_text = (await label_el.inner_text()).strip() if label_el else ""
                if not question_text:
                    question_text = await sel.get_attribute("aria-label") or ""
                if not question_text:
                    continue
                opt_els = await sel.query_selector_all("option")
                options = [
                    (await o.inner_text()).strip()
                    for o in opt_els
                    if (await o.get_attribute("value") or "").strip()
                ]
                answer = resolve(question_text, "dropdown", options, job_id=job_id)
                if answer:
                    await sel.select_option(label=answer)
            except Exception:
                continue

        # ── Sayısal ve kısa metin inputları ─────────────────────────────────
        inputs = await modal.query_selector_all("input[type='number'], input[type='text']")
        for inp in inputs:
            try:
                if not await inp.is_visible():
                    continue
                current = (await inp.input_value()).strip()
                if current:
                    continue
                inp_id = await inp.get_attribute("id")
                if not inp_id:
                    continue
                label_el = await modal.query_selector(f"label[for='{inp_id}']")
                if not label_el:
                    continue
                question_text = (await label_el.inner_text()).strip()
                if not question_text or len(question_text) < 3:
                    continue
                inp_type = (await inp.get_attribute("type")) or "text"
                answer = resolve(question_text, inp_type, [], job_id=job_id)
                if answer:
                    await inp.fill(answer)
            except Exception:
                continue

        # ── Typeahead / combobox inputları (şehir, konum vb.) ────────────────
        # LinkedIn bazı alanlarda native input yerine combobox kullanır.
        # Metin yazıldıktan sonra açılan listbox'tan ilk seçeneği seçmek gerekir.
        comboboxes = await modal.query_selector_all("input[role='combobox']")
        for inp in comboboxes:
            try:
                if not await inp.is_visible():
                    continue
                current = (await inp.input_value()).strip()
                if current:
                    # Zaten dolu — listbox açık kalmış olabilir, Escape ile kapat
                    await inp.press("Escape")
                    await self.page.wait_for_timeout(300)
                    continue
                inp_id = await inp.get_attribute("id")
                label_el = None
                if inp_id:
                    label_el = await modal.query_selector(f"label[for='{inp_id}']")
                question_text = (await label_el.inner_text()).strip() if label_el else ""
                if not question_text:
                    question_text = await inp.get_attribute("aria-label") or ""
                if not question_text:
                    continue
                answer = resolve(question_text, "text", [], job_id=job_id)
                if not answer:
                    continue
                await inp.fill(answer)
                await self.page.wait_for_timeout(1200)
                # Klavye ile ilk seçeneği seç (ArrowDown + Enter)
                await inp.press("ArrowDown")
                await self.page.wait_for_timeout(400)
                await inp.press("Enter")
                await self.page.wait_for_timeout(500)
            except Exception:
                continue

    async def _fill_contact_fields(self):
        """Telefon numarası ve e-posta gibi basit alanları modal içinde doldur."""
        modal = await self.page.query_selector(
            ".jobs-easy-apply-modal, [data-test-modal], .artdeco-modal"
        )
        if not modal:
            return
        phone_selectors = [
            "input[name*='phone']",
            "input[id*='phone']",
            "input[placeholder*='telefon' i]",
            "input[placeholder*='phone' i]",
        ]
        for sel in phone_selectors:
            try:
                field = await modal.query_selector(sel)
                if field and await field.is_visible():
                    current = (await field.input_value()).strip()
                    if not current:
                        await field.fill(self.PHONE)
            except Exception:
                continue

    async def _upload_cv(self, cv_path: str):
        """Dosya yükleme input'u varsa CV'yi yükle."""
        try:
            upload_input = await self.page.query_selector("input[type='file']")
            if upload_input:
                await upload_input.set_input_files(cv_path)
                await self.page.wait_for_timeout(1000)
                logger.info(f"  CV yüklendi: {Path(cv_path).name}")
        except Exception as e:
            logger.warning(f"  CV yükleme hatası: {e}")

    async def _skip_cover_letter(self):
        """Cover letter textarea'sı varsa boş bırak (zaten boş olacak)."""
        pass  # _has_complex_questions zaten bunu kontrol ediyor;
              # buraya ek mantık gerekirse eklenebilir

    async def _click_submit(self) -> bool:
        """Submit / Başvur butonuna tıkla."""
        selectors = [
            "button[aria-label='Submit application']",
            "button[aria-label='Başvuruyu gönder']",
            "button:has-text('Submit application')",
            "button:has-text('Başvuruyu gönder')",
            "button:has-text('Gönder')",
            "footer button.artdeco-button--primary:has-text('Submit')",
            "footer button.artdeco-button--primary:has-text('Gönder')",
        ]
        return await self._try_click_any(selectors)

    async def _click_review(self) -> bool:
        """Review application butonuna tıkla."""
        selectors = [
            "button[aria-label='Review your application']",
            "button[aria-label='Başvuruyu incele']",
            "button:has-text('Review')",
            "button:has-text('İncele')",
            "footer button.artdeco-button--primary:has-text('Review')",
        ]
        return await self._try_click_any(selectors)

    async def _click_next(self) -> bool:
        """Next / İleri butonuna tıkla."""
        selectors = [
            "button[aria-label='Continue to next step']",
            "button[aria-label='Sonraki adıma geç']",
            "button:has-text('Next')",
            "button:has-text('İleri')",
            "button:has-text('Devam et')",
            "footer button.artdeco-button--primary",   # modal footer'daki primary buton
        ]
        return await self._try_click_any(selectors)

    async def _click_any_primary(self) -> bool:
        """Sayfadaki visible+enabled primary butonların sonuncusuna tıkla."""
        try:
            buttons = await self.page.query_selector_all(
                "button.artdeco-button--primary, button[data-easy-apply-next-button]"
            )
            for btn in reversed(buttons):
                if await btn.is_visible() and await btn.is_enabled():
                    text = (await btn.inner_text()).strip()
                    logger.info(f"  Fallback buton: '{text}'")
                    await btn.click()
                    return True
        except Exception:
            pass
        return False

    async def _try_click_any(self, selectors: list[str]) -> bool:
        for sel in selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    await btn.click()
                    return True
            except Exception:
                continue
        return False

    async def _close_modal(self):
        """Modalı kapat (Vazgeç / Discard)."""
        close_selectors = [
            "button[aria-label='Dismiss']",
            "button[aria-label='Kapat']",
            "button[data-test-modal-close-btn]",
            ".artdeco-modal__dismiss",
        ]
        for sel in close_selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await self.page.wait_for_timeout(1000)
                    # "Discard" onay ekranı çıkabilir
                    discard = await self.page.query_selector(
                        "button:has-text('Discard'), button:has-text('Vazgeç')"
                    )
                    if discard:
                        await discard.click()
                    return
            except Exception:
                continue

    # ── Ana Akış ──────────────────────────────────────────────────────────────

    async def run(self):
        if not APPLY_AUTOMATICALLY and not self.dry_run:
            console.print(
                "[bold red]APPLY_AUTOMATICALLY = False![/bold red]\n"
                "config/settings.py dosyasında APPLY_AUTOMATICALLY = True yaparak "
                "otomatik başvuruyu etkinleştir.\n"
                "Ya da sadece test etmek için --dry-run parametresiyle çalıştır:\n"
                "  [cyan]py applicator/linkedin_applicator.py --dry-run[/cyan]"
            )
            return

        jobs = get_cv_ready_jobs()
        if self.limit:
            jobs = jobs[:self.limit]
        if not jobs:
            console.print(
                f"[yellow]Başvuru yapılacak ilan yok "
                f"(cv_ready + match_score >= {MIN_MATCH_SCORE}).[/yellow]"
            )
            return

        console.print(
            f"\n[bold cyan]{len(jobs)} ilan için başvuru başlatılıyor...[/bold cyan]"
            + (" [DRY-RUN]" if self.dry_run else "")
        )

        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=OPERA_PROFILE,
                executable_path=OPERA_EXE,
                headless=self.headless,
                slow_mo=80,
                args=AUTOMATION_WINDOW_ARGS,
                viewport={"width": 1280, "height": 800},
            )
            for old_page in context.pages:
                await old_page.close()
            self.page = await context.new_page()

            # Profil giriş yapılıysa login atla
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await self.page.wait_for_timeout(2000)
            if "feed" not in self.page.url:
                await self.login()

            for job in jobs:
                cv_path = find_cv_path(job)
                if not cv_path:
                    logger.warning(
                        f"  CV bulunamadı: {job['title']} @ {job['company']} — atlanıyor."
                    )
                    self.results.append((job, "no_cv"))
                    continue

                console.print(
                    f"\n[bold]-> {job['title']}[/bold] @ {job['company']} "
                    f"(Skor: {job['match_score']:.0f})"
                )
                console.print(f"  CV: {Path(cv_path).name}")

                outcome = await self.apply_to_job(job, cv_path)
                self.results.append((job, outcome))

                if outcome == "applied" and not self.dry_run:
                    mark_applied(job["id"])
                    if self.max_real_applications is not None:
                        self.max_real_applications -= 1
                        if self.max_real_applications <= 0:
                            logger.info("Gerçek başvuru sınırına ulaşıldı, durduruluyor.")
                            break

                if outcome == "daily_limit":
                    logger.warning("Günlük limit doldu, yarın devam edilecek.")
                    break

                await asyncio.sleep(3)  # ilanlar arası bekle

            await context.close()

        self._show_summary()

    def _show_summary(self):
        table = Table(title="Başvuru Özeti", show_lines=True)
        table.add_column("Sonuç",   width=16)
        table.add_column("Pozisyon", width=35)
        table.add_column("Şirket",   width=25)
        table.add_column("Skor",     width=6)

        status_color = {
            "applied":       "green",
            "skipped":       "yellow",
            "no_easy_apply": "dim",
            "external_ats":  "dim",
            "no_cv":         "red",
            "error":         "red",
        }

        for job, outcome in self.results:
            color = status_color.get(outcome, "white")
            table.add_row(
                f"[{color}]{outcome}[/{color}]",
                job["title"],
                job["company"],
                f"{job['match_score']:.0f}",
            )

        console.print()
        console.print(table)

        applied_count = sum(1 for _, o in self.results if o == "applied")
        console.print(
            f"\n[bold green]Toplam {applied_count}/{len(self.results)} başvuru tamamlandı.[/bold green]"
        )


# ─── Çalıştır ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    dry_run  = "--dry-run"  in sys.argv
    headless = "--headless" in sys.argv
    limit    = None
    max_apply = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            try:
                limit = int(arg.split("=")[1])
            except ValueError:
                pass
        if arg.startswith("--max-apply="):
            try:
                max_apply = int(arg.split("=")[1])
            except ValueError:
                pass
    applicator = LinkedInApplicator(headless=headless, dry_run=dry_run, limit=limit,
                                     max_real_applications=max_apply)
    asyncio.run(applicator.run())
