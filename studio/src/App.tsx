// Captioneer Studio - Production-Ready Implementation
// Complete architectural overhaul for stability and reliability

import { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import './index.css';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ============================================================================
// AVAILABLE FONTS
// ============================================================================
const FONTS = [
  { name: 'Inter', value: 'Inter', style: "'Inter', sans-serif" },
  { name: 'Roboto', value: 'Roboto', style: "'Roboto', sans-serif" },
  { name: 'Montserrat', value: 'Montserrat', style: "'Montserrat', sans-serif" },
  { name: 'Poppins', value: 'Poppins', style: "'Poppins', sans-serif" },
  { name: 'Oswald', value: 'Oswald', style: "'Oswald', sans-serif" },
  { name: 'Bebas Neue', value: 'Bebas Neue', style: "'Bebas Neue', cursive" },
  { name: 'Anton', value: 'Anton', style: "'Anton', sans-serif" },
  { name: 'Bangers', value: 'Bangers', style: "'Bangers', cursive" },
  { name: 'Permanent Marker', value: 'Permanent Marker', style: "'Permanent Marker', cursive" },
  { name: 'Rubik', value: 'Rubik', style: "'Rubik', sans-serif" },
  { name: 'Space Grotesk', value: 'Space Grotesk', style: "'Space Grotesk', sans-serif" },
  { name: 'Epilogue', value: 'Epilogue', style: "'Epilogue', sans-serif" },
];

// All possible font weights
const ALL_FONT_WEIGHTS = [
  { name: 'Light', value: 300 },
  { name: 'Regular', value: 400 },
  { name: 'Medium', value: 500 },
  { name: 'Semi Bold', value: 600 },
  { name: 'Bold', value: 700 },
  { name: 'Extra Bold', value: 800 },
  { name: 'Black', value: 900 },
];

// Available weights for each font family (must match Google Fonts AND backend static files)
const FONT_AVAILABLE_WEIGHTS: Record<string, number[]> = {
  'Inter': [300, 400, 500, 600, 700, 800, 900],
  'Roboto': [300, 400, 500, 700, 900],
  'Montserrat': [300, 400, 500, 600, 700, 800, 900],
  'Poppins': [300, 400, 500, 600, 700, 800, 900],
  'Oswald': [300, 400, 500, 600, 700],  // No 800, 900
  'Bebas Neue': [400],  // Only Regular
  'Anton': [400],  // Only Regular
  'Bangers': [400],  // Only Regular
  'Permanent Marker': [400],  // Only Regular
  'Rubik': [300, 400, 500, 600, 700, 800, 900],
  'Space Grotesk': [300, 400, 500, 600, 700],  // Only 300-700, NO 800 or 900!
  'Epilogue': [300, 400, 500, 600, 700, 800, 900],
};

// Helper to get available weights for a font
const getAvailableWeights = (fontFamily: string) => {
  const availableValues = FONT_AVAILABLE_WEIGHTS[fontFamily] || [400, 700];
  return ALL_FONT_WEIGHTS.filter(w => availableValues.includes(w.value));
};

const TEXT_TRANSFORMS = [
  { name: 'Normal', value: 'none' },
  { name: 'UPPERCASE', value: 'uppercase' },
  { name: 'lowercase', value: 'lowercase' },
  { name: 'Capitalize', value: 'capitalize' },
];

// ============================================================================
// ANIMATION CONSTANTS (matching backend exactly)
// ============================================================================
const CHAR_STAGGER = 0.025;
const ENTRY_DURATION = 0.28;
const MAX_WORDS_ON_SCREEN = 3;

const ENTRY_BLUR_START = 20.0;
const ENTRY_OPACITY_START = 0.1;
const ENTRY_SCALE_START = 0.96;
const ENTRY_Y_OFFSET_START = 6.0;

const ENTRY_BLUR_END = 0.0;
const ENTRY_OPACITY_END = 1.0;
const ENTRY_SCALE_END = 1.0;
const ENTRY_Y_OFFSET_END = 0.0;

// Easing function
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

// ============================================================================
// TYPES
// ============================================================================
interface Word {
  id: string;
  text: string;
  start: number;
  end: number;
  index: number;
}

interface DisplayGroup {
  wordIndices: number[];
  startTime: number;
  endTime: number;
}

interface Character {
  char: string;
  wordIndex: number;
  charIndexInWord: number;
  globalCharIndex: number;
  entryStart: number;
  focusTime: number;
}

interface CharProperties {
  opacity: number;
  blur: number;
  scale: number;
  yOffset: number;
  visible: boolean;
}

interface Project {
  id: string;
  name: string;
  video_url: string | null;
  video_path?: string;
  video_width: number;
  video_height: number;
  video_duration: number;
  canvas: { position_x: number; position_y: number; anchor: string };
  style: { font_family: string; font_size: number; font_weight: number; text_transform: string; alignment: string; stroke_width: number; text_color: string; stroke_color: string; letter_spacing: number };
  motion: { max_words_on_screen: number; entry_blur_start: number; entry_duration: number; char_stagger: number; entry_scale: number; y_drift: number; entry_opacity_start: number };
  words: Word[];
}

// ============================================================================
// ANIMATION LOGIC
// ============================================================================
function charStateEntryOnly(
  currentTime: number,
  charEntryStart: number,
  charFocusTime: number,
  motion: Project['motion']
): CharProperties {
  if (currentTime < charEntryStart) {
    return {
      opacity: 0,
      blur: motion.entry_blur_start,
      scale: motion.entry_scale,
      yOffset: motion.y_drift,
      visible: false
    };
  }

  if (charEntryStart <= currentTime && currentTime < charFocusTime) {
    const progress = Math.min(1.0, Math.max(0.0, (currentTime - charEntryStart) / motion.entry_duration));
    const e = easeOutCubic(progress);

    const opacity = motion.entry_opacity_start + (ENTRY_OPACITY_END - motion.entry_opacity_start) * e;
    const blur = motion.entry_blur_start + (ENTRY_BLUR_END - motion.entry_blur_start) * e;
    const scale = motion.entry_scale + (ENTRY_SCALE_END - motion.entry_scale) * e;
    const yOffset = motion.y_drift + (ENTRY_Y_OFFSET_END - motion.y_drift) * e;

    return { opacity, blur, scale, yOffset, visible: true };
  }

  return {
    opacity: 1.0,
    blur: 0.0,
    scale: 1.0,
    yOffset: 0.0,
    visible: true
  };
}

function computeDisplayGroups(words: Word[], maxWords: number): DisplayGroup[] {
  if (!words.length) return [];

  const groups: DisplayGroup[] = [];
  let currentWordIndices: number[] = [];
  let currentGroupStart: number | null = null;
  const entryDuration = ENTRY_DURATION;

  for (let i = 0; i < words.length; i++) {
    const word = words[i];
    const wordEntryStart = word.start - entryDuration;

    if (currentWordIndices.length >= maxWords) {
      if (currentWordIndices.length > 0) {
        groups.push({
          wordIndices: [...currentWordIndices],
          startTime: currentGroupStart!,
          endTime: wordEntryStart
        });
      }
      currentWordIndices = [i];
      currentGroupStart = wordEntryStart;
    } else {
      if (currentWordIndices.length === 0) {
        currentGroupStart = wordEntryStart;
      }
      currentWordIndices.push(i);
    }
  }

  if (currentWordIndices.length > 0) {
    const lastWord = words[currentWordIndices[currentWordIndices.length - 1]];
    groups.push({
      wordIndices: currentWordIndices,
      startTime: currentGroupStart!,
      endTime: lastWord.end + 1.0
    });
  }

  return groups;
}

function decomposeGroupToCharacters(words: Word[], group: DisplayGroup, charStagger: number, entryDuration: number): Character[] {
  const characters: Character[] = [];
  let globalCharIdx = 0;

  for (const wordIdx of group.wordIndices) {
    const word = words[wordIdx];

    for (let charIdx = 0; charIdx < word.text.length; charIdx++) {
      const staggerOffset = charIdx * charStagger;
      const entryStart = word.start - entryDuration + staggerOffset;
      const focusTime = word.start + staggerOffset;

      characters.push({
        char: word.text[charIdx],
        wordIndex: wordIdx,
        charIndexInWord: charIdx,
        globalCharIndex: globalCharIdx,
        entryStart,
        focusTime
      });
      globalCharIdx++;
    }

    if (wordIdx !== group.wordIndices[group.wordIndices.length - 1]) {
      const lastCharIdx = word.text.length - 1;
      const staggerOffset = lastCharIdx * charStagger;
      characters.push({
        char: ' ',
        wordIndex: wordIdx,
        charIndexInWord: word.text.length,
        globalCharIndex: globalCharIdx,
        entryStart: word.start - entryDuration + staggerOffset,
        focusTime: word.start + staggerOffset
      });
      globalCharIdx++;
    }
  }

  return characters;
}

// ============================================================================
// ZUSTAND STORE WITH PERSISTENCE
// ============================================================================
const DEFAULT_PROJECT: Project = {
  id: crypto.randomUUID(),
  name: 'Untitled',
  video_url: null,
  video_width: 1080,
  video_height: 1920,
  video_duration: 0,
  canvas: { position_x: 50, position_y: 75, anchor: 'bottom' },
  style: { font_family: 'Inter', font_size: 72, font_weight: 700, text_transform: 'uppercase', alignment: 'center', stroke_width: 5, text_color: '#FFFFFF', stroke_color: '#000000', letter_spacing: 0 },
  motion: {
    max_words_on_screen: MAX_WORDS_ON_SCREEN,
    entry_blur_start: ENTRY_BLUR_START,
    entry_duration: ENTRY_DURATION,
    char_stagger: CHAR_STAGGER,
    entry_scale: ENTRY_SCALE_START,
    y_drift: ENTRY_Y_OFFSET_START,
    entry_opacity_start: ENTRY_OPACITY_START
  },
  words: []
};

interface StoreState {
  project: Project;
  currentTime: number;
  isPlaying: boolean;
  setProject: (p: Partial<Project>) => void;
  setCurrentTime: (t: number) => void;
  setIsPlaying: (p: boolean) => void;
  updateStyle: (s: Partial<Project['style']>) => void;
  updateMotion: (m: Partial<Project['motion']>) => void;
  updateCanvas: (c: Partial<Project['canvas']>) => void;
  setWords: (w: Word[]) => void;
  updateWord: (id: string, updates: Partial<Word>) => void;
  deleteWord: (id: string) => void;
  resetProject: () => void;
}

const useStore = create<StoreState>()(
  persist(
    (set) => ({
      project: DEFAULT_PROJECT,
      currentTime: 0,
      isPlaying: false,
      setProject: (p) => set((state) => ({ project: { ...state.project, ...p } })),
      setCurrentTime: (currentTime) => set({ currentTime }),
      setIsPlaying: (isPlaying) => set({ isPlaying }),
      updateStyle: (s) => set((state) => ({ project: { ...state.project, style: { ...state.project.style, ...s } } })),
      updateMotion: (m) => set((state) => ({ project: { ...state.project, motion: { ...state.project.motion, ...m } } })),
      updateCanvas: (c) => set((state) => ({ project: { ...state.project, canvas: { ...state.project.canvas, ...c } } })),
      setWords: (words) => set((state) => ({ project: { ...state.project, words } })),
      updateWord: (id, updates) => set((state) => ({ project: { ...state.project, words: state.project.words.map(w => w.id === id ? { ...w, ...updates } : w) } })),
      deleteWord: (id) => set((state) => ({ project: { ...state.project, words: state.project.words.filter(w => w.id !== id) } })),
      resetProject: () => set({ project: { ...DEFAULT_PROJECT, id: crypto.randomUUID() }, currentTime: 0, isPlaying: false })
    }),
    {
      name: 'captioneer-project',
      partialize: (state) => ({
        project: state.project,
        // Don't persist currentTime or isPlaying
      }),
    }
  )
);

// ============================================================================
// ANIMATED CAPTION COMPONENT
// ============================================================================
function AnimatedCaption({
  words,
  currentTime,
  style,
  motion
}: {
  words: Word[];
  currentTime: number;
  style: Project['style'];
  motion: Project['motion'];
}) {
  const displayGroups = useMemo(
    () => computeDisplayGroups(words, motion.max_words_on_screen),
    [words, motion.max_words_on_screen]
  );

  const activeGroup = useMemo(() => {
    return displayGroups.find(g => currentTime >= g.startTime && currentTime < g.endTime);
  }, [displayGroups, currentTime]);

  if (!activeGroup) return null;

  const characters = decomposeGroupToCharacters(
    words,
    activeGroup,
    motion.char_stagger,
    motion.entry_duration
  );

  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      justifyContent: style.alignment === 'center' ? 'center' : style.alignment === 'right' ? 'flex-end' : 'flex-start',
      fontWeight: style.font_weight,
      textTransform: style.text_transform as 'none' | 'uppercase' | 'lowercase' | 'capitalize',
      letterSpacing: `${style.letter_spacing * 0.02}em`
    }}>
      {characters.map((char, i) => {
        const props = charStateEntryOnly(currentTime, char.entryStart, char.focusTime, motion);

        if (!props.visible && props.opacity === 0) return null;

        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              opacity: props.opacity,
              filter: props.blur > 0.5 ? `blur(${props.blur * 0.5}px)` : 'none',
              transform: `scale(${props.scale}) translateY(${props.yOffset * 0.5}px)`,
              color: style.text_color,
              WebkitTextStroke: `${style.stroke_width * 0.05}px ${style.stroke_color}`,
              textShadow: `0 2px 8px rgba(0,0,0,0.5)`,
              whiteSpace: char.char === ' ' ? 'pre' : 'normal',
              transition: 'none'
            }}
          >
            {char.char}
          </span>
        );
      })}
    </div>
  );
}

// ============================================================================
// TOAST COMPONENT
// ============================================================================
function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error' | 'info'; onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div style={{
      position: 'fixed',
      bottom: '2rem',
      left: '50%',
      transform: 'translateX(-50%)',
      padding: '0.875rem 1.5rem',
      borderRadius: '12px',
      background: type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#6366f1',
      color: 'white',
      fontWeight: 500,
      fontSize: '0.9rem',
      boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      animation: 'fadeInUp 0.3s ease'
    }}>
      {type === 'success' && '✓'}
      {type === 'error' && '✕'}
      {type === 'info' && 'ℹ'}
      {message}
    </div>
  );
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

// ============================================================================
// MAIN APP
// ============================================================================
function App() {
  const { project, currentTime, isPlaying, setProject, setCurrentTime, setIsPlaying, updateStyle, updateMotion, updateCanvas, setWords, updateWord, deleteWord, resetProject } = useStore();
  const [uploading, setUploading] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [exportMode, setExportMode] = useState<'burn-in' | 'overlay'>('burn-in');
  const [exportFormat, setExportFormat] = useState<'mp4' | 'mov'>('mp4');
  const [selectedWord, setSelectedWord] = useState<string | null>(null);
  const [editingWord, setEditingWord] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [activeTab, setActiveTab] = useState<'style' | 'motion' | 'position'>('style');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(() => localStorage.getItem('captioneer_api_url') || '');
  const [showSettings, setShowSettings] = useState(false);

  // Persist API URL
  useEffect(() => {
    localStorage.setItem('captioneer_api_url', apiBaseUrl);
  }, [apiBaseUrl]);

  // Helper for API calls
  const apiFetch = useCallback(async (endpoint: string, options?: RequestInit) => {
    const url = apiBaseUrl ? `${apiBaseUrl.replace(/\/$/, '')}${endpoint}` : endpoint;
    return fetch(url, options);
  }, [apiBaseUrl]);

  const videoRef = useRef<HTMLVideoElement>(null);
  const animationRef = useRef<number>(0);

  const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
  }, []);

  // Has video check
  const hasVideo = !!project.video_url;

  // Sync video time with state
  useEffect(() => {
    if (videoRef.current && !isPlaying) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime, isPlaying]);

  // Animation loop
  useEffect(() => {
    const animate = () => {
      if (videoRef.current && isPlaying) {
        setCurrentTime(videoRef.current.currentTime);
      }
      animationRef.current = requestAnimationFrame(animate);
    };

    if (isPlaying) {
      animationRef.current = requestAnimationFrame(animate);
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, setCurrentTime]);

  // Upload video
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await apiFetch('/api/upload', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Upload failed');

      const data = await res.json();

      setProject({
        video_url: data.url,
        video_path: data.path,
        video_width: data.info.width,
        video_height: data.info.height,
        video_duration: data.info.duration
      });

      setUploading(false);
      setTranscribing(true);
      showToast('Video uploaded! Transcribing...', 'info');

      const transcribeForm = new FormData();
      transcribeForm.append('video_path', data.path);
      transcribeForm.append('model', 'small');

      const transcribeRes = await apiFetch('/api/transcribe', { method: 'POST', body: transcribeForm });

      if (transcribeRes.ok) {
        const transcribeData = await transcribeRes.json();
        const indexedWords = transcribeData.words.map((w: Word, i: number) => ({ ...w, index: i }));
        setWords(indexedWords);
        showToast(`Transcribed ${indexedWords.length} words!`, 'success');
      }

      setTranscribing(false);

    } catch (error) {
      console.error('Upload error:', error);
      showToast('Upload failed: ' + (error as Error).message, 'error');
      setUploading(false);
      setTranscribing(false);
    }
  };

  // Export
  const handleExport = async () => {
    if (project.words.length === 0) {
      showToast('No words to export. Upload a video first.', 'error');
      return;
    }

    setExporting(true);
    setExportProgress(0);

    try {
      // DEBUG: Log what's being sent
      console.log('[EXPORT] Sending style:', project.style);
      console.log('[EXPORT] Font weight:', project.style.font_weight);

      const res = await apiFetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project: {
            id: project.id,
            name: project.name,
            video_width: project.video_width,
            video_height: project.video_height,
            video_fps: 30,
            video_duration: project.video_duration,
            canvas: project.canvas,
            style: project.style,
            motion: project.motion,
            words: project.words,
            video_path: project.video_path
          },
          mode: exportMode,
          format: exportFormat
        })
      });

      if (!res.ok) throw new Error('Export failed');

      const { job_id } = await res.json();
      let downloaded = false;

      const poll = setInterval(async () => {
        if (downloaded) return;

        try {
          const statusRes = await apiFetch(`/api/export/${job_id}/status`);
          const status = await statusRes.json();
          setExportProgress(status.progress);

          if (status.status === 'complete' && !downloaded) {
            downloaded = true;
            clearInterval(poll);
            setExporting(false);

            const link = document.createElement('a');
            link.href = status.output_path;
            link.download = `captioneer_export_${Date.now()}.${exportFormat}`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            showToast('Export complete! Your file is downloading.', 'success');
          } else if (status.status === 'error' && !downloaded) {
            downloaded = true;
            clearInterval(poll);
            setExporting(false);
            showToast('Export failed: ' + status.message, 'error');
          }
        } catch (e) {
          // Ignore polling errors
        }
      }, 500);

    } catch (error) {
      console.error('Export error:', error);
      setExporting(false);
      showToast('Export failed', 'error');
    }
  };

  const handleSeek = (time: number) => {
    setCurrentTime(time);
    if (videoRef.current) videoRef.current.currentTime = time;
  };

  const togglePlay = () => {
    if (!videoRef.current) return;

    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const setPositionPreset = (preset: 'top' | 'center' | 'bottom') => {
    const y = preset === 'top' ? 15 : preset === 'center' ? 50 : 80;
    updateCanvas({ position_x: 50, position_y: y, anchor: preset });
  };

  // Get font style for preview
  const previewFontStyle = FONTS.find(f => f.value === project.style.font_family)?.style || "'Inter', sans-serif";

  return (
    <div className="studio-container">

      {/* Header */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1.5rem', background: 'var(--studio-panel)', borderBottom: '1px solid var(--studio-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--studio-text)' }}>Captioneer Studio</span>
          <span style={{ color: 'var(--studio-border)' }}>|</span>
          <input value={project.name} onChange={(e) => setProject({ name: e.target.value })} style={{ background: 'transparent', border: 'none', color: 'var(--studio-text)', fontSize: '0.95rem', width: '200px', fontWeight: 500 }} />
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {uploading && <span style={{ color: '#6366f1', fontSize: '0.875rem' }}>⏳ Uploading...</span>}
          {transcribing && <span style={{ color: '#22c55e', fontSize: '0.875rem' }}>🎤 Transcribing...</span>}
          {exporting && <span style={{ color: '#f59e0b', fontSize: '0.875rem' }}>📤 Exporting {exportProgress}%</span>}

          <label className="btn btn-secondary" style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            📁 Upload
            <input type="file" accept="video/*,audio/*" onChange={handleUpload} style={{ display: 'none' }} />
          </label>

          {/* Export Mode Select */}
          <select
            value={exportMode}
            onChange={(e) => setExportMode(e.target.value as 'burn-in' | 'overlay')}
            style={{ padding: '0.5rem 0.75rem', background: 'var(--studio-input-bg)', border: '1px solid var(--studio-border)', borderRadius: '8px', color: 'var(--studio-text)', fontSize: '0.875rem' }}
          >
            <option value="burn-in">Burn-in Video</option>
            <option value="overlay">Transparent Overlay</option>
          </select>

          {/* Export Format Select */}
          <select
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as 'mp4' | 'mov')}
            style={{ padding: '0.5rem 0.75rem', background: 'var(--studio-input-bg)', border: '1px solid var(--studio-border)', borderRadius: '8px', color: 'var(--studio-text)', fontSize: '0.875rem' }}
          >
            <option value="mp4">MP4</option>
            <option value="mov">MOV</option>
          </select>

          <button
            onClick={handleExport}
            disabled={exporting || project.words.length === 0}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', opacity: (exporting || project.words.length === 0) ? 0.5 : 1 }}
          >
            📤 {exporting ? `${exportProgress}%` : 'Export'}
          </button>

          {hasVideo && (
            <button
              onClick={resetProject}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
              title="Start new project"
            >
              🔄 New
            </button>
          )}


          <button
            onClick={() => setShowSettings(!showSettings)}
            className="btn btn-secondary"
            title="Settings"
          >
            ⚙️
          </button>
        </div>
      </header>

      {/* API Settings Modal */}
      {
        showSettings && (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.7)', zIndex: 1000,
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <div style={{
              background: 'var(--studio-panel)', padding: '2rem', borderRadius: '12px',
              width: '400px', border: '1px solid var(--studio-border)'
            }}>
              <h3 style={{ marginTop: 0, color: 'var(--studio-text)' }}>⚙️ Settings</h3>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Backend API URL</label>
                <input
                  type="text"
                  value={apiBaseUrl}
                  onChange={(e) => setApiBaseUrl(e.target.value)}
                  placeholder="https://your-ngrok-url.ngrok-free.app"
                  style={{
                    width: '100%', padding: '0.75rem', borderRadius: '8px',
                    border: '1px solid var(--studio-border)', background: 'var(--studio-input-bg)',
                    color: 'var(--studio-text)'
                  }}
                />
                <p style={{ fontSize: '0.8rem', color: 'var(--studio-text-muted)', marginTop: '0.5rem' }}>
                  If you are running the backend locally, leave this empty.
                  If you are sharing with friends via Ngrok, paste the Ngrok URL here.
                </p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                <button onClick={() => setShowSettings(false)} className="btn btn-primary">Done</button>
              </div>
            </div>
          </div>
        )
      }

      {/* Main */}
      <div className="main-layout">

        {/* Canvas */}
        <div className="ui-grid-bg canvas-area">
          <div style={{ position: 'relative', borderRadius: '16px', overflow: 'hidden', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05)', background: '#000' }}>
            {hasVideo ? (
              <>
                <video
                  ref={videoRef}
                  src={project.video_url!}
                  onEnded={() => setIsPlaying(false)}
                  onLoadedMetadata={(e) => {
                    const video = e.currentTarget;
                    if (project.video_duration === 0) {
                      setProject({ video_duration: video.duration });
                    }
                  }}
                  style={{ maxWidth: '420px', maxHeight: '65vh', display: 'block' }}
                />

                {/* Caption Overlay */}
                <div style={{
                  position: 'absolute',
                  left: `${project.canvas.position_x}%`,
                  top: `${project.canvas.position_y}%`,
                  transform: 'translate(-50%, -50%)',
                  width: '90%',
                  textAlign: project.style.alignment as 'left' | 'center' | 'right',
                  fontSize: `${project.style.font_size * 0.45}px`,
                  fontFamily: previewFontStyle,
                  pointerEvents: 'none'
                }}>
                  <AnimatedCaption
                    words={project.words}
                    currentTime={currentTime}
                    style={project.style}
                    motion={project.motion}
                  />
                </div>
              </>
            ) : (
              <div style={{ width: '320px', height: '520px', background: 'linear-gradient(180deg, #1e1e2e 0%, #0a0a0f 100%)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#6b7280', gap: '1.5rem' }}>
                <div style={{ fontSize: '4rem', opacity: 0.5 }}>🎬</div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Upload a video</div>
                  <div style={{ fontSize: '0.85rem', opacity: 0.7 }}>to see the magic happen</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Control Panel */}
        <div className="controls-area">

          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--studio-border)' }}>
            {(['style', 'motion', 'position'] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                style={{ flex: 1, padding: '0.85rem', background: 'transparent', border: 'none', borderBottom: activeTab === tab ? '2px solid var(--studio-accent)' : '2px solid transparent', color: activeTab === tab ? 'var(--studio-text)' : 'var(--studio-text-muted)', cursor: 'pointer', textTransform: 'capitalize', fontSize: '0.85rem', fontWeight: activeTab === tab ? 600 : 400, transition: 'all 0.15s' }}>
                {tab}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, padding: '1.25rem', overflowY: 'auto' }}>

            {activeTab === 'style' && (
              <>
                <Section title="Font">
                  <div style={{ marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--studio-text)', marginBottom: '0.5rem', fontWeight: 500 }}>Font Family</div>
                    <select
                      value={project.style.font_family}
                      onChange={(e) => {
                        const newFont = e.target.value;
                        const availableWeights = FONT_AVAILABLE_WEIGHTS[newFont] || [400, 700];
                        const currentWeight = project.style.font_weight;

                        // If current weight isn't available for new font, pick closest
                        if (!availableWeights.includes(currentWeight)) {
                          const closest = availableWeights.reduce((prev, curr) =>
                            Math.abs(curr - currentWeight) < Math.abs(prev - currentWeight) ? curr : prev
                          );
                          updateStyle({ font_family: newFont, font_weight: closest });
                        } else {
                          updateStyle({ font_family: newFont });
                        }
                      }}
                      style={{
                        width: '100%',
                        padding: '0.6rem 0.8rem',
                        background: 'var(--studio-input-bg)',
                        border: '1px solid var(--studio-border)',
                        borderRadius: '8px',
                        color: 'var(--studio-text)',
                        fontSize: '0.85rem',
                        cursor: 'pointer'
                      }}
                    >
                      {FONTS.map(font => (
                        <option key={font.value} value={font.value}>
                          {font.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div style={{ marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--studio-text)', marginBottom: '0.5rem', fontWeight: 500 }}>Font Weight</div>
                    <select
                      value={project.style.font_weight}
                      onChange={(e) => updateStyle({ font_weight: Number(e.target.value) })}
                      style={{
                        width: '100%',
                        padding: '0.6rem 0.8rem',
                        background: 'var(--studio-input-bg)',
                        border: '1px solid var(--studio-border)',
                        borderRadius: '8px',
                        color: 'var(--studio-text)',
                        fontSize: '0.85rem',
                        cursor: 'pointer'
                      }}
                    >
                      {getAvailableWeights(project.style.font_family).map((fw: { name: string; value: number }) => (
                        <option key={fw.value} value={fw.value}>
                          {fw.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div style={{ marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--studio-text)', marginBottom: '0.5rem', fontWeight: 500 }}>Capitalization</div>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      {TEXT_TRANSFORMS.map(tt => (
                        <button
                          key={tt.value}
                          onClick={() => updateStyle({ text_transform: tt.value })}
                          style={{
                            flex: 1,
                            padding: '0.5rem',
                            background: project.style.text_transform === tt.value ? 'var(--studio-accent)' : 'var(--studio-input-bg)',
                            border: '1px solid var(--studio-border)',
                            borderRadius: '6px',
                            color: project.style.text_transform === tt.value ? 'white' : 'var(--studio-text)',
                            fontSize: '0.75rem',
                            cursor: 'pointer'
                          }}
                        >
                          {tt.name}
                        </button>
                      ))}
                    </div>
                  </div>
                </Section>

                <Section title="Colors">
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.85rem', color: 'var(--studio-text)', marginBottom: '0.5rem', fontWeight: 500 }}>Text</div>
                      <input type="color" value={project.style.text_color} onChange={(e) => updateStyle({ text_color: e.target.value })} style={{ width: '100%', height: '40px', borderRadius: '8px', border: '1px solid var(--studio-border)', cursor: 'pointer' }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.85rem', color: 'var(--studio-text)', marginBottom: '0.5rem', fontWeight: 500 }}>Stroke</div>
                      <input type="color" value={project.style.stroke_color} onChange={(e) => updateStyle({ stroke_color: e.target.value })} style={{ width: '100%', height: '40px', borderRadius: '8px', border: '1px solid var(--studio-border)', cursor: 'pointer' }} />
                    </div>
                  </div>
                </Section>

                <Section title="Size & Stroke">
                  <Slider label="Font Size" value={project.style.font_size} min={24} max={200} onChange={(v) => updateStyle({ font_size: v })} />
                  <Slider label="Stroke Width" value={project.style.stroke_width} min={0} max={20} onChange={(v) => updateStyle({ stroke_width: v })} />
                  <Slider label="Letter Spacing" value={project.style.letter_spacing} min={-10} max={30} onChange={(v) => updateStyle({ letter_spacing: v })} />
                </Section>
              </>
            )}

            {activeTab === 'motion' && (
              <>
                <Section title="Word Display">
                  <Slider label="Max Words on Screen" value={project.motion.max_words_on_screen} min={1} max={10} step={1} onChange={(v) => updateMotion({ max_words_on_screen: v })} />
                </Section>
                <Section title="Entry Animation">
                  <Slider label="Blur Amount" value={project.motion.entry_blur_start} min={0} max={40} onChange={(v) => updateMotion({ entry_blur_start: v })} />
                  <Slider label="Entry Duration" value={project.motion.entry_duration} min={0.1} max={1} step={0.01} onChange={(v) => updateMotion({ entry_duration: v })} />
                  <Slider label="Character Stagger" value={project.motion.char_stagger} min={0} max={0.1} step={0.005} onChange={(v) => updateMotion({ char_stagger: v })} />
                  <Slider label="Scale" value={project.motion.entry_scale} min={0.5} max={1.5} step={0.01} onChange={(v) => updateMotion({ entry_scale: v })} />
                  <Slider label="Y Drift" value={project.motion.y_drift} min={0} max={30} onChange={(v) => updateMotion({ y_drift: v })} />
                </Section>
              </>
            )}

            {activeTab === 'position' && (
              <>
                <Section title="Quick Presets">
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {(['top', 'center', 'bottom'] as const).map(preset => (
                      <button
                        key={preset}
                        onClick={() => setPositionPreset(preset)}
                        style={{
                          flex: 1,
                          padding: '0.6rem',
                          background: project.canvas.anchor === preset ? 'var(--studio-accent)' : 'var(--studio-input-bg)',
                          border: '1px solid var(--studio-border)',
                          borderRadius: '8px',
                          color: project.canvas.anchor === preset ? 'white' : 'var(--studio-text)',
                          fontSize: '0.85rem',
                          cursor: 'pointer',
                          textTransform: 'capitalize'
                        }}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                </Section>
                <Section title="Position">
                  <Slider label="Horizontal (X)" value={project.canvas.position_x} min={0} max={100} onChange={(v) => updateCanvas({ position_x: v })} suffix="%" />
                  <Slider label="Vertical (Y)" value={project.canvas.position_y} min={0} max={100} onChange={(v) => updateCanvas({ position_y: v })} suffix="%" />
                </Section>
                <Section title="Alignment">
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {(['left', 'center', 'right'] as const).map(align => (
                      <button
                        key={align}
                        onClick={() => updateStyle({ alignment: align })}
                        style={{
                          flex: 1,
                          padding: '0.6rem',
                          background: project.style.alignment === align ? 'var(--studio-accent)' : 'var(--studio-input-bg)',
                          border: '1px solid var(--studio-border)',
                          borderRadius: '8px',
                          color: project.style.alignment === align ? 'white' : 'var(--studio-text)',
                          fontSize: '0.85rem',
                          cursor: 'pointer',
                          textTransform: 'capitalize'
                        }}
                      >
                        {align}
                      </button>
                    ))}
                  </div>
                </Section>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div style={{ background: 'var(--studio-panel)', borderTop: '1px solid var(--studio-border)', padding: '1rem 1.5rem', boxShadow: '0 -4px 6px -1px rgba(0,0,0,0.02)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.75rem' }}>
          <button
            onClick={() => handleSeek(Math.max(0, currentTime - 5))}
            disabled={!hasVideo}
            style={{ padding: '0.5rem 0.75rem', background: 'var(--studio-bg)', border: '1px solid var(--studio-border)', borderRadius: '8px', color: 'var(--studio-text)', cursor: hasVideo ? 'pointer' : 'not-allowed', fontSize: '1rem', opacity: hasVideo ? 1 : 0.5 }}
          >
            ⏮
          </button>
          <button
            onClick={togglePlay}
            disabled={!hasVideo}
            className="btn btn-primary"
            style={{ minWidth: '60px', borderRadius: '10px', fontSize: '1.1rem', opacity: hasVideo ? 1 : 0.5, cursor: hasVideo ? 'pointer' : 'not-allowed' }}
          >
            {isPlaying ? '⏸' : '▶'}
          </button>
          <button
            onClick={() => handleSeek(Math.min(project.video_duration || 30, currentTime + 5))}
            disabled={!hasVideo}
            style={{ padding: '0.5rem 0.75rem', background: 'var(--studio-bg)', border: '1px solid var(--studio-border)', borderRadius: '8px', color: 'var(--studio-text)', cursor: hasVideo ? 'pointer' : 'not-allowed', fontSize: '1rem', opacity: hasVideo ? 1 : 0.5 }}
          >
            ⏭
          </button>

          <span style={{ fontFamily: 'monospace', color: 'var(--studio-text-muted)', minWidth: '110px', fontSize: '0.9rem' }}>
            {formatTime(currentTime)} / {formatTime(project.video_duration || 0)}
          </span>

          <input
            type="range"
            min={0}
            max={project.video_duration || 30}
            step={0.01}
            value={currentTime}
            onChange={(e) => handleSeek(Number(e.target.value))}
            disabled={!hasVideo}
            style={{ flex: 1, accentColor: 'var(--studio-accent)', opacity: hasVideo ? 1 : 0.5 }}
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', maxHeight: '160px', overflowY: 'auto', paddingRight: '0.5rem' }}>
          {project.words.length === 0 ? (
            <span style={{ color: 'var(--studio-text-muted)', fontSize: '0.875rem' }}>No words yet. Upload a video to auto-generate captions.</span>
          ) : (
            project.words.map(word => {
              const isActive = currentTime >= word.start && currentTime < word.end;
              const isSelected = selectedWord === word.id;
              const isEditing = editingWord === word.id;

              return (
                <div
                  key={word.id}
                  onClick={() => {
                    setSelectedWord(word.id);
                    handleSeek(word.start);
                  }}
                  onDoubleClick={() => {
                    setEditingWord(word.id);
                    setEditText(word.text);
                  }}
                  style={{
                    padding: '0.4rem 0.7rem',
                    borderRadius: '6px',
                    background: isActive ? 'var(--studio-accent)' : isSelected ? 'rgba(99, 102, 241, 0.3)' : 'var(--studio-input-bg)',
                    border: `1px solid ${isSelected ? 'var(--studio-accent)' : 'var(--studio-border)'}`,
                    color: isActive ? 'white' : 'var(--studio-text)',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    transition: 'all 0.1s',
                    userSelect: 'none'
                  }}
                >
                  {isEditing ? (
                    <input
                      autoFocus
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      onBlur={() => {
                        if (editText.trim()) updateWord(word.id, { text: editText.trim() });
                        setEditingWord(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          if (editText.trim()) updateWord(word.id, { text: editText.trim() });
                          setEditingWord(null);
                        } else if (e.key === 'Escape') {
                          setEditingWord(null);
                        }
                      }}
                      onClick={(e) => e.stopPropagation()}
                      style={{ background: 'transparent', border: 'none', color: 'inherit', width: '60px', fontSize: 'inherit', outline: 'none' }}
                    />
                  ) : (
                    <>
                      <span>{word.text}</span>
                      {isSelected && (
                        <>
                          <span style={{ opacity: 0.5, fontSize: '0.7rem' }}>{word.start.toFixed(1)}s</span>
                          <button
                            onClick={(e) => { e.stopPropagation(); deleteWord(word.id); setSelectedWord(null); }}
                            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.85rem', padding: 0 }}
                            title="Delete"
                          >✕</button>
                        </>
                      )}
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>

        {project.words.length > 0 && (
          <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: '#6b7280' }}>
            💡 Double-click a word to edit • Click to select • Press ✕ to delete
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <style>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateX(-50%) translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
          }
        }
      `}</style>
    </div >
  );
}

// ============================================================================
// UI COMPONENTS
// ============================================================================
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '2rem' }}>
      <h3 style={{ fontSize: '0.75rem', color: 'var(--studio-text-muted)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>{title}</h3>
      {children}
    </div>
  );
}

function Slider({ label, value, min, max, step = 1, onChange, suffix = '' }: { label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void; suffix?: string }) {
  return (
    <label style={{ display: 'block', marginBottom: '1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--studio-text)', fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: '0.85rem', color: 'var(--studio-text-muted)' }}>{typeof value === 'number' ? (step < 1 ? value.toFixed(2) : value) : value}{suffix}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: '100%', accentColor: 'var(--studio-accent)' }}
      />
    </label>
  );
}

export default App;
