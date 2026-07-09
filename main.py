"""
LinkedIn Job Tracker — Ana Giriş Noktası
─────────────────────────────────────────
Kullanım:
    python main.py scrape     → iş ilanlarını topla
    python main.py analyze    → ilanları AI ile analiz et
    python main.py dashboard  → Streamlit dashboard aç
    python main.py apply      → otomatik başvur (dikkatli!)
"""

import sys
from rich.console import Console
from rich.panel import Panel

console = Console()

MENU = """
[bold cyan]LinkedIn Job Tracker[/bold cyan]

  [1] İş ilanlarını topla   (scrape)
  [2] İlanları analiz et    (analyze)
  [3] Dashboard aç          (dashboard)
  [4] Otomatik başvur       (apply)
  [q] Çıkış
"""

def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
    else:
        console.print(Panel(MENU, expand=False))
        cmd = console.input("[bold]Seçim: [/bold]").strip()

    if cmd in ("1", "scrape"):
        from scraper.linkedin_scraper import LinkedInScraper
        import asyncio
        asyncio.run(LinkedInScraper(headless=False).run())

    elif cmd in ("2", "analyze"):
        console.print("[yellow]Analiz modülü yakında...[/yellow]")

    elif cmd in ("3", "dashboard"):
        import subprocess
        subprocess.run(["streamlit", "run", "dashboard/app.py"])

    elif cmd in ("4", "apply"):
        console.print("[yellow]Otomatik başvuru modülü yakında...[/yellow]")

    elif cmd in ("q", "quit", "exit"):
        console.print("Görüşürüz!")
    else:
        console.print("[red]Geçersiz seçim.[/red]")

if __name__ == "__main__":
    main()
