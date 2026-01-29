#!/usr/bin/env python3
"""
Captioneer - Cinematic Character-Level Kinetic Typography Engine

Supports:
  - Direct video input with automatic transcription (faster-whisper)
  - JSON word timestamps input
  
Animation Model:
  - Dynamic word grouping based on natural speech rhythm
  - 1-3 words visible at any time (never forced to 3)
  - Words accumulate as spoken, hard-cut when 4th word arrives
  - Each word enters with character-level blur → focus animation
  - Outgoing words vanish INSTANTLY (hard cut)

Output: Transparent ProRes 4444 overlay for CapCut, Premiere, Resolve, etc.
"""

import argparse
import json
import subprocess
import sys
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import hashlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================================
# EASING FUNCTIONS
# ============================================================================

def ease_out_cubic(t: float) -> float:
    """Smooth deceleration - fog clearing into focus."""
    return 1 - pow(1 - t, 3)


# ============================================================================
# ANIMATION CONSTANTS
# ============================================================================

CHAR_STAGGER = 0.025
ENTRY_DURATION = 0.28
MAX_WORDS_ON_SCREEN = 3

ENTRY_BLUR_START = 20.0
ENTRY_OPACITY_START = 0.1
ENTRY_SCALE_START = 0.96
ENTRY_Y_OFFSET_START = 6.0

ENTRY_BLUR_END = 0.0
ENTRY_OPACITY_END = 1.0
ENTRY_SCALE_END = 1.0
ENTRY_Y_OFFSET_END = 0.0


# ============================================================================
# ANIMATION STATE
# ============================================================================

@dataclass(frozen=True)
class CharProperties:
    opacity: float = 0.0
    blur: float = ENTRY_BLUR_START
    scale: float = ENTRY_SCALE_START
    y_offset: float = ENTRY_Y_OFFSET_START
    visible: bool = False


def char_state_entry_only(
    current_time: float,
    char_entry_start: float,
    char_focus_time: float
) -> CharProperties:
    if current_time < char_entry_start:
        return CharProperties(visible=False)
    
    if char_entry_start <= current_time < char_focus_time:
        progress = (current_time - char_entry_start) / ENTRY_DURATION
        progress = min(1.0, max(0.0, progress))
        e = ease_out_cubic(progress)
        
        opacity = ENTRY_OPACITY_START + (ENTRY_OPACITY_END - ENTRY_OPACITY_START) * e
        blur = ENTRY_BLUR_START + (ENTRY_BLUR_END - ENTRY_BLUR_START) * e
        scale = ENTRY_SCALE_START + (ENTRY_SCALE_END - ENTRY_SCALE_START) * e
        y_offset = ENTRY_Y_OFFSET_START + (ENTRY_Y_OFFSET_END - ENTRY_Y_OFFSET_START) * e
        
        return CharProperties(
            opacity=opacity,
            blur=blur,
            scale=scale,
            y_offset=y_offset,
            visible=True
        )
    
    return CharProperties(
        opacity=1.0,
        blur=0.0,
        scale=1.0,
        y_offset=0.0,
        visible=True
    )


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Word:
    text: str
    start: float
    end: float
    index: int = 0


@dataclass
class Character:
    char: str
    word_index: int
    char_index_in_word: int
    global_char_index: int
    entry_start: float
    focus_time: float


@dataclass
class DisplayGroup:
    word_indices: List[int]
    start_time: float
    end_time: float


# ============================================================================
# FFMPEG PATH DISCOVERY
# ============================================================================

def find_ffmpeg() -> Optional[str]:
    """Find FFmpeg executable, checking common locations."""
    # Check if in PATH first
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return 'ffmpeg'
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    
    # Common installation locations on Windows
    search_paths = [
        Path.home() / "AppData/Local/CapCut/Apps",
        Path("C:/Program Files/FFmpeg/bin"),
        Path("C:/Program Files (x86)/FFmpeg/bin"),
        Path("C:/ffmpeg/bin"),
        Path.home() / "scoop/apps/ffmpeg/current/bin",
        Path.home() / "AppData/Local/Microsoft/WinGet/Packages",
    ]
    
    for base_path in search_paths:
        if base_path.exists():
            # Search recursively for ffmpeg.exe
            for ffmpeg_path in base_path.rglob("ffmpeg.exe"):
                return str(ffmpeg_path)
    
    return None

# Global FFmpeg path (cached)
_FFMPEG_PATH: Optional[str] = None

def get_ffmpeg() -> str:
    """Get FFmpeg path, raising error if not found."""
    global _FFMPEG_PATH
    if _FFMPEG_PATH is None:
        _FFMPEG_PATH = find_ffmpeg()
    if _FFMPEG_PATH is None:
        raise RuntimeError(
            "FFmpeg not found. Please install FFmpeg:\n"
            "  - Download from https://ffmpeg.org/download.html\n"
            "  - Or run: winget install Gyan.FFmpeg\n"
            "  - Then restart your terminal/application"
        )
    return _FFMPEG_PATH


# ============================================================================
# VIDEO TRANSCRIPTION
# ============================================================================

def check_faster_whisper() -> bool:
    try:
        import faster_whisper
        return True
    except ImportError:
        return False


def extract_audio_from_video(video_path: str) -> str:
    """Extract audio from video to temporary WAV file."""
    ffmpeg = get_ffmpeg()
    
    temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_audio.close()
    
    cmd = [
        ffmpeg, '-y',
        '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        temp_audio.name
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        os.unlink(temp_audio.name)
        raise RuntimeError(f"Failed to extract audio: {e.stderr.decode()}")
    
    return temp_audio.name


def transcribe_video(video_path: str, model_size: str = "small") -> List[Word]:
    """Transcribe video using faster-whisper and return Word objects."""
    if not check_faster_whisper():
        print("ERROR: faster-whisper is not installed.", file=sys.stderr)
        print("", file=sys.stderr)
        print("To use video input, install it with:", file=sys.stderr)
        print("  pip install faster-whisper", file=sys.stderr)
        print("", file=sys.stderr)
        print("Or use --words with a pre-made JSON file instead.", file=sys.stderr)
        sys.exit(1)
    
    from faster_whisper import WhisperModel
    
    print(f"      Extracting audio from video...")
    audio_path = extract_audio_from_video(video_path)
    
    try:
        print(f"      Loading Whisper model ({model_size})...")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        
        print(f"      Transcribing speech...")
        segments, info = model.transcribe(
            audio_path,
            word_timestamps=True,
            language=None
        )
        
        words = []
        word_index = 0
        
        for segment in segments:
            if segment.words:
                for word_info in segment.words:
                    # Clean text: remove punctuation, lowercase optional
                    text = word_info.word.strip()
                    # Remove common punctuation
                    for punct in '.,!?;:"\'-()[]{}':
                        text = text.replace(punct, '')
                    text = text.strip()
                    
                    if text:
                        words.append(Word(
                            text=text,
                            start=word_info.start,
                            end=word_info.end,
                            index=word_index
                        ))
                        word_index += 1
        
        print(f"      ✓ Transcribed {len(words)} words")
        return words
        
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)


def dump_words_to_json(words: List[Word], output_path: str):
    """Save words to JSON file."""
    data = [
        {"text": w.text, "start": w.start, "end": w.end}
        for w in words
    ]
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"      ✓ Words saved to {output_path}")


# ============================================================================
# DYNAMIC GROUPING ENGINE
# ============================================================================

def compute_display_groups(words: List[Word]) -> List[DisplayGroup]:
    if not words:
        return []
    
    groups = []
    current_word_indices = []
    current_group_start = None
    
    for i, word in enumerate(words):
        word.index = i
        word_entry_start = word.start - ENTRY_DURATION
        
        if len(current_word_indices) >= MAX_WORDS_ON_SCREEN:
            if current_word_indices:
                groups.append(DisplayGroup(
                    word_indices=current_word_indices.copy(),
                    start_time=current_group_start,
                    end_time=word_entry_start
                ))
            current_word_indices = [i]
            current_group_start = word_entry_start
        else:
            if not current_word_indices:
                current_group_start = word_entry_start
            current_word_indices.append(i)
    
    if current_word_indices:
        last_word = words[current_word_indices[-1]]
        groups.append(DisplayGroup(
            word_indices=current_word_indices,
            start_time=current_group_start,
            end_time=last_word.end + 1.0
        ))
    
    return groups


def decompose_group_to_characters(words: List[Word], group: DisplayGroup) -> List[Character]:
    characters = []
    global_char_idx = 0
    
    for word_idx in group.word_indices:
        word = words[word_idx]
        
        for char_idx, char in enumerate(word.text):
            stagger_offset = char_idx * CHAR_STAGGER
            entry_start = word.start - ENTRY_DURATION + stagger_offset
            focus_time = word.start + stagger_offset
            
            characters.append(Character(
                char=char,
                word_index=word_idx,
                char_index_in_word=char_idx,
                global_char_index=global_char_idx,
                entry_start=entry_start,
                focus_time=focus_time
            ))
            
            global_char_idx += 1
    
    return characters


# ============================================================================
# CHARACTER CACHE
# ============================================================================

class CharacterRenderCache:
    def __init__(self):
        self._cache: Dict[str, Image.Image] = {}
    
    def get_key(self, char: str, blur: float, scale: float, font_size: int) -> str:
        blur_rounded = round(blur * 2) / 2
        scale_rounded = round(scale * 100) / 100
        key_data = f"{char}|{blur_rounded:.1f}|{scale_rounded:.2f}|{font_size}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Image.Image]:
        return self._cache.get(key)
    
    def set(self, key: str, image: Image.Image):
        self._cache[key] = image.copy()


# ============================================================================
# CHARACTER RENDERER
# ============================================================================

class CharacterRenderer:
    def __init__(self, font_path: str, font_size: int, stroke_width: int = 5):
        self.font_path = font_path
        self.font_size = font_size
        self.stroke_width = stroke_width
        self.font = ImageFont.truetype(font_path, font_size)
        self._char_size_cache: Dict[str, Tuple[int, int]] = {}
        self.render_cache = CharacterRenderCache()
    
    def measure_char(self, char: str) -> Tuple[int, int]:
        if char not in self._char_size_cache:
            temp = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
            draw = ImageDraw.Draw(temp)
            bbox = draw.textbbox((0, 0), char, font=self.font)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            self._char_size_cache[char] = (max(1, width), max(1, height))
        return self._char_size_cache[char]
    
    def measure_text(self, text: str) -> Tuple[int, int]:
        temp = Image.new('RGBA', (2000, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(temp)
        bbox = draw.textbbox((0, 0), text, font=self.font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    def render_character(self, char: str, props: CharProperties, supersample: int = 1) -> Tuple[Image.Image, int]:
        actual_blur = props.blur if props.blur >= 1.2 else 0.0
        
        cache_key = self.render_cache.get_key(char, actual_blur, props.scale, self.font_size)
        cached = self.render_cache.get(cache_key)
        if cached is not None:
            return self._apply_opacity(cached.copy(), props.opacity)
        
        char_w, char_h = self.measure_char(char)
        padding = self.stroke_width * 2 + int(actual_blur * 3) + 20
        
        ss = supersample
        ss_w = (char_w + padding * 2) * ss
        ss_h = (char_h + padding * 2) * ss
        
        ss_font = ImageFont.truetype(self.font_path, self.font_size * ss)
        canvas = Image.new('RGBA', (ss_w, ss_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        
        text_x = padding * ss
        text_y = padding * ss
        
        stroke_w = self.stroke_width * ss
        stroke_color = (0, 0, 0, 255)
        step = max(1, stroke_w // 3)
        
        for dx in range(-stroke_w, stroke_w + 1, step):
            for dy in range(-stroke_w, stroke_w + 1, step):
                if dx * dx + dy * dy <= stroke_w * stroke_w:
                    draw.text((text_x + dx, text_y + dy), char, font=ss_font, fill=stroke_color)
        
        draw.text((text_x, text_y), char, font=ss_font, fill=(255, 255, 255, 255))
        
        if ss > 1:
            target_w = char_w + padding * 2
            target_h = char_h + padding * 2
            canvas = canvas.resize((target_w, target_h), Image.LANCZOS)
        
        if abs(props.scale - 1.0) > 0.001:
            cur_w, cur_h = canvas.size
            new_w = max(1, int(cur_w * props.scale))
            new_h = max(1, int(cur_h * props.scale))
            scaled = canvas.resize((new_w, new_h), Image.LANCZOS)
            result = Image.new('RGBA', (cur_w, cur_h), (0, 0, 0, 0))
            paste_x = (cur_w - new_w) // 2
            paste_y = (cur_h - new_h) // 2
            result.paste(scaled, (paste_x, paste_y))
            canvas = result
        
        if actual_blur >= 1.2:
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=actual_blur))
        
        self.render_cache.set(cache_key, canvas)
        return self._apply_opacity(canvas, props.opacity)
    
    def _apply_opacity(self, image: Image.Image, opacity: float) -> Tuple[Image.Image, int]:
        if opacity < 1.0:
            r, g, b, a = image.split()
            a = a.point(lambda x: int(x * opacity))
            image = Image.merge('RGBA', (r, g, b, a))
        padding = self.stroke_width * 2 + 20
        return image, padding


# ============================================================================
# LAYOUT ENGINE
# ============================================================================

class DynamicLayoutEngine:
    def __init__(self, canvas_width: int, canvas_height: int, char_renderer: CharacterRenderer):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.char_renderer = char_renderer
    
    def compute_layout(self, words: List[Word], group: DisplayGroup) -> Dict[Tuple[int, int], Tuple[float, float]]:
        if not group.word_indices:
            return {}
        
        text_parts = [words[i].text for i in group.word_indices]
        full_text = " ".join(text_parts)
        total_width, text_height = self.char_renderer.measure_text(full_text)
        
        start_x = (self.canvas_width - total_width) / 2
        center_y = (self.canvas_height - text_height) / 2
        
        positions: Dict[Tuple[int, int], Tuple[float, float]] = {}
        current_x = start_x
        
        for idx, word_idx in enumerate(group.word_indices):
            word = words[word_idx]
            
            if idx > 0:
                space_w, _ = self.char_renderer.measure_char(" ")
                current_x += space_w
            
            for char_idx, char in enumerate(word.text):
                positions[(word_idx, char_idx)] = (current_x, center_y)
                char_w, _ = self.char_renderer.measure_char(char)
                current_x += char_w
        
        return positions


# ============================================================================
# FRAME COMPOSER
# ============================================================================

class FrameComposer:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
    
    def compose_frame(self, char_renders: List[Tuple[Image.Image, float, float, int]]) -> np.ndarray:
        frame = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        
        for char_img, x, y, padding in char_renders:
            paste_x = int(x - padding)
            paste_y = int(y - padding)
            
            if paste_x >= self.width or paste_y >= self.height:
                continue
            if paste_x + char_img.width <= 0 or paste_y + char_img.height <= 0:
                continue
            
            frame.paste(char_img, (paste_x, paste_y), char_img)
        
        return np.array(frame)


# ============================================================================
# VIDEO ENCODER (PIPE-BASED)
# ============================================================================

class VideoEncoder:
    def __init__(self, output_path: str, width: int, height: int, fps: int = 30):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.process = None
        self.frame_count = 0
    
    def __enter__(self):
        ffmpeg = get_ffmpeg()
        cmd = [
            ffmpeg, '-y',
            '-f', 'rawvideo',
            '-pix_fmt', 'rgba',
            '-s', f'{self.width}x{self.height}',
            '-r', str(self.fps),
            '-i', '-',
            '-c:v', 'prores_ks',
            '-profile:v', '4444',
            '-pix_fmt', 'yuva444p10le',
            '-vendor', 'apl0',
            '-bits_per_mb', '8000',
            '-f', 'mov',
            self.output_path
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        self.frame_count = 0
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            try:
                self.process.stdin.close()
                self.process.wait()
            except Exception:
                pass
    
    def add_frame(self, frame: np.ndarray):
        if self.process and self.process.stdin:
            self.process.stdin.write(frame.tobytes())
            self.frame_count += 1
    
    def encode(self):
        if self.process:
            self.process.stdin.close()
            _, stderr = self.process.communicate()
            if self.process.returncode != 0:
                raise RuntimeError(f"FFmpeg encoding failed: {stderr.decode()}")


# ============================================================================
# MAIN CAPTION RENDERER
# ============================================================================

class CaptionRenderer:
    def __init__(
        self,
        width: int,
        height: int,
        font_path: str,
        font_size: int = 72,
        fps: int = 30
    ):
        self.width = width
        self.height = height
        self.fps = fps
        
        self.char_renderer = CharacterRenderer(font_path=font_path, font_size=font_size)
        self.layout_engine = DynamicLayoutEngine(
            canvas_width=width,
            canvas_height=height,
            char_renderer=self.char_renderer
        )
        self.frame_composer = FrameComposer(width, height)
    
    def render(self, words: List[Word], output_path: str, progress_callback=None):
        if not words:
            raise ValueError("No words to render")
        
        for i, w in enumerate(words):
            w.index = i
        
        groups = compute_display_groups(words)
        
        if not groups:
            raise ValueError("No groups to render")
        
        group_data = []
        for group in groups:
            chars = decompose_group_to_characters(words, group)
            layout = self.layout_engine.compute_layout(words, group)
            group_data.append({
                'group': group,
                'characters': chars,
                'layout': layout
            })
        
        video_start = max(0, groups[0].start_time - 0.1)
        video_end = groups[-1].end_time + 0.3
        
        total_duration = video_end - video_start
        total_frames = int(total_duration * self.fps)
        
        group_sizes = [len(g.word_indices) for g in groups]
        size_counts = {1: 0, 2: 0, 3: 0}
        for s in group_sizes:
            if s in size_counts:
                size_counts[s] += 1
        
        print(f"Rendering {total_frames} frames ({total_duration:.2f}s) at {self.fps} FPS")
        print(f"Words: {len(words)}, Display groups: {len(groups)}")
        print(f"Group distribution: 1-word={size_counts[1]}, 2-word={size_counts[2]}, 3-word={size_counts[3]}")
        print(f"Timeline: {video_start:.2f}s → {video_end:.2f}s")
        
        with VideoEncoder(output_path, self.width, self.height, self.fps) as encoder:
            for frame_idx in range(total_frames):
                current_time = video_start + (frame_idx / self.fps)
                
                frame = self._render_frame(current_time, words, group_data)
                encoder.add_frame(frame)
                
                if progress_callback:
                    progress_callback(frame_idx, total_frames)
                elif frame_idx % self.fps == 0:
                    pct = (frame_idx / total_frames) * 100
                    print(f"\rRendering: {pct:.1f}% ({frame_idx}/{total_frames})", end="", flush=True)
            
            print("\n\nEncoding to ProRes 4444...")
            encoder.encode()
        
        print(f"Output saved: {output_path}")
    
    def _render_frame(
        self,
        current_time: float,
        words: List[Word],
        group_data: List[dict]
    ) -> np.ndarray:
        char_renders = []
        
        active_gd = None
        for gd in group_data:
            group = gd['group']
            if group.start_time <= current_time < group.end_time:
                active_gd = gd
                break
        
        if active_gd is None:
            return self.frame_composer.compose_frame([])
        
        characters = active_gd['characters']
        layout = active_gd['layout']
        
        for char in characters:
            key = (char.word_index, char.char_index_in_word)
            if key not in layout:
                continue
            
            base_x, base_y = layout[key]
            
            props = char_state_entry_only(
                current_time,
                char.entry_start,
                char.focus_time
            )
            
            if not props.visible or props.opacity < 0.01:
                continue
            
            char_img, padding = self.char_renderer.render_character(char.char, props)
            render_y = base_y + props.y_offset
            
            char_renders.append((char_img, base_x, render_y, padding))
        
        return self.frame_composer.compose_frame(char_renders)


# ============================================================================
# CLI FUNCTIONS
# ============================================================================

def load_words(json_path: str) -> List[Word]:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"Words file not found: {json_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of word objects")
    
    words = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Word {i} must be an object")
        
        for field in ['text', 'start', 'end']:
            if field not in item:
                raise ValueError(f"Word {i} missing '{field}'")
        
        try:
            word = Word(
                text=str(item['text']),
                start=float(item['start']),
                end=float(item['end']),
                index=i
            )
            if word.end < word.start:
                raise ValueError(f"Word {i}: end < start")
            words.append(word)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid word {i}: {e}")
    
    words.sort(key=lambda w: w.start)
    return words


def find_epilogue_font() -> Optional[str]:
    # First check local static folder (preferred - bundled fonts)
    script_dir = Path(__file__).parent.absolute()
    static_dir = script_dir / "static"
    
    # Default font: Epilogue-Light.ttf
    default_font = static_dir / "Epilogue-Light.ttf"
    if default_font.exists():
        return str(default_font)
    
    # Check for any Epilogue font in static folder
    if static_dir.exists():
        for font_file in static_dir.glob("Epilogue-*.ttf"):
            return str(font_file)
    
    # Fallback: System font directories
    font_dirs = [
        Path("C:/Windows/Fonts"),
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
        Path.home() / ".fonts",
        Path("/usr/share/fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
    ]
    
    patterns = [
        "Epilogue-Light.ttf",
        "Epilogue-Bold.ttf",
        "Epilogue-Bold.otf",
        "EpilogueBold.ttf",
        "Epilogue Bold.ttf",
        "epilogue-bold.ttf",
    ]
    
    for font_dir in font_dirs:
        if font_dir.exists():
            for pattern in patterns:
                font_path = font_dir / pattern
                if font_path.exists():
                    return str(font_path)
    
    return None


def validate_font(font_path: str) -> str:
    path = Path(font_path)
    
    if not path.exists():
        raise ValueError(f"Font not found: {font_path}")
    
    if path.suffix.lower() not in ['.ttf', '.otf']:
        raise ValueError(f"Font must be .ttf or .otf: {font_path}")
    
    try:
        ImageFont.truetype(str(path), 12)
    except Exception as e:
        raise ValueError(f"Cannot load font: {e}")
    
    return str(path.absolute())


def check_ffmpeg() -> bool:
    return find_ffmpeg() is not None


def main():
    default_font = find_epilogue_font()
    
    parser = argparse.ArgumentParser(
        description="Captioneer - Dynamic Kinetic Typography with Video/Transcription Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Input Options (mutually exclusive):
  --words words.json    Use pre-made word timestamps
  --video input.mp4     Transcribe video using faster-whisper

Examples:
  python main.py --words words.json --output overlay.mov
  python main.py --video input.mp4 --output overlay.mov
  python main.py --video input.mp4 --model medium --dump-words words.json
        """
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--words', '-w', help='Path to words.json')
    input_group.add_argument('--video', '-v', help='Path to video file for transcription')
    
    parser.add_argument('--output', '-o', default='overlay.mov', help='Output path')
    parser.add_argument('--model', '-m', default='small',
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help='Whisper model size (default: small)')
    parser.add_argument('--dump-words', help='Save transcribed words to JSON file')
    
    font_help = 'Font file (.ttf/.otf)'
    if default_font:
        font_help += ' (default: Epilogue Light)'
    
    parser.add_argument('--font', '-f', default=default_font, required=(default_font is None), help=font_help)
    parser.add_argument('--width', type=int, default=1080, help='Width (default: 1080)')
    parser.add_argument('--height', type=int, default=1920, help='Height (default: 1920)')
    parser.add_argument('--font-size', type=int, default=72, help='Font size (default: 72)')
    parser.add_argument('--fps', type=int, default=30, help='FPS (default: 30)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("  CAPTIONEER - Dynamic Kinetic Typography Engine")
    print("=" * 70)
    print()
    
    print("[1/5] Checking FFmpeg...")
    if not check_ffmpeg():
        print("ERROR: FFmpeg not found!", file=sys.stderr)
        sys.exit(1)
    print("      ✓ FFmpeg found")
    
    print("\n[2/5] Loading font...")
    try:
        font_path = validate_font(args.font)
        print(f"      ✓ Font: {Path(font_path).name}")
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    
    print("\n[3/5] Loading words...")
    
    if args.video:
        print(f"      Input: Video ({args.video})")
        try:
            words = transcribe_video(args.video, args.model)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        
        if args.dump_words:
            dump_words_to_json(words, args.dump_words)
    else:
        print(f"      Input: JSON ({args.words})")
        try:
            words = load_words(args.words)
            print(f"      ✓ Loaded {len(words)} words")
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    
    groups = compute_display_groups(words)
    total_chars = sum(len(w.text) for w in words)
    
    preview = ' '.join(w.text for w in words[:8])
    if len(words) > 8:
        preview += '...'
    print(f"      Preview: \"{preview}\"")
    print(f"      Display groups: {len(groups)} (dynamic 1-3 words)")
    print(f"      Characters: {total_chars}")
    
    print("\n[4/5] Rendering...")
    print(f"      Resolution: {args.width}×{args.height}")
    print(f"      FPS: {args.fps}")
    print(f"      Output: {args.output}")
    print()
    
    try:
        renderer = CaptionRenderer(
            width=args.width,
            height=args.height,
            font_path=font_path,
            font_size=args.font_size,
            fps=args.fps
        )
        
        renderer.render(words, args.output)
        
        print()
        print("=" * 70)
        print("  RENDERING COMPLETE")
        print("=" * 70)
        print()
        print(f"  Output: {args.output}")
        print()
        print("  Import into CapCut, Premiere, Resolve and composite over footage.")
        print()
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
