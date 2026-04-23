import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react'

const THEMES = {
  default: {
    name: 'Default',
    vars: {
      '--theme-bg': '#030712',
      '--theme-bg-secondary': '#0f172a',
      '--theme-bg-card': 'rgba(30, 41, 59, 0.7)',
      '--theme-bg-card-hover': 'rgba(30, 41, 59, 0.85)',
      '--theme-border': 'rgba(71, 85, 105, 0.4)',
      '--theme-border-hover': 'rgba(71, 85, 105, 0.6)',
      '--theme-neon': 'rgba(59, 130, 246, 0.3)',
      '--theme-neon-hover': 'rgba(59, 130, 246, 0.5)',
      '--theme-neon-glow': 'rgba(59, 130, 246, 0.1)',
      '--theme-text': '#f1f5f9',
      '--theme-text-secondary': '#cbd5e1',
      '--theme-text-muted': '#64748b',
      '--theme-accent': '#3b82f6',
      '--theme-accent-glow': 'rgba(59, 130, 246, 0.4)',
      '--theme-sidebar-bg': '#030712',
      '--theme-sidebar-border': '#1f2937',
      '--theme-sidebar-active': '#1f2937',
      '--theme-sidebar-hover': '#111827',
      '--theme-buy': '#22c55e',
      '--theme-sell': '#ef4444',
      '--theme-hold': '#6b7280',
      '--theme-font-data': '"JetBrains Mono", ui-monospace, monospace',
    },
  },
  matrix: {
    name: 'Matrix',
    vars: {
      '--theme-bg': '#000000',
      '--theme-bg-secondary': '#000000',
      '--theme-bg-card': '#000000',
      '--theme-bg-card-hover': '#020402',
      '--theme-border': 'rgba(0, 255, 65, 0.2)',
      '--theme-border-hover': 'rgba(0, 255, 65, 0.35)',
      '--theme-neon': 'rgba(0, 255, 65, 0.2)',
      '--theme-neon-hover': 'rgba(0, 255, 65, 0.35)',
      '--theme-neon-glow': 'rgba(0, 255, 65, 0.06)',
      '--theme-text': '#00ff41',
      '--theme-text-secondary': '#00d436',
      '--theme-text-muted': '#008f2a',
      '--theme-accent': '#00ff41',
      '--theme-accent-glow': 'rgba(0, 255, 65, 0.6)',
      '--theme-sidebar-bg': '#000000',
      '--theme-sidebar-border': 'rgba(0, 255, 65, 0.16)',
      '--theme-sidebar-active': 'rgba(0, 255, 65, 0.08)',
      '--theme-sidebar-hover': 'rgba(0, 255, 65, 0.04)',
      '--theme-buy': '#00ff41',
      '--theme-sell': '#00ff41',
      '--theme-hold': '#008f2a',
      '--theme-font-data': '"JetBrains Mono", "Fira Code", monospace',
    },
  },
  cyberpunk: {
    name: 'Cyberpunk',
    vars: {
      '--theme-bg': '#0a0014',
      '--theme-bg-secondary': '#0f0020',
      '--theme-bg-card': 'rgba(15, 0, 40, 0.75)',
      '--theme-bg-card-hover': 'rgba(25, 0, 60, 0.85)',
      '--theme-border': 'rgba(0, 212, 255, 0.2)',
      '--theme-border-hover': 'rgba(0, 212, 255, 0.4)',
      '--theme-neon': 'rgba(122, 0, 255, 0.3)',
      '--theme-neon-hover': 'rgba(122, 0, 255, 0.5)',
      '--theme-neon-glow': 'rgba(0, 212, 255, 0.1)',
      '--theme-text': '#e0e0ff',
      '--theme-text-secondary': '#a0a0d0',
      '--theme-text-muted': '#5a5a8a',
      '--theme-accent': '#00d4ff',
      '--theme-accent-glow': 'rgba(0, 212, 255, 0.4)',
      '--theme-sidebar-bg': '#0a0014',
      '--theme-sidebar-border': 'rgba(122, 0, 255, 0.2)',
      '--theme-sidebar-active': 'rgba(122, 0, 255, 0.15)',
      '--theme-sidebar-hover': 'rgba(122, 0, 255, 0.08)',
      '--theme-buy': '#22c55e',
      '--theme-sell': '#ff0055',
      '--theme-hold': '#5a5a8a',
      '--theme-font-data': '"JetBrains Mono", ui-monospace, monospace',
    },
  },
}

const ThemeContext = createContext(null)

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be inside ThemeProvider')
  return ctx
}

export { THEMES }

export default function ThemeProvider({ children }) {
  const [themeName, setThemeName] = useState(() => {
    try {
      return localStorage.getItem('theme') || 'default'
    } catch {
      return 'default'
    }
  })

  const setTheme = useCallback((name) => {
    if (THEMES[name]) {
      setThemeName(name)
      try { localStorage.setItem('theme', name) } catch {}
    }
  }, [])

  // Apply CSS variables to root
  useEffect(() => {
    const vars = THEMES[themeName]?.vars || THEMES.default.vars
    const root = document.documentElement
    for (const [key, value] of Object.entries(vars)) {
      root.style.setProperty(key, value)
    }
    root.setAttribute('data-theme', themeName)
  }, [themeName])

  const value = useMemo(() => ({
    theme: themeName,
    themeConfig: THEMES[themeName],
    setTheme,
    themes: THEMES,
  }), [themeName, setTheme])

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}
