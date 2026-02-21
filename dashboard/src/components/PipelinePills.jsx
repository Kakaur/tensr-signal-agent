const TIERS = [
  { key: 'HOT',     label: 'Hot',     classes: 'bg-red-500/15 text-red-400 border-red-500/30',     dot: 'bg-red-400' },
  { key: 'WARM',    label: 'Warm',    classes: 'bg-amber-500/15 text-amber-400 border-amber-500/30', dot: 'bg-amber-400' },
  { key: 'NURTURE', label: 'Nurture', classes: 'bg-blue-500/15 text-blue-400 border-blue-500/30',   dot: 'bg-blue-400' },
  { key: 'HOLD',    label: 'Hold',    classes: 'bg-slate-500/15 text-slate-400 border-slate-500/30', dot: 'bg-slate-400' },
]

export default function PipelinePills({ summary }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {TIERS.map(({ key, label, classes, dot }) => (
        <div key={key} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold shadow-sm ${classes}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
          <span>{label}</span>
          <span className="font-bold">{summary?.[key] ?? 0}</span>
        </div>
      ))}
    </div>
  )
}
