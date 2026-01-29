# Captioneer Studio

**Professional Kinetic Typography Editor**

A Canva-like interactive caption editor built on top of the Captioneer rendering engine.

## Features

- **Video Canvas** — Drag captions anywhere on the frame
- **Real-time Preview** — See changes instantly
- **Style Controls** — Font, size, spacing, colors, motion parameters
- **Timeline Editing** — Adjust word timing, delete, edit text
- **Auto-Transcription** — Upload video, get captions automatically
- **Export** — ProRes 4444 (transparent overlay) or burn-in

## Quick Start

### Windows

```batch
start-studio.bat
```

### Manual Start

1. **Start API Server**
   ```bash
   python -m api.server
   ```

2. **Start Frontend** (in another terminal)
   ```bash
   cd studio
   npm install  # first time only
   npm run dev
   ```

3. **Open in Browser**
   - Studio: http://localhost:5174
   - API: http://localhost:8000

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Video Canvas  │  Style Panel    │     Word Timeline           │
│   (Konva.js)    │  (Controls)     │                             │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
                    ┌──────▼──────┐
                    │ Zustand     │
                    │ EditorState │
                    └──────┬──────┘
                           │ REST + WebSocket
                    ┌──────▼──────┐
                    │  FastAPI    │
                    │  Backend    │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
    ┌────▼────┐     ┌──────▼──────┐   ┌──────▼──────┐
    │Transcribe│     │  Renderer   │   │  Exporter   │
    │ (Whisper)│     │ (Headless)  │   │  (FFmpeg)   │
    └─────────┘     └─────────────┘   └─────────────┘
```

## Project Structure

```
captioneer/
├── api/                 # FastAPI backend
│   ├── server.py        # Main API server
│   └── routes/          # API route handlers
│
├── engine/              # Core rendering engine
│   ├── renderer.py      # Headless frame renderer
│   ├── motion.py        # Animation calculations
│   ├── layout.py        # Text positioning
│   └── encoder.py       # Video encoding
│
├── studio/              # React frontend
│   ├── src/
│   │   ├── components/  # UI components
│   │   ├── stores/      # Zustand state
│   │   ├── hooks/       # Custom hooks
│   │   └── types/       # TypeScript types
│   └── package.json
│
├── static/              # Fonts
├── tests/               # E2E and unit tests
└── main.py              # CLI entrypoint
```

## API Endpoints

### Project Management
- `POST /api/project/create` — Create new project
- `GET /api/project/{id}` — Load project
- `PUT /api/project/{id}` — Save project

### Video & Transcription
- `POST /api/upload` — Upload video file
- `POST /api/transcribe` — Transcribe video to words

### Preview
- `POST /api/preview/frame` — Render single frame
- `WS /ws/preview` — Real-time frame streaming

### Export
- `POST /api/export` — Start export job
- `GET /api/export/{job_id}/status` — Check progress

## Development

### Install Dependencies

```bash
# Python
pip install -r requirements.txt

# Frontend
cd studio
npm install
```

### Run Tests

```bash
# E2E tests (requires Playwright)
cd studio
npx playwright install
npx playwright test
```

## License

MIT
