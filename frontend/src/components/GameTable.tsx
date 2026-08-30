import type { Game } from '../types'
import clsx from 'clsx'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'

interface Props {
  games: Game[]
  selectedIds: Set<number>
  onSelectionChange: (ids: Set<number>) => void
  sortBy: string
  sortDir: 'asc' | 'desc'
  onSortChange: (col: string, dir: 'asc' | 'desc') => void
}

const COLUMNS: { key: string; label: string; width?: string }[] = [
  { key: 'sort_title', label: 'Title' },
  { key: 'system_id', label: 'System', width: 'w-32' },
  { key: 'release_year', label: 'Year', width: 'w-20' },
  { key: '', label: 'Region', width: 'w-28' },
  { key: '', label: 'Languages', width: 'w-28' },
  { key: '', label: 'Genre', width: 'w-36' },
]

export default function GameTable({
  games, selectedIds, onSelectionChange, sortBy, sortDir, onSortChange,
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
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="border-b border-gray-800 bg-gray-900 text-left text-xs text-gray-400 uppercase tracking-wide">
            <th className="w-10 px-3 py-2">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                className="accent-brand-500"
              />
            </th>
            {COLUMNS.map(col => (
              <th
                key={col.key || col.label}
                className={clsx('px-3 py-2 font-medium', col.width, col.key && 'cursor-pointer hover:text-gray-200')}
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
        <tbody>
          {games.map((game, i) => (
            <tr
              key={game.id}
              onClick={() => toggle(game.id)}
              className={clsx(
                'border-b border-gray-800/50 cursor-pointer transition-colors',
                selectedIds.has(game.id)
                  ? 'bg-brand-500/10'
                  : i % 2 === 0
                  ? 'bg-gray-900/30 hover:bg-gray-800/50'
                  : 'hover:bg-gray-800/50',
              )}
            >
              <td className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={selectedIds.has(game.id)}
                  onChange={() => toggle(game.id)}
                  onClick={e => e.stopPropagation()}
                  className="accent-brand-500"
                />
              </td>
              <td className="px-3 py-2 font-medium text-gray-100 max-w-xs">
                <span className="truncate block" title={game.title}>{game.title}</span>
              </td>
              <td className="px-3 py-2 text-gray-400">
                <span className="badge bg-gray-800 text-gray-300">{game.system_esde_folder}</span>
              </td>
              <td className="px-3 py-2 text-gray-400">{game.release_year ?? '—'}</td>
              <td className="px-3 py-2 text-gray-400">{game.region ?? '—'}</td>
              <td className="px-3 py-2 text-gray-400">{game.languages ?? '—'}</td>
              <td className="px-3 py-2 text-gray-400 truncate max-w-[9rem]">{game.genre ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
