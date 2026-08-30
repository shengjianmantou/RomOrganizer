import { Routes, Route, NavLink } from 'react-router-dom'
import { Library, Settings, Gamepad2, LayoutGrid } from 'lucide-react'
import LibraryPage from './pages/LibraryPage'
import SettingsPage from './pages/SettingsPage'
import clsx from 'clsx'

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <nav className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-5 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <Gamepad2 className="text-brand-400" size={22} />
            <span className="font-bold text-lg text-white tracking-tight">RomOrganizer</span>
          </div>
        </div>
        <div className="flex-1 p-3 space-y-1">
          <NavItem to="/" icon={<LayoutGrid size={18} />} label="Library" />
          <NavItem to="/settings" icon={<Settings size={18} />} label="Settings" />
        </div>
        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-500">
          v0.1.0
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-950">
        <Routes>
          <Route path="/" element={<LibraryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}

function NavItem({
  to,
  icon,
  label,
}: {
  to: string
  icon: React.ReactNode
  label: string
}) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          isActive
            ? 'bg-brand-500/20 text-brand-300'
            : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100',
        )
      }
    >
      {icon}
      {label}
    </NavLink>
  )
}
