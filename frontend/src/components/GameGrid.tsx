import type { Game } from '../types'
import clsx from 'clsx'
import { Gamepad2 } from 'lucide-react'

interface Props {
  games: Game[]
  selectedIds: Set<number>
  onSelectionChange: (ids: Set<number>) => void
}

export default function GameGrid({ games, selectedIds, onSelectionChange }: Props) {
  const toggle = (id: number) => {
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelectionChange(next)
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-8 gap-3">
      {games.map(game => (
        <GameCard
          key={game.id}
          game={game}
          selected={selectedIds.has(game.id)}
          onToggle={() => toggle(game.id)}
        />
      ))}
    </div>
  )
}

function GameCard({
  game,
  selected,
  onToggle,
}: {
  game: Game
  selected: boolean
  onToggle: () => void
}) {
  const coverUrl = game.cover_art_path ? `/media/${game.cover_art_path}` : null

  return (
    <div
      onClick={onToggle}
      className={clsx(
        'group relative rounded-xl overflow-hidden cursor-pointer transition-all duration-150',
        'border-2',
        selected
          ? 'border-brand-400 shadow-lg shadow-brand-500/20'
          : 'border-transparent hover:border-gray-600',
      )}
    >
      {/* Cover art */}
      <div className="aspect-[3/4] bg-gray-800 relative">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={game.title}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <Gamepad2 size={36} className="text-gray-600" />
          </div>
        )}

        {/* Selection overlay */}
        {selected && (
          <div className="absolute inset-0 bg-brand-500/20 flex items-start justify-end p-1.5">
            <div className="w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center">
              <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        )}

        {/* System badge */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-xs text-gray-300">{game.system_esde_folder.toUpperCase()}</span>
        </div>
      </div>

      {/* Title */}
      <div className="p-1.5 bg-gray-900">
        <p className="text-xs font-medium text-gray-200 truncate leading-tight" title={game.title}>
          {game.title}
        </p>
        <div className="flex items-center gap-1 mt-0.5">
          {game.release_year && (
            <span className="text-xs text-gray-500">{game.release_year}</span>
          )}
          {game.region && (
            <span className="badge bg-gray-800 text-gray-400 text-[10px]">{game.region}</span>
          )}
        </div>
      </div>
    </div>
  )
}
