import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LayoutGrid, List, Download, Upload, Search, X, SlidersHorizontal, RefreshCw, FolderOpen, ShieldCheck, CheckCircle2, Trash2,
} from 'lucide-react'
import clsx from 'clsx'

import { fetchGames, fetchSystems, fetchFilterOptions, fetchLibraryStats, startImport, pickDirectory, rematchLibrary, fetchAllGameIds, clearLibrary } from '../hooks/api'
import type { Game, LibraryFilters, System } from '../types'
import GameGrid from '../components/GameGrid'
import GameTable from '../components/GameTable'
import FilterSidebar from '../components/FilterSidebar'
import ExportPanel from '../components/ExportPanel'
import ProgressToast from '../components/ProgressToast'
import GameDetailModal from '../components/GameDetailModal'

const DEFAULT_FILTERS: LibraryFilters = {
  search: '',
  system_ids: [],
  languages: [],
  regions: [],
  genres: [],
  series: '',
  sort_by: 'sort_title',
  sort_dir: 'asc',
}

export default function LibraryPage() {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => {
    return (localStorage.getItem('romorganizer_view_mode') as 'grid' | 'list') || 'grid'
  })
  const [filters, setFilters] = useState<LibraryFilters>(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [showFilters, setShowFilters] = useState(true)
  const [showExport, setShowExport] = useState(false)
  const [importDirs, setImportDirs] = useState<string>(() => {
    return localStorage.getItem('romorganizer_last_import_dir') || ''
  })
  const [importJobId, setImportJobId] = useState<number | null>(null)
  const [exportJobId, setExportJobId] = useState<number | null>(null)
  const [inspectedGame, setInspectedGame] = useState<Game | null>(null)
  const [rematchStatus, setRematchStatus] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const queryClient = useQueryClient()

  const rematchMutation = useMutation({
    mutationFn: rematchLibrary,
    onSuccess: (data) => {
      setRematchStatus(`✓ Updated ${data.updated} games using ${data.dats_loaded} loaded DATs!`)
      queryClient.invalidateQueries({ queryKey: ['games'] })
      queryClient.invalidateQueries({ queryKey: ['libraryStats'] })
      queryClient.invalidateQueries({ queryKey: ['filterOptions'] })
      setTimeout(() => setRematchStatus(null), 5000)
    },
    onError: () => {
      setRematchStatus('Failed to re-match library')
      setTimeout(() => setRematchStatus(null), 4000)
    },
  })

  const { data: gamesData, isLoading, isFetching } = useQuery({
    queryKey: ['games', filters, page],
    queryFn: () => fetchGames(filters, page, 60),
  })

  const { data: systems = [] } = useQuery({
    queryKey: ['systems'],
    queryFn: fetchSystems,
  })

  const { data: filterOptions } = useQuery({
    queryKey: ['filterOptions', filters],
    queryFn: () => fetchFilterOptions(filters),
  })

  const { data: stats } = useQuery({
    queryKey: ['libraryStats'],
    queryFn: fetchLibraryStats,
    refetchInterval: 30_000,
  })

  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [selectingAll, setSelectingAll] = useState(false)

  const clearMutation = useMutation({
    mutationFn: clearLibrary,
    onSuccess: () => {
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['games'] })
      queryClient.invalidateQueries({ queryKey: ['libraryStats'] })
      queryClient.invalidateQueries({ queryKey: ['filterOptions'] })
      setShowClearConfirm(false)
    },
  })

  // Debounced search
  const handleSearchChange = (val: string) => {
    setSearchInput(val)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => {
      setFilters(f => ({ ...f, search: val }))
      setPage(1)
    }, 400)
  }

  const handleFiltersChange = (updated: Partial<LibraryFilters>) => {
    setFilters(f => ({ ...f, ...updated }))
    setPage(1)
  }

  const handleSelectAll = async () => {
    if (!gamesData) return
    // If all matching games are already selected, deselect all
    if (selectedIds.size === total && total > 0) {
      setSelectedIds(new Set())
      return
    }
    // Select all matching games across ALL pages
    setSelectingAll(true)
    try {
      const allIds = await fetchAllGameIds(filters)
      setSelectedIds(new Set(allIds))
    } catch {
      setSelectedIds(new Set(gamesData.items.map(g => g.id)))
    } finally {
      setSelectingAll(false)
    }
  }

  const handleStartImport = async () => {
    const dirs = importDirs.split('\n').map(d => d.trim()).filter(Boolean)
    if (!dirs.length) return
    const job = await startImport(dirs)
    setImportJobId(job.id)
    setImportDirs('')
  }

  const games = gamesData?.items ?? []
  const total = gamesData?.total ?? 0
  const totalPages = Math.ceil(total / 60)

  return (
    <div className="flex h-full">
      {/* Filter sidebar */}
      {showFilters && (
        <FilterSidebar
          systems={systems}
          filterOptions={filterOptions}
          filters={filters}
          onChange={handleFiltersChange}
          onClose={() => setShowFilters(false)}
        />
      )}

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 bg-gray-900 flex-shrink-0">
          {!showFilters && (
            <button
              onClick={() => setShowFilters(true)}
              className="btn-secondary flex items-center gap-1 text-sm"
            >
              <SlidersHorizontal size={15} /> Filters
            </button>
          )}

          {/* Search */}
          <div className="relative flex-1 max-w-sm">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchInput}
              onChange={e => handleSearchChange(e.target.value)}
              placeholder="Search games..."
              className="input w-full pl-9 text-sm"
            />
            {searchInput && (
              <button
                onClick={() => handleSearchChange('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Stats */}
          <span className="text-sm text-gray-400 hidden md:block">
            {isFetching ? (
              <RefreshCw size={14} className="animate-spin inline mr-1" />
            ) : null}
            {total.toLocaleString()} games
            {stats && ` · ${stats.total_systems} systems`}
          </span>

          <div className="ml-auto flex items-center gap-2">
            {/* Quick Verified Toggle */}
            <button
              onClick={() => handleFiltersChange({ verified: filters.verified === 'verified' ? 'all' : 'verified' })}
              title="Toggle Verified ROMs (No-Intro / Redump Checksum Match)"
              className={clsx(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors',
                filters.verified === 'verified'
                  ? 'bg-green-950/70 border-green-700 text-green-300 shadow-sm'
                  : 'bg-gray-800/80 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600',
              )}
            >
              <ShieldCheck size={14} className={filters.verified === 'verified' ? 'text-green-400' : 'text-gray-500'} />
              <span>Verified Only</span>
            </button>

            {/* View toggle (Grid / List) */}
            <div className="flex rounded-lg overflow-hidden border border-gray-700 bg-gray-850 p-0.5">
              <button
                onClick={() => {
                  setViewMode('grid')
                  localStorage.setItem('romorganizer_view_mode', 'grid')
                }}
                title="Switch to Grid View (Cover Art)"
                className={clsx(
                  'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors',
                  viewMode === 'grid'
                    ? 'bg-brand-500 text-white shadow-sm'
                    : 'text-gray-400 hover:text-white hover:bg-gray-750',
                )}
              >
                <LayoutGrid size={14} />
                <span>Grid</span>
              </button>
              <button
                onClick={() => {
                  setViewMode('list')
                  localStorage.setItem('romorganizer_view_mode', 'list')
                }}
                title="Switch to List View (Table)"
                className={clsx(
                  'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors',
                  viewMode === 'list'
                    ? 'bg-brand-500 text-white shadow-sm'
                    : 'text-gray-400 hover:text-white hover:bg-gray-750',
                )}
              >
                <List size={14} />
                <span>List</span>
              </button>
            </div>

            {/* Re-Match DATs */}
            <button
              onClick={() => rematchMutation.mutate()}
              disabled={rematchMutation.isPending}
              title="Re-scan loaded DAT files and update matching game names in your library"
              className="btn-secondary flex items-center gap-1.5 text-sm"
            >
              <RefreshCw size={14} className={rematchMutation.isPending ? 'animate-spin text-brand-400' : ''} />
              <span>{rematchMutation.isPending ? 'Re-matching…' : 'Re-Match'}</span>
            </button>

            {/* Import */}
            <ImportButton onImport={handleStartImport} dirs={importDirs} setDirs={setImportDirs} />

            {/* Clear Library */}
            <button
              onClick={() => setShowClearConfirm(true)}
              disabled={clearMutation.isPending || total === 0}
              title="Clear all games from library"
              className="btn-secondary flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-950/30 border-red-900/30"
            >
              <Trash2 size={14} className={clearMutation.isPending ? 'animate-spin' : ''} />
              <span>Clear</span>
            </button>

            {/* Export */}
            <button
              onClick={() => setShowExport(true)}
              disabled={selectedIds.size === 0}
              className="btn-primary flex items-center gap-1.5 text-sm"
            >
              <Download size={15} />
              Export {selectedIds.size > 0 && `(${selectedIds.size.toLocaleString()})`}
            </button>
          </div>
        </div>

        {/* Clear Library Confirmation Dialog */}
        {showClearConfirm && (
          <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="card p-6 max-w-md w-full border border-red-900/50 shadow-2xl">
              <div className="flex items-center gap-3 text-red-400 mb-3">
                <Trash2 size={24} />
                <h3 className="text-lg font-semibold text-white">Clear Entire Library?</h3>
              </div>
              <p className="text-sm text-gray-300 mb-6 leading-relaxed">
                This will remove all {total.toLocaleString()} indexed games and clear the library storage so you can start a completely fresh session. Your original ROM source folders are untouched.
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowClearConfirm(false)}
                  disabled={clearMutation.isPending}
                  className="btn-secondary text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => clearMutation.mutate()}
                  disabled={clearMutation.isPending}
                  className="btn-danger text-sm flex items-center gap-2"
                >
                  {clearMutation.isPending ? <RefreshCw size={14} className="animate-spin" /> : <Trash2 size={14} />}
                  <span>{clearMutation.isPending ? 'Clearing…' : 'Yes, Clear Everything'}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Re-match Status Alert Banner */}
        {rematchStatus && (
          <div className="flex items-center gap-2 px-4 py-2 bg-green-950/60 border-b border-green-700/50 text-green-300 text-xs font-medium">
            <CheckCircle2 size={14} className="text-green-400 flex-shrink-0" />
            <span>{rematchStatus}</span>
            <button onClick={() => setRematchStatus(null)} className="ml-auto text-green-400 hover:text-white">
              <X size={14} />
            </button>
          </div>
        )}

        {/* Selection bar */}
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-3 px-4 py-2 bg-brand-500/15 border-b border-brand-500/30 text-sm">
            <span className="text-brand-300 font-medium">
              {selectedIds.size === total && total > 0
                ? `✓ All ${total.toLocaleString()} games across all pages selected`
                : `${selectedIds.size.toLocaleString()} selected`}
            </span>
            {selectedIds.size < total && (
              <button
                onClick={handleSelectAll}
                disabled={selectingAll}
                className="text-brand-400 hover:text-brand-200 underline font-medium text-xs ml-1"
              >
                {selectingAll ? 'Selecting all…' : `Select all ${total.toLocaleString()} games across all pages`}
              </button>
            )}
            <button
              onClick={() => setSelectedIds(new Set())}
              className="ml-auto text-xs text-gray-400 hover:text-white flex items-center gap-1 bg-gray-800/60 px-2 py-1 rounded"
            >
              <span>Clear selection</span>
              <X size={13} />
            </button>
          </div>
        )}

        {/* Game list / grid */}
        <div className="flex-1 overflow-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>
          ) : games.length === 0 ? (
            <EmptyState />
          ) : viewMode === 'grid' ? (
            <GameGrid
              games={games}
              selectedIds={selectedIds}
              onSelectionChange={setSelectedIds}
              onInspect={setInspectedGame}
            />
          ) : (
            <GameTable
              games={games}
              selectedIds={selectedIds}
              onSelectionChange={setSelectedIds}
              onSortChange={(col, dir) => handleFiltersChange({ sort_by: col, sort_dir: dir })}
              sortBy={filters.sort_by}
              sortDir={filters.sort_dir}
              onInspect={setInspectedGame}
              onSelectAllMatching={handleSelectAll}
              totalMatching={total}
            />
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 py-3 border-t border-gray-800 bg-gray-900">
            <button
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
              className="btn-secondary text-sm px-3 py-1 disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-sm text-gray-400">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page === totalPages}
              onClick={() => setPage(p => p + 1)}
              className="btn-secondary text-sm px-3 py-1 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Game Details Inspector Modal */}
      {inspectedGame && (
        <GameDetailModal
          game={inspectedGame}
          onClose={() => setInspectedGame(null)}
        />
      )}

      {/* Export panel */}
      {showExport && (
        <ExportPanel
          selectedIds={Array.from(selectedIds)}
          onClose={() => setShowExport(false)}
          onExportStarted={(jobId) => {
            setExportJobId(jobId)
            setShowExport(false)
          }}
        />
      )}

      {/* Progress toasts */}
      {importJobId && (
        <ProgressToast
          type="import"
          jobId={importJobId}
          onDone={() => {
            setImportJobId(null)
            queryClient.invalidateQueries({ queryKey: ['games'] })
            queryClient.invalidateQueries({ queryKey: ['libraryStats'] })
            queryClient.invalidateQueries({ queryKey: ['filterOptions'] })
          }}
        />
      )}
      {exportJobId && (
        <ProgressToast
          type="export"
          jobId={exportJobId}
          onDone={() => setExportJobId(null)}
        />
      )}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center text-gray-500 text-sm">
      <p>No games in library or matching active filters.</p>
    </div>
  )
}

function ImportButton({
  onImport,
  dirs,
  setDirs,
}: {
  onImport: () => void
  dirs: string
  setDirs: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [picking, setPicking] = useState(false)

  const handleBrowse = async () => {
    setPicking(true)
    try {
      const selected = await pickDirectory('Select ROM Directory to Import')
      if (selected) {
        const next = dirs.trim() ? `${dirs.trim()}\n${selected}` : selected
        setDirs(next)
        localStorage.setItem('romorganizer_last_import_dir', next)
      }
    } finally {
      setPicking(false)
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="btn-secondary flex items-center gap-1.5 text-sm"
      >
        <Upload size={15} /> Import
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 card p-4 z-50 shadow-2xl">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-white">Import ROM Directories</p>
            <button
              onClick={handleBrowse}
              disabled={picking}
              className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1 bg-brand-500/10 px-2 py-1 rounded border border-brand-500/20"
            >
              {picking ? <span className="animate-spin">⟳</span> : <FolderOpen size={13} />}
              Select Folder…
            </button>
          </div>
          <p className="text-xs text-gray-400 mb-2">
            Select a folder using the dialog or enter one directory path per line (read-only):
          </p>
          <textarea
            value={dirs}
            onChange={e => {
              setDirs(e.target.value)
              localStorage.setItem('romorganizer_last_import_dir', e.target.value)
            }}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            className="input w-full text-sm font-mono h-28 resize-none mb-2"
            placeholder="/path/to/roms&#10;/another/path"
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => { onImport(); setOpen(false) }}
              disabled={!dirs.trim()}
              className="btn-primary flex-1 text-sm"
            >
              Start Import
            </button>
            <button
              onClick={() => setOpen(false)}
              className="btn-secondary text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
