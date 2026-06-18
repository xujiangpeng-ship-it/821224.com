"""Rebuild home page and category pages using main.py functions."""
import shutil
import sys
import os
from pathlib import Path

# Add generate directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import load_config, rebuild_home, rebuild_category_pages, rebuild_sitemap

ROOT = Path(__file__).resolve().parent.parent
config = load_config()
print(f"Site: {config['site']['name']}")

print("Rebuilding home page...")
rebuild_home(config)

print("Rebuilding category pages...")
rebuild_category_pages(config)

print("Rebuilding sitemap...")
rebuild_sitemap(config)

print("Copying static assets to public/...")
static_dir = ROOT / "static"
public_dir = ROOT / "public"
if static_dir.exists():
    for item in static_dir.iterdir():
        dest = public_dir / item.name
        if item.is_file():
            shutil.copy2(item, dest)
            print(f"  {item.name} -> public/{item.name}")
        elif item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
            print(f"  {item.name}/ -> public/{item.name}/")

print("Done: home, category pages, sitemap rebuilt, static assets copied.")
