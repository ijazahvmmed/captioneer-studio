"""
Download Google Fonts for Captioneer export rendering.
Uses the official Google Fonts GitHub repository.
"""

import os
import urllib.request
from pathlib import Path

# Base URL for Google Fonts GitHub repo (stable URLs)
BASE = "https://raw.githubusercontent.com/google/fonts/main"

FONT_URLS = {
    # Inter - all weights (static files) - VERIFIED WORKING
    "Inter-Light.ttf": f"{BASE}/ofl/inter/static/Inter_18pt-Light.ttf",
    "Inter-Regular.ttf": f"{BASE}/ofl/inter/static/Inter_18pt-Regular.ttf",
    "Inter-Medium.ttf": f"{BASE}/ofl/inter/static/Inter_18pt-Medium.ttf",
    "Inter-SemiBold.ttf": f"{BASE}/ofl/inter/static/Inter_18pt-SemiBold.ttf",
    "Inter-Bold.ttf": f"{BASE}/ofl/inter/static/Inter_18pt-Bold.ttf",
    "Inter-ExtraBold.ttf": f"{BASE}/ofl/inter/static/Inter_18pt-ExtraBold.ttf",
    "Inter-Black.ttf": f"{BASE}/ofl/inter/static/Inter_18pt-Black.ttf",
    
    # Roboto - Limited weights available as static
    "Roboto-Regular.ttf": f"{BASE}/apache/roboto/Roboto%5Bwdth%2Cwght%5D.ttf",
    "Roboto-Bold.ttf": f"{BASE}/apache/roboto/Roboto%5Bwdth%2Cwght%5D.ttf",
    
    # Montserrat - static files available
    "Montserrat-Light.ttf": f"{BASE}/ofl/montserrat/static/Montserrat-Light.ttf",
    "Montserrat-Regular.ttf": f"{BASE}/ofl/montserrat/static/Montserrat-Regular.ttf",
    "Montserrat-Medium.ttf": f"{BASE}/ofl/montserrat/static/Montserrat-Medium.ttf",
    "Montserrat-Bold.ttf": f"{BASE}/ofl/montserrat/static/Montserrat-Bold.ttf",
    
    # Poppins - all weights (static files in root folder)
    "Poppins-Light.ttf": f"{BASE}/ofl/poppins/Poppins-Light.ttf",
    "Poppins-Regular.ttf": f"{BASE}/ofl/poppins/Poppins-Regular.ttf",
    "Poppins-Medium.ttf": f"{BASE}/ofl/poppins/Poppins-Medium.ttf",
    "Poppins-SemiBold.ttf": f"{BASE}/ofl/poppins/Poppins-SemiBold.ttf",
    "Poppins-Bold.ttf": f"{BASE}/ofl/poppins/Poppins-Bold.ttf",
    "Poppins-ExtraBold.ttf": f"{BASE}/ofl/poppins/Poppins-ExtraBold.ttf",
    "Poppins-Black.ttf": f"{BASE}/ofl/poppins/Poppins-Black.ttf",
    
    # Oswald - variable font only
    "Oswald-Regular.ttf": f"{BASE}/ofl/oswald/Oswald%5Bwght%5D.ttf",
    "Oswald-Bold.ttf": f"{BASE}/ofl/oswald/Oswald%5Bwght%5D.ttf",
    
    # Bebas Neue (only Regular available)
    "BebasNeue-Regular.ttf": f"{BASE}/ofl/bebasneue/BebasNeue-Regular.ttf",
    
    # Anton (only Regular available)
    "Anton-Regular.ttf": f"{BASE}/ofl/anton/Anton-Regular.ttf",
    
    # Bangers (only Regular available)
    "Bangers-Regular.ttf": f"{BASE}/ofl/bangers/Bangers-Regular.ttf",
    
    # Permanent Marker (only Regular available)
    "PermanentMarker-Regular.ttf": f"{BASE}/apache/permanentmarker/PermanentMarker-Regular.ttf",
    
    # Rubik - variable font only
    "Rubik-Regular.ttf": f"{BASE}/ofl/rubik/Rubik%5Bwght%5D.ttf",
    "Rubik-Bold.ttf": f"{BASE}/ofl/rubik/Rubik%5Bwght%5D.ttf",
    
    # Space Grotesk - variable font only
    "SpaceGrotesk-Regular.ttf": f"{BASE}/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    "SpaceGrotesk-Bold.ttf": f"{BASE}/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    
    # Epilogue - static files available
    "Epilogue-Light.ttf": f"{BASE}/ofl/epilogue/static/Epilogue-Light.ttf",
    "Epilogue-Regular.ttf": f"{BASE}/ofl/epilogue/static/Epilogue-Regular.ttf",
    "Epilogue-Medium.ttf": f"{BASE}/ofl/epilogue/static/Epilogue-Medium.ttf",
    "Epilogue-SemiBold.ttf": f"{BASE}/ofl/epilogue/static/Epilogue-SemiBold.ttf",
    "Epilogue-Bold.ttf": f"{BASE}/ofl/epilogue/static/Epilogue-Bold.ttf",
    "Epilogue-ExtraBold.ttf": f"{BASE}/ofl/epilogue/static/Epilogue-ExtraBold.ttf",
    "Epilogue-Black.ttf": f"{BASE}/ofl/epilogue/static/Epilogue-Black.ttf",
}

def download_fonts():
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    
    print(f"Downloading fonts to {static_dir}\n")
    
    success = 0
    failed = 0
    
    for filename, url in FONT_URLS.items():
        dest = static_dir / filename
        if dest.exists():
            print(f"✓ {filename} (already exists)")
            success += 1
            continue
            
        try:
            print(f"↓ Downloading {filename}...", end=" ", flush=True)
            urllib.request.urlretrieve(url, dest)
            # Check file size
            if dest.stat().st_size < 1000:
                print(f"FAILED (too small)")
                dest.unlink()
                failed += 1
            else:
                print("done")
                success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Downloaded: {success} fonts")
    if failed:
        print(f"Failed: {failed} fonts")
    print(f"Fonts saved to: {static_dir}")

if __name__ == "__main__":
    download_fonts()
