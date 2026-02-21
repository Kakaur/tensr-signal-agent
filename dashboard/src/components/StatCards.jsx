import { BarChart2, Flame, Globe, Layers } from 'lucide-react'
import { formatDomain } from '../utils/formatters.js'

function StatCard({ icon, label, value, sub, accent }) {
  const accentMap = {
    indigo: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400',
    red:    'bg-red-500/10    border-red-500/20    text-red-400',
    amber:  'bg-amber-500/10  border-amber-500/20  text-amber-400',
    violet: 'bg-violet-500/10 border-violet-500/20 text-violet-400',
  }
  const iconMap = {
    indigo: 'text-indigo-400',
    red:    'text-red-400',
    amber:  'text-amber-400',
    violet: 'text-violet-400',
  }
  const IconComponent = icon
  return (
    <div className={`flex items-center gap-4 px-5 py-4 rounded-xl border bg-slate-900/75 shadow-sm ${accentMap[accent]}`}>
      <div className={`p-2 rounded-lg bg-slate-800 ${iconMap[accent]}`}>
        <IconComponent size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-0.5">{label}</p>
        <p className={`text-xl font-extrabold leading-none truncate ${iconMap[accent]}`}>{value}</p>
        {sub && <p className="text-[10px] text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function StatCards({ summary, signals = [] }) {
  const total = summary?.total ?? signals.length

  const highConviction = signals.filter(s => (s.total_score ?? 0) > 75).length

  const meCount = signals.filter(s => (s.region || '').toLowerCase().includes('middle east')).length
  const eeCount = signals.filter(s => {
    const r = (s.region || '').toLowerCase()
    return r.includes('eastern europe') || (r.includes('europe') && !r.includes('middle'))
  }).length

  const domainCounts = {}
  signals.forEach(s => { if (s.domain) domainCounts[s.domain] = (domainCounts[s.domain] || 0) + 1 })
  const topDomainKey = Object.entries(domainCounts).sort((a, b) => b[1] - a[1])[0]?.[0]
  const topDomainLabel = topDomainKey ? formatDomain(topDomainKey) : '—'

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard icon={BarChart2} label="Total Signals"     value={total}                       accent="indigo" />
      <StatCard icon={Flame}     label="High-Conviction"   value={highConviction} sub="Score > 75" accent="red" />
      <StatCard icon={Globe}     label="Active Regions"    value={`${meCount} ME · ${eeCount} EE`} accent="amber" />
      <StatCard icon={Layers}    label="Top Domain"        value={topDomainLabel}                accent="violet" />
    </div>
  )
}
