"""
Video Encoder - FFmpeg-based video encoding

Handles encoding frames to ProRes 4444 or H.264 output.
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable


def find_ffmpeg() -> Optional[str]:
    """Find FFmpeg executable."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return 'ffmpeg'
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    
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
            for ffmpeg_path in base_path.rglob("ffmpeg.exe"):
                return str(ffmpeg_path)
    
    return None


_cached_h264_encoder = None

def get_h264_encoder(ffmpeg_path: str) -> str:
    """Detect best available H.264 encoder."""
    global _cached_h264_encoder
    if _cached_h264_encoder:
        return _cached_h264_encoder
        
    try:
        output = subprocess.check_output([ffmpeg_path, '-encoders']).decode('utf-8', errors='ignore')
        
        # Preference order
        candidates = ['libx264', 'h264_nvenc', 'h264_amf', 'h264_qsv', 'h264_mf']
        
        for candidate in candidates:
            for line in output.splitlines():
                if candidate in line and "H.264" in line:
                    _cached_h264_encoder = candidate
                    return candidate
                    
        # Fallback to generic h264 if allowed
        _cached_h264_encoder = "h264"
        return "h264"
        
    except Exception:
        return "libx264" # Hope for the best


class VideoEncoder:
    """
    Pipe-based video encoder using FFmpeg.
    
    Supports:
    - ProRes 4444 (transparent overlay)
    - H.264 (burn-in composite)
    """
    
    def __init__(
        self,
        output_path: str,
        width: int,
        height: int,
        fps: int = 30,
        codec: str = "prores"  # prores or h264
    ):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self.process = None
        self.frame_count = 0
        self.ffmpeg = find_ffmpeg()
        
        if not self.ffmpeg:
            raise RuntimeError("FFmpeg not found")
    
    def __enter__(self):
        if self.codec == "prores":
            cmd = [
                self.ffmpeg, '-y',
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
        else:  # h264
            encoder = get_h264_encoder(self.ffmpeg)
            cmd = [
                self.ffmpeg, '-y',
                '-f', 'rawvideo',
                '-pix_fmt', 'rgba',
                '-s', f'{self.width}x{self.height}',
                '-r', str(self.fps),
                '-i', '-',
                '-c:v', encoder,
                '-pix_fmt', 'yuv420p',
                '-b:v', '15M',
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
                if self.process.stdin:
                    # Flush and close stdin to signal end of input
                    self.process.stdin.flush()
                    self.process.stdin.close()
                
                # Use communicate() for proper cleanup - this waits for FFmpeg to finish
                # Give FFmpeg up to 120 seconds to finalize the video
                try:
                    _, stderr = self.process.communicate(timeout=120)
                    if self.process.returncode != 0 and stderr:
                        print(f"FFmpeg warning: {stderr.decode()[:500]}")
                except subprocess.TimeoutExpired:
                    print("FFmpeg encoding timed out, terminating...")
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
            except Exception as e:
                print(f"Encoder cleanup error: {e}")
                try:
                    self.process.kill()
                except:
                    pass
    
    def add_frame(self, frame):
        """Add a frame (numpy array or bytes)."""
        if self.process and self.process.stdin:
            if hasattr(frame, 'tobytes'):
                self.process.stdin.write(frame.tobytes())
            else:
                self.process.stdin.write(frame)
            self.frame_count += 1
    
    def encode(self):
        """Finalize encoding."""
        if self.process:
            self.process.stdin.close()
            _, stderr = self.process.communicate()
            if self.process.returncode != 0:
                raise RuntimeError(f"FFmpeg encoding failed: {stderr.decode()}")


def composite_with_video(
    video_path: str,
    overlay_path: str,
    output_path: str,
    progress_callback: Optional[Callable[[float], None]] = None
) -> bool:
    """
    Composite caption overlay onto source video.
    
    Args:
        video_path: Path to source video
        overlay_path: Path to transparent overlay
        output_path: Path for output video
        progress_callback: Optional function to report progress (0-100)
    
    Returns:
        True if successful
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False
    
    cmd = [
        ffmpeg, '-y',
        '-i', video_path,
        '-i', overlay_path,
        '-filter_complex', '[0:v][1:v]overlay=0:0:format=auto',
    ]

    if output_path.lower().endswith('.mov'):
        # ProRes 4444 for MOV
        cmd.extend([
            '-c:v', 'prores_ks',
            '-profile:v', '4444',
            '-c:a', 'copy'
        ])
    else:
        # H.264 for MP4 (default)
        encoder = get_h264_encoder(ffmpeg)
        cmd.extend([
            '-c:v', encoder,
            '-b:v', '20M',
            '-c:a', 'copy'
        ])

    cmd.append(output_path)
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else "Unknown FFmpeg error"
        print(f"Compositing error: {error_msg}")
        raise RuntimeError(f"FFmpeg compositing failed: {error_msg}")
