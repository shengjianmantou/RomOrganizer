import { X, CheckCircle, Gamepad2, FileText, Hash, ShieldCheck, Calendar, Globe, User, Tag } from 'lucide-react'
import type { Game } from '../types'

interface Props {
  game: Game | null
  onClose: () => void
}

export default function GameDetailModal({ game, onClose }: Props) {
  if (!game) return null

  const coverUrl = game.cover_art_path ? `/media/${game.cover_art_path}` : null
  const screenshotUrl = game.screenshot_path ? `/media/${game.screenshot_path}` : null
  const rom = game.rom_files?.[0]
  const isDatMatched = rom?.dat_matched || Boolean(game.no_intro_name)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="card w-full max-w-2xl bg-gray-900 border border-gray-800 shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 bg-gray-900/80">
          <div className="flex items-center gap-2 min-w-0">
            <Gamepad2 className="text-brand-400 flex-shrink-0" size={20} />
            <h2 className="font-bold text-lg text-white truncate" title={game.title}>
              {game.title}
            </h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
          {/* Main Info Box */}
          <div className="flex flex-col sm:flex-row gap-5">
            {/* Cover image */}
            <div className="w-36 sm:w-44 flex-shrink-0 aspect-[3/4] bg-gray-800 rounded-xl overflow-hidden relative border border-gray-700 flex items-center justify-center">
              {coverUrl ? (
                <img src={coverUrl} alt={game.title} className="w-full h-full object-cover" />
              ) : (
                <Gamepad2 size={48} className="text-gray-600" />
              )}
              <span className="absolute bottom-2 left-2 badge bg-black/80 text-brand-300 font-mono text-xs border border-brand-500/30">
                {game.system_esde_folder.toUpperCase()}
              </span>
            </div>

            {/* Quick Metadata */}
            <div className="flex-1 space-y-3">
              {/* Title & Official No-Intro Title */}
              <div>
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-1">
                  Official Canonical Name
                </span>
                <p className="text-base font-bold text-white">{game.title}</p>
                {game.no_intro_name && (
                  <div className="flex items-center gap-1.5 mt-1.5 text-xs text-green-400 bg-green-950/40 border border-green-800/50 px-2.5 py-1 rounded-md">
                    <ShieldCheck size={14} className="flex-shrink-0" />
                    <span className="font-mono truncate" title={game.no_intro_name}>
                      No-Intro: {game.no_intro_name}
                    </span>
                  </div>
                )}
              </div>

              {/* Tags grid */}
              <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                <div className="flex items-center gap-1.5 text-gray-300">
                  <Globe size={13} className="text-gray-500" />
                  <span>Region: <strong className="text-white">{game.region || 'Unknown'}</strong></span>
                </div>
                <div className="flex items-center gap-1.5 text-gray-300">
                  <Tag size={13} className="text-gray-500" />
                  <span>Languages: <strong className="text-white">{game.languages || '—'}</strong></span>
                </div>
                <div className="flex items-center gap-1.5 text-gray-300">
                  <Calendar size={13} className="text-gray-500" />
                  <span>Year: <strong className="text-white">{game.release_year || '—'}</strong></span>
                </div>
                <div className="flex items-center gap-1.5 text-gray-300">
                  <User size={13} className="text-gray-500" />
                  <span>Genre: <strong className="text-white">{game.genre || '—'}</strong></span>
                </div>
              </div>

              {(game.publisher || game.developer) && (
                <div className="text-xs text-gray-400 pt-1 space-y-0.5">
                  {game.publisher && <p>Publisher: <span className="text-gray-200">{game.publisher}</span></p>}
                  {game.developer && <p>Developer: <span className="text-gray-200">{game.developer}</span></p>}
                </div>
              )}
            </div>
          </div>

          {/* Description */}
          {game.description && (
            <div className="bg-gray-850 border border-gray-800/80 rounded-lg p-3.5 space-y-1">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
                Overview
              </span>
              <p className="text-xs text-gray-300 leading-relaxed max-h-36 overflow-y-auto">
                {game.description}
              </p>
            </div>
          )}

          {/* ROM & Checksum Details */}
          {rom && (
            <div className="border border-gray-800 bg-gray-950/60 rounded-lg p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-300 flex items-center gap-1.5 uppercase tracking-wider">
                  <FileText size={14} className="text-brand-400" /> File & Checksum Verification
                </span>
                {isDatMatched ? (
                  <span className="badge bg-green-500/20 text-green-400 border border-green-500/30 text-[10px] flex items-center gap-1">
                    <CheckCircle size={11} /> Verified Dump
                  </span>
                ) : (
                  <span className="badge bg-gray-800 text-gray-400 text-[10px]">
                    Filename Tag Match
                  </span>
                )}
              </div>

              <div className="space-y-1.5 text-xs">
                <div>
                  <span className="text-gray-500 block">Original File Name:</span>
                  <span className="font-mono text-gray-200 break-all">{rom.original_filename}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 font-mono text-[11px]">
                  {rom.crc32 && (
                    <div className="bg-gray-900 px-2 py-1.5 rounded border border-gray-800">
                      <span className="text-gray-500 block text-[10px]">CRC32</span>
                      <span className="text-brand-300 font-bold">{rom.crc32.toUpperCase()}</span>
                    </div>
                  )}
                  {rom.md5 && (
                    <div className="bg-gray-900 px-2 py-1.5 rounded border border-gray-800">
                      <span className="text-gray-500 block text-[10px]">MD5</span>
                      <span className="text-gray-300 truncate block" title={rom.md5}>{rom.md5}</span>
                    </div>
                  )}
                  {rom.sha1 && (
                    <div className="bg-gray-900 px-2 py-1.5 rounded border border-gray-800">
                      <span className="text-gray-500 block text-[10px]">SHA1</span>
                      <span className="text-gray-300 truncate block" title={rom.sha1}>{rom.sha1}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Screenshot */}
          {screenshotUrl && (
            <div>
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-2">
                In-Game Screenshot
              </span>
              <img
                src={screenshotUrl}
                alt="Screenshot"
                className="w-full rounded-lg border border-gray-800 max-h-56 object-cover"
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end px-5 py-3 border-t border-gray-800 bg-gray-900/50">
          <button onClick={onClose} className="btn-secondary text-sm px-4">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
