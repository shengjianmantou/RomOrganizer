import { useEffect, useRef, useState } from 'react'
import { X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

interface ProgressState {
  status: 'running' | 'done' | 'error'
  total: number
  processed: number
  imported?: number
  exported?: number
  skipped: number
  errors: number
  message?: string
}

interface Props {
  type: 'import' | 'export'
  jobId: number
  onDone: () => void
}

export default function ProgressToast({ type, jobId, onDone }: Props) {
  const [state, setState] = useState<ProgressState>({
    status: 'running',
    total: 0,
    processed: 0,
    skipped: 0,
    errors: 0,
  })
  const [dismissed, setDismissed] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const endpoint = `/api/${type}/${jobId}/status`
    const es = new EventSource(endpoint)
    esRef.current = es

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setState(prev => ({
          ...prev,
          status: data.status === 'done' ? 'done' : data.status === 'error' ? 'error' : 'running',
          total: data.total ?? prev.total,
          processed: data.processed ?? data.exported ?? prev.processed,
          imported: data.imported,
          exported: data.exported,
          skipped: data.skipped ?? prev.skipped,
          errors: data.errors ?? prev.errors,
          message: data.message,
        }))
        if (data.status === 'done' || data.status === 'error') {
          es.close()
          if (data.status === 'done') {
            setTimeout(() => {
              onDone()
            }, 3000)
          }
        }
      } catch {}
    }

    es.onerror = () => {
      setState(prev => ({ ...prev, status: 'error', message: 'Connection lost' }))
      es.close()
    }

    return () => {
      es.close()
    }
  }, [jobId, type])

  if (dismissed) return null

  const pct = state.total > 0 ? Math.round((state.processed / state.total) * 100) : 0
  const label = type === 'import' ? 'Import' : 'Export'
  const count = type === 'import' ? state.imported : state.exported

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 card shadow-2xl overflow-hidden">
      {/* Progress bar */}
      {state.status === 'running' && (
        <div className="h-1 bg-gray-800">
          <div
            className="h-full bg-brand-500 transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className="mt-0.5 flex-shrink-0">
            {state.status === 'running' && (
              <Loader2 size={18} className="text-brand-400 animate-spin" />
            )}
            {state.status === 'done' && (
              <CheckCircle size={18} className="text-green-400" />
            )}
            {state.status === 'error' && (
              <AlertCircle size={18} className="text-red-400" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold text-white">
                {state.status === 'running' && `${label}ing…`}
                {state.status === 'done' && `${label} complete`}
                {state.status === 'error' && `${label} failed`}
              </span>
              <button
                onClick={() => { setDismissed(true); esRef.current?.close(); onDone() }}
                className="text-gray-500 hover:text-gray-300"
              >
                <X size={14} />
              </button>
            </div>

            {state.status === 'running' && state.total > 0 && (
              <p className="text-xs text-gray-400">
                {state.processed.toLocaleString()} / {state.total.toLocaleString()} ({pct}%)
              </p>
            )}

            {(state.status === 'done' || state.status === 'running') && count != null && (
              <div className="flex gap-3 mt-1.5 text-xs">
                <span className="text-green-400">✓ {count} {type === 'import' ? 'imported' : 'exported'}</span>
                {state.skipped > 0 && <span className="text-gray-400">⊘ {state.skipped} skipped</span>}
                {state.errors > 0 && <span className="text-red-400">✗ {state.errors} errors</span>}
              </div>
            )}

            {state.status === 'error' && state.message && (
              <p className="text-xs text-red-400 mt-1 truncate">{state.message}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
