import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useTheme, THEMES } from '../theme/ThemeProvider'

export default function Layout() {
  const { theme, setTheme } = useTheme()
  const isMatrix = theme === 'matrix'

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--theme-bg)' }}>
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar with theme toggle */}
        <header
          className="flex items-center justify-end px-6 py-2 shrink-0"
          style={{ borderBottom: '1px solid var(--theme-border)' }}
        >
          <div className="flex items-center gap-4">
            {isMatrix && (
              <div className="text-[11px] font-mono leading-tight uppercase tracking-[0.24em]" style={{ color: 'var(--theme-text)' }}>
                <div>AUTOTRADER v1.0</div>
                <div style={{ color: 'var(--theme-text-muted)' }}>SYSTEM: ONLINE</div>
              </div>
            )}
            <div className="flex items-center gap-1">
              <span className="text-[10px] uppercase tracking-wider mr-2" style={{ color: 'var(--theme-text-muted)' }}>
                Theme
              </span>
              {Object.entries(THEMES).map(([key, cfg]) => (
                <button
                  key={key}
                  onClick={() => setTheme(key)}
                  className={`theme-btn ${theme === key ? 'active' : ''}`}
                >
                  {cfg.name}
                </button>
              ))}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
