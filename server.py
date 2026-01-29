import os
import shutil
import json
import time
import uuid
import threading
from pathlib import Path
from typing import List, Optional, Dict

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

# Import the core rendering engine
from main import (
    CaptionRenderer, Word, find_epilogue_font, check_ffmpeg, 
    load_words, check_faster_whisper, transcribe_video, get_ffmpeg
)

app = FastAPI(title="Captioneer API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory to store generated files
TEMP_DIR = Path("temp_output")
TEMP_DIR.mkdir(exist_ok=True)

# Mount temp dir for downloads
app.mount("/files", StaticFiles(directory=TEMP_DIR), name="files")

# Progress tracking
progress_store: Dict[str, dict] = {}

def cleanup_old_sessions():
    """Delete sessions older than 30 minutes."""
    try:
        now = time.time()
        for p in TEMP_DIR.iterdir():
            if p.is_dir():
                if now - p.stat().st_mtime > 1800:
                    shutil.rmtree(p, ignore_errors=True)
        # Clean old progress entries
        old_sessions = [k for k, v in progress_store.items() 
                       if now - v.get('updated', 0) > 1800]
        for k in old_sessions:
            del progress_store[k]
    except Exception as e:
        print(f"Cleanup error: {e}")

def create_preview(input_path: Path, output_path: Path) -> bool:
    """Create a browser-compatible preview. Returns True if successful."""
    import subprocess
    ffmpeg = get_ffmpeg()
    
    # Try H.264 first (most compatible)
    try:
        cmd = [
            ffmpeg, '-y',
            '-i', str(input_path),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'fast',
            '-crf', '23',
            str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"H.264 encoding failed: {e}")
    
    # Fallback: Try VP9 WebM
    try:
        webm_output = output_path.with_suffix('.webm')
        cmd = [
            ffmpeg, '-y',
            '-i', str(input_path),
            '-c:v', 'libvpx-vp9',
            '-crf', '30',
            '-b:v', '0',
            str(webm_output)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        # Rename to expected output
        if webm_output.exists():
            shutil.copy(webm_output, output_path)
        return True
    except Exception as e:
        print(f"VP9 encoding failed: {e}")
    
    # Final fallback: Just copy the master (won't play in browser but can download)
    try:
        shutil.copy(input_path, output_path)
        return True
    except Exception as e:
        print(f"Copy fallback failed: {e}")
    
    return False

@app.get("/health")
def health_check():
    return {
        "status": "ok", 
        "ffmpeg": check_ffmpeg(),
        "faster_whisper": check_faster_whisper()
    }

@app.get("/progress/{session_id}")
def get_progress(session_id: str):
    """Get current progress for a session."""
    if session_id in progress_store:
        return progress_store[session_id]
    return {"stage": "unknown", "progress": 0, "message": "Session not found"}

def update_progress(session_id: str, stage: str, progress: float, message: str = ""):
    """Update progress for a session."""
    progress_store[session_id] = {
        "stage": stage,
        "progress": progress,
        "message": message,
        "updated": time.time()
    }

def render_task(
    session_id: str,
    words: List[Word],
    master_path: Path,
    preview_path: Path,
    font_path_str: str,
    width: int,
    height: int,
    font_size: int,
    fps: int
):
    """Background rendering task with progress updates."""
    try:
        update_progress(session_id, "rendering", 0, "Starting render...")
        
        renderer = CaptionRenderer(
            width=width,
            height=height,
            font_path=font_path_str,
            font_size=font_size,
            fps=fps
        )
        
        def progress_callback(frame_idx, total_frames):
            # Rendering is 0-80% of total progress
            pct = (frame_idx / total_frames) * 80
            update_progress(session_id, "rendering", pct, 
                          f"Rendering frame {frame_idx}/{total_frames}")
        
        renderer.render(words, str(master_path), progress_callback=progress_callback)
        
        update_progress(session_id, "encoding", 85, "Creating preview...")
        preview_success = create_preview(master_path, preview_path)
        
        update_progress(session_id, "complete", 100, "Done!")
        
        # Build result - use master as preview fallback if preview failed
        result = {
            "master_url": f"/files/{session_id}/captioneer_master.mov",
            "word_count": len(words)
        }
        
        if preview_success and preview_path.exists():
            result["preview_url"] = f"/files/{session_id}/preview.mp4"
        else:
            # Use master as preview (browser may not play it but download works)
            result["preview_url"] = f"/files/{session_id}/captioneer_master.mov"
        
        progress_store[session_id]["result"] = result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        update_progress(session_id, "error", 0, str(e))

@app.post("/render")
async def render_video(
    words_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    font_file: Optional[UploadFile] = File(None),
    width: int = Form(1080),
    height: int = Form(1920),
    font_size: int = Form(72),
    fps: int = Form(30),
    whisper_model: str = Form("small")
):
    # Garbage collection
    cleanup_old_sessions()

    # Validate input
    if not words_file and not video_file:
        return JSONResponse(status_code=400, content={"error": "Must provide either words_file (JSON) or video_file"})
    
    if words_file and video_file:
        return JSONResponse(status_code=400, content={"error": "Provide only one: words_file OR video_file, not both"})

    try:
        session_id = str(uuid.uuid4())
        session_dir = TEMP_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        update_progress(session_id, "initializing", 0, "Processing input...")
        
        words: List[Word] = []
        
        # Handle video input (transcription)
        if video_file:
            if not check_faster_whisper():
                return JSONResponse(status_code=400, content={
                    "error": "faster-whisper is not installed. Install with: pip install faster-whisper"
                })
            
            update_progress(session_id, "uploading", 5, "Saving video...")
            video_path = session_dir / video_file.filename
            with open(video_path, "wb") as f:
                shutil.copyfileobj(video_file.file, f)
            
            update_progress(session_id, "transcribing", 10, "Extracting audio...")
            try:
                def transcribe_with_progress():
                    update_progress(session_id, "transcribing", 15, "Loading Whisper model...")
                    return transcribe_video(str(video_path), whisper_model)
                
                words = await run_in_threadpool(transcribe_with_progress)
                update_progress(session_id, "transcribing", 20, f"Transcribed {len(words)} words")
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": f"Transcription failed: {str(e)}"})
            finally:
                if video_path.exists():
                    os.unlink(video_path)
        
        # Handle JSON input
        elif words_file:
            words_path = session_dir / "words.json"
            with open(words_path, "wb") as f:
                content = await words_file.read()
                f.write(content)
            
            try:
                words = await run_in_threadpool(load_words, str(words_path))
                update_progress(session_id, "loaded", 20, f"Loaded {len(words)} words")
            except Exception as e:
                return JSONResponse(status_code=400, content={"error": f"Invalid JSON: {str(e)}"})

        if not words:
            return JSONResponse(status_code=400, content={"error": "No words found to render"})

        # Handle Font
        font_path_str = None
        if font_file:
            font_path = session_dir / font_file.filename
            with open(font_path, "wb") as f:
                shutil.copyfileobj(font_file.file, f)
            font_path_str = str(font_path)
        else:
            font_path_str = find_epilogue_font()
            if not font_path_str:
                if os.path.exists("C:/Windows/Fonts/arialbd.ttf"):
                    font_path_str = "C:/Windows/Fonts/arialbd.ttf"
                else:
                    return JSONResponse(status_code=400, content={"error": "Default font not found. Please upload one."})

        master_path = session_dir / "captioneer_master.mov"
        preview_path = session_dir / "preview.mp4"
        
        # Start rendering in background thread
        thread = threading.Thread(
            target=render_task,
            args=(session_id, words, master_path, preview_path, 
                  font_path_str, width, height, font_size, fps)
        )
        thread.start()

        # Return session ID for progress polling
        return {
            "session_id": session_id,
            "word_count": len(words),
            "status": "processing"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    print("Starting Captioneer Server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
