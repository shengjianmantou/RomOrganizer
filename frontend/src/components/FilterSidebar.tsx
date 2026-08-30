import { useState } from 'react'
import { X, ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react'
import clsx from 'clsx'
import type { FilterOptions, LibraryFilters, System } from '../types'

interface Props {
  systems: System[]
  filterOptions?: FilterOptions
  filters: LibraryFilters
  onChange: (updated: Partial<LibraryFilters>) => void
  onClose: () => void
}

export default function FilterSidebar({ systems, filterOptions, filters, onChange, onClose }: Props) {
  return (
    <div className="w-60 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-sm font-semibold text-gray-200">Filters</span>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {/* Reset */}
        <button
          onClick={() => onChange({ system_ids: [], languages: [], regions: [], genres: [], series: '', verified: 'all' })}
          className="text-xs text-brand-400 hover:text-brand-300 mb-2"
        >
          Reset all filters
        </button>

        {/* Verification Status */}
        <FilterSection title="Status">
          <div className="space-y-1">
            {[
              { id: 'all', label: 'All Games' },
              { id: 'verified', label: '🛡️ Verified Only' },
              { id: 'unverified', label: 'Unverified / Custom' },
            ].map(item => (
              <label
                key={item.id}
                className={clsx(
                  'flex items-center gap-2 text-xs py-1 px-1.5 rounded cursor-pointer transition-colors',
                  (filters.verified || 'all') === item.id
                    ? 'bg-brand-500/20 text-white font-medium'
                    : 'text-gray-300 hover:text-white hover:bg-gray-800',
                )}
              >
                <input
                  type="radio"
                  name="verified_status"
                  value={item.id}
                  checked={(filters.verified || 'all') === item.id}
                  onChange={() => onChange({ verified: item.id as 'all' | 'verified' | 'unverified' })}
                  className="accent-brand-500"
                />
                <span>{item.label}</span>
              </label>
            ))}
          </div>
        </FilterSection>

        {/* Systems */}
        <FilterSection title="System">
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {systems.map(sys => (
              <label key={sys.id} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer hover:text-white">
                <input
                  type="checkbox"
                  className="accent-brand-500"
                  checked={filters.system_ids.includes(sys.id)}
                  onChange={e => {
                    const next = e.target.checked
                      ? [...filters.system_ids, sys.id]
                      : filters.system_ids.filter(id => id !== sys.id)
                    onChange({ system_ids: next })
                  }}
                />
                <span className="truncate">{sys.name}</span>
              </label>
            ))}
          </div>
        </FilterSection>

        {/* Language */}
        <FilterSection title="Language">
          <div className="flex flex-wrap gap-1.5">
            {['En', 'Zh', 'Ja', 'Fr', 'De', 'Es', 'It', 'Pt', 'Ko', 'Ru'].map(lang => (
              <button
                key={lang}
                onClick={() => {
                  const next = filters.languages.includes(lang)
                    ? filters.languages.filter(l => l !== lang)
                    : [...filters.languages, lang]
                  onChange({ languages: next })
                }}
                className={clsx(
                  'badge text-xs cursor-pointer transition-colors',
                  filters.languages.includes(lang)
                    ? 'bg-brand-500 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700',
                )}
              >
                {lang}
              </button>
            ))}
          </div>
        </FilterSection>

        {/* Region */}
        {filterOptions?.regions && filterOptions.regions.length > 0 && (
          <FilterSection title="Region">
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {filterOptions.regions.map(region => (
                <label key={region} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    className="accent-brand-500"
                    checked={filters.regions.includes(region)}
                    onChange={e => {
                      const next = e.target.checked
                        ? [...filters.regions, region]
                        : filters.regions.filter(r => r !== region)
                      onChange({ regions: next })
                    }}
                  />
                  {region}
                </label>
              ))}
            </div>
          </FilterSection>
        )}

        {/* Genre */}
        {filterOptions?.genres && filterOptions.genres.length > 0 && (
          <FilterSection title="Genre">
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {filterOptions.genres.map(genre => (
                <label key={genre} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer hover:text-white">
                  <input
                    type="checkbox"
                    className="accent-brand-500"
                    checked={filters.genres.includes(genre)}
                    onChange={e => {
                      const next = e.target.checked
                        ? [...filters.genres, genre]
                        : filters.genres.filter(g => g !== genre)
                      onChange({ genres: next })
                    }}
                  />
                  <span className="truncate">{genre}</span>
                </label>
              ))}
            </div>
          </FilterSection>
        )}

        {/* Series */}
        {filterOptions?.series && filterOptions.series.length > 0 && (
          <FilterSection title="Series">
            <select
              value={filters.series}
              onChange={e => onChange({ series: e.target.value })}
              className="input w-full text-sm"
            >
              <option value="">All series</option>
              {filterOptions.series.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </FilterSection>
        )}

        {/* Year range */}
        {filterOptions?.years && filterOptions.years.length > 0 && (
          <FilterSection title="Release Year">
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder={String(filterOptions.years[0])}
                value={filters.year_min ?? ''}
                onChange={e => onChange({ year_min: e.target.value ? Number(e.target.value) : undefined })}
                className="input w-full text-sm"
                min={filterOptions.years[0]}
                max={filterOptions.years[filterOptions.years.length - 1]}
              />
              <span className="text-gray-500">–</span>
              <input
                type="number"
                placeholder={String(filterOptions.years[filterOptions.years.length - 1])}
                value={filters.year_max ?? ''}
                onChange={e => onChange({ year_max: e.target.value ? Number(e.target.value) : undefined })}
                className="input w-full text-sm"
                min={filterOptions.years[0]}
                max={filterOptions.years[filterOptions.years.length - 1]}
              />
            </div>
          </FilterSection>
        )}
      </div>
    </div>
  )
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="border-b border-gray-800 pb-3">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center justify-between w-full py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider hover:text-gray-200"
      >
        {title}
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>
      {open && <div className="mt-1">{children}</div>}
    </div>
  )
}
