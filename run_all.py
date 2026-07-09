"""
LinkedIn Pipeline — Tüm adımları sırayla çalıştırır.
Kullanım: py run_all.py
"""
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
PY   = str(BASE / "venv/Scripts/python.exe")

ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

steps = [
    ("Opera kapat",    ["taskkill", "/f", "/im", "opera.exe"],          True),
    ("Scraper",        [PY, "scraper/linkedin_scraper.py"],              False),
    ("Analyzer",       [PY, "analyzer/job_analyzer.py"],                 False),
    ("CV Manager",     [PY, "cv_manager/cv_manager.py"],                 False),
    ("Applicator",     [PY, "applicator/linkedin_applicator.py"],        False),
]

for name, cmd, ignore_error in steps:
    print(f"\n{'='*50}")
    print(f">>> {name}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, cwd=BASE, env=ENV)
    if result.returncode != 0 and not ignore_error:
        print(f"\n[HATA] {name} başarısız (exit code {result.returncode}). Durduruluyor.")
        sys.exit(1)

print("\nPipeline tamamlandi.")
