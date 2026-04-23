# Session: Signal Board + Theme System

**Date:** 2026-04-13
**Goal:** Substituir Signal Radar por Signal Board (ticker panel) e implementar sistema de temas (Default/Matrix/Cyberpunk)

---

## What was done

### Signal Board
- Criado `SignalBoard.jsx` — painel tipo ticker/order book com lista vertical
- Grid 3 colunas: Symbol | Signal (badge com glow) | Confidence (barra + %)
- Ordenado por confidence DESC (sinais mais fortes no topo)
- Header com contagem: "Active Signals: 11" + breakdown BUY/SELL/HOLD
- Flash animation quando sinal muda de direcao
- Hover highlight nas linhas
- Usa mesmo endpoint `/api/predict/signals/radar` (ensemble-only)
- SignalRadar.jsx mantido no repo mas nao mais importado

### Theme System
- Criado `src/theme/ThemeProvider.jsx` com React Context
- 3 temas: Default (preserva visual atual), Matrix (verde neon, terminal), Cyberpunk (azul+roxo, glow)
- CSS variables: `--theme-bg`, `--theme-accent`, `--theme-text`, `--theme-buy/sell/hold`, etc.
- Toggle no header do Layout: `[ Default | Matrix | Cyberpunk ]`
- Persistencia via localStorage
- Aplicacao global: `.glass-card`, `.neon-border`, `.glass-panel` agora usam CSS vars com fallback
- Nova classe `.themed-card` para panels do Control Tower
- Sidebar, headings, DataStream migrados para theme vars

## Files created
- `command_center/frontend/src/theme/ThemeProvider.jsx`
- `command_center/frontend/src/components/control_tower/SignalBoard.jsx`

## Files modified
- `main.jsx` — ThemeProvider wrapping
- `Layout.jsx` — theme toggle header
- `Sidebar.jsx` — theme CSS vars
- `ControlTower.jsx` — SignalBoard + theme vars
- `Dashboard.jsx`, `Logs.jsx` — theme vars on headings
- `DataStream.jsx`, `AICorePanel.jsx`, `SessionPanel.jsx`, `WorldMap.jsx`, `LivePredictionChart.jsx`, `ControlTowerClock.jsx` — themed-card
- `index.css` — theme CSS vars, themed-card, signal-flash, sidebar hover

## Decisions made
- [010] Signal Board substitui Signal Radar (clareza > estetica)
- [011] Theme system via CSS variables + React Context

## What was learned
- CSS variables com fallback (`var(--theme-bg, #default)`) permitem migracao incremental — componentes nao migrados continuam funcionando
- `color-mix(in srgb, color 12%, transparent)` funciona para criar backgrounds translucidos a partir de cores dinamicas

## Next steps
- Migrar mais paginas para usar theme vars nos textos (Overview, Symbols, Models, etc.)
- Considerar adicionar mais temas (ex: Light mode para uso diurno)
- Testar performance com troca rapida de tema em todos os componentes
