"""Copy backend/app -> api/app for the Vercel serverless bundle.

Single source of truth is backend/app; run this after backend changes:
    python scripts/sync_api.py
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
src = root / "backend" / "app"
dst = root / "api" / "app"

if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
print(f"synced {src} -> {dst}")
