import { useState, useRef, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, RotateCcw, Check, AlertTriangle, BookOpen, ChevronRight, Upload, Loader2 } from 'lucide-react'
import { api } from '../services/api'

type PhotoStep = 'back' | 'front' | 'spine'
type CaptureMethod = 'camera' | 'upload'

const STEPS: { key: PhotoStep; label: string; description: string }[] = [
  { key: 'back', label: 'Back Cover', description: 'Place book face-down on the mat. ISBN barcode must be visible.' },
  { key: 'front', label: 'Front Cover', description: 'Flip book face-up on the mat. All 4 markers must be visible.' },
  { key: 'spine', label: 'Spine', description: 'Lay book on its side, spine facing up. Markers must be visible.' },
]

interface PhotoboothResult {
  isbn: string | null
  title: string | null
  authors: string[]
  publisher: string | null
  height_mm: number | null
  width_mm: number | null
  depth_mm: number | null
  isbn_confidence: number
  title_confidence: number
  dimension_confidence: number
  warnings: string[]
  front_raw_text: string | null
  back_raw_text: string | null
  spine_raw_text: string | null
  api_title: string | null
  api_authors: string[]
  api_publisher: string | null
  api_description: string | null
  api_cover_url: string | null
  api_page_count: number | null
  api_height_mm: number | null
}

export default function PhotoBooth() {
  const queryClient = useQueryClient()
  const [captureMethod, setCaptureMethod] = useState<CaptureMethod>('camera')
  const [currentStep, setCurrentStep] = useState(0)
  const [photos, setPhotos] = useState<Record<PhotoStep, Blob | null>>({ back: null, front: null, spine: null })
  const [previews, setPreviews] = useState<Record<PhotoStep, string | null>>({ back: null, front: null, spine: null })
  const [result, setResult] = useState<PhotoboothResult | null>(null)
  const [editData, setEditData] = useState<Record<string, string>>({})

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const processPhotos = useMutation({
    mutationFn: async () => {
      const formData = new FormData()
      if (photos.front) formData.append('front', photos.front, 'front.jpg')
      if (photos.back) formData.append('back', photos.back, 'back.jpg')
      if (photos.spine) formData.append('spine', photos.spine, 'spine.jpg')
      return api.processPhotobooth(formData)
    },
    onSuccess: (data: PhotoboothResult) => {
      setResult(data)
      // Pre-fill edit form with best available data
      setEditData({
        isbn: data.isbn || '',
        title: data.api_title || data.title || '',
        authors: (data.api_authors.length ? data.api_authors : data.authors).join(', '),
        publisher: data.api_publisher || data.publisher || '',
        height_mm: String(data.height_mm || data.api_height_mm || ''),
        width_mm: String(data.width_mm || ''),
        depth_mm: String(data.depth_mm || ''),
        page_count: String(data.api_page_count || ''),
        description: data.api_description || '',
        cover_url: data.api_cover_url || '',
      })
    },
  })

  const saveBook = useMutation({
    mutationFn: async () => {
      const bookData = {
        isbn: editData.isbn || undefined,
        title: editData.title,
        authors: editData.authors.split(',').map(a => a.trim()).filter(Boolean),
        publisher: editData.publisher || undefined,
        height_mm: editData.height_mm ? parseFloat(editData.height_mm) : undefined,
        width_mm: editData.width_mm ? parseFloat(editData.width_mm) : undefined,
        depth_mm: editData.depth_mm ? parseFloat(editData.depth_mm) : undefined,
        page_count: editData.page_count ? parseInt(editData.page_count) : undefined,
        description: editData.description || undefined,
        cover_url: editData.cover_url || undefined,
      }
      return api.createBook(bookData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      resetAll()
    },
  })

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 3840 }, height: { ideal: 2160 } }
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
    } catch {
      setCaptureMethod('upload')
    }
  }, [])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
  }, [])

  const capturePhoto = useCallback(() => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas) return

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(video, 0, 0)

    canvas.toBlob(blob => {
      if (!blob) return
      const step = STEPS[currentStep].key
      setPhotos(prev => ({ ...prev, [step]: blob }))
      setPreviews(prev => ({ ...prev, [step]: URL.createObjectURL(blob) }))
    }, 'image/jpeg', 0.95)
  }, [currentStep])

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const step = STEPS[currentStep].key
    setPhotos(prev => ({ ...prev, [step]: file }))
    setPreviews(prev => ({ ...prev, [step]: URL.createObjectURL(file) }))
  }, [currentStep])

  const nextStep = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(prev => prev + 1)
    } else {
      stopCamera()
      processPhotos.mutate()
    }
  }

  const retakePhoto = () => {
    const step = STEPS[currentStep].key
    setPhotos(prev => ({ ...prev, [step]: null }))
    setPreviews(prev => ({ ...prev, [step]: null }))
  }

  const resetAll = () => {
    stopCamera()
    setCurrentStep(0)
    setPhotos({ back: null, front: null, spine: null })
    setPreviews({ back: null, front: null, spine: null })
    setResult(null)
    setEditData({})
  }

  const step = STEPS[currentStep]
  const hasCurrentPhoto = photos[step.key] !== null

  // --- Review/Edit screen ---
  if (result) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">Review & Confirm</h1>
          <button onClick={resetAll} className="text-sm text-slate-400 hover:text-white">
            Scan Another
          </button>
        </div>

        {result.warnings.length > 0 && (
          <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-3">
            {result.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-amber-300 text-sm">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                {w}
              </div>
            ))}
          </div>
        )}

        {/* Confidence indicators */}
        <div className="flex gap-3 text-xs">
          <ConfidenceBadge label="ISBN" value={result.isbn_confidence} />
          <ConfidenceBadge label="Title" value={result.title_confidence} />
          <ConfidenceBadge label="Dimensions" value={result.dimension_confidence} />
        </div>

        {/* Cover preview */}
        {editData.cover_url && (
          <div className="flex justify-center">
            <img src={editData.cover_url} alt="Cover" className="h-40 rounded shadow-lg" />
          </div>
        )}

        {/* Editable fields */}
        <div className="space-y-3">
          <Field label="ISBN" value={editData.isbn} onChange={v => setEditData(d => ({ ...d, isbn: v }))} />
          <Field label="Title" value={editData.title} onChange={v => setEditData(d => ({ ...d, title: v }))} />
          <Field label="Authors (comma-separated)" value={editData.authors} onChange={v => setEditData(d => ({ ...d, authors: v }))} />
          <Field label="Publisher" value={editData.publisher} onChange={v => setEditData(d => ({ ...d, publisher: v }))} />

          <div className="grid grid-cols-3 gap-2">
            <Field label="Height (mm)" value={editData.height_mm} onChange={v => setEditData(d => ({ ...d, height_mm: v }))} type="number" />
            <Field label="Width (mm)" value={editData.width_mm} onChange={v => setEditData(d => ({ ...d, width_mm: v }))} type="number" />
            <Field label="Depth (mm)" value={editData.depth_mm} onChange={v => setEditData(d => ({ ...d, depth_mm: v }))} type="number" />
          </div>

          <Field label="Pages" value={editData.page_count} onChange={v => setEditData(d => ({ ...d, page_count: v }))} type="number" />
          <Field label="Description" value={editData.description} onChange={v => setEditData(d => ({ ...d, description: v }))} multiline />
        </div>

        {/* OCR debug (collapsible) */}
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer">Raw OCR text</summary>
          <div className="mt-2 space-y-1">
            {result.front_raw_text && <p><span className="text-slate-400">Front:</span> {result.front_raw_text}</p>}
            {result.back_raw_text && <p><span className="text-slate-400">Back:</span> {result.back_raw_text}</p>}
            {result.spine_raw_text && <p><span className="text-slate-400">Spine:</span> {result.spine_raw_text}</p>}
          </div>
        </details>

        <button
          onClick={() => saveBook.mutate()}
          disabled={saveBook.isPending || !editData.title}
          className="w-full py-3 bg-green-600 hover:bg-green-700 disabled:bg-slate-700 rounded-lg font-medium flex items-center justify-center gap-2"
        >
          {saveBook.isPending ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />}
          {saveBook.isPending ? 'Saving...' : 'Save Book'}
        </button>

        {saveBook.isSuccess && (
          <div className="text-center text-green-400 text-sm">Book saved successfully!</div>
        )}
      </div>
    )
  }

  // --- Processing screen ---
  if (processPhotos.isPending) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <Loader2 size={48} className="animate-spin text-blue-400" />
        <p className="text-slate-400">Processing photos...</p>
        <p className="text-xs text-slate-600">Detecting markers, reading barcode, running OCR</p>
      </div>
    )
  }

  // --- Capture screen ---
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Camera size={24} />
          PhotoBooth
        </h1>
        <div className="flex gap-1 text-xs">
          <button
            onClick={() => setCaptureMethod('camera')}
            className={`px-2 py-1 rounded ${captureMethod === 'camera' ? 'bg-blue-600' : 'bg-slate-800'}`}
          >Camera</button>
          <button
            onClick={() => setCaptureMethod('upload')}
            className={`px-2 py-1 rounded ${captureMethod === 'upload' ? 'bg-blue-600' : 'bg-slate-800'}`}
          >Upload</button>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              i < currentStep ? 'bg-green-600' :
              i === currentStep ? 'bg-blue-600' : 'bg-slate-700'
            }`}>
              {i < currentStep ? <Check size={16} /> : i + 1}
            </div>
            <span className={`ml-1 text-xs ${i === currentStep ? 'text-white' : 'text-slate-500'}`}>
              {s.label}
            </span>
            {i < STEPS.length - 1 && <ChevronRight size={14} className="mx-1 text-slate-600" />}
          </div>
        ))}
      </div>

      {/* Instructions */}
      <div className="bg-slate-900 rounded-lg p-3 text-sm text-slate-300">
        <BookOpen size={14} className="inline mr-1" />
        {step.description}
      </div>

      {/* Photo preview thumbnails */}
      <div className="flex gap-2">
        {STEPS.map((s) => (
          <div key={s.key} className={`flex-1 h-16 rounded border-2 overflow-hidden ${
            s.key === step.key ? 'border-blue-500' : previews[s.key] ? 'border-green-600' : 'border-slate-700'
          }`}>
            {previews[s.key] ? (
              <img src={previews[s.key]!} alt={s.label} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-slate-600 text-xs">
                {s.label}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Camera / Upload area */}
      <div className="aspect-[4/3] bg-black rounded-lg overflow-hidden relative">
        {hasCurrentPhoto && previews[step.key] ? (
          <img src={previews[step.key]!} alt="Captured" className="w-full h-full object-contain" />
        ) : captureMethod === 'camera' ? (
          <>
            <video ref={videoRef} autoPlay playsInline className="w-full h-full object-contain" />
            {!streamRef.current && (
              <button
                onClick={startCamera}
                className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-900/80"
              >
                <Camera size={48} className="text-blue-400" />
                <span className="text-sm">Tap to start camera</span>
              </button>
            )}
          </>
        ) : (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full h-full flex flex-col items-center justify-center gap-2"
          >
            <Upload size={48} className="text-slate-400" />
            <span className="text-sm text-slate-400">Tap to select photo</span>
          </button>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileUpload}
        className="hidden"
      />
      <canvas ref={canvasRef} className="hidden" />

      {/* Action buttons */}
      <div className="flex gap-3">
        {hasCurrentPhoto ? (
          <>
            <button onClick={retakePhoto} className="flex-1 py-3 bg-slate-700 rounded-lg flex items-center justify-center gap-2">
              <RotateCcw size={18} />
              Retake
            </button>
            <button onClick={nextStep} className="flex-1 py-3 bg-blue-600 rounded-lg flex items-center justify-center gap-2">
              {currentStep < STEPS.length - 1 ? (
                <>Next <ChevronRight size={18} /></>
              ) : (
                <>Process <Check size={18} /></>
              )}
            </button>
          </>
        ) : captureMethod === 'camera' && streamRef.current ? (
          <>
            <button onClick={capturePhoto} className="flex-1 py-3 bg-blue-600 rounded-lg flex items-center justify-center gap-2">
              <Camera size={18} />
              Capture
            </button>
            <button onClick={nextStep} className="py-3 px-4 bg-slate-700 rounded-lg text-sm text-slate-400">
              Skip
            </button>
          </>
        ) : (
          <button onClick={nextStep} className="flex-1 py-3 bg-slate-700 rounded-lg text-sm text-slate-400">
            Skip this photo
          </button>
        )}
      </div>
    </div>
  )
}

function Field({
  label, value, onChange, type = 'text', multiline = false
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  multiline?: boolean
}) {
  return (
    <label className="block">
      <span className="text-xs text-slate-400">{label}</span>
      {multiline ? (
        <textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          rows={3}
          className="w-full mt-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded text-sm focus:border-blue-500 focus:outline-none"
        />
      ) : (
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full mt-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded text-sm focus:border-blue-500 focus:outline-none"
        />
      )}
    </label>
  )
}

function ConfidenceBadge({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'text-green-400' : pct >= 50 ? 'text-amber-400' : 'text-red-400'
  return (
    <span className={`${color}`}>
      {label}: {pct}%
    </span>
  )
}
