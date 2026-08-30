import type { Game } from '../types'
import clsx from 'clsx'
import { ChevronUp, ChevronDown, ChevronsUpDown, ShieldCheck, Info } from 'lucide-react'

interface Props {
  games: Game[]
  selectedIds: Set<number>
  onSelectionChange: (ids: Set<number>) => void
  sortBy: string
  sortDir: 'asc' | 'desc'
  onSortChange: (col: string, dir: 'asc' | 'desc') => void
  onInspect?: (game: Game) => void
}

const COLUMNS: { key: string; label: string; width?: string }[] = [
  { key: 'sort_title', label: 'Official Game Title' },
  { key: 'system_id', label: 'System', width: 'w-28' },
  { key: 'release_year', label: 'Year', width: 'w-20' },
  { key: '', label: 'Region', width: 'w-24' },
  { key: '', label: 'Languages', width: 'w-24' },
  { key: '', label: 'Genre', width: 'w-32' },
  { key: '', label: '', width: 'w-12' },
]

export default function GameTable({
  games, selectedIds, onSelectionChange, sortBy, sortDir, onSortChange, onInspect,
}: Props) {
  const allSelected = games.length > 0 && games.every(g => selectedIds.has(g.id))

  const toggle = (id: number) => {
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelectionChange(next)
  }

  const toggleAll = () => {
    if (allSelected) {
      const next = new Set(selectedIds)
      games.forEach(g => next.delete(g.id))
      onSelectionChange(next)
    } else {
      const next = new Set(selectedIds)
      games.forEach(g => next.add(g.id))
      onSelectionChange(next)
    }
  }

  const handleSort = (col: string) => {
    if (!col) return
    if (sortBy === col) {
      onSortChange(col, sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      onSortChange(col, 'asc')
    }
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-800 bg-gray-900/40">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="border-b border-gray-800 bg-gray-900 text-left text-xs text-gray-400 uppercase tracking-wide">
            <th className="w-10 px-3 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                className="accent-brand-500 rounded"
              />
            </th>
            {COLUMNS.map(col => (
              <th
                key={col.key || col.label}
                className={clsx('px-3 py-3 font-medium', col.width, col.key && 'cursor-pointer hover:text-gray-200')}
                onClick={() => handleSort(col.key)}
              >
                <span className="flex items-center gap-1">
                  {col.label}
                  {col.key && (
                    sortBy === col.key
                      ? sortDir === 'asc'
                        ? <ChevronUp size={13} />
                        : <ChevronDown size={13} />
                      : <ChevronsUpDown size={13} className="opacity-30" />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/60">
          {games.map((game, i) => {
            const isVerified = Boolean(game.no_intro_name) || Boolean(game.rom_files?.[0]?.dat_matched)
            const rawFilename = game.rom_files?.[0]?.original_filename

            return (
              <tr
                key={game.id}
                onClick={() => toggle(game.id)}
                className={clsx(
                  'cursor-pointer transition-colors group',
                  selectedIds.has(game.id)
                    ? 'bg-brand-500/10 hover:bg-brand-500/15'
                    : i % 2 === 0
                    ? 'bg-gray-900/20 hover:bg-gray-800/40'
                    : 'hover:bg-gray-800/40',
                )}
              >
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(game.id)}
                    onChange={() => toggle(game.id)}
                    onClick={e => e.stopPropagation()}
                    className="accent-brand-500 rounded"
                  />
                </td>
                <td className="px-3 py-2.5 max-w-sm">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-gray-100 truncate block" title={game.title}>
                      {game.title}
                    </span>
                    {isVerified && (
                      <span title={`Verified: ${game.no_intro_name || 'No-Intro DAT match'}`}>
                        <ShieldCheck size={14} className="text-green-400 flex-shrink-0" />
                      </span>
                    )}
                  </div>
                  {rawFilename && rawFilename !== game.title && (
                    <span className="text-[11px] text-gray-500 truncate block font-mono">
                      {rawFilename}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-gray-400">
                  <span className="badge bg-gray-800 text-brand-300 font-mono text-[11px] border border-gray-700">
                    {game.system_esde_folder.toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-gray-300 font-mono">{game.release_year ?? '—'}</td>
                <td className="px-3 py-2.5 text-gray-400">{game.region ?? '—'}</td>
                <td className="px-3 py-2.5 text-gray-400 font-mono text-xs">{game.languages ?? '—'}</td>
                <td className="px-3 py-2.5 text-gray-400 truncate max-w-[10rem]">{game.genre ?? '—'}</td>
                <td className="px-3 py-2.5 text-right">
                  {onInspect && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        onInspect(game)
                      }}
                      title="Inspect Game Details"
                      className="p-1 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    >
                      <Info size={15} />
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
