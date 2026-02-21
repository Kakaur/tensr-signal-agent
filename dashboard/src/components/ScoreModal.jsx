import { X, ExternalLink } from 'lucide-react'
import { formatDate } from '../utils/formatters.js'

const TIER = {
  HOT:     'bg-red-500/15 text-red-400 border border-red-500/30',
  WARM:    'bg-amber-500/15 text-amber-400 border border-amber-500/30',
  NURTURE: 'bg-blue-500/15 text-blue-400 border border-blue-500/30',
  HOLD:    'bg-slate-500/15 text-slate-400 border border-slate-500/30',
}

const CATS = [
  { key: 'action_pts',        label: 'Action Type',              max: 30 },
  { key: 'seniority_pts',     label: 'Seniority',                max: 20 },
  { key: 'domain_pts',        label: 'Domain Fit',               max: 25 },
  { key: 'accessibility_pts', label: 'Institution Accessibility', max: 15 },
  { key: 'recency_pts',       label: 'Recency',                  max: 10 },
]

const BAR_COLOR = tier => ({
  HOT:     'bg-red-500',
  WARM:    'bg-amber-500',
  NURTURE: 'bg-blue-500',
  HOLD:    'bg-slate-500',
}[tier] || 'bg-slate-500')

export default function ScoreModal({ signal, onClose }) {
  const tierKey = (signal.priority_tier || 'HOLD').toUpperCase()
  const tierCls = TIER[tierKey] || TIER.HOLD
  const barCol  = BAR_COLOR(tierKey)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/70 backdrop-blur-sm"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="relative w-full max-w-lg max-h-[88vh] overflow-y-auto bg-slate-900 border border-slate-700 rounded-2xl p-7 shadow-2xl">
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <X size={16} />
        </button>

        {/* Header */}
        <div className="flex items-start gap-3 mb-4 pr-8">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-bold text-white truncate">{signal.institution}</h2>
            <p className="text-xs text-slate-400 mt-0.5">{signal.country || signal.region}</p>
          </div>
          <span className={`flex-shrink-0 px-2.5 py-1 rounded text-[10px] font-extrabold uppercase tracking-wider ${tierCls}`}>
            {signal.priority_tier || 'HOLD'}
          </span>
        </div>

        {/* Summary */}
        <p className="text-sm text-slate-300 leading-relaxed mb-6">{signal.summary}</p>

        {/* Score breakdown */}
        <div className="mb-1">
          <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 mb-4">
            Score Breakdown — {signal.total_score ?? 0} / 100
          </h3>
          <div className="space-y-3">
            {CATS.map(cat => {
              const pts = signal[cat.key] ?? 0
              const pct = Math.round((pts / cat.max) * 100)
              return (
                <div key={cat.key} className="flex items-center gap-3">
                  <span className="w-44 text-xs text-slate-400 flex-shrink-0">{cat.label}</span>
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all ${barCol}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-10 text-right text-xs font-semibold text-slate-300 tabular-nums">
                    {pts}/{cat.max}
                  </span>
                </div>
              )
            })}
          </div>
          {signal.seniority_inferred === 1 && (
            <p className="text-[10px] text-slate-500 italic mt-3">* Seniority was inferred from signal context</p>
          )}
        </div>

        {/* Metadata */}
        <div className="mt-5 pt-4 border-t border-slate-800 flex flex-wrap items-center gap-4 text-[11px] text-slate-500">
          <span>Signal: {formatDate(signal.signal_date)}</span>
          {signal.scored_at && <span>Scored: {formatDate(signal.scored_at)}</span>}
          {signal.run_timestamp && <span>Run: {formatDate(signal.run_timestamp)}</span>}
          {signal.source_url && (
            <a
              href={signal.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              <ExternalLink size={11} /> View Source
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
