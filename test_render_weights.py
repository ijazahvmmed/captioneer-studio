from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def test_font_weights():
    width, height = 800, 400
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    font_dir = Path("static")
    fonts_to_test = [
        ("Inter-Light.ttf", "Inter Light (300)"),
        ("Inter-Bold.ttf", "Inter Bold (700)"),
        ("SpaceGrotesk-Light.ttf", "Space Light (300)"),
        ("SpaceGrotesk-Bold.ttf", "Space Bold (700)")
    ]
    
    y = 50
    for filename, label in fonts_to_test:
        font_path = font_dir / filename
        if not font_path.exists():
            print(f"Missing: {filename}")
            continue
            
        try:
            font = ImageFont.truetype(str(font_path), 60)
            draw.text((50, y), f"{label}: Testing 123", font=font, fill=(0, 0, 0))
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            
        y += 80
        
    image.save("font_test_render.png")
    print("Test render saved to font_test_render.png")

if __name__ == "__main__":
    test_font_weights()
