/** Axios API client instance and helper functions. */
import axios from 'axios'
import type {
  ExportJob, ExportOptions, FilterOptions, Game, GamesResponse,
  ImportJob, LibraryFilters, System,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

// ── Library ───────────────────────────────────────────────────────────────────

export async function fetchGames(
  filters: Partial<LibraryFilters>,
  page = 1,
  pageSize = 50,
): Promise<GamesResponse> {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  }
  if (filters.search) params.search = filters.search
  if (filters.system_ids?.length) params.system_ids = filters.system_ids.join(',')
  if (filters.languages?.length) params.languages = filters.languages.join(',')
  if (filters.regions?.length) params.regions = filters.regions.join(',')
  if (filters.genres?.length) params.genres = filters.genres.join(',')
  if (filters.series) params.series = filters.series
  if (filters.year_min != null) params.year_min = String(filters.year_min)
  if (filters.year_max != null) params.year_max = String(filters.year_max)
  if (filters.verified && filters.verified !== 'all') params.verified = filters.verified
  if (filters.sort_by) params.sort_by = filters.sort_by
  if (filters.sort_dir) params.sort_dir = filters.sort_dir
  const { data } = await api.get<GamesResponse>('/library/games', { params })
  return data
}

export async function fetchFilterOptions(filters?: Partial<LibraryFilters>): Promise<FilterOptions> {
  const params: Record<string, string> = {}
  if (filters) {
    if (filters.search) params.search = filters.search
    if (filters.system_ids?.length) params.system_ids = filters.system_ids.join(',')
    if (filters.languages?.length) params.languages = filters.languages.join(',')
    if (filters.regions?.length) params.regions = filters.regions.join(',')
    if (filters.genres?.length) params.genres = filters.genres.join(',')
    if (filters.series) params.series = filters.series
    if (filters.year_min != null) params.year_min = String(filters.year_min)
    if (filters.year_max != null) params.year_max = String(filters.year_max)
    if (filters.verified && filters.verified !== 'all') params.verified = filters.verified
  }
  const { data } = await api.get<FilterOptions>('/library/filters', { params })
  return data
}

export async function fetchLibraryStats() {
  const { data } = await api.get('/library/stats')
  return data
}

export async function fetchAllGameIds(filters?: Partial<LibraryFilters>): Promise<number[]> {
  const params: Record<string, string> = {}
  if (filters) {
    if (filters.search) params.search = filters.search
    if (filters.system_ids?.length) params.system_ids = filters.system_ids.join(',')
    if (filters.languages?.length) params.languages = filters.languages.join(',')
    if (filters.regions?.length) params.regions = filters.regions.join(',')
    if (filters.genres?.length) params.genres = filters.genres.join(',')
    if (filters.series) params.series = filters.series
    if (filters.year_min != null) params.year_min = String(filters.year_min)
    if (filters.year_max != null) params.year_max = String(filters.year_max)
    if (filters.verified && filters.verified !== 'all') params.verified = filters.verified
  }
  const { data } = await api.get<number[]>('/library/game-ids', { params })
  return data
}

export async function clearLibrary(): Promise<void> {
  await api.post('/library/clear')
}

export async function deleteGame(gameId: number): Promise<void> {
  await api.delete(`/library/games/${gameId}`)
}

// ── Systems ───────────────────────────────────────────────────────────────────

export async function fetchSystems(): Promise<System[]> {
  const { data } = await api.get<System[]>('/systems')
  return data
}

// ── Import ────────────────────────────────────────────────────────────────────

export async function startImport(sourceDirectories: string[]): Promise<ImportJob> {
  const { data } = await api.post<ImportJob>('/import', { source_directories: sourceDirectories })
  return data
}

export async function fetchImportJobs(): Promise<ImportJob[]> {
  const { data } = await api.get<ImportJob[]>('/import')
  return data
}

export async function fetchImportJob(jobId: number): Promise<ImportJob> {
  const { data } = await api.get<ImportJob>(`/import/${jobId}`)
  return data
}

// ── Export ────────────────────────────────────────────────────────────────────

export async function startExport(options: ExportOptions): Promise<ExportJob> {
  const { data } = await api.post<ExportJob>('/export', options)
  return data
}

export async function fetchExportJobs(): Promise<ExportJob[]> {
  const { data } = await api.get<ExportJob[]>('/export')
  return data
}

// ── Settings ──────────────────────────────────────────────────────────────────

export async function fetchSettings() {
  const { data } = await api.get('/settings')
  return data
}

export async function updateSettings(settings: Record<string, unknown>) {
  const { data } = await api.put('/settings', settings)
  return data
}

export async function rematchLibrary() {
  const { data } = await api.post('/library/rematch')
  return data
}

// ── Filesystem Dialog ─────────────────────────────────────────────────────────

export async function pickDirectory(prompt = 'Select Directory'): Promise<string | null> {
  const { data } = await api.post<{ path: string | null; canceled: boolean }>('/filesystem/pick-directory', { prompt })
  if (data.canceled || !data.path) return null
  return data.path
}

export default api
