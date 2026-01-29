import { useState, useCallback, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, Film, Settings, Play, Download, CheckCircle, Loader2, AlertCircle, FileVideo, FileJson } from 'lucide-react'

function cn(...classes) {
    return classes.filter(Boolean).join(' ')
}

export default function App() {
    const [step, setStep] = useState('upload') // upload, config, processing, complete, error
    const [inputType, setInputType] = useState(null) // 'json' or 'video'
    const [wordsFile, setWordsFile] = useState(null)
    const [videoFile, setVideoFile] = useState(null)
    const [fontFile, setFontFile] = useState(null)
    const [config, setConfig] = useState({
        width: 1080,
        height: 1920,
        fontsize: 72,
        fps: 30,
        whisperModel: 'small'
    })
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)
    const [progress, setProgress] = useState(0)
    const [progressMessage, setProgressMessage] = useState('')
    const [sessionId, setSessionId] = useState(null)
    const pollingRef = useRef(null)

    // Poll for progress updates
    useEffect(() => {
        if (step === 'processing' && sessionId) {
            const pollProgress = async () => {
                try {
                    const res = await fetch(`/progress/${sessionId}`)
                    if (res.ok) {
                        const data = await res.json()
                        setProgress(data.progress || 0)
                        setProgressMessage(data.message || '')

                        if (data.stage === 'complete' && data.result) {
                            clearInterval(pollingRef.current)
                            setResult(data.result)
                            setStep('complete')
                        } else if (data.stage === 'error') {
                            clearInterval(pollingRef.current)
                            setError(data.message)
                            setStep('error')
                        }
                    }
                } catch (err) {
                    console.error('Progress poll error:', err)
                }
            }

            // Poll every 500ms
            pollingRef.current = setInterval(pollProgress, 500)
            pollProgress() // Initial call

            return () => {
                if (pollingRef.current) {
                    clearInterval(pollingRef.current)
                }
            }
        }
    }, [step, sessionId])

    const handleFileDrop = useCallback((e) => {
        e.preventDefault()
        const file = e.dataTransfer?.files[0] || e.target?.files[0]
        if (!file) return

        const ext = file.name.split('.').pop().toLowerCase()

        if (ext === 'json') {
            setInputType('json')
            setWordsFile(file)
            setVideoFile(null)
            setStep('config')
        } else if (['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4a', 'mp3', 'wav'].includes(ext)) {
            setInputType('video')
            setVideoFile(file)
            setWordsFile(null)
            setStep('config')
        }
    }, [])

    const handleSubmit = async () => {
        setStep('processing')
        setProgress(0)
        setProgressMessage('Starting...')
        setError(null)
        setSessionId(null)

        const formData = new FormData()

        if (inputType === 'json' && wordsFile) {
            formData.append('words_file', wordsFile)
        } else if (inputType === 'video' && videoFile) {
            formData.append('video_file', videoFile)
            formData.append('whisper_model', config.whisperModel)
        }

        if (fontFile) formData.append('font_file', fontFile)
        formData.append('width', config.width)
        formData.append('height', config.height)
        formData.append('font_size', config.fontsize)
        formData.append('fps', config.fps)

        try {
            const res = await fetch('/render', { method: 'POST', body: formData })

            if (!res.ok) {
                const errData = await res.json()
                throw new Error(errData.error || 'Rendering failed')
            }

            const data = await res.json()

            if (data.status === 'processing' && data.session_id) {
                // Background processing - start polling
                setSessionId(data.session_id)
                setProgressMessage(`Processing ${data.word_count} words...`)
            } else if (data.preview_url) {
                // Immediate result (shouldn't happen with new flow, but handle it)
                setResult(data)
                setProgress(100)
                setStep('complete')
            }
        } catch (err) {
            setError(err.message)
            setStep('error')
        }
    }

    const resetApp = () => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current)
        }
        setStep('upload')
        setInputType(null)
        setWordsFile(null)
        setVideoFile(null)
        setFontFile(null)
        setResult(null)
        setError(null)
        setProgress(0)
        setProgressMessage('')
        setSessionId(null)
    }

    const getStageLabel = () => {
        if (progress < 20) return 'Preparing...'
        if (progress < 80) return 'Rendering frames...'
        if (progress < 100) return 'Encoding video...'
        return 'Complete!'
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white flex flex-col items-center justify-center p-6">
            {/* Background glow */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
                <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="relative z-10 w-full max-w-xl"
            >
                {/* Header */}
                <div className="text-center mb-8">
                    <motion.h1
                        className="text-4xl font-bold bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                    >
                        Captioneer
                    </motion.h1>
                    <p className="text-slate-400 mt-2">Cinematic kinetic typography</p>
                </div>

                {/* Main Card */}
                <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl overflow-hidden">
                    <AnimatePresence mode="wait">
                        {/* Upload Step */}
                        {step === 'upload' && (
                            <motion.div
                                key="upload"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="p-8"
                            >
                                <div
                                    onDragOver={(e) => e.preventDefault()}
                                    onDrop={handleFileDrop}
                                    className="border-2 border-dashed border-slate-600 hover:border-violet-500/50 rounded-xl p-12 text-center transition-all cursor-pointer group"
                                >
                                    <input
                                        type="file"
                                        accept=".json,.mp4,.mov,.avi,.mkv,.webm,.m4a,.mp3,.wav"
                                        onChange={handleFileDrop}
                                        className="hidden"
                                        id="file-input"
                                    />
                                    <label htmlFor="file-input" className="cursor-pointer">
                                        <div className="flex justify-center gap-4 mb-4">
                                            <FileJson className="w-10 h-10 text-slate-500 group-hover:text-violet-400 transition-colors" />
                                            <FileVideo className="w-10 h-10 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                                        </div>
                                        <p className="text-slate-300 font-medium">Drop your file here</p>
                                        <p className="text-slate-500 text-sm mt-2">
                                            <span className="text-violet-400">words.json</span> or <span className="text-cyan-400">video file</span>
                                        </p>
                                        <p className="text-slate-600 text-xs mt-3">
                                            Video files will be auto-transcribed using Whisper
                                        </p>
                                    </label>
                                </div>
                            </motion.div>
                        )}

                        {/* Config Step */}
                        {step === 'config' && (
                            <motion.div
                                key="config"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="p-8"
                            >
                                <div className="flex items-center gap-3 mb-6">
                                    {inputType === 'json' ? (
                                        <FileJson className="w-5 h-5 text-violet-400" />
                                    ) : (
                                        <FileVideo className="w-5 h-5 text-cyan-400" />
                                    )}
                                    <span className="text-slate-300 font-medium truncate">
                                        {inputType === 'json' ? wordsFile?.name : videoFile?.name}
                                    </span>
                                    <span className={cn(
                                        "text-xs px-2 py-0.5 rounded-full",
                                        inputType === 'json' ? "bg-violet-500/20 text-violet-300" : "bg-cyan-500/20 text-cyan-300"
                                    )}>
                                        {inputType === 'json' ? 'JSON' : 'Video'}
                                    </span>
                                </div>

                                {/* Video-specific: Whisper Model */}
                                {inputType === 'video' && (
                                    <div className="mb-6 p-4 bg-slate-800/50 rounded-xl border border-slate-700/50">
                                        <label className="text-sm text-slate-400 mb-2 block">Whisper Model (for transcription)</label>
                                        <select
                                            value={config.whisperModel}
                                            onChange={(e) => setConfig({ ...config, whisperModel: e.target.value })}
                                            className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                                        >
                                            <option value="tiny">Tiny (fastest, less accurate)</option>
                                            <option value="base">Base</option>
                                            <option value="small">Small (balanced)</option>
                                            <option value="medium">Medium</option>
                                            <option value="large">Large (slowest, most accurate)</option>
                                        </select>
                                    </div>
                                )}

                                <div className="grid grid-cols-2 gap-4 mb-6">
                                    <div>
                                        <label className="text-sm text-slate-400 mb-1 block">Width</label>
                                        <input
                                            type="number"
                                            value={config.width}
                                            onChange={(e) => setConfig({ ...config, width: parseInt(e.target.value) })}
                                            className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-violet-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-slate-400 mb-1 block">Height</label>
                                        <input
                                            type="number"
                                            value={config.height}
                                            onChange={(e) => setConfig({ ...config, height: parseInt(e.target.value) })}
                                            className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-violet-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-slate-400 mb-1 block">Font Size</label>
                                        <input
                                            type="number"
                                            value={config.fontsize}
                                            onChange={(e) => setConfig({ ...config, fontsize: parseInt(e.target.value) })}
                                            className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-violet-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-slate-400 mb-1 block">FPS</label>
                                        <input
                                            type="number"
                                            value={config.fps}
                                            onChange={(e) => setConfig({ ...config, fps: parseInt(e.target.value) })}
                                            className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-violet-500"
                                        />
                                    </div>
                                </div>

                                {/* Font upload */}
                                <div className="mb-6">
                                    <label className="text-sm text-slate-400 mb-2 block">Custom Font (optional)</label>
                                    <input
                                        type="file"
                                        accept=".ttf,.otf"
                                        onChange={(e) => setFontFile(e.target.files[0])}
                                        className="w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-slate-700 file:text-white hover:file:bg-slate-600 cursor-pointer"
                                    />
                                    {fontFile && <p className="text-xs text-slate-500 mt-1">{fontFile.name}</p>}
                                </div>

                                <div className="flex gap-3">
                                    <button
                                        onClick={resetApp}
                                        className="flex-1 py-3 px-4 rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors font-medium"
                                    >
                                        Back
                                    </button>
                                    <button
                                        onClick={handleSubmit}
                                        className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 transition-all font-medium flex items-center justify-center gap-2"
                                    >
                                        <Play className="w-4 h-4" />
                                        {inputType === 'video' ? 'Transcribe & Render' : 'Render'}
                                    </button>
                                </div>
                            </motion.div>
                        )}

                        {/* Processing Step */}
                        {step === 'processing' && (
                            <motion.div
                                key="processing"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="p-8 text-center"
                            >
                                <Loader2 className="w-12 h-12 text-violet-400 animate-spin mx-auto mb-4" />
                                <p className="text-slate-300 font-medium mb-2">
                                    {getStageLabel()}
                                </p>
                                <p className="text-slate-500 text-sm mb-4">
                                    {progressMessage || 'Processing...'}
                                </p>
                                <div className="w-full bg-slate-700 rounded-full h-3 overflow-hidden">
                                    <motion.div
                                        className="h-full bg-gradient-to-r from-violet-500 to-cyan-500"
                                        initial={{ width: 0 }}
                                        animate={{ width: `${progress}%` }}
                                        transition={{ duration: 0.3, ease: "easeOut" }}
                                    />
                                </div>
                                <p className="text-slate-400 text-sm mt-2 font-mono">{Math.round(progress)}%</p>
                            </motion.div>
                        )}

                        {/* Complete Step */}
                        {step === 'complete' && result && (
                            <motion.div
                                key="complete"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="p-8"
                            >
                                <div className="text-center mb-6">
                                    <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
                                    <p className="text-slate-300 font-medium">Rendering Complete!</p>
                                    <p className="text-slate-500 text-sm">{result.word_count} words rendered</p>
                                </div>

                                {/* Video Preview */}
                                <div className="mb-6 rounded-xl overflow-hidden bg-black">
                                    <video
                                        src={result.preview_url}
                                        controls
                                        autoPlay
                                        loop
                                        muted
                                        className="w-full"
                                    />
                                </div>

                                {/* Download buttons */}
                                <div className="grid grid-cols-2 gap-3 mb-4">
                                    <a
                                        href={result.preview_url}
                                        download="preview.mp4"
                                        className="py-3 px-4 rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors font-medium flex items-center justify-center gap-2"
                                    >
                                        <Download className="w-4 h-4" />
                                        Preview (MP4)
                                    </a>
                                    <a
                                        href={result.master_url}
                                        download="captioneer_master.mov"
                                        className="py-3 px-4 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 transition-all font-medium flex items-center justify-center gap-2"
                                    >
                                        <Download className="w-4 h-4" />
                                        Master (ProRes)
                                    </a>
                                </div>

                                <button
                                    onClick={resetApp}
                                    className="w-full py-3 px-4 rounded-xl border border-slate-600 hover:bg-slate-800 transition-colors font-medium"
                                >
                                    Render Another
                                </button>
                            </motion.div>
                        )}

                        {/* Error Step */}
                        {step === 'error' && (
                            <motion.div
                                key="error"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="p-8 text-center"
                            >
                                <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
                                <p className="text-slate-300 font-medium mb-2">Rendering Failed</p>
                                <p className="text-red-400 text-sm mb-6 bg-red-500/10 rounded-lg p-3">{error}</p>
                                <button
                                    onClick={resetApp}
                                    className="py-3 px-6 rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors font-medium"
                                >
                                    Try Again
                                </button>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Footer */}
                <p className="text-center text-slate-600 text-xs mt-6">
                    Transparent ProRes 4444 output • Character-level animation
                </p>
            </motion.div>
        </div>
    )
}
