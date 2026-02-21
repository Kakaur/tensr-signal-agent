import { useState } from 'react'
import { SlidersHorizontal, X, ChevronDown, ChevronUp } from 'lucide-react'
import { formatDomain } from '../utils/formatters.js'

const SELECT_CLS = [
  'bg-slate-800/80 border border-slate-600 text-slate-100 text-sm',
  'rounded-lg px-3 py-2 cursor-pointer outline-none',
  'hover:border-cyan-400/70 focus:border-cyan-400/70 transition-colors',
  'min-w-[140px]',
].join(' ')

export default function FilterBar({ filters, signals, onChange }) {
  const [showDomains, setShowDomains] = useState(false)
  const regions = [...new Set(signals.map(s => s.region).filter(Boolean))].sort()
  const domains = [...new Set(signals.map(s => s.domain).filter(Boolean))].sort()
  const tiers = ['HOT', 'WARM', 'NURTURE', 'HOLD']

  const set = key => e => onChange(prev => ({ ...prev, [key]: e.target.value }))

  const toggleDomain = domain =>
    onChange(prev => {
      const current = Array.isArray(prev.domains) ? prev.domains : []
      const exists = current.includes(domain)
      return {
        ...prev,
        domains: exists ? current.filter(d => d !== domain) : [...current, domain],
      }
    })

  const clearDomains = () =>
    onChange(prev => ({ ...prev, domains: [] }))

  const clearAll = () =>
    onChange({ region: '', domains: [], priority_tier: '' })

  const selectedDomains = Array.isArray(filters.domains) ? filters.domains : []
  const hasFilters = Boolean(filters.region || filters.priority_tier || selectedDomains.length)

  return (
    <div className="flex flex-wrap items-center gap-2 px-5 py-3 bg-slate-900/40 border-b border-slate-700/80 md:px-6">
      <SlidersHorizontal size={14} className="text-slate-300/90 flex-shrink-0" />
      <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mr-1">Filters</span>

      <select className={SELECT_CLS} value={filters.region} onChange={set('region')}>
        <option value="">All Regions</option>
        {regions.map(r => <option key={r} value={r}>{r}</option>)}
      </select>

      <div className="relative">
        <button
          onClick={() => setShowDomains(v => !v)}
          className="inline-flex items-center gap-1 bg-slate-800/80 border border-slate-600 text-slate-100 text-sm rounded-lg px-3 py-2 hover:border-cyan-400/70 transition-colors"
        >
          All Domains
          {selectedDomains.length > 0 && (
            <span className="rounded-full bg-cyan-500/20 px-1.5 py-0.5 text-[10px] text-cyan-200 border border-cyan-500/30">
              {selectedDomains.length}
            </span>
          )}
          {showDomains ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        {showDomains && (
          <div className="absolute z-30 mt-2 w-72 max-h-72 overflow-y-auto rounded-xl border border-slate-600 bg-slate-900/95 p-3 shadow-2xl backdrop-blur-md">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-widest text-slate-400">Select domains</span>
              {!!selectedDomains.length && (
                <button
                  onClick={clearDomains}
                  className="text-[10px] text-slate-300 hover:text-white transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="space-y-2">
              {domains.map(d => (
                <label key={d} className="flex items-center gap-2 text-sm text-slate-200 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedDomains.includes(d)}
                    onChange={() => toggleDomain(d)}
                    className="h-4 w-4 rounded border-slate-500 bg-slate-800 text-cyan-500 focus:ring-cyan-400"
                  />
                  <span>{formatDomain(d)}</span>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      <select className={SELECT_CLS} value={filters.priority_tier} onChange={set('priority_tier')}>
        <option value="">All Tiers</option>
        {tiers.map(t => <option key={t} value={t}>{t}</option>)}
      </select>

      {hasFilters && (
        <button
          onClick={clearAll}
          className="inline-flex items-center gap-1 px-3 py-2 text-xs text-slate-300 bg-slate-800 border border-slate-600 rounded-lg hover:text-white hover:border-slate-400 transition-colors"
        >
          <X size={12} /> Clear
        </button>
      )}
    </div>
  )
}
