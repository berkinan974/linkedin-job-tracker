"""
Windows Toast Bildirimleri
───────────────────────────
Analiz sonrası yüksek skorlu ilanlar için Windows bildirim gönderir.
plyer kütüphanesi kullanır (pip install plyer).
"""

import sqlite3
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import DB_PATH, MIN_MATCH_SCORE


def get_high_score_jobs(min_score: float = 60.0) -> list[dict]:
    """Yeni analiz edilmiş ve skoru yüksek ilanları getir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT title, company, location, match_score
        FROM jobs
        WHERE status = 'analyzed'
          AND match_score >= ?
        ORDER BY match_score DESC
    """, (min_score,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def send_notification(title: str, message: str, timeout: int = 10):
    """Windows toast bildirimi gönder."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="LinkedIn Job Tracker",
            timeout=timeout,
        )
    except ImportError:
        print(f"[BILDIRIM] {title}: {message}")
        print("  (plyer kurulu degil: pip install plyer)")
    except Exception as e:
        print(f"[BILDIRIM HATASI] {e}")


def notify_high_score_jobs(min_score: float = 60.0):
    """Yüksek skorlu ilanlar için bildirim gönder."""
    jobs = get_high_score_jobs(min_score)
    if not jobs:
        return

    count = len(jobs)
    top = jobs[0]

    if count == 1:
        title = "LinkedIn: Yeni Uyumlu İlan!"
        msg = (
            f"{top['title']} — {top['company']}\n"
            f"Skor: {top['match_score']:.0f}/100 | {top['location']}"
        )
    else:
        title = f"LinkedIn: {count} Yüksek Skorlu İlan!"
        lines = [f"{j['title']} ({j['match_score']:.0f}) — {j['company']}" for j in jobs[:3]]
        msg = "\n".join(lines)
        if count > 3:
            msg += f"\n... ve {count - 3} ilan daha"

    send_notification(title, msg)
    print(f"[Bildirim] {count} yüksek skorlu ilan bildirimi gönderildi.")
