# Captioneer Web Interface

A professional, high-quality Web UI for the Captioneer engine.
Features a cinematic dark mode interface, real-time preview, and dual-format export (H.264 Preview + ProRes 4444 Master).

## Prerequisites

- **Python 3.8+** (for the backend)
- **Node.js 16+** (for the frontend)
- **FFmpeg** (installed and in PATH)

## Quick Start

### 1. Start the Backend Server

Open a terminal in the root `captioneer` folder:

```bash
# Install backend dependencies
pip install -r requirements.txt

# Start the API server
python server.py
```
_The server will run on `http://localhost:8000`_

### 2. Start the Frontend Application

Open a **new terminal** in the `captioneer/web` folder:

```bash
cd web

# Install frontend dependencies (first time only)
npm install

# Start the development server
npm run dev
```

### 3. Open in Browser

Click the link shown in the frontend terminal (usually `http://localhost:5173`).

---

## Features

- **Drag & Drop Workflow**: Upload `words.json` seamlessly.
- **Visual Configuration**: Adjust Width, Height, FPS, and Font Size.
- **Dual Output**:
  - **Preview (MP4)**: H.264 video for immediate browser playback.
  - **Master (MOV)**: ProRes 4444 with Transparency for editing.
- **Cinematic UI**: Glassmorphism, smooth animations, and dark mode.

## Troubleshooting

- **Server Connection Refused**: Ensure `server.py` is running on port 8000.
- **Rendering Error**: Check the backend terminal for Python error logs.
- **Missing Font**: If using a custom font, ensure it's a valid `.ttf` or `.otf`.
