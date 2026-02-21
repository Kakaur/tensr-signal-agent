import { useEffect, useState } from 'react'
import Header        from './components/Header.jsx'
import FilterBar     from './components/FilterBar.jsx'
import SignalTable   from './components/SignalTable.jsx'
import PipelineButton from './components/PipelineButton.jsx'
import ScoreModal    from './components/ScoreModal.jsx'
import BriefingModal from './components/BriefingModal.jsx'
import PipelineSettingsModal from './components/PipelineSettingsModal.jsx'
import { useSignals }  from './hooks/useSignals.js'
import { usePipeline } from './hooks/usePipeline.js'

export default function App() {
  const [filters, setFilters]             = useState({ region: '', domains: [], priority_tier: '' })
  const [sortKey, setSortKey]             = useState('priority_tier')
  const [sortDir, setSortDir]             = useState('desc')
  const [selectedSignal, setSelectedSignal] = useState(null)
  const [briefingOpen, setBriefingOpen]   = useState(false)
  const [settingsOpen, setSettingsOpen]   = useState(false)
  const [activeProfilePath, setActiveProfilePath] = useState(
    () => localStorage.getItem('tensr_active_profile_path') || ''
  )
  const [activeProfile, setActiveProfile] = useState(() => {
    const savedProfile = localStorage.getItem('tensr_active_profile_json') || ''
    if (!savedProfile) return null
    try {
      return JSON.parse(savedProfile)
    } catch {
      return null
    }
  })
  const [selectedProfilePaths, setSelectedProfilePaths] = useState([])
  const [runAllProfiles, setRunAllProfiles] = useState(false)

  const { signals, loading, error, refresh } = useSignals()
  const { running, runPipeline }                      = usePipeline({ onComplete: refresh })

  const filtered = signals
    .filter(s => !filters.region       || s.region       === filters.region)
    .filter(s => !filters.domains?.length || filters.domains.includes(s.domain))
    .filter(s => !filters.priority_tier || s.priority_tier === filters.priority_tier)

  useEffect(() => {
    if (activeProfilePath) localStorage.setItem('tensr_active_profile_path', activeProfilePath)
    else localStorage.removeItem('tensr_active_profile_path')

    if (activeProfile) localStorage.setItem('tensr_active_profile_json', JSON.stringify(activeProfile))
    else localStorage.removeItem('tensr_active_profile_json')
  }, [activeProfilePath, activeProfile])

  return (
    <div className="min-h-screen font-sans">
      <Header />

      <main className="px-4 py-5 md:px-6 md:py-8">
        <div className="mx-auto max-w-[1320px]">
          <div className="rounded-2xl border border-slate-700/70 bg-slate-900/50 backdrop-blur-md shadow-[0_24px_60px_rgba(2,6,23,0.5)]">
            <div className="px-5 py-5 border-b border-slate-700/80 flex flex-col gap-4 md:px-6">
              <PipelineButton
                running={running}
                onRun={() => runPipeline({
                  profilePath: activeProfilePath,
                  profilePaths: selectedProfilePaths,
                  runAllProfiles,
                })}
                onOpenBriefing={() => setBriefingOpen(true)}
                onOpenSettings={() => setSettingsOpen(true)}
                activeProfilePath={activeProfilePath}
                selectedProfilePaths={selectedProfilePaths}
                onSelectedProfilePathsChange={setSelectedProfilePaths}
                runAllProfiles={runAllProfiles}
                onRunAllProfilesChange={setRunAllProfiles}
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
      <BriefingModal
        open={briefingOpen}
        onClose={() => setBriefingOpen(false)}
        onProfileReady={(path, profile) => {
          setActiveProfilePath(path || '')
          setActiveProfile(profile || null)
          setBriefingOpen(false)
        }}
      />
      <PipelineSettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        profile={activeProfile}
        profilePath={activeProfilePath}
        onProfileUpdated={(path, profile) => {
          setActiveProfilePath(path || '')
          setActiveProfile(profile || null)
        }}
      />
    </div>
  )
}
