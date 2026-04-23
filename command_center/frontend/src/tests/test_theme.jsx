import { render, act } from '@testing-library/react'
import { describe, test, expect, beforeEach } from 'vitest'
import ThemeProvider, { useTheme, THEMES } from '../theme/ThemeProvider'

function Consumer({ onReady }) {
  const ctx = useTheme()
  onReady?.(ctx)
  return <div data-testid="current-theme">{ctx.theme}</div>
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  test('wraps children and provides default theme', () => {
    const { getByTestId } = render(
      <ThemeProvider>
        <Consumer />
      </ThemeProvider>,
    )
    expect(getByTestId('current-theme').textContent).toBe('default')
  })

  test('exposes all three themes: default, matrix, cyberpunk', () => {
    expect(Object.keys(THEMES).sort()).toEqual(['cyberpunk', 'default', 'matrix'])
  })

  test('switches to matrix theme and applies data-theme attribute', () => {
    let ctx
    render(
      <ThemeProvider>
        <Consumer onReady={(c) => (ctx = c)} />
      </ThemeProvider>,
    )
    act(() => {
      ctx.setTheme('matrix')
    })
    expect(document.documentElement.getAttribute('data-theme')).toBe('matrix')
  })

  test('switches to cyberpunk theme', () => {
    let ctx
    render(
      <ThemeProvider>
        <Consumer onReady={(c) => (ctx = c)} />
      </ThemeProvider>,
    )
    act(() => {
      ctx.setTheme('cyberpunk')
    })
    expect(document.documentElement.getAttribute('data-theme')).toBe('cyberpunk')
  })

  test('persists theme in localStorage', () => {
    let ctx
    render(
      <ThemeProvider>
        <Consumer onReady={(c) => (ctx = c)} />
      </ThemeProvider>,
    )
    act(() => ctx.setTheme('matrix'))
    expect(localStorage.getItem('theme')).toBe('matrix')
  })

  test('ignores unknown theme names', () => {
    let ctx
    render(
      <ThemeProvider>
        <Consumer onReady={(c) => (ctx = c)} />
      </ThemeProvider>,
    )
    act(() => ctx.setTheme('unknown_theme'))
    expect(ctx.theme).toBe('default')
  })

  test('applies CSS variables for active theme', () => {
    let ctx
    render(
      <ThemeProvider>
        <Consumer onReady={(c) => (ctx = c)} />
      </ThemeProvider>,
    )
    act(() => ctx.setTheme('matrix'))
    const bg = document.documentElement.style.getPropertyValue('--theme-bg')
    expect(bg).toBe('#000000')
  })
})
