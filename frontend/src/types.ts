/** Shared TypeScript types for the RomOrganizer frontend. */

export interface RomFile {
  id: number
  library_path: string
  original_filename: string
  file_format: string
  crc32?: string
  md5?: string
  sha1?: string
  file_size?: number
  dat_matched: boolean
}

export interface Game {
  id: number
  title: string
  sort_title?: string
  system_id: number
  system_name: string
  system_esde_folder: string
  region?: string
  languages?: string
  series?: string
  genre?: string
  publisher?: string
  developer?: string
  release_year?: number
  description?: string
  cover_art_path?: string
  screenshot_path?: string
  no_intro_name?: string
  rating?: number
  players?: number
  rom_files: RomFile[]
}

export interface GamesResponse {
  total: number
  page: number
  page_size: number
  items: Game[]
}

export interface System {
  id: number
  name: string
  esde_folder: string
  extensions: string
  manufacturer?: string
  release_year?: number
}

export interface FilterOptions {
  genres: string[]
  regions: string[]
  series: string[]
  years: number[]
}

export interface LibraryFilters {
  search: string
  system_ids: number[]
  languages: string[]
  regions: string[]
  genres: string[]
  series: string
  year_min?: number
  year_max?: number
  sort_by: string
  sort_dir: 'asc' | 'desc'
}

export interface ImportJob {
  id: number
  status: string
  total_files: number
  processed_files: number
  imported_games: number
  skipped_duplicates: number
  errors: number
}

export interface ExportJob {
  id: number
  export_dir: string
  output_format: string
  dedup_mode: string
  lang_priority: string
  status: string
  total_games: number
  exported_games: number
  skipped_games: number
  errors: number
}

export interface ExportOptions {
  game_ids: number[]
  export_dir: string
  output_format: 'original' | 'zip' | '7z'
  dedup_mode: 'single' | 'all'
  lang_priority: string
}
