import { useState } from 'react'
import { X, FolderOpen, Download } from 'lucide-react'
import { startExport, pickDirectory } from '../hooks/api'
import type { ExportOptions } from '../types'

interface Props {
  selectedIds: number[]
  onClose: () => void
  onExportStarted: (jobId: number) => void
}

export default function ExportPanel({ selectedIds, onClose, onExportStarted }: Props) {
  const [exportDir, setExportDir] = useState<string>(() => {
    return localStorage.getItem('romorganizer_last_export_dir') || ''
  })
  const [picking, setPicking] = useState(false)
  const [outputFormat, setOutputFormat] = useState<'original' | 'uncompressed' | 'zip' | '7z'>('uncompressed')
  const [dedupMode, setDedupMode] = useState<'single' | 'all'>('single')
  const [langPriority, setLangPriority] = useState('En,Zh,Ja')
  const [renameFiles, setRenameFiles] = useState(true)
  const [onlyPreferredLanguages, setOnlyPreferredLanguages] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleBrowse = async () => {
    setPicking(true)
    try {
      const selected = await pickDirectory('Select Export Directory (e.g. MicroSD)')
      if (selected) {
        setExportDir(selected)
        localStorage.setItem('romorganizer_last_export_dir', selected)
      }
    } finally {
      setPicking(false)
    }
  }

  const handleExport = async () => {
    if (!exportDir.trim()) {
      setError('Please enter an export directory path.')
      return
    }
    setError('')
    setLoading(true)
    try {
      localStorage.setItem('romorganizer_last_export_dir', exportDir.trim())
      const options: ExportOptions = {
        game_ids: selectedIds,
        export_dir: exportDir.trim(),
        output_format: outputFormat,
        dedup_mode: dedupMode,
        lang_priority: langPriority,
        rename_files: renameFiles,
        only_preferred_languages: onlyPreferredLanguages,
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
      <div className="card w-full max-w-lg mx-4 shadow-2xl">
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

        <div className="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {/* Game count */}
          <p className="text-sm text-gray-300">
            Exporting <span className="font-semibold text-white">{selectedIds.length}</span> selected game{selectedIds.length !== 1 ? 's' : ''}.
          </p>

          {/* Export directory */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Export Directory
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <FolderOpen size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={exportDir}
                  onChange={e => setExportDir(e.target.value)}
                  className="input w-full pl-9 text-sm font-mono"
                  placeholder="/Volumes/MicroSD or /path/to/export"
                />
              </div>
              <button
                type="button"
                onClick={handleBrowse}
                disabled={picking}
                className="btn-secondary text-sm px-3 flex items-center gap-1.5 whitespace-nowrap"
              >
                {picking ? <span className="animate-spin">⟳</span> : <FolderOpen size={15} />}
                Browse…
              </button>
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
            <div className="grid grid-cols-4 gap-2">
              {(
                [
                  { id: 'original', label: 'Original' },
                  { id: 'uncompressed', label: 'Uncompressed' },
                  { id: 'zip', label: 'ZIP' },
                  { id: '7z', label: '7Z' },
                ] as const
              ).map(fmt => (
                <button
                  key={fmt.id}
                  onClick={() => setOutputFormat(fmt.id)}
                  className={`py-2 px-1 rounded-lg text-xs font-medium border transition-colors text-center ${
                    outputFormat === fmt.id
                      ? 'bg-brand-500 border-brand-500 text-white shadow-sm'
                      : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                  }`}
                >
                  {fmt.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {outputFormat === 'original' && 'Files are copied as-is (archives stay archives, raw stays raw).'}
              {outputFormat === 'uncompressed' && 'Extracts raw ROM files (.nes, .sfc, .z64) from zip/7z/rar archives.'}
              {outputFormat === 'zip' && 'Compresses or keeps games in standard ZIP archives.'}
              {outputFormat === '7z' && 'Compresses or keeps games in high-compression 7Z archives.'}
            </p>
          </div>

          {/* File renaming option */}
          <div className="pt-1">
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={renameFiles}
                onChange={e => setRenameFiles(e.target.checked)}
                className="accent-brand-500 rounded cursor-pointer"
              />
              <span className="text-sm text-gray-200">Rename exported files to official game names</span>
            </label>
            <p className="text-xs text-gray-500 ml-6 mt-0.5">
              {renameFiles ? 'e.g. "Dr. Mario (Japan, USA).nes"' : 'Preserves original incoming filenames (e.g. "dr_mario_(ju).zip")'}
            </p>
          </div>

          {/* Dedup mode */}
          <div className="pt-1 border-t border-gray-800">
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Duplicate Handling (1G1R)
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
                  <p className="text-sm text-gray-200 group-hover:text-white">1G1R: Best version only (recommended)</p>
                  <p className="text-xs text-gray-500">
                    Groups regional duplicates together and prioritizes <strong>USA/En → World → Europe → Chinese</strong> releases.
                  </p>
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
                  <p className="text-xs text-gray-500">Export all selected variants without deduplication.</p>
                </div>
              </label>
            </div>
          </div>

          {/* Filter out un-understood foreign languages */}
          {dedupMode === 'single' && (
            <div className="space-y-3 pt-1">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={onlyPreferredLanguages}
                  onChange={e => setOnlyPreferredLanguages(e.target.checked)}
                  className="accent-brand-500 rounded cursor-pointer"
                />
                <span className="text-sm text-gray-200">Only export English, World & Chinese games</span>
              </label>
              <p className="text-xs text-gray-500 ml-6">
                Skips games that only exist in languages you don't understand (e.g. Japanese-only or German-only).
              </p>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1">
                  Custom Language Priority Order
                </label>
                <input
                  type="text"
                  value={langPriority}
                  onChange={e => setLangPriority(e.target.value)}
                  className="input w-full text-xs"
                  placeholder="En,Zh,Ja"
                />
              </div>
            </div>
          )}

          {error && (
            <p className="text-sm text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-5 pb-5 pt-2 border-t border-gray-800">
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
