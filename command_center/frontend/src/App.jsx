import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ControlTower from './pages/ControlTower'
import Positions from './pages/Positions'
import AIModel from './pages/AIModel'
import News from './pages/News'
import NewsAnalytics from './pages/NewsAnalytics'
import Logs from './pages/Logs'
import Overview from './pages/Overview'
import Symbols from './pages/Symbols'
import Models from './pages/Models'
import Experiments from './pages/Experiments'
import Backtest from './pages/Backtest'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/control-tower" replace />} />
        <Route path="control-tower" element={<ControlTower />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="overview" element={<Overview />} />
        <Route path="symbols" element={<Symbols />} />
        <Route path="models" element={<Models />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="positions" element={<Positions />} />
        <Route path="ai" element={<AIModel />} />
        <Route path="experiments" element={<Experiments />} />
        <Route path="news" element={<News />} />
        <Route path="news-analytics" element={<NewsAnalytics />} />
        <Route path="logs" element={<Logs />} />
      </Route>
    </Routes>
  )
}
