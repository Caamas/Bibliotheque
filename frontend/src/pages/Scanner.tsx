import { useState, useRef, useCallback, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Keyboard, Plus, Check, AlertCircle } from 'lucide-react'
import { Html5Qrcode } from 'html5-qrcode'
import { api, type ScanResult, type Book } from '../services/api'

type ScanMode = 'camera' | 'manual' | 'batch'

export default function Scanner() {
  const [mode, setMode] = useState<ScanMode>('manual')
  const [manualIsbn, setManualIsbn] = useState('')
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [batchResults, setBatchResults] = useState<{ isbn: string; title: string; status: string }[]>([])
  const [scanning, setScanning] = useState(false)
  const scannerRef = useRef<Html5Qrcode | null>(null)
  const queryClient = useQueryClient()

  const scanMutation = useMutation({
    mutationFn: (isbn: string) => api.scanISBN(isbn),
    onSuccess: (result) => setScanResult(result),
  })

  const addMutation = useMutation({
    mutationFn: (isbn: string) => api.scanAndAdd(isbn),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      setScanResult(null)
    },
  })

  const batchAddMutation = useMutation({
    mutationFn: (isbn: string) => api.scanAndAdd(isbn),
    onSuccess: (book: Book, isbn: string) => {
      setBatchResults(prev => [...prev, { isbn, title: book.title, status: 'added' }])
      queryClient.invalidateQueries({ queryKey: ['books'] })
    },
    onError: (_err, isbn: string) => {
      setBatchResults(prev => [...prev, { isbn, title: isbn, status: 'error' }])
    },
  })

  // Camera scanning
  const startCamera = useCallback(async () => {
    try {
      const scanner = new Html5Qrcode('scanner-container')
      scannerRef.current = scanner
      setScanning(true)

      await scanner.start(
        { facingMode: 'environment' },
        {
          fps: 10,
          qrbox: { width: 300, height: 150 },
          aspectRatio: 1.0,
        },
        (decodedText) => {
          // Barcode detected
          const isbn = decodedText.replace(/[^0-9X]/gi, '')
          if (isbn.length === 10 || isbn.length === 13) {
            if (mode === 'batch') {
              batchAddMutation.mutate(isbn)
            } else {
              scanner.stop()
              setScanning(false)
              scanMutation.mutate(isbn)
            }
          }
        },
        () => {} // Ignore scan failures (continuous scanning)
      )
    } catch (err) {
      console.error('Camera error:', err)
      setScanning(false)
    }
  }, [mode, scanMutation, batchAddMutation])

  const stopCamera = useCallback(async () => {
    if (scannerRef.current) {
      try {
        await scannerRef.current.stop()
      } catch { /* ignore */ }
      scannerRef.current = null
    }
    setScanning(false)
  }, [])

  useEffect(() => {
    return () => { stopCamera() }
  }, [stopCamera])

  const handleManualScan = () => {
    const isbn = manualIsbn.replace(/[^0-9X]/gi, '')
    if (isbn.length === 10 || isbn.length === 13) {
      scanMutation.mutate(isbn)
      setManualIsbn('')
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">ISBN Scanner</h1>

      {/* Mode selector */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => { stopCamera(); setMode('manual') }}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === 'manual' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'
          }`}
        >
          <Keyboard size={16} className="inline mr-1" /> Manual
        </button>
        <button
          onClick={() => { setMode('camera'); startCamera() }}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === 'camera' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'
          }`}
        >
          <Camera size={16} className="inline mr-1" /> Camera
        </button>
        <button
          onClick={() => { setMode('batch'); startCamera() }}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === 'batch' ? 'bg-green-600 text-white' : 'bg-slate-800 text-slate-400'
          }`}
        >
          <Plus size={16} className="inline mr-1" /> Batch
        </button>
      </div>

      {/* Camera viewfinder */}
      {(mode === 'camera' || mode === 'batch') && (
        <div className="mb-4">
          <div id="scanner-container" className="rounded-lg overflow-hidden bg-black" />
          {scanning && (
            <p className="text-center text-sm text-slate-400 mt-2">
              {mode === 'batch' ? 'Batch mode: scanning continuously...' : 'Point camera at ISBN barcode'}
            </p>
          )}
          {!scanning && (
            <button
              onClick={startCamera}
              className="w-full mt-2 py-2 bg-blue-600 rounded-lg text-sm"
            >
              Start Camera
            </button>
          )}
        </div>
      )}

      {/* Manual ISBN input */}
      {mode === 'manual' && (
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="Enter ISBN (10 or 13 digits)"
            value={manualIsbn}
            onChange={e => setManualIsbn(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleManualScan()}
            className="flex-1 px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-lg focus:outline-none focus:border-blue-500"
            inputMode="numeric"
            autoFocus
          />
          <button
            onClick={handleManualScan}
            disabled={scanMutation.isPending}
            className="px-6 py-3 bg-blue-600 rounded-lg font-medium disabled:opacity-50"
          >
            Scan
          </button>
        </div>
      )}

      {/* Loading */}
      {scanMutation.isPending && (
        <div className="text-center py-8 text-slate-400">Looking up ISBN...</div>
      )}

      {/* Scan result */}
      {scanResult && (
        <div className={`p-4 rounded-lg border mb-4 ${
          scanResult.already_owned
            ? 'bg-amber-950/50 border-amber-700'
            : scanResult.found
              ? 'bg-green-950/50 border-green-700'
              : 'bg-red-950/50 border-red-700'
        }`}>
          {scanResult.already_owned && scanResult.book ? (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle size={20} className="text-amber-400" />
                <span className="font-medium text-amber-300">Already in collection</span>
              </div>
              <p className="text-lg font-medium">{scanResult.book.title}</p>
              <p className="text-slate-400">{scanResult.book.authors?.join(', ')}</p>
            </div>
          ) : scanResult.found && scanResult.metadata ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Check size={20} className="text-green-400" />
                <span className="font-medium text-green-300">Book found</span>
              </div>
              <div className="flex gap-4">
                {scanResult.metadata.cover_url && (
                  <img src={scanResult.metadata.cover_url} alt="" className="w-20 h-28 object-cover rounded" />
                )}
                <div className="flex-1">
                  <p className="text-lg font-medium">{scanResult.metadata.title}</p>
                  <p className="text-slate-400">{scanResult.metadata.authors?.join(', ')}</p>
                  <p className="text-sm text-slate-500 mt-1">{scanResult.metadata.publisher}</p>
                  {scanResult.metadata.height_mm && (
                    <p className="text-xs text-slate-600 mt-1">Height: {scanResult.metadata.height_mm}mm</p>
                  )}
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => addMutation.mutate(scanResult.metadata?.isbn_13 || scanResult.metadata?.isbn_10 || '')}
                  disabled={addMutation.isPending}
                  className="flex-1 py-2 bg-green-600 rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  <Plus size={16} className="inline mr-1" />
                  Add to Collection
                </button>
                <button
                  onClick={() => setScanResult(null)}
                  className="px-4 py-2 bg-slate-700 rounded-lg text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <AlertCircle size={20} className="text-red-400" />
              <span className="text-red-300">{scanResult.message}</span>
            </div>
          )}
        </div>
      )}

      {/* Batch results */}
      {mode === 'batch' && batchResults.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-400 mb-2">
            Scanned: {batchResults.length} books
          </h3>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {batchResults.map((r, i) => (
              <div key={i} className={`flex items-center gap-2 text-sm px-3 py-2 rounded ${
                r.status === 'added' ? 'bg-green-950/30' : 'bg-red-950/30'
              }`}>
                {r.status === 'added' ? (
                  <Check size={14} className="text-green-400" />
                ) : (
                  <AlertCircle size={14} className="text-red-400" />
                )}
                <span className="truncate">{r.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="mt-6 p-4 bg-slate-900 rounded-lg text-sm text-slate-400">
        <h3 className="font-medium text-slate-300 mb-2">Tips</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li><strong>Camera mode:</strong> Scan one book, review, then add</li>
          <li><strong>Batch mode:</strong> Scan many books continuously (auto-adds)</li>
          <li><strong>Manual mode:</strong> Type ISBN if barcode won't scan</li>
          <li>Books with missing height data will default to 210mm (standard)</li>
        </ul>
      </div>
    </div>
  )
}
