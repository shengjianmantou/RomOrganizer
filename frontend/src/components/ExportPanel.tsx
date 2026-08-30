import { useState } from 'react'
import { X, FolderOpen, Download } from 'lucide-react'
import { startExport } from '../hooks/api'
import type { ExportOptions } from '../types'

interface Props {
  selectedIds: number[]
  onClose: () => void
  onExportStarted: (jobId: number) => void
}

export default function ExportPanel({ selectedIds, onClose, onExportStarted }: Props) {
  const [exportDir, setExportDir] = useState('')
  const [outputFormat, setOutputFormat] = useState<'original' | 'zip' | '7z'>('original')
  const [dedupMode, setDedupMode] = useState<'single' | 'all'>('single')
  const [langPriority, setLangPriority] = useState('En,Zh,Ja')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleExport = async () => {
    if (!exportDir.trim()) {
      setError('Please enter an export directory path.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const options: ExportOptions = {
        game_ids: selectedIds,
        export_dir: exportDir.trim(),
        output_format: outputFormat,
        dedup_mode: dedupMode,
        lang_priority: langPriority,
      }
      const job = await startExport(options)
      onExportStarted(job.id)
    } catch (e: unknown) {
      setError('Failed to start export. Please check the directory path.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="card w-full max-w-md mx-4 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Download size={18} className="text-brand-400" />
            <span className="font-semibold text-white">Export ROMs</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Game count */}
          <p className="text-sm text-gray-300">
            Exporting <span className="font-semibold text-white">{selectedIds.length}</span> selected game{selectedIds.length !== 1 ? 's' : ''}.
          </p>

          {/* Export directory */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Export Directory
            </label>
            <div className="relative">
              <FolderOpen size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={exportDir}
                onChange={e => setExportDir(e.target.value)}
                className="input w-full pl-9 text-sm font-mono"
                placeholder="/Volumes/MicroSD or /path/to/export"
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Will create <code className="text-gray-400">roms/</code> and <code className="text-gray-400">RomOrganizer/</code> subdirectories. Existing files are never overwritten.
            </p>
          </div>

          {/* Output format */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              ROM Format
            </label>
            <div className="flex gap-2">
              {(['original', 'zip', '7z'] as const).map(fmt => (
                <button
                  key={fmt}
                  onClick={() => setOutputFormat(fmt)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    outputFormat === fmt
                      ? 'bg-brand-500 border-brand-500 text-white'
                      : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                  }`}
                >
                  {fmt === 'original' ? 'Original' : fmt.toUpperCase()}
                </button>
              ))}
            </div>
            {outputFormat === 'original' && (
              <p className="text-xs text-gray-500 mt-1">Files are copied as-is (zip stays zip, raw stays raw).</p>
            )}
          </div>

          {/* Dedup mode */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Duplicate Handling
            </label>
            <div className="space-y-2">
              <label className="flex items-start gap-3 cursor-pointer group">
                <input
                  type="radio"
                  name="dedup"
                  value="single"
                  checked={dedupMode === 'single'}
                  onChange={() => setDedupMode('single')}
                  className="mt-0.5 accent-brand-500"
                />
                <div>
                  <p className="text-sm text-gray-200 group-hover:text-white">Best version only (recommended)</p>
                  <p className="text-xs text-gray-500">One version per game, chosen by language priority.</p>
                </div>
              </label>
              <label className="flex items-start gap-3 cursor-pointer group">
                <input
                  type="radio"
                  name="dedup"
                  value="all"
                  checked={dedupMode === 'all'}
                  onChange={() => setDedupMode('all')}
                  className="mt-0.5 accent-brand-500"
                />
                <div>
                  <p className="text-sm text-gray-200 group-hover:text-white">All versions</p>
                  <p className="text-xs text-gray-500">Export all selected variants (multiple regions/languages).</p>
                </div>
              </label>
            </div>
          </div>

          {/* Language priority */}
          {dedupMode === 'single' && (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Language Priority <span className="text-gray-500 font-normal">(comma-separated, highest first)</span>
              </label>
              <input
                type="text"
                value={langPriority}
                onChange={e => setLangPriority(e.target.value)}
                className="input w-full text-sm"
                placeholder="En,Zh,Ja"
              />
              <p className="text-xs text-gray-500 mt-1">
                Common codes: En, Zh, Ja, Fr, De, Es, It, Pt, Ko, Ru
              </p>
            </div>
          )}

          {error && (
            <p className="text-sm text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-5 pb-5">
          <button onClick={onClose} className="btn-secondary flex-1">
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={loading || !exportDir.trim()}
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            {loading ? (
              <><span className="animate-spin">⟳</span> Starting…</>
            ) : (
              <><Download size={15} /> Export</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
