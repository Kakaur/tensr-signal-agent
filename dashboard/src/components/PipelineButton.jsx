import { useCallback, useEffect, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Play,
  Trash2,
} from 'lucide-react'

function formatDay(dayValue) {
  if (!dayValue) return 'Unknown day'
  const parsed = new Date(dayValue)
  if (Number.isNaN(parsed.getTime())) return dayValue
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function PipelineButton({ running, onRun, onRefresh }) {
  const [batches, setBatches] = useState([])
  const [batchesLoading, setBatchesLoading] = useState(false)
  const [batchesError, setBatchesError] = useState('')
  const [batchesNotice, setBatchesNotice] = useState('')
  const [deletingBatchId, setDeletingBatchId] = useState(null)
  const [deletingAllBatches, setDeletingAllBatches] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  const loadBatches = useCallback(async () => {
    setBatchesLoading(true)
    setBatchesError('')
    try {
      const res = await fetch('/api/batches')
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
      setBatches(data.batches || [])
    } catch (e) {
      setBatchesError(e.message)
    } finally {
      setBatchesLoading(false)
    }
  }, [])

  useEffect(() => {
    loadBatches()
  }, [loadBatches])

  const deleteBatch = async batch => {
    const confirmed = window.confirm(`Delete batch #${batch.id}?`)
    if (!confirmed) return

    setDeletingBatchId(batch.id)
    setBatchesError('')
    setBatchesNotice('')
    try {
      const res = await fetch('/api/batches/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: batch.id }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
      await loadBatches()
      await onRefresh?.()
      setBatchesNotice(`Deleted batch #${batch.id}.`)
      void data
    } catch (e) {
      setBatchesError(e.message)
    } finally {
      setDeletingBatchId(null)
    }
  }

  const deleteAllBatches = async () => {
    if (!batches.length) return
    const confirmed = window.confirm(`Delete all ${batches.length} batches?`)
    if (!confirmed) return

    setDeletingAllBatches(true)
    setBatchesError('')
    setBatchesNotice('')
    try {
      const res = await fetch('/api/batches/delete-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
      await loadBatches()
      await onRefresh?.()
      setBatchesNotice(`Deleted ${data.runs_deleted || 0} batch(es).`)
    } catch (e) {
      setBatchesError(e.message)
    } finally {
      setDeletingAllBatches(false)
    }
  }

  return (
    <div className="flex flex-col items-stretch gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          onClick={() => setHistoryOpen(prev => !prev)}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-700/80"
        >
          {historyOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          Run History
          <span className="rounded-md border border-slate-500/60 px-1.5 py-0.5 text-[10px] text-slate-300">
            {batches.length}
          </span>
        </button>

        <button
          onClick={onRun}
          disabled={running}
          className={[
            'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all',
            running
              ? 'bg-slate-700 text-slate-300 cursor-not-allowed'
              : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white cursor-pointer shadow-lg shadow-blue-900/35',
          ].join(' ')}
        >
          {running
            ? <><Loader2 size={14} className="animate-spin" /> Running...</>
            : <><Play size={14} fill="currentColor" /> Run Search</>
          }
        </button>
      </div>

      {historyOpen && (
        <div className="rounded-xl border border-slate-700/80 bg-slate-900/55 p-3 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-300">
              Saved Batches
            </p>
            <div className="flex items-center gap-2">
              <p className="text-[10px] text-slate-400">
                {batchesLoading ? 'Loading...' : `${batches.length} total`}
              </p>
              <button
                onClick={deleteAllBatches}
                disabled={deletingAllBatches || batchesLoading || !batches.length}
                className="inline-flex items-center gap-1 rounded-md border border-red-500/50 bg-red-500/15 px-2 py-1 text-[10px] font-semibold text-red-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deletingAllBatches ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                Delete All
              </button>
            </div>
          </div>

          <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
            {!batchesLoading && !batches.length && (
              <p className="text-xs text-slate-400">No batches found.</p>
            )}
            {batches.map(batch => (
              <div
                key={batch.id}
                className="flex items-center gap-2 rounded-lg border border-slate-700/80 bg-slate-800/60 px-2 py-1.5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs text-slate-200">
                    #{batch.id} • {batch.output_file || 'Unknown output'}
                  </p>
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">
                    {formatDay(batch.timestamp)} • {batch.signal_count || 0} signals
                  </p>
                </div>
                <button
                  onClick={() => deleteBatch(batch)}
                  disabled={deletingBatchId === batch.id || deletingAllBatches}
                  className="rounded-md border border-red-500/45 bg-red-500/12 p-1 text-red-200 hover:bg-red-500/25 disabled:cursor-not-allowed disabled:opacity-60"
                  title="Delete batch"
                >
                  {deletingBatchId === batch.id
                    ? <Loader2 size={11} className="animate-spin" />
                    : <Trash2 size={11} />
                  }
                </button>
              </div>
            ))}
          </div>

          {batchesError && (
            <p className="text-[11px] text-red-300">{batchesError}</p>
          )}
          {batchesNotice && (
            <p className="text-[11px] text-emerald-300">{batchesNotice}</p>
          )}
        </div>
      )}
    </div>
  )
}
