"""
Download ALL font weights for Captioneer export rendering.
Uses multiple sources to ensure all weights are available for pixel-perfect export.
"""

import os
import urllib.request
from pathlib import Path
import zipfile
import io

# Direct download URLs for static font files
# Using multiple reliable sources

FONT_SOURCES = {
    # ===== INTER (100-900) - FIXING CORRUPT FILES =====
    "Inter-Light.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-300-normal.ttf",
    "Inter-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.ttf",
    "Inter-Medium.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-500-normal.ttf",
    "Inter-SemiBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-600-normal.ttf",
    "Inter-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-700-normal.ttf",
    "Inter-ExtraBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-800-normal.ttf",
    "Inter-Black.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-900-normal.ttf",

    # ===== SPACE GROTESK (300-700) =====
    # From fontsource CDN - individual static files
    "SpaceGrotesk-Light.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk@latest/latin-300-normal.ttf",
    "SpaceGrotesk-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk@latest/latin-400-normal.ttf",
    "SpaceGrotesk-Medium.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk@latest/latin-500-normal.ttf",
    "SpaceGrotesk-SemiBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk@latest/latin-600-normal.ttf",
    "SpaceGrotesk-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk@latest/latin-700-normal.ttf",
    
    # ===== OSWALD (300-700) =====
    "Oswald-Light.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/oswald@latest/latin-300-normal.ttf",
    "Oswald-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/oswald@latest/latin-400-normal.ttf",
    "Oswald-Medium.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/oswald@latest/latin-500-normal.ttf",
    "Oswald-SemiBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/oswald@latest/latin-600-normal.ttf",
    "Oswald-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/oswald@latest/latin-700-normal.ttf",
    
    # ===== ROBOTO (300-900) =====
    "Roboto-Light.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/roboto@latest/latin-300-normal.ttf",
    "Roboto-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/roboto@latest/latin-400-normal.ttf",
    "Roboto-Medium.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/roboto@latest/latin-500-normal.ttf",
    "Roboto-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/roboto@latest/latin-700-normal.ttf",
    "Roboto-Black.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/roboto@latest/latin-900-normal.ttf",
    
    # ===== RUBIK (300-900) =====
    "Rubik-Light.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/rubik@latest/latin-300-normal.ttf",
    "Rubik-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/rubik@latest/latin-400-normal.ttf",
    "Rubik-Medium.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/rubik@latest/latin-500-normal.ttf",
    "Rubik-SemiBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/rubik@latest/latin-600-normal.ttf",
    "Rubik-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/rubik@latest/latin-700-normal.ttf",
    "Rubik-ExtraBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/rubik@latest/latin-800-normal.ttf",
    "Rubik-Black.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/rubik@latest/latin-900-normal.ttf",
    
    # ===== MONTSERRAT (missing weights) =====
    "Montserrat-SemiBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-600-normal.ttf",
    "Montserrat-ExtraBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-800-normal.ttf",
    "Montserrat-Black.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-900-normal.ttf",
}

def download_fonts():
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    
    print(f"Downloading missing font weights to {static_dir}\n")
    
    success = 0
    failed = 0
    skipped = 0
    
    for filename, url in FONT_SOURCES.items():
        dest = static_dir / filename
        if dest.exists() and dest.stat().st_size > 5000:
            print(f"✓ {filename} (already exists)")
            skipped += 1
            continue
            
        try:
            print(f"↓ Downloading {filename}...", end=" ", flush=True)
            
            # Add headers to avoid 403 errors
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            with urllib.request.urlopen(req) as response:
                data = response.read()
                
            # Check file size (should be at least 10KB for a TTF)
            if len(data) < 10000:
                print(f"FAILED (too small: {len(data)} bytes)")
                failed += 1
            else:
                with open(dest, 'wb') as f:
                    f.write(data)
                print(f"done ({len(data)//1024}KB)")
                success += 1
                
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Downloaded: {success} fonts")
    print(f"Skipped (already exist): {skipped} fonts")
    if failed:
        print(f"Failed: {failed} fonts")
    print(f"Fonts saved to: {static_dir}")

if __name__ == "__main__":
    download_fonts()
