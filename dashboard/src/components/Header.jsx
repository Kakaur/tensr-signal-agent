import { Zap } from 'lucide-react'

export default function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-700/80 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1320px] items-center justify-between px-5 py-4 md:px-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-cyan-900/40">
          <Zap size={18} className="text-white" fill="white" />
          </div>
          <div>
            <h1 className="text-lg font-extrabold text-white leading-tight tracking-tight">
              Tensr Signal Agent
            </h1>
            <p className="text-xs text-slate-300/80 leading-tight">
              Deal Intelligence Command Center
            </p>
          </div>
        </div>
        <span className="hidden md:inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-widest text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
          Live
        </span>
      </div>
    </header>
  )
}
