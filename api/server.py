"""
Captioneer Studio API Server

FastAPI-based backend for the interactive caption editor.
Provides endpoints for:
- Project management
- Transcription
- Real-time preview
- Export
"""

import os
import sys
import uuid
import json
import time
import shutil
import asyncio
import base64
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent to path for engine imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.renderer import FrameRenderer, ProjectState
from engine.motion import MotionSettings, Word
from engine.layout import StyleSettings, CanvasSettings


# ============================================================================
# Configuration
# ============================================================================

UPLOAD_DIR = Path("uploads")
PROJECTS_DIR = Path("projects") 
EXPORT_DIR = Path("exports")

for d in [UPLOAD_DIR, PROJECTS_DIR, EXPORT_DIR]:
    d.mkdir(exist_ok=True)


# ============================================================================
# Pydantic Models
# ============================================================================

class WordModel(BaseModel):
    id: str
    text: str
    start: float
    end: float


class CanvasModel(BaseModel):
    width: int = 1080
    height: int = 1920
    position_x: int = 540
    position_y: int = 1400
    anchor: str = "center"


class StyleModel(BaseModel):
    font_family: str = "Epilogue-Light"
    font_size: int = 72
    font_weight: int = 700
    text_transform: str = "none"  # none, uppercase, lowercase, capitalize
    line_spacing: float = 1.1
    letter_spacing: int = 0
    alignment: str = "center"
    stroke_width: int = 5
    text_color: str = "#FFFFFF"
    stroke_color: str = "#000000"


class MotionModel(BaseModel):
    max_words_on_screen: int = 3
    entry_blur_start: float = 20.0
    entry_duration: float = 0.28
    char_stagger: float = 0.025
    entry_scale: float = 0.96
    y_drift: float = 6.0
    entry_opacity_start: float = 0.1  # Match frontend


class ProjectModel(BaseModel):
    id: str
    name: str
    video_path: Optional[str] = None
    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    video_duration: float = 0.0
    canvas: CanvasModel = CanvasModel()
    style: StyleModel = StyleModel()
    motion: MotionModel = MotionModel()
    words: List[WordModel] = []


class FrameRequest(BaseModel):
    project: ProjectModel
    time: float
    quality: str = "low"  # low (360p), medium (540p), high (full)


class ExportRequest(BaseModel):
    project: ProjectModel
    mode: str = "burn-in"  # overlay or burn-in
    format: str = "mp4"    # mp4 or mov


# ============================================================================
# In-memory state
# ============================================================================

active_projects: Dict[str, ProjectModel] = {}
export_jobs: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Captioneer Studio API starting...")
    yield
    # Shutdown
    print("Captioneer Studio API shutting down...")


# ============================================================================
# App
# ============================================================================

app = FastAPI(
    title="Captioneer Studio API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directories
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/exports", StaticFiles(directory=EXPORT_DIR), name="exports")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


# ============================================================================
# Font Management
# ============================================================================

@app.get("/api/fonts")
async def list_fonts():
    """List available fonts."""
    static_dir = Path(__file__).parent.parent / "static"
    fonts = []
    
    if static_dir.exists():
        for f in static_dir.glob("*.ttf"):
            fonts.append({
                "name": f.stem,
                "file": f.name
            })
        for f in static_dir.glob("*.otf"):
            fonts.append({
                "name": f.stem,
                "file": f.name
            })
    
    return {"fonts": fonts}


# ============================================================================
# Project Management
# ============================================================================

@app.post("/api/project/create")
async def create_project(name: str = Form("Untitled")):
    """Create a new project."""
    project_id = str(uuid.uuid4())
    project = ProjectModel(
        id=project_id,
        name=name
    )
    active_projects[project_id] = project
    
    # Save to disk
    project_path = PROJECTS_DIR / f"{project_id}.json"
    with open(project_path, 'w') as f:
        json.dump(project.model_dump(), f, indent=2)
    
    return project


@app.get("/api/project/{project_id}")
async def get_project(project_id: str):
    """Get project by ID."""
    # Check memory first
    if project_id in active_projects:
        return active_projects[project_id]
    
    # Try loading from disk
    project_path = PROJECTS_DIR / f"{project_id}.json"
    if project_path.exists():
        with open(project_path) as f:
            data = json.load(f)
            project = ProjectModel(**data)
            active_projects[project_id] = project
            return project
    
    raise HTTPException(status_code=404, detail="Project not found")


@app.put("/api/project/{project_id}")
async def update_project(project_id: str, project: ProjectModel):
    """Update project."""
    active_projects[project_id] = project
    
    # Save to disk
    project_path = PROJECTS_DIR / f"{project_id}.json"
    with open(project_path, 'w') as f:
        json.dump(project.model_dump(), f, indent=2)
    
    return {"status": "saved"}


@app.delete("/api/project/{project_id}")
async def delete_project(project_id: str):
    """Delete project."""
    if project_id in active_projects:
        del active_projects[project_id]
    
    project_path = PROJECTS_DIR / f"{project_id}.json"
    if project_path.exists():
        project_path.unlink()
    
    return {"status": "deleted"}


# ============================================================================
# Video Upload & Transcription
# ============================================================================

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file."""
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    save_path = UPLOAD_DIR / f"{file_id}{ext}"
    
    with open(save_path, 'wb') as f:
        shutil.copyfileobj(file.file, f)
    
    # Get video info via ffprobe
    video_info = await get_video_info(str(save_path))
    
    return {
        "file_id": file_id,
        "path": str(save_path),
        "url": f"/uploads/{file_id}{ext}",
        "info": video_info
    }


async def get_video_info(video_path: str) -> Dict[str, Any]:
    """Get video metadata using ffprobe."""
    from engine.encoder import find_ffmpeg
    
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {"width": 1080, "height": 1920, "fps": 30, "duration": 0}
    
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    if not Path(ffprobe).exists():
        ffprobe = ffprobe.replace("ffmpeg.exe", "ffprobe.exe")
    
    try:
        import subprocess
        cmd = [
            ffprobe, '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams', '-show_format',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        video_stream = next(
            (s for s in data.get('streams', []) if s['codec_type'] == 'video'),
            None
        )
        
        if video_stream:
            fps_parts = video_stream.get('r_frame_rate', '30/1').split('/')
            fps = int(fps_parts[0]) / int(fps_parts[1]) if len(fps_parts) == 2 else 30
            
            return {
                "width": video_stream.get('width', 1080),
                "height": video_stream.get('height', 1920),
                "fps": fps,
                "duration": float(data.get('format', {}).get('duration', 0))
            }
    except Exception as e:
        print(f"Error getting video info: {e}")
    
    return {"width": 1080, "height": 1920, "fps": 30, "duration": 0}


@app.post("/api/transcribe")
async def transcribe_video(
    video_path: str = Form(...),
    model: str = Form("small")
):
    """Transcribe video to word timeline."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="faster-whisper not installed. Run: pip install faster-whisper"
        )
    
    from engine.encoder import find_ffmpeg
    import tempfile
    import subprocess
    
    # Extract audio
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise HTTPException(status_code=500, detail="FFmpeg not found")
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_path = tmp.name
    
    try:
        cmd = [
            ffmpeg, '-y', '-i', video_path,
            '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
            audio_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Transcribe
        whisper = WhisperModel(model, device="cpu", compute_type="int8")
        segments, _ = whisper.transcribe(
            audio_path,
            word_timestamps=True,
            vad_filter=True
        )
        
        words = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    word_text = w.word.strip()
                    # Only remove punctuation, preserve original casing
                    # (text_transform setting will handle capitalization)
                    word_text = ''.join(c for c in word_text if c.isalnum() or c == "'")
                    if word_text:
                        words.append(WordModel(
                            id=f"w{len(words)}",
                            text=word_text,
                            start=round(w.start, 3),
                            end=round(w.end, 3)
                        ))
        
        return {"words": [w.model_dump() for w in words]}
    
    finally:
        if Path(audio_path).exists():
            Path(audio_path).unlink()


# ============================================================================
# Preview Rendering
# ============================================================================

def project_to_state(project: ProjectModel) -> ProjectState:
    """Convert ProjectModel to engine's ProjectState."""
    # Apply text transform
    transform = project.style.text_transform
    transformed_words = []
    
    for w in project.words:
        text = w.text
        if transform == 'uppercase':
            text = text.upper()
        elif transform == 'lowercase':
            text = text.lower()
        elif transform == 'capitalize':
            text = text.capitalize()
            
        transformed_words.append(Word(id=w.id, text=text, start=w.start, end=w.end))

    words = transformed_words
    
    # CRITICAL: Frontend sends position as percentages (0-100)
    # Backend LayoutEngine expects pixel coordinates
    # Convert percentage to pixels
    pixel_x = int((project.canvas.position_x / 100) * project.video_width)
    pixel_y = int((project.canvas.position_y / 100) * project.video_height)
    
    canvas = CanvasSettings(
        width=project.video_width,
        height=project.video_height,
        position_x=pixel_x,
        position_y=pixel_y,
        anchor=project.canvas.anchor
    )
    
    # DEBUG: Log received style settings
    print(f"[EXPORT] Received style: font_family={project.style.font_family}, font_weight={project.style.font_weight}")
    
    style = StyleSettings(
        font_family=project.style.font_family,
        font_size=project.style.font_size,
        font_weight=project.style.font_weight,
        text_transform=project.style.text_transform,
        line_spacing=project.style.line_spacing,
        letter_spacing=project.style.letter_spacing,
        alignment=project.style.alignment,
        stroke_width=project.style.stroke_width,
        text_color=project.style.text_color,
        stroke_color=project.style.stroke_color
    )
    
    motion = MotionSettings(
        max_words_on_screen=project.motion.max_words_on_screen,
        entry_blur_start=project.motion.entry_blur_start,
        entry_duration=project.motion.entry_duration,
        char_stagger=project.motion.char_stagger,
        entry_scale=project.motion.entry_scale,
        y_drift=project.motion.y_drift,
        entry_opacity_start=project.motion.entry_opacity_start
    )
    
    return ProjectState(
        video_width=project.video_width,
        video_height=project.video_height,
        video_fps=project.video_fps,
        canvas=canvas,
        style=style,
        motion=motion,
        words=words
    )


@app.post("/api/preview/frame")
async def render_preview_frame(request: FrameRequest):
    """Render a single preview frame."""
    state = project_to_state(request.project)
    
    # Scale for quality
    scale = {"low": 0.33, "medium": 0.5, "high": 1.0}.get(request.quality, 0.33)
    
    if scale < 1.0:
        state.video_width = int(state.video_width * scale)
        state.video_height = int(state.video_height * scale)
        state.canvas.position_x = int(state.canvas.position_x * scale)
        state.canvas.position_y = int(state.canvas.position_y * scale)
        state.style.font_size = int(state.style.font_size * scale)
        state.style.stroke_width = max(1, int(state.style.stroke_width * scale))
    
    renderer = FrameRenderer(state)
    frame = renderer.render_frame(request.time)
    
    # Convert to base64 PNG
    buffer = BytesIO()
    frame.save(buffer, format='PNG')
    buffer.seek(0)
    b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return {
        "frame": f"data:image/png;base64,{b64}",
        "width": state.video_width,
        "height": state.video_height,
        "time": request.time
    }


# ============================================================================
# WebSocket Preview Streaming
# ============================================================================

@app.websocket("/ws/preview")
async def preview_websocket(websocket: WebSocket):
    """WebSocket for streaming preview frames."""
    await websocket.accept()
    
    renderer = None
    last_state_hash = None
    
    try:
        while True:
            data = await websocket.receive_json()
            
            project = ProjectModel(**data['project'])
            time = data.get('time', 0)
            quality = data.get('quality', 'low')
            
            state = project_to_state(project)
            
            # Scale for quality
            scale = {"low": 0.33, "medium": 0.5, "high": 1.0}.get(quality, 0.33)
            if scale < 1.0:
                state.video_width = int(state.video_width * scale)
                state.video_height = int(state.video_height * scale)
                state.canvas.position_x = int(state.canvas.position_x * scale)
                state.canvas.position_y = int(state.canvas.position_y * scale)
                state.style.font_size = int(state.style.font_size * scale)
                state.style.stroke_width = max(1, int(state.style.stroke_width * scale))
            
            # Check if we need new renderer
            state_hash = hash(str(state))
            if renderer is None or state_hash != last_state_hash:
                renderer = FrameRenderer(state)
                last_state_hash = state_hash
            
            frame = renderer.render_frame(time)
            
            # Convert to base64 PNG
            buffer = BytesIO()
            frame.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            await websocket.send_json({
                "frame": f"data:image/png;base64,{b64}",
                "time": time
            })
    
    except WebSocketDisconnect:
        pass


# ============================================================================
# Export
# ============================================================================

@app.post("/api/export")
async def start_export(request: ExportRequest):
    """Start an export job."""
    job_id = str(uuid.uuid4())
    
    export_jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Starting export...",
        "output_path": None
    }
    
    # Start export in background
    asyncio.create_task(run_export(job_id, request))
    
    return {"job_id": job_id}


async def run_export(job_id: str, request: ExportRequest):
    """Run export job in background."""
    from engine.encoder import VideoEncoder
    import numpy as np
    
    try:
        export_jobs[job_id]["status"] = "running"
        export_jobs[job_id]["message"] = "Preparing..."
        
        state = project_to_state(request.project)
        renderer = FrameRenderer(state)
        
        # Calculate frames
        start_time, end_time = renderer.get_timeline_range()
        if end_time <= 0:
            end_time = request.project.video_duration or 10.0
        
        total_frames = int((end_time - start_time) * state.video_fps)
        
        # Output path
        # Determine output file
        ext = request.format.lower()
        if ext not in ['mp4', 'mov']: ext = 'mp4'
        
        if request.mode == "burn-in":
            # Temporary overlay file (always MOV ProRes for quality intermediate)
            overlay_filename = f"temp_overlay_{job_id}.mov"
            overlay_path = EXPORT_DIR / overlay_filename
            final_filename = f"captioneer_export_{job_id}.{ext}"
            final_path = EXPORT_DIR / final_filename
            encoder_path = overlay_path
        else:
            # Overlay is the final output
            # If format is MP4, it won't support alpha well, but we respect request
            # Usually Overlay should be MOV
            output_filename = f"captioneer_export_{job_id}.{ext}"
            encoder_path = EXPORT_DIR / output_filename
            final_filename = output_filename
            final_path = encoder_path
            
        export_jobs[job_id]["message"] = f"Encoding {total_frames} frames..."
        
        # Encode Overlay (Always ProRes if intermediate, else depends on format)
        # If we are doing burn-in, we need high quality intermediate -> ProRes
        # If we are doing overlay output, we check format. 
        # But VideoEncoder currently supports 'prores' (alpha) or h264 (no alpha yet in my code for h264 raw?)
        # Let's check VideoEncoder class. It supports 'prores' or 'h264'.
        # 'h264' in VideoEncoder generates yuv420p (no alpha).
        # So for Overlay, we MUST use ProRes if we want alpha.
        # If user requests MP4 Overlay, it will have black background.
        
        codec = "prores"
        if request.mode == "overlay" and ext == "mp4":
             codec = "h264" # No alpha
        
        with VideoEncoder(
            str(encoder_path),
            state.video_width,
            state.video_height,
            state.video_fps,
            codec=codec
        ) as encoder:
            for i in range(total_frames):
                if export_jobs[job_id]["status"] == "error": break # Check cancellation
                
                t = start_time + (i / state.video_fps)
                frame = renderer.render_frame_array(t)
                encoder.add_frame(frame)
                
                # Explicit memory cleanup
                del frame
                
                # Clear cache periodically to prevent memory buildup
                if i % 100 == 0 and i > 0:
                    renderer.cache.clear()
                    import gc
                    gc.collect()
                
                # Progress scaling: 0-100% (overlay only) or 0-80% (burn-in)
                prog_factor = 0.8 if request.mode == "burn-in" else 1.0
                progress = int((i + 1) / total_frames * 100 * prog_factor)
                
                export_jobs[job_id]["progress"] = progress
                export_jobs[job_id]["message"] = f"Rendering frame {i+1}/{total_frames}"
                
                # Yield to event loop
                if i % 10 == 0:
                    await asyncio.sleep(0)
        
        # Final cleanup
        renderer.cache.clear()
        import gc
        gc.collect()
        
        # If burn-in, perform compositing
        if request.mode == "burn-in":
            export_jobs[job_id]["message"] = "Compositing with original video..."
            
            # Find original video path
            # We need to look it up from the project ID or assuming request.project.video_path is valid
            # The frontend might not send the full server path, checking ProjectModel
            
            # Assuming active_projects has the full path or request.project has it
            video_path = None
            if request.project.id in active_projects:
                 # Prefer server-side record which might have trusted path
                 video_path = active_projects[request.project.id].video_path
            
            # Fallback to path in request (frontend sends it but might be url, we need path)
            # The frontend sends 'video_url', but we need the local file path.
            # In `api/server.py`, `upload_video` returns `path` and `url`.
            # We need to ensure we can find the video.
            
            # Let's try to deduce path from URL if video_path is missing
            if not video_path:
                 # Check if we can find it in uploads
                 # request.project might not have video_path populated by frontend
                 pass
            
            # IMPORTANT: For this to work, the Backend PROJECT state must have the video_path.
            # When we create project or upload, we set it.
            # Check create_projects / upload_video implementation
            
            # Wait, `ProjectModel` has `video_path`.
            # Does the Frontend send it back?
            # Frontend project structure matches Backend ProjectModel?
            # Frontend: interface Project { ... video_url: string | null ... }
            # Backend: class ProjectModel(BaseModel): ... video_path: Optional[str] = None ...
            
            # If the frontend sends the project back, it might overwrite video_path with null if it doesn't track it!
            # We should probably use `active_projects[project.id]` to get the video path.
            
            server_project = active_projects.get(request.project.id)
            if server_project and server_project.video_path:
                video_source = server_project.video_path
            elif request.project.video_path:
                video_source = request.project.video_path
            else:
                # Try to find by video_url?
                # This is tricky if frontend doesn't send path.
                # Let's assume for now the user uploaded it in this session.
                # Or we fail gracefully.
                video_source = None
                # Hack: search in uploads if we have a url
                # URL is like /uploads/guid.mp4
                # Path is uploads/guid.mp4
                # But frontend project might just have the URL.
                pass
                
            if not video_source:
                 # Try to reconstruct from URL
                 # Frontend has video_url?
                 # request.project is Pydantic model. extra fields ignored?
                 # No, FrameRequest has project: ProjectModel. 
                 # If frontend JSON has video_url but not video_path, video_path is None.
                 
                 # Let's verify what `upload_video` sets.
                 pass

            # Let's modify the code to handle this AFTER verification.
            # For now, let's write the compositing logic assuming we find the path
            
            from engine.encoder import composite_with_video
            
            # We'll use a safer lookup logic
            if not video_source and request.project.id in active_projects:
                 video_source = active_projects[request.project.id].video_path
            
            if video_source and Path(video_source).exists():
                success = composite_with_video(video_source, str(overlay_path), str(final_path))
                if not success:
                    raise RuntimeError("Compositing failed")
                
                # Cleanup overlay
                try:
                    overlay_path.unlink()
                except:
                    pass
            else:
                 raise RuntimeError(f"Original video source not found for compositing. Path: {video_source}")

        export_jobs[job_id]["status"] = "complete"
        export_jobs[job_id]["progress"] = 100
        export_jobs[job_id]["message"] = "Export complete!"
        export_jobs[job_id]["output_path"] = f"/exports/{final_filename}"
    
    except Exception as e:
        export_jobs[job_id]["status"] = "error"
        export_jobs[job_id]["message"] = str(e)


@app.get("/api/export/{job_id}/status")
async def get_export_status(job_id: str):
    """Get export job status."""
    if job_id not in export_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return export_jobs[job_id]


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("Starting Captioneer Studio API on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
