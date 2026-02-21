import { useState } from 'react'
import Header from './components/Header.jsx'
import FilterBar from './components/FilterBar.jsx'
import SignalTable from './components/SignalTable.jsx'
import PipelineButton from './components/PipelineButton.jsx'
import ScoreModal from './components/ScoreModal.jsx'
import { useSignals } from './hooks/useSignals.js'
import { usePipeline } from './hooks/usePipeline.js'

export default function App() {
  const [filters, setFilters] = useState({ region: '', domains: [], priority_tier: '' })
  const [sortKey, setSortKey] = useState('priority_tier')
  const [sortDir, setSortDir] = useState('desc')
  const [selectedSignal, setSelectedSignal] = useState(null)

  const { signals, loading, error, refresh } = useSignals()
  const { running, runPipeline } = usePipeline({ onComplete: refresh })

  const filtered = signals
    .filter(s => !filters.region || s.region === filters.region)
    .filter(s => !filters.domains?.length || filters.domains.includes(s.domain))
    .filter(s => !filters.priority_tier || s.priority_tier === filters.priority_tier)

  return (
    <div className="min-h-screen font-sans">
      <Header />

      <main className="px-4 py-5 md:px-6 md:py-8">
        <div className="mx-auto max-w-[1320px]">
          <div className="rounded-2xl border border-slate-700/70 bg-slate-900/50 backdrop-blur-md shadow-[0_24px_60px_rgba(2,6,23,0.5)]">
            <div className="px-5 py-5 border-b border-slate-700/80 flex flex-col gap-4 md:px-6">
              <PipelineButton
                running={running}
                onRun={() => runPipeline()}
                onRefresh={refresh}
              />
            </div>

            <FilterBar filters={filters} signals={signals} onChange={setFilters} />

            {loading && (
              <p className="text-center text-slate-300/80 text-sm py-16">Loading signals...</p>
            )}
            {error && (
              <p className="text-center text-red-300 text-sm py-16">Error loading signals: {error}</p>
            )}
            {!loading && !error && (
              <SignalTable
                signals={filtered}
                sortKey={sortKey}
                sortDir={sortDir}
                onToggleSort={key => {
                  if (sortKey === key) {
                    setSortDir(d => d === 'desc' ? 'asc' : 'desc')
                    return
                  }
                  setSortKey(key)
                  setSortDir('desc')
                }}
                onRowClick={setSelectedSignal}
                onRefresh={refresh}
              />
            )}
          </div>
        </div>
      </main>

      {selectedSignal && (
        <ScoreModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
      )}
    </div>
  )
}
