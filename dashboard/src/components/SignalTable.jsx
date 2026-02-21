import { useState } from 'react'
import { ArrowUp, ArrowDown, ChevronDown, ChevronUp, Loader2, Trash2 } from 'lucide-react'
import SignalRow from './SignalRow.jsx'

const SOVEREIGN_KW = [
  'vision 2030', 'national ai strategy', 'in-country value', 'icv',
  'non-oil', 'giga-project', 'neom', 'sovereign cloud', 'smart city',
  'saudi vision', 'uae national',
]

const TIER_ORDER = { HOT: 0, WARM: 1, NURTURE: 2, HOLD: 3 }
const TH = 'px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-widest text-slate-400 whitespace-nowrap bg-slate-900/95'

const isSovereign = s => {
  const t = ((s.summary || '') + ' ' + (s.regional_keyword_match || '')).toLowerCase()
  return SOVEREIGN_KW.some(kw => t.includes(kw))
}

const toTimestamp = value => {
  if (!value) return 0
  const ts = Date.parse(value)
  return Number.isNaN(ts) ? 0 : ts
}

const formatBatchTimestamp = value => {
  if (!value) return 'Unknown run time'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const compareDateKey = (a, b, key, dir) => {
  const left = toTimestamp(a[key])
  const right = toTimestamp(b[key])
  if (left === right) return 0
  return dir === 'desc' ? right - left : left - right
}

const compareTextKey = (a, b, key, dir) => {
  const left = String(a[key] ?? '').toLowerCase()
  const right = String(b[key] ?? '').toLowerCase()
  if (left === right) return 0
  if (dir === 'desc') return left < right ? 1 : -1
  return left > right ? 1 : -1
}

const compareNumericKey = (a, b, key, dir) => {
  const left = Number(a[key] ?? 0)
  const right = Number(b[key] ?? 0)
  if (left === right) return 0
  return dir === 'desc' ? right - left : left - right
}

const comparePriority = (a, b, dir) => {
  const ta = TIER_ORDER[(a.priority_tier || '').toUpperCase()] ?? 4
  const tb = TIER_ORDER[(b.priority_tier || '').toUpperCase()] ?? 4
  if (ta === tb) return 0
  if (dir === 'desc') return ta - tb
  return tb - ta
}

const sortRows = (arr, sortKey, sortDir) => [...arr].sort((a, b) => {
  if (sortKey === 'priority_tier') {
    const byTier = comparePriority(a, b, sortDir)
    if (byTier !== 0) return byTier
    return compareNumericKey(a, b, 'total_score', 'desc')
  }

  if (sortKey === 'signal_date' || sortKey === 'run_timestamp') {
    const byDate = compareDateKey(a, b, sortKey, sortDir)
    if (byDate !== 0) return byDate
  } else if (sortKey === 'total_score') {
    const byScore = compareNumericKey(a, b, 'total_score', sortDir)
    if (byScore !== 0) return byScore
  } else if (sortKey === 'country_or_region') {
    const countryA = a.country || a.region || ''
    const countryB = b.country || b.region || ''
    const byCountry = compareTextKey({ v: countryA }, { v: countryB }, 'v', sortDir)
    if (byCountry !== 0) return byCountry
  } else {
    const byText = compareTextKey(a, b, sortKey, sortDir)
    if (byText !== 0) return byText
  }

  const byTier = comparePriority(a, b, 'desc')
  if (byTier !== 0) return byTier
  return compareNumericKey(a, b, 'total_score', 'desc')
})

function SortableHeader({ label, sortKey, activeSortKey, sortDir, onToggle }) {
  const active = activeSortKey === sortKey
  return (
    <th className={`${TH} cursor-pointer select-none hover:text-slate-200 transition-colors`} onClick={() => onToggle(sortKey)}>
      <span className="inline-flex items-center gap-1">
        {label}
        {active && (sortDir === 'desc' ? <ArrowDown size={11} /> : <ArrowUp size={11} />)}
      </span>
    </th>
  )
}

function BatchSection({
  batch,
  sortKey,
  sortDir,
  onToggleSort,
  onRowClick,
  onBatchDeleted,
  onBatchDeletedLocal,
}) {
  const rows = sortRows(batch.signals, sortKey, sortDir)
  const tierCounts = rows.reduce((acc, row) => {
    const tier = (row.priority_tier || 'HOLD').toUpperCase()
    acc[tier] = (acc[tier] || 0) + 1
    return acc
  }, { HOT: 0, WARM: 0, NURTURE: 0, HOLD: 0 })

  const [collapsed, setCollapsed] = useState(false)
  const [deletingBatch, setDeletingBatch] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const tableShellClass = rows.length > 7
    ? 'max-h-[460px] overflow-auto rounded-xl border border-slate-700/90 shadow-[0_12px_24px_rgba(2,6,23,0.35)]'
    : 'overflow-x-auto rounded-xl border border-slate-700/90 shadow-[0_12px_24px_rgba(2,6,23,0.35)]'

  const deleteBatch = async () => {
    if (!batch.run_id || deletingBatch) return
    const confirmed = window.confirm(`Delete signal batch #${batch.run_id}?`)
    if (!confirmed) return

    setDeletingBatch(true)
    setDeleteError('')
    try {
      const res = await fetch('/api/batches/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: batch.run_id }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
      onBatchDeletedLocal?.(batch.key)
      await onBatchDeleted?.()
    } catch (e) {
      setDeleteError(e.message)
    } finally {
      setDeletingBatch(false)
    }
  }

  return (
    <section className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 pt-2 pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setCollapsed(v => !v)}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-widest text-slate-200 hover:border-slate-500 transition-colors"
            title={collapsed ? 'Expand batch' : 'Collapse batch'}
          >
            {collapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
            Signal Batch
          </button>
          <span className="text-[10px] text-slate-300 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700">
            {formatBatchTimestamp(batch.run_timestamp)}
          </span>
          <span className="text-[10px] text-slate-400">
            {rows.length} signal{rows.length !== 1 ? 's' : ''}
          </span>
          <span className="text-[10px] text-red-300 bg-red-500/10 px-2 py-0.5 rounded-full border border-red-500/30">HOT {tierCounts.HOT}</span>
          <span className="text-[10px] text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30">WARM {tierCounts.WARM}</span>
          <span className="text-[10px] text-blue-300 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/30">NURTURE {tierCounts.NURTURE}</span>
        </div>
        <button
          onClick={deleteBatch}
          disabled={!batch.run_id || deletingBatch}
          className="inline-flex items-center gap-1 rounded-md border border-red-500/45 bg-red-500/12 px-2 py-1 text-[10px] font-semibold text-red-200 hover:bg-red-500/25 disabled:cursor-not-allowed disabled:opacity-50"
          title={batch.run_id ? `Delete batch #${batch.run_id}` : 'Batch cannot be deleted'}
        >
          {deletingBatch ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
          Delete Batch
        </button>
      </div>
      {deleteError && <p className="px-1 pb-2 text-[11px] text-red-300">{deleteError}</p>}

      {!collapsed && (
      <div className={tableShellClass}>
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10">
            <tr className="border-b border-slate-800">
              <SortableHeader label="Priority" sortKey="priority_tier" activeSortKey={sortKey} sortDir={sortDir} onToggle={onToggleSort} />
              <SortableHeader label="Institution" sortKey="institution" activeSortKey={sortKey} sortDir={sortDir} onToggle={onToggleSort} />
              <th className={TH}>Search on LinkedIn</th>
              <th className={TH}>News</th>
              <SortableHeader label="Country/Region" sortKey="country_or_region" activeSortKey={sortKey} sortDir={sortDir} onToggle={onToggleSort} />
              <SortableHeader label="Signal Type" sortKey="signal_type" activeSortKey={sortKey} sortDir={sortDir} onToggle={onToggleSort} />
              <SortableHeader label="Domain" sortKey="domain" activeSortKey={sortKey} sortDir={sortDir} onToggle={onToggleSort} />
              <SortableHeader label="Score" sortKey="total_score" activeSortKey={sortKey} sortDir={sortDir} onToggle={onToggleSort} />
              <SortableHeader label="Signal Date" sortKey="signal_date" activeSortKey={sortKey} sortDir={sortDir} onToggle={onToggleSort} />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {rows.map((s, i) => (
              <SignalRow
                key={s.id ?? `${s.institution}-${s.signal_type}-${i}`}
                signal={s}
                sovereign={isSovereign(s)}
                onClick={() => onRowClick(s)}
              />
            ))}
          </tbody>
        </table>
      </div>
      )}
    </section>
  )
}

export default function SignalTable({ signals, sortKey, sortDir, onToggleSort, onRowClick, onRefresh }) {
  const [hiddenBatchKeys, setHiddenBatchKeys] = useState([])

  const hideBatch = batchKey => {
    setHiddenBatchKeys(prev => (prev.includes(batchKey) ? prev : [...prev, batchKey]))
  }

  if (!signals.length) {
    return <p className="text-center text-slate-300 text-sm py-16">No signals match the current filters.</p>
  }

  const groupedMap = new Map()
  for (const sig of signals) {
    const batchKey = String(sig.run_id ?? sig.run_timestamp ?? 'unknown')
    if (!groupedMap.has(batchKey)) {
      groupedMap.set(batchKey, {
        key: batchKey,
        run_id: sig.run_id ?? null,
        run_timestamp: sig.run_timestamp || null,
        signals: [],
      })
    }
    groupedMap.get(batchKey).signals.push(sig)
  }

  const batches = [...groupedMap.values()].sort((a, b) => {
    const left = toTimestamp(a.run_timestamp)
    const right = toTimestamp(b.run_timestamp)
    if (left === right) return 0
    if (sortKey === 'run_timestamp') {
      return sortDir === 'desc' ? right - left : left - right
    }
    return right - left
  })

  const visibleBatches = batches.filter(batch => !hiddenBatchKeys.includes(batch.key))

  return (
    <div className="px-5 pb-8 md:px-6 md:pb-10">
      {visibleBatches.map(batch => (
        <BatchSection
          key={batch.key}
          batch={batch}
          sortKey={sortKey}
          sortDir={sortDir}
          onToggleSort={onToggleSort}
          onRowClick={onRowClick}
          onBatchDeleted={onRefresh}
          onBatchDeletedLocal={hideBatch}
        />
      ))}
    </div>
  )
}
