"""
Layout Engine - Text positioning and measurement

Computes character positions based on style settings and canvas configuration.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from PIL import ImageFont


@dataclass
class StyleSettings:
    """Typography style configuration."""
    font_family: str = "Epilogue-Light"
    font_size: int = 72
    font_weight: int = 700
    text_transform: str = "none"
    line_spacing: float = 1.1
    letter_spacing: int = 0
    alignment: str = "center"  # left, center, right
    stroke_width: int = 5
    text_color: str = "#FFFFFF"
    stroke_color: str = "#000000"


@dataclass
class CanvasSettings:
    """Canvas positioning configuration."""
    width: int = 1080
    height: int = 1920
    position_x: int = 540
    position_y: int = 1400
    anchor: str = "center"  # center, top, bottom, custom
    safe_margin_top: int = 100
    safe_margin_bottom: int = 200
    safe_margin_left: int = 50
    safe_margin_right: int = 50


class LayoutEngine:
    """
    Computes text layout and character positions.
    """
    
    def __init__(
        self,
        style: StyleSettings,
        canvas: CanvasSettings,
        font_dir: Optional[Path] = None
    ):
        self.style = style
        self.canvas = canvas
        self.font_dir = font_dir or Path(__file__).parent.parent / "static"
        
        # Load font
        self.font = self._load_font()
        self._char_size_cache: Dict[str, Tuple[int, int]] = {}
    
    def _load_font(self) -> ImageFont.FreeTypeFont:
        """Load the configured font with exact weight matching from static folder."""
        font_family = self.style.font_family
        font_weight = self.style.font_weight
        font_size = self.style.font_size
        
        # Weight to suffix mapping
        weight_map = {
            300: "Light",
            400: "Regular",
            500: "Medium",
            600: "SemiBold",
            700: "Bold",
            800: "ExtraBold",
            900: "Black"
        }
        weight_suffix = weight_map.get(font_weight, "Bold")
        
        # Font-specific available weights (what's actually in static folder)
        # This ensures we only try weights that exist for each font
        # SYNCED WITH FRONTEND FONT_AVAILABLE_WEIGHTS
        font_available_weights = {
            "Inter": ["Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"],
            "Roboto": ["Light", "Regular", "Medium", "Bold", "Black"],
            "Montserrat": ["Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"],
            "Poppins": ["Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"],
            "Oswald": ["Light", "Regular", "Medium", "SemiBold", "Bold"],
            "Bebas Neue": ["Regular"],  # Only Regular available
            "Anton": ["Regular"],  # Only Regular available
            "Bangers": ["Regular"],  # Only Regular available
            "Permanent Marker": ["Regular"],  # Only Regular available
            "Rubik": ["Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"],
            "Space Grotesk": ["Light", "Regular", "Medium", "SemiBold", "Bold"],  # 300-700
            "Epilogue": ["Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"],
        }
        
        # Weight fallback priority (try these in order if exact weight not available)
        weight_fallback_order = {
            300: ["Light", "Regular", "Medium"],
            400: ["Regular", "Medium", "Light"],
            500: ["Medium", "Regular", "SemiBold"],
            600: ["SemiBold", "Bold", "Medium"],
            700: ["Bold", "SemiBold", "ExtraBold"],
            800: ["ExtraBold", "Bold", "Black"],
            900: ["Black", "ExtraBold", "Bold"]
        }
        
        # Fonts that use different naming (spaces removed, etc.)
        font_name_map = {
            "Bebas Neue": "BebasNeue",
            "Permanent Marker": "PermanentMarker",
            "Space Grotesk": "SpaceGrotesk",
        }
        
        # Get the actual filename prefix
        file_prefix = font_name_map.get(font_family, font_family)
        
        # Get available weights for this font
        available = font_available_weights.get(font_family, ["Regular", "Bold"])
        
        # Build priority list of weight suffixes to try
        weight_candidates = []
        
        # First try exact weight
        if weight_suffix in available:
            weight_candidates.append(weight_suffix)
        
        # Then try fallbacks in order
        for fallback in weight_fallback_order.get(font_weight, ["Regular", "Bold"]):
            if fallback in available and fallback not in weight_candidates:
                weight_candidates.append(fallback)
        
        # Always include Regular as ultimate fallback
        if "Regular" not in weight_candidates:
            weight_candidates.append("Regular")
        
        # Build priority list of font paths
        candidates = []
        for weight in weight_candidates:
            candidates.append(self.font_dir / f"{file_prefix}-{weight}.ttf")
        
        # Also try just the font name (for single-file fonts)
        candidates.append(self.font_dir / f"{file_prefix}.ttf")
        
        # Windows font fallbacks
        win_fonts = Path("C:/Windows/Fonts")
        if font_weight >= 700:
            candidates.append(win_fonts / "arialbd.ttf")
        else:
            candidates.append(win_fonts / "arial.ttf")
        
        # Log what we're trying (for debugging)
        print(f"[FONT] Looking for: {font_family} weight {font_weight} -> suffix '{weight_suffix}'")
        print(f"[FONT] Candidates: {[c.name for c in candidates[:5]]}")
        
        # Find first existing font
        for path in candidates:
            if path.exists():
                try:
                    font = ImageFont.truetype(str(path), font_size)
                    print(f"[FONT] ✓ Loaded: {path.name}")
                    return font
                except Exception as e:
                    # print(f"  -> Failed to load {path.name}: {e}")
                    continue
        
        # Ultimate fallback
        print(f"WARNING: No font found for {font_family}, using Arial")
        return ImageFont.truetype(str(win_fonts / "arial.ttf"), font_size)
    
    def measure_char(self, char: str) -> Tuple[int, int]:
        """Get the width and height of a character."""
        if char not in self._char_size_cache:
            from PIL import Image, ImageDraw
            temp = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
            draw = ImageDraw.Draw(temp)
            bbox = draw.textbbox((0, 0), char, font=self.font)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            self._char_size_cache[char] = (max(1, width), max(1, height))
        return self._char_size_cache[char]
    
    def measure_text(self, text: str) -> Tuple[int, int]:
        """Get the width and height of a text string."""
        from PIL import Image, ImageDraw
        temp = Image.new('RGBA', (2000, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(temp)
        bbox = draw.textbbox((0, 0), text, font=self.font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    def compute_positions(
        self,
        words: List[str]
    ) -> Dict[Tuple[int, int], Tuple[float, float]]:
        """
        Compute (x, y) positions for each character.
        
        Matches the frontend behavior exactly:
        - Creates a virtual container (90% of canvas width) centered at position_x
        - Applies textAlign within that container
        
        Returns: Dict[(word_idx, char_idx)] → (x, y)
        """
        if not words:
            return {}
        
        # Build full text to measure
        full_text = " ".join(words)
        total_width, text_height = self.measure_text(full_text)
        
        # --- MATCH FRONTEND EXACTLY ---
        # Frontend creates a container that is:
        # - 90% of the video width
        # - Centered at position_x (using transform: translate(-50%, -50%))
        # - textAlign applied within that container
        
        container_width = self.canvas.width * 0.90  # 90% like frontend
        
        # Container left edge (centered at position_x)
        container_left = self.canvas.position_x - (container_width / 2)
        
        # Compute starting X based on alignment WITHIN the container
        if self.style.alignment == "center":
            # Center the text within the container
            start_x = container_left + (container_width - total_width) / 2
        elif self.style.alignment == "right":
            # Right-align within container
            start_x = container_left + container_width - total_width
        else:  # left
            # Left-align within container
            start_x = container_left
        
        # Y position (centered at position_y, like transform: translate(-50%, -50%))
        center_y = self.canvas.position_y - (text_height / 2)
        
        positions: Dict[Tuple[int, int], Tuple[float, float]] = {}
        current_x = start_x
        
        for word_idx, word in enumerate(words):
            if word_idx > 0:
                space_w, _ = self.measure_char(" ")
                current_x += space_w + self.style.letter_spacing
            
            for char_idx, char in enumerate(word):
                positions[(word_idx, char_idx)] = (current_x, center_y)
                char_w, _ = self.measure_char(char)
                current_x += char_w + self.style.letter_spacing
        
        return positions
    
    def get_font(self) -> ImageFont.FreeTypeFont:
        """Return the loaded font."""
        return self.font
    
    def update_style(self, style: StyleSettings):
        """Update style and reload font if needed."""
        if style.font_family != self.style.font_family or style.font_size != self.style.font_size:
            self.style = style
            self.font = self._load_font()
            self._char_size_cache.clear()
        else:
            self.style = style
    
    def update_canvas(self, canvas: CanvasSettings):
        """Update canvas configuration."""
        self.canvas = canvas
