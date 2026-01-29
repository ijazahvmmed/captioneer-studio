# Captioneer Studio

A professional web-based tool for creating cinematic animated captions.

## Overview

Captioneer Studio provides a seamless workflow for creating high-end kinetic typography:
1. **Upload Video** -> **Transcribe** (Faster-Whisper)
2. **Edit** -> **Customize** (Real-time Preview)
3. **Export** -> **ProRes 4444** (Transparent Overlay or Burn-in)

## Features

- **Real-time Preview**: Instant feedback on animations and styling.
- **Cinematic Motion**: "Fog-to-focus" character reveals, similar to high-end After Effects templates.
- **Export Formats**: Transparent .MOV (ProRes 4444) for overlay, or .MP4 burn-in.
- **Font Support**: Google Fonts integration with correct weight handling.
- **Privacy First**: All processing happens locally on your machine.

## Architecture

- **Frontend**: React, Vite, TailwindCSS
- **Backend**: FastAPI, Python, PIL (Pillow), FFmpeg
- **Engine**: Custom Python-based deterministic rendering engine (headless).

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- FFmpeg (must be in system PATH)

### Installation

1. **Install Backend Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Frontend Dependencies**
   ```bash
   cd studio
   npm install
   ```

3. **Download Fonts**
   ```bash
   python download_all_fonts.py
   ```

### Running

1. **Start Backend**
   ```bash
   python -m api.server
   ```

2. **Start Frontend**
   ```bash
   cd studio
   npm run dev
   ```

3. Open http://localhost:5173

## Project Structure

- `api/`: FastAPI server endpoints
- `engine/`: Core rendering logic (layout, motion, rendering)
- `studio/`: React frontend application
- `static/`: Project assets and fonts

## License

MIT
