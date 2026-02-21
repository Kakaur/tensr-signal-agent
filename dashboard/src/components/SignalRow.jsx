import { ExternalLink, Info, Building2 } from 'lucide-react'
import { formatDate, formatSignalType, formatDomain } from '../utils/formatters.js'

const TIER = {
  HOT:     { pill: 'bg-red-500/15 text-red-400 border border-red-500/30',     bar: 'bg-red-500',     left: 'border-l-red-500' },
  WARM:    { pill: 'bg-amber-500/15 text-amber-400 border border-amber-500/30', bar: 'bg-amber-500',   left: 'border-l-amber-500' },
  NURTURE: { pill: 'bg-blue-500/15 text-blue-400 border border-blue-500/30',   bar: 'bg-blue-500',    left: 'border-l-blue-500' },
  HOLD:    { pill: 'bg-slate-500/15 text-slate-400 border border-slate-500/30', bar: 'bg-slate-500',   left: 'border-l-slate-600' },
}

const REGION_PREFIX = { 'middle east': 'ME', 'eastern europe': 'EE', 'europe': 'EE' }

function InfoHint({ text }) {
  return (
    <span className="relative inline-flex items-center group">
      <Info size={10} className="text-slate-400 cursor-help" title={text} />
      <span className="pointer-events-none absolute bottom-[130%] left-1/2 z-30 w-56 -translate-x-1/2 rounded-md border border-slate-600 bg-slate-900 px-2 py-1 text-[10px] leading-snug text-slate-200 opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
        {text}
      </span>
    </span>
  )
}

function getPrefix(region) {
  const r = (region || '').toLowerCase()
  for (const [key, val] of Object.entries(REGION_PREFIX)) { if (r.includes(key)) return val }
  return null
}

function ScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score ?? 0))
  const color = pct >= 80 ? 'bg-red-500' : pct >= 60 ? 'bg-amber-500' : pct >= 40 ? 'bg-blue-500' : 'bg-slate-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-bold text-slate-200 tabular-nums w-6 text-right">{pct}</span>
    </div>
  )
}

export default function SignalRow({ signal, sovereign, onClick }) {
  const tier   = TIER[(signal.priority_tier || 'HOLD').toUpperCase()] || TIER.HOLD
  const prefix = getPrefix(signal.region)

  const seniority = signal.seniority && signal.seniority.toLowerCase() !== 'unknown'
    ? signal.seniority : null

  const openSource = e => {
    e.stopPropagation()
    if (signal.source_url) window.open(signal.source_url, '_blank', 'noopener,noreferrer')
  }

  const company = (signal.institution || '').trim()
  const country = (signal.country || '').trim()
  const linkedInKeywords = `${company} ${country}`.trim()
  const linkedInUrl = `https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(linkedInKeywords)}`

  return (
    <tr
      onClick={onClick}
      className={`group border-l-2 ${tier.left} hover:bg-slate-800/80 cursor-pointer transition-colors`}
    >
      {/* Priority */}
      <td className="px-4 py-3 whitespace-nowrap">
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider ${tier.pill}`}>
          {signal.priority_tier || 'HOLD'}
        </span>
        {seniority && (
          <div className="mt-1 text-[9px] text-slate-500 leading-none flex items-center gap-1">
            <span>Seniority: {seniority}</span>
          </div>
        )}
      </td>

      {/* Institution */}
      <td className="px-4 py-3 max-w-[200px]">
        <p className="text-sm font-semibold text-slate-100 truncate">{signal.institution || '—'}</p>
        {sovereign && (
          <div className="mt-1 text-[9px] text-violet-300 leading-none flex items-center gap-1">
            <span>Sovereign Alignment</span>
          </div>
        )}
      </td>

      {/* LinkedIn */}
      <td className="px-4 py-3 whitespace-nowrap" onClick={e => e.stopPropagation()}>
        <a
          href={linkedInUrl}
          target="_blank"
          rel="noreferrer"
          title={`Search ${signal.institution || 'company'} on LinkedIn`}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-[11px] font-semibold bg-cyan-500/15 text-cyan-200 border border-cyan-500/30 hover:bg-cyan-500/25 transition-all"
        >
          <Building2 size={11} /> Search on LinkedIn
        </a>
      </td>

      {/* News */}
      <td className="px-4 py-3 whitespace-nowrap" onClick={e => e.stopPropagation()}>
        <button
          onClick={openSource}
          disabled={!signal.source_url}
          title="Open source article"
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-[11px] font-semibold bg-slate-700 text-slate-300 border border-slate-600 hover:bg-slate-600 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <ExternalLink size={11} /> News
        </button>
      </td>

      {/* Country/Region */}
      <td className="px-4 py-3 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          {prefix && (
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-400 border border-indigo-500/20">
              {prefix}
            </span>
          )}
          <span className="text-xs text-slate-400">{signal.country || signal.region || '—'}</span>
        </div>
      </td>

      {/* Signal Type */}
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="text-sm font-bold text-slate-200">{formatSignalType(signal.signal_type)}</span>
        {seniority && (
          <div className="mt-1 text-[9px] text-slate-500 leading-none flex items-center gap-1">
            <span>Seniority: {seniority}</span>
            <InfoHint text="Role level tied to the signal. Higher seniority usually contributes more points to score." />
          </div>
        )}
        {sovereign && (
          <div className="mt-1 text-[9px] text-violet-300 leading-none flex items-center gap-1">
            <span>Sovereign Alignment</span>
            <InfoHint text="Signal text matches national strategy themes such as ICV, Vision 2030, sovereign cloud, or smart-city programs." />
          </div>
        )}
      </td>

      {/* Domain */}
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="text-xs text-slate-400">{formatDomain(signal.domain)}</span>
      </td>

      {/* Score */}
      <td className="px-4 py-3 whitespace-nowrap">
        <ScoreBar score={signal.total_score} />
      </td>

      {/* Timestamp */}
      <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-500 tabular-nums">
        <p>{formatDate(signal.signal_date)}</p>
      </td>

    </tr>
  )
}
