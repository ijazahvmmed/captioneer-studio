"""
Frame Renderer - Headless frame generation

Takes a project state and timestamp, returns a rendered PIL.Image.
This is the core deterministic renderer used by both preview and export.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import hashlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .motion import (
    MotionSettings, Word, DisplayGroup, Character, CharProperties,
    compute_display_groups, decompose_group_to_characters, compute_char_state
)
from .layout import LayoutEngine, StyleSettings, CanvasSettings


@dataclass
class ProjectState:
    """Complete project state for rendering."""
    video_width: int
    video_height: int
    video_fps: int
    canvas: CanvasSettings
    style: StyleSettings
    motion: MotionSettings
    words: List[Word]


class CharacterRenderCache:
    """Cache for rendered character images."""
    
    def __init__(self, max_size: int = 500):
        self._cache: Dict[str, Image.Image] = {}
        self._max_size = max_size
    
    def get_key(self, char: str, blur: float, scale: float, font_size: int) -> str:
        blur_rounded = round(blur * 2) / 2
        scale_rounded = round(scale * 100) / 100
        key_data = f"{char}|{blur_rounded:.1f}|{scale_rounded:.2f}|{font_size}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Image.Image]:
        return self._cache.get(key)
    
    def set(self, key: str, image: Image.Image):
        if len(self._cache) >= self._max_size:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = image.copy()
    
    def clear(self):
        self._cache.clear()


class FrameRenderer:
    """
    Headless frame renderer.
    
    Consumes a ProjectState and renders frames at any timestamp.
    Completely deterministic - same inputs always produce same output.
    """
    
    def __init__(self, state: ProjectState):
        self.state = state
        
        # Initialize layout engine
        self.layout = LayoutEngine(
            style=state.style,
            canvas=state.canvas
        )
        
        # Precompute display groups
        self.groups = compute_display_groups(state.words, state.motion)
        
        # Precompute characters for each group
        self.group_data: List[Dict] = []
        for group in self.groups:
            word_texts = [w.text for w in state.words if w.id in group.word_ids]
            positions = self.layout.compute_positions(word_texts)
            characters = decompose_group_to_characters(state.words, group, state.motion)
            
            # Map positions to characters
            char_positions = {}
            word_idx_map = {w.id: i for i, w in enumerate(
                [w for w in state.words if w.id in group.word_ids]
            )}
            for char in characters:
                word_idx = word_idx_map.get(char.word_id, 0)
                key = (word_idx, char.char_index)
                if key in positions:
                    char_positions[char] = positions[key]
            
            self.group_data.append({
                'group': group,
                'characters': characters,
                'positions': char_positions
            })
        
        # Character render cache
        self.cache = CharacterRenderCache()
    
    def update_state(self, state: ProjectState):
        """Update state and recompute groups."""
        self.state = state
        self.layout.update_style(state.style)
        self.layout.update_canvas(state.canvas)
        self.groups = compute_display_groups(state.words, state.motion)
        self._recompute_group_data()
        self.cache.clear()
    
    def _recompute_group_data(self):
        """Recompute group data after state change."""
        self.group_data = []
        for group in self.groups:
            word_texts = [w.text for w in self.state.words if w.id in group.word_ids]
            positions = self.layout.compute_positions(word_texts)
            characters = decompose_group_to_characters(
                self.state.words, group, self.state.motion
            )
            
            word_idx_map = {w.id: i for i, w in enumerate(
                [w for w in self.state.words if w.id in group.word_ids]
            )}
            char_positions = {}
            for char in characters:
                word_idx = word_idx_map.get(char.word_id, 0)
                key = (word_idx, char.char_index)
                if key in positions:
                    char_positions[char] = positions[key]
            
            self.group_data.append({
                'group': group,
                'characters': characters,
                'positions': char_positions
            })
    
    def render_frame(self, time: float) -> Image.Image:
        """
        Render a single frame at the given timestamp.
        
        Args:
            time: Timestamp in seconds
            
        Returns:
            PIL.Image in RGBA mode
        """
        # Create transparent canvas
        frame = Image.new('RGBA', 
            (self.state.video_width, self.state.video_height), 
            (0, 0, 0, 0)
        )
        
        # Find active group
        active_gd = None
        for gd in self.group_data:
            group = gd['group']
            if group.start_time <= time < group.end_time:
                active_gd = gd
                break
        
        if active_gd is None:
            return frame
        
        # Render each character
        for char in active_gd['characters']:
            if char not in active_gd['positions']:
                continue
            
            base_x, base_y = active_gd['positions'][char]
            
            props = compute_char_state(
                time,
                char.entry_start,
                char.focus_time,
                self.state.motion
            )
            
            if not props.visible or props.opacity < 0.01:
                continue
            
            char_img, padding = self._render_character(char.char, props)
            # CRITICAL: Frontend uses y_offset * 0.5 in CSS transform
            render_y = base_y + (props.y_offset * 0.5)
            
            paste_x = int(base_x - padding)
            paste_y = int(render_y - padding)
            
            if paste_x >= self.state.video_width or paste_y >= self.state.video_height:
                continue
            if paste_x + char_img.width <= 0 or paste_y + char_img.height <= 0:
                continue
            
            frame.paste(char_img, (paste_x, paste_y), char_img)
        
        return frame
    
    def render_frame_array(self, time: float) -> np.ndarray:
        """Render frame and return as numpy array."""
        return np.array(self.render_frame(time))
    
    def _render_character(
        self,
        char: str,
        props: CharProperties
    ) -> Tuple[Image.Image, int]:
        """Render a single character with animation properties.
        
        CRITICAL: Frontend applies these transformations in CSS:
        - blur: props.blur * 0.5 (in _render_character)
        - y_offset: props.yOffset * 0.5 (in _render_group)
        - stroke: stroke_width * 0.05 (WebkitTextStroke approximation)
        - shadow: textShadow 0 2px 8px rgba(0,0,0,0.5)
        
        We must match these EXACTLY for visual parity.
        """
        # CRITICAL: Frontend uses blur * 0.5 in CSS filter
        scaled_blur = props.blur * 0.5
        actual_blur = scaled_blur if scaled_blur >= 0.6 else 0.0
        
        # Check cache
        cache_key = self.cache.get_key(
            char, actual_blur, props.scale, self.state.style.font_size
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return self._apply_opacity(cached.copy(), props.opacity)
        
        # Measure character
        char_w, char_h = self.layout.measure_char(char)
        
        # FIX: Significantly increase padding to prevent clipping of shadows/glows/ascenders
        # Some fonts like Inter have tall metrics
        padding = self.state.style.stroke_width * 2 + int(actual_blur * 4) + 60
        
        canvas_w = char_w + padding * 2
        canvas_h = char_h + padding * 2
        
        # Create character image
        canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        
        # Center the text in the padded canvas
        # Note: measure_char returns bounding box size, not advanced width/height
        # We draw at (padding, padding) but need to account for font offset potentially
        text_x = padding
        text_y = padding
        
        # Draw text shadow first (matches frontend: textShadow: 0 2px 8px rgba(0,0,0,0.5))
        # We'll render a shadow layer behind the text
        shadow_color = (0, 0, 0, 128)  # rgba(0,0,0,0.5)
        shadow_y_offset = 2
        shadow_blur = 8
        
        # Create shadow layer
        shadow_layer = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.text(
            (text_x, text_y + shadow_y_offset),
            char,
            font=self.layout.get_font(),
            fill=shadow_color
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur / 2))
        canvas = Image.alpha_composite(canvas, shadow_layer)
        draw = ImageDraw.Draw(canvas)  # Refresh draw context
        
        # Draw stroke
        # CRITICAL: Frontend uses stroke_width * 0.05 for WebkitTextStroke
        # For PIL, we approximate this but need thicker for visibility
        # WebkitTextStroke is thinner, so we scale down our stroke
        raw_stroke = self.state.style.stroke_width
        stroke_w = max(1, int(raw_stroke * 0.3))  # Scale factor to match CSS appearance
        stroke_color = self._parse_color(self.state.style.stroke_color)
        step = max(1, stroke_w // 2)
        
        for dx in range(-stroke_w, stroke_w + 1, step):
            for dy in range(-stroke_w, stroke_w + 1, step):
                if dx * dx + dy * dy <= stroke_w * stroke_w:
                    draw.text(
                        (text_x + dx, text_y + dy),
                        char,
                        font=self.layout.get_font(),
                        fill=stroke_color
                    )
        
        # Draw text
        text_color = self._parse_color(self.state.style.text_color)
        draw.text((text_x, text_y), char, font=self.layout.get_font(), fill=text_color)
        
        # Apply scale
        if abs(props.scale - 1.0) > 0.001:
            new_w = max(1, int(canvas_w * props.scale))
            new_h = max(1, int(canvas_h * props.scale))
            scaled = canvas.resize((new_w, new_h), Image.LANCZOS)
            result = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            paste_x = (canvas_w - new_w) // 2
            paste_y = (canvas_h - new_h) // 2
            result.paste(scaled, (paste_x, paste_y))
            canvas = result
        
        # Apply blur
        if actual_blur >= 1.2:
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=actual_blur))
        
        # Cache and return
        self.cache.set(cache_key, canvas)
        return self._apply_opacity(canvas, props.opacity)
    
    def _apply_opacity(
        self,
        image: Image.Image,
        opacity: float
    ) -> Tuple[Image.Image, int]:
        """Apply opacity to an image."""
        if opacity < 1.0:
            r, g, b, a = image.split()
            a = a.point(lambda x: int(x * opacity))
            image = Image.merge('RGBA', (r, g, b, a))
        padding = self.state.style.stroke_width * 2 + 60
        return image, padding
    
    def _parse_color(self, color: str) -> Tuple[int, int, int, int]:
        """Parse hex color to RGBA tuple."""
        color = color.lstrip('#')
        if len(color) == 6:
            return (
                int(color[0:2], 16),
                int(color[2:4], 16),
                int(color[4:6], 16),
                255
            )
        elif len(color) == 8:
            return (
                int(color[0:2], 16),
                int(color[2:4], 16),
                int(color[4:6], 16),
                int(color[6:8], 16)
            )
        return (255, 255, 255, 255)
    
    def get_timeline_range(self) -> Tuple[float, float]:
        """Get the start and end time of all captions."""
        if not self.groups:
            return (0.0, 0.0)
        return (
            self.groups[0].start_time,
            self.groups[-1].end_time
        )
