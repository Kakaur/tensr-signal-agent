import { useEffect, useState } from 'react'
import { X, Send, CheckCircle2 } from 'lucide-react'

export default function BriefingModal({ open, onClose, onProfileReady }) {
  const [sessionId, setSessionId] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [profilePath, setProfilePath] = useState('')

  useEffect(() => {
    if (!open) return
    const start = async () => {
      setBusy(true)
      setError('')
      try {
        const res = await fetch('/api/briefing/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        })
        const data = await res.json()
        if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
        setSessionId(data.session_id)
        setMessages(data.messages || [])
      } catch (e) {
        setError(e.message)
      } finally {
        setBusy(false)
      }
    }
    start()
  }, [open])

  if (!open) return null

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || busy) return
    setBusy(true)
    setError('')
    try {
      const res = await fetch('/api/briefing/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: input.trim() }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
      setMessages(data.messages || [])
      setInput('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const finalize = async () => {
    if (!sessionId || busy) return
    setBusy(true)
    setError('')
    try {
      const res = await fetch('/api/briefing/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
      setProfilePath(data.profile_path || '')
      onProfileReady?.(data.profile_path || '', data.profile || null)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm p-4 md:p-6 flex items-center justify-center">
      <div className="w-full max-w-3xl rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <div>
            <h3 className="text-base font-bold text-white">Pipeline Briefing Agent</h3>
            <p className="text-xs text-slate-400">Define objective, scope, ranking, and constraints before run.</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800">
            <X size={16} />
          </button>
        </div>

        <div className="h-[380px] overflow-y-auto px-5 py-4 space-y-3">
          {messages.map((m, idx) => (
            <div key={idx} className={m.role === 'assistant' ? 'text-left' : 'text-right'}>
              <div className={[
                'inline-block max-w-[85%] rounded-xl px-3 py-2 text-sm',
                m.role === 'assistant'
                  ? 'bg-slate-800 text-slate-100 border border-slate-700'
                  : 'bg-cyan-600/20 text-cyan-100 border border-cyan-500/30',
              ].join(' ')}>
                {m.content}
              </div>
            </div>
          ))}
          {busy && <p className="text-xs text-slate-400">Thinking...</p>}
          {error && <p className="text-xs text-red-300">{error}</p>}
        </div>

        <div className="px-5 py-4 border-t border-slate-700 space-y-3">
          {profilePath && (
            <p className="text-xs text-emerald-300 inline-flex items-center gap-1">
              <CheckCircle2 size={12} /> Profile ready: {profilePath}
            </p>
          )}
          <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Answer briefing question..."
              className="flex-1 rounded-lg bg-slate-800 border border-slate-600 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
              onKeyDown={e => { if (e.key === 'Enter') sendMessage() }}
            />
            <button
              onClick={sendMessage}
              disabled={busy || !input.trim()}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-2 bg-slate-800 border border-slate-600 text-slate-100 hover:bg-slate-700 disabled:opacity-50"
            >
              <Send size={13} /> Send
            </button>
            <button
              onClick={finalize}
              disabled={busy || !messages.length}
              className="rounded-lg px-3 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-semibold disabled:opacity-50"
            >
              Finalize
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
