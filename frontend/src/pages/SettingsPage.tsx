import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, RefreshCw, Database, Key } from 'lucide-react'
import { fetchSettings, updateSettings } from '../hooks/api'

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  })

  const [form, setForm] = useState({
    screenscraper_user: '',
    screenscraper_password: '',
    thegamesdb_api_key: '',
    igdb_client_id: '',
    igdb_client_secret: '',
    scrape_on_import: true,
  })

  const [saved, setSaved] = useState(false)

  // Populate form when settings load
  useState(() => {
    if (settings) {
      setForm({
        screenscraper_user: settings.screenscraper_user ?? '',
        screenscraper_password: '',
        thegamesdb_api_key: '',
        igdb_client_id: settings.igdb_client_id ?? '',
        igdb_client_secret: '',
        scrape_on_import: settings.scrape_on_import ?? true,
      })
    }
  })

  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      setSaved(true)
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const handleSave = () => {
    mutation.mutate(form)
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Metadata sources */}
      <section className="card p-5 space-y-5">
        <div className="flex items-center gap-2 mb-2">
          <Key size={16} className="text-brand-400" />
          <h2 className="text-base font-semibold text-white">Metadata API Credentials</h2>
        </div>

        <p className="text-sm text-gray-400">
          Enter your API credentials to enable automatic metadata and cover art fetching during import.
          Credentials are stored locally in the library database.
        </p>

        {/* ScreenScraper */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-300 border-b border-gray-800 pb-1">
            ScreenScraper{' '}
            <a href="https://www.screenscraper.fr" target="_blank" rel="noreferrer"
               className="text-brand-400 hover:underline font-normal text-xs">
              (get free account →)
            </a>
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Username</label>
              <input
                type="text"
                value={form.screenscraper_user}
                onChange={e => setForm(f => ({ ...f, screenscraper_user: e.target.value }))}
                className="input w-full text-sm"
                placeholder="your_username"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Password</label>
              <input
                type="password"
                value={form.screenscraper_password}
                onChange={e => setForm(f => ({ ...f, screenscraper_password: e.target.value }))}
                className="input w-full text-sm"
                placeholder={settings?.screenscraper_password === '***' ? '(saved)' : 'password'}
              />
            </div>
          </div>
        </div>

        {/* TheGamesDB */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-300 border-b border-gray-800 pb-1">
            TheGamesDB{' '}
            <a href="https://thegamesdb.net" target="_blank" rel="noreferrer"
               className="text-brand-400 hover:underline font-normal text-xs">
              (get API key →)
            </a>
          </h3>
          <div>
            <label className="block text-xs text-gray-400 mb-1">API Key</label>
            <input
              type="password"
              value={form.thegamesdb_api_key}
              onChange={e => setForm(f => ({ ...f, thegamesdb_api_key: e.target.value }))}
              className="input w-full text-sm"
              placeholder={settings?.thegamesdb_api_key === '***' ? '(saved)' : 'your-api-key'}
            />
          </div>
        </div>

        {/* Scrape on import toggle */}
        <label className="flex items-center gap-3 cursor-pointer group">
          <div
            onClick={() => setForm(f => ({ ...f, scrape_on_import: !f.scrape_on_import }))}
            className={`relative w-10 h-5 rounded-full transition-colors ${
              form.scrape_on_import ? 'bg-brand-500' : 'bg-gray-700'
            }`}
          >
            <div className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
              form.scrape_on_import ? 'translate-x-5' : ''
            }`} />
          </div>
          <div>
            <p className="text-sm text-gray-200 group-hover:text-white">Scrape metadata on import</p>
            <p className="text-xs text-gray-500">Automatically fetch cover art and game info when importing ROMs.</p>
          </div>
        </label>
      </section>

      {/* DAT files */}
      <section className="card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-brand-400" />
          <h2 className="text-base font-semibold text-white">No-Intro DAT Files</h2>
        </div>

        <p className="text-sm text-gray-400">
          Place No-Intro DAT XML files in the <code className="text-gray-300 bg-gray-800 px-1 rounded">dat_files/</code> directory
          next to the app. Download them from{' '}
          <a href="https://www.no-intro.org" target="_blank" rel="noreferrer"
             className="text-brand-400 hover:underline">
            no-intro.org
          </a>{' '}
          (free account required).
        </p>

        {settings?.dat_stats && (
          <div className="bg-gray-800 rounded-lg p-3 text-sm space-y-1">
            <p className="text-gray-300">
              <span className="text-white font-medium">{settings.dat_stats.loaded_dats}</span> DAT files loaded
            </p>
            <p className="text-gray-300">
              <span className="text-white font-medium">{settings.dat_stats.sha1_entries?.toLocaleString()}</span> SHA1 entries indexed
            </p>
          </div>
        )}
      </section>

      {/* Save */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {mutation.isPending ? <RefreshCw size={15} className="animate-spin" /> : <Save size={15} />}
          Save Settings
        </button>
        {saved && <span className="text-sm text-green-400">✓ Saved</span>}
        {mutation.isError && <span className="text-sm text-red-400">Failed to save</span>}
      </div>
    </div>
  )
}
