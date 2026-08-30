import type { Game } from '../types'
import clsx from 'clsx'
import { Gamepad2, Info, ShieldCheck } from 'lucide-react'

interface Props {
  games: Game[]
  selectedIds: Set<number>
  onSelectionChange: (ids: Set<number>) => void
  onInspect?: (game: Game) => void
}

export default function GameGrid({ games, selectedIds, onSelectionChange, onInspect }: Props) {
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
          onInspect={onInspect ? () => onInspect(game) : undefined}
        />
      ))}
    </div>
  )
}

function GameCard({
  game,
  selected,
  onToggle,
  onInspect,
}: {
  game: Game
  selected: boolean
  onToggle: () => void
  onInspect?: () => void
}) {
  const coverUrl = game.cover_art_path ? `/media/${game.cover_art_path}` : null
  const isVerified = Boolean(game.no_intro_name) || Boolean(game.rom_files?.[0]?.dat_matched)

  return (
    <div
      onClick={onToggle}
      className={clsx(
        'group relative rounded-xl overflow-hidden cursor-pointer transition-all duration-150',
        'border-2 bg-gray-900',
        selected
          ? 'border-brand-400 shadow-lg shadow-brand-500/20'
          : 'border-gray-800/80 hover:border-gray-600',
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

        {/* Verified badge */}
        {isVerified && (
          <div className="absolute top-1.5 left-1.5 z-10" title={`Verified Dump: ${game.no_intro_name || game.title}`}>
            <span className="badge bg-green-950/80 text-green-400 border border-green-700/60 text-[9px] px-1 py-0.5 shadow flex items-center gap-0.5">
              <ShieldCheck size={10} /> Verified
            </span>
          </div>
        )}

        {/* Details info button */}
        {onInspect && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onInspect()
            }}
            title="View full official details & checksums"
            className="absolute top-1.5 right-1.5 z-10 p-1 rounded-full bg-black/60 hover:bg-black text-gray-300 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Info size={13} />
          </button>
        )}

        {/* Selection overlay */}
        {selected && (
          <div className="absolute inset-0 bg-brand-500/20 flex items-start justify-end p-1.5">
            <div className="w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center shadow">
              <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        )}

        {/* System badge */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent px-2 py-1 flex items-center justify-between">
          <span className="text-[10px] font-bold text-gray-300 tracking-wide font-mono">
            {game.system_esde_folder.toUpperCase()}
          </span>
          {game.release_year && (
            <span className="text-[10px] text-gray-400">{game.release_year}</span>
          )}
        </div>
      </div>

      {/* Official Title Info */}
      <div className="p-2">
        <p className="text-xs font-semibold text-gray-100 truncate leading-snug" title={game.title}>
          {game.title}
        </p>
        <div className="flex items-center justify-between gap-1 mt-1 text-[10px] text-gray-400">
          <span className="truncate">{game.region || 'World'}</span>
          {game.languages && (
            <span className="font-mono text-gray-500">{game.languages}</span>
          )}
        </div>
      </div>
    </div>
  )
}
