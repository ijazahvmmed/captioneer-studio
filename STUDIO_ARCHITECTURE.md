# Captioneer Studio — Technical Architecture

## Executive Summary

Captioneer Studio transforms the existing CLI-based kinetic typography engine into a professional, interactive caption editor with:
- Real-time canvas editing (Canva-like)
- Draggable caption positioning
- Live style/motion parameter tuning
- Timeline-based word editing
- Instant preview rendering
- Professional export (burn-in or alpha overlay)

---

## 1. Recommended Technology Stack

### Frontend: React + Vite (Web UI)
```
React 18          - Component framework
Vite              - Build tool with HMR
Zustand           - Lightweight state management
Framer Motion     - UI animations
Konva.js          - Canvas rendering for draggable elements
WaveSurfer.js     - Audio waveform timeline
TailwindCSS       - Styling
```

### Backend: Python + FastAPI
```
FastAPI           - Async API server
faster-whisper    - Speech transcription
Pillow + NumPy    - Frame rendering
FFmpeg            - Video encoding/decoding
WebSocket         - Real-time preview streaming
```

### Architecture Pattern
```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Video Canvas  │  Style Panel    │     Word Timeline           │
│   (Konva.js)    │  (Controls)     │     (WaveSurfer)            │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
         └─────────────────┴───────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ Zustand     │
                    │ EditorState │
                    └──────┬──────┘
                           │ WebSocket + REST
                    ┌──────▼──────┐
                    │  FastAPI    │
                    │  Backend    │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐     ┌──────▼──────┐   ┌──────▼──────┐
    │Transcribe│     │  Renderer   │   │  Exporter   │
    │ (Whisper)│     │ (Headless)  │   │  (FFmpeg)   │
    └─────────┘     └─────────────┘   └─────────────┘
```

---

## 2. Data Model

### Project State (JSON)
```json
{
  "version": "1.0",
  "video": {
    "path": "/uploads/input.mp4",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "duration": 35.5
  },
  "canvas": {
    "position": { "x": 540, "y": 1400 },
    "anchor": "center",
    "safeMargin": { "top": 100, "bottom": 200, "left": 50, "right": 50 }
  },
  "style": {
    "fontFamily": "Epilogue-Light",
    "fontSize": 72,
    "lineSpacing": 1.1,
    "letterSpacing": 0,
    "alignment": "center",
    "strokeWidth": 5,
    "textColor": "#FFFFFF",
    "strokeColor": "#000000"
  },
  "motion": {
    "maxWordsOnScreen": 3,
    "entryBlurStart": 20.0,
    "entryDuration": 0.28,
    "charStagger": 0.025,
    "entryScale": 0.96,
    "yDrift": 6.0,
    "entryOpacityStart": 0.1
  },
  "words": [
    { "id": "w1", "text": "beneath", "start": 0.10, "end": 0.45 },
    { "id": "w2", "text": "the", "start": 0.48, "end": 0.60 },
    { "id": "w3", "text": "surface", "start": 0.62, "end": 1.10 }
  ]
}
```

### TypeScript Types (Frontend)
```typescript
interface Project {
  version: string;
  video: VideoMeta;
  canvas: CanvasSettings;
  style: StyleSettings;
  motion: MotionSettings;
  words: Word[];
}

interface Word {
  id: string;
  text: string;
  start: number;
  end: number;
}

interface CanvasSettings {
  position: { x: number; y: number };
  anchor: 'center' | 'top' | 'bottom' | 'custom';
  safeMargin: { top: number; bottom: number; left: number; right: number };
}

interface StyleSettings {
  fontFamily: string;
  fontSize: number;
  lineSpacing: number;
  letterSpacing: number;
  alignment: 'left' | 'center' | 'right';
  strokeWidth: number;
  textColor: string;
  strokeColor: string;
}

interface MotionSettings {
  maxWordsOnScreen: 1 | 2 | 3;
  entryBlurStart: number;
  entryDuration: number;
  charStagger: number;
  entryScale: number;
  yDrift: number;
  entryOpacityStart: number;
}
```

---

## 3. Component Layout

### Main UI Layout
```
┌────────────────────────────────────────────────────────────────┐
│  HEADER: Project Name | Save | Export | Settings               │
├──────────────────────────────────────────┬─────────────────────┤
│                                          │                     │
│                                          │   STYLE PANEL       │
│          VIDEO CANVAS                    │   ─────────────     │
│          ─────────────                   │   Font: [Epilogue]  │
│                                          │   Size: [72]        │
│     ┌─────────────────────┐              │   Spacing: [1.1]    │
│     │                     │              │   Align: [center]   │
│     │   [Video Frame]     │              │                     │
│     │                     │              │   MOTION            │
│     │   ┌─────────────┐   │              │   ─────────────     │
│     │   │ Draggable   │   │              │   Max Words: [3]    │
│     │   │ Caption     │   │              │   Blur: [20]        │
│     │   │ Overlay     │   │              │   Duration: [0.28]  │
│     │   └─────────────┘   │              │   Stagger: [0.025]  │
│     │                     │              │                     │
│     └─────────────────────┘              │                     │
│                                          │                     │
├──────────────────────────────────────────┴─────────────────────┤
│  TIMELINE                                                       │
│  ─────────────────────────────────────────────────────────────  │
│  [▶] 00:00:05.24 / 00:00:35.50                    [🔊 Waveform] │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │████▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│ │
│  └────────────────────────────────────────────────────────────┘ │
│  WORDS: [beneath] [the] [surface] [a] [tireless] [heartbeat]... │
└────────────────────────────────────────────────────────────────┘
```

### React Component Tree
```
<App>
  <ProjectProvider>
    <Header />
    <MainLayout>
      <CanvasPanel>
        <VideoPlayer />
        <CaptionOverlay />        // Konva.js draggable layer
        <SafeMarginGuides />
      </CanvasPanel>
      <StylePanel>
        <FontControls />
        <TypographyControls />
        <MotionControls />
        <ColorControls />
      </StylePanel>
    </MainLayout>
    <Timeline>
      <PlaybackControls />
      <Waveform />
      <WordTrack />
    </Timeline>
  </ProjectProvider>
</App>
```

---

## 4. Rendering Pipeline

### Live Preview Pipeline
```
User Edit → Zustand State Update → Debounce (50ms)
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ POST /preview/frame │
                              │ { time, state }     │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ Python Renderer     │
                              │ (Low-res, fast)     │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ Return PNG frame    │
                              │ as base64           │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ Overlay on Canvas   │
                              └─────────────────────┘
```

### WebSocket Streaming (Alternative)
```python
# Server-side
@app.websocket("/ws/preview")
async def preview_stream(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        frame = render_preview_frame(data['time'], data['state'])
        await websocket.send_bytes(frame)
```

### Export Pipeline
```
User clicks "Export"
        │
        ▼
┌───────────────────────────────────────────────┐
│ POST /export                                  │
│ { project_state, mode: "overlay" | "burn-in" }│
└───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────┐
│ Full-resolution render (all frames)           │
│ Progress streamed via WebSocket               │
└───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────┐
│ FFmpeg encode to ProRes 4444 or H.264         │
└───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────┐
│ Return download URL                           │
└───────────────────────────────────────────────┘
```

---

## 5. API Endpoints

### REST Endpoints
```
POST   /api/project/create          Create new project
GET    /api/project/{id}            Load project
PUT    /api/project/{id}            Save project
DELETE /api/project/{id}            Delete project

POST   /api/transcribe              Upload video, get word timeline
POST   /api/preview/frame           Render single frame at time T
POST   /api/export                  Start export job
GET    /api/export/{job_id}/status  Check export progress
GET    /api/fonts                   List available fonts
```

### WebSocket Endpoints
```
WS     /ws/preview                  Real-time frame streaming
WS     /ws/export/{job_id}          Export progress updates
```

---

## 6. File Structure

```
captioneer/
├── studio/                          # NEW: Studio frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Canvas/
│   │   │   │   ├── VideoPlayer.tsx
│   │   │   │   ├── CaptionOverlay.tsx
│   │   │   │   └── SafeMarginGuides.tsx
│   │   │   ├── Timeline/
│   │   │   │   ├── PlaybackControls.tsx
│   │   │   │   ├── Waveform.tsx
│   │   │   │   └── WordTrack.tsx
│   │   │   ├── StylePanel/
│   │   │   │   ├── FontControls.tsx
│   │   │   │   ├── TypographyControls.tsx
│   │   │   │   └── MotionControls.tsx
│   │   │   └── Header.tsx
│   │   ├── stores/
│   │   │   ├── projectStore.ts      # Zustand store
│   │   │   └── previewStore.ts
│   │   ├── hooks/
│   │   │   ├── usePreview.ts
│   │   │   └── useWebSocket.ts
│   │   ├── types/
│   │   │   └── project.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── engine/                          # REFACTORED: Core renderer
│   ├── __init__.py
│   ├── renderer.py                  # Headless frame renderer
│   ├── motion.py                    # Animation functions
│   ├── layout.py                    # Text layout engine
│   └── encoder.py                   # Video encoding
│
├── api/                             # NEW: API server
│   ├── __init__.py
│   ├── server.py                    # FastAPI main
│   ├── routes/
│   │   ├── project.py
│   │   ├── transcribe.py
│   │   ├── preview.py
│   │   └── export.py
│   └── websocket.py
│
├── tests/                           # NEW: Automated tests
│   ├── e2e/
│   │   ├── happy_path.spec.ts
│   │   ├── stress_test.spec.ts
│   │   └── positioning.spec.ts
│   └── unit/
│       └── renderer_test.py
│
├── static/                          # Fonts
│   └── Epilogue-*.ttf
│
└── main.py                          # CLI entrypoint (preserved)
```

---

## 7. Implementation Phases

### Phase 1: Core Refactoring (Day 1)
- [ ] Extract renderer into `engine/` module
- [ ] Create headless `render_frame(time, state) → PIL.Image`
- [ ] Parametrize all constants from state JSON

### Phase 2: API Server (Day 1-2)
- [ ] FastAPI server with project CRUD
- [ ] `/transcribe` endpoint with faster-whisper
- [ ] `/preview/frame` for single frame rendering
- [ ] WebSocket `/ws/preview` for streaming

### Phase 3: Studio Frontend (Day 2-4)
- [ ] React + Vite setup with TailwindCSS
- [ ] Zustand project store
- [ ] Video player with HTML5 video
- [ ] Konva.js draggable caption overlay
- [ ] Style controls panel
- [ ] Timeline with word editing

### Phase 4: Real-time Preview (Day 4-5)
- [ ] Frame request debouncing
- [ ] Low-res preview mode (360p)
- [ ] WebSocket streaming optimization
- [ ] Cache rendered frames

### Phase 5: Export & Polish (Day 5-6)
- [ ] Full-res export pipeline
- [ ] Progress tracking
- [ ] Burn-in mode (composite with video)
- [ ] Alpha overlay mode (ProRes 4444)

### Phase 6: Testing (Day 6-7)
- [ ] Playwright E2E tests
- [ ] Happy path test
- [ ] Stress test (long video)
- [ ] Positioning regression test

---

## 8. Key Technical Decisions

### Why Web UI over Desktop (PySide6)?
1. **Cross-platform** without compilation
2. **Modern UI** with React ecosystem
3. **Easier deployment** (run locally, no install)
4. **Hot reload** for development
5. **Familiar stack** for most developers

### Why Konva.js for Canvas?
1. **Built for dragging** — handles hit detection, transforms
2. **High performance** — canvas-based, not DOM
3. **React integration** — react-konva bindings
4. **Overlays video** — transparent layer compositing

### Why Zustand over Redux?
1. **Minimal boilerplate** — no actions/reducers
2. **TypeScript-first** — excellent type inference
3. **Small bundle** — 1KB vs 7KB+
4. **Subscriptions** — components re-render only on used state

### Preview Rendering Strategy
1. **Debounce edits** — 50ms wait before rendering
2. **Low resolution** — 360p for instant feedback
3. **Single frame** — only current playhead position
4. **Cache recent** — LRU cache of last 30 frames
5. **WebSocket** — stream frames during playback

---

## 9. Performance Targets

| Metric | Target |
|--------|--------|
| Preview frame latency | < 100ms |
| Scrub response | < 50ms (cached) |
| Word edit → preview update | < 200ms |
| Style change → preview update | < 150ms |
| Export speed (1080p30) | Real-time or faster |

---

## 10. Testing Strategy

### E2E Tests (Playwright)
```typescript
// happy_path.spec.ts
test('complete workflow', async ({ page }) => {
  await page.goto('/');
  
  // Upload video
  await page.setInputFiles('[data-testid="video-upload"]', 'test.mp4');
  await expect(page.locator('[data-testid="video-player"]')).toBeVisible();
  
  // Wait for transcription
  await expect(page.locator('[data-testid="word-track"]')).toContainText('beneath');
  
  // Drag caption
  const caption = page.locator('[data-testid="caption-overlay"]');
  await caption.dragTo(page.locator('[data-testid="canvas"]'), { targetPosition: { x: 200, y: 300 } });
  
  // Change style
  await page.fill('[data-testid="font-size"]', '96');
  await expect(caption).toHaveCSS('font-size', '96px');
  
  // Export
  await page.click('[data-testid="export-button"]');
  await expect(page.locator('[data-testid="export-progress"]')).toContainText('100%');
  await expect(page.locator('[data-testid="download-link"]')).toBeVisible();
});
```

---

This architecture provides a professional-grade caption editor while preserving the deterministic, headless nature of the core Captioneer engine.
