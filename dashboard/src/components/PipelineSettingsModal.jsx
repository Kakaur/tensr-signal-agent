import { useEffect, useState } from 'react'
import { X } from 'lucide-react'

function ReadOnlyRow({ label, value }) {
  return (
    <tr className="border-b border-slate-800/70">
      <td className="px-3 py-2 text-[11px] font-semibold uppercase tracking-widest text-slate-400">{label}</td>
      <td className="px-3 py-2 text-sm text-slate-200">{value || '—'}</td>
    </tr>
  )
}

function EditableRow({ label, children }) {
  return (
    <tr className="border-b border-slate-800/70">
      <td className="px-3 py-2 align-top text-[11px] font-semibold uppercase tracking-widest text-slate-400">{label}</td>
      <td className="px-3 py-2">{children}</td>
    </tr>
  )
}

function textInputClass() {
  return 'w-full rounded-md border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-slate-100 outline-none focus:border-cyan-400'
}

function parseCsv(value) {
  return (value || '')
    .split(',')
    .map(v => v.trim())
    .filter(Boolean)
}

function parseLines(value) {
  return (value || '')
    .split('\n')
    .map(v => v.trim())
    .filter(Boolean)
}

function formatCreatedAt(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function profileToDraft(profile) {
  return {
    objective: profile?.objective || '',
    regions: (profile?.regions || []).join(', '),
    countries: (profile?.countries || []).join(', '),
    time_window_days: String(profile?.time_window_days ?? 90),
    domains: (profile?.domains || []).join(', '),
    signal_types: (profile?.signal_types || []).join(', '),
    min_signals: String(profile?.target_output?.min_signals ?? 20),
    max_signals: String(profile?.target_output?.max_signals ?? 25),
    dedupe_policy: profile?.target_output?.dedupe_policy || 'prefer_new',
    inclusion_rules: (profile?.inclusion_rules || []).join('\n'),
    exclusion_rules: (profile?.exclusion_rules || []).join('\n'),
    ranking_categories_json: JSON.stringify(profile?.ranking?.categories || [], null, 2),
    priority_thresholds_json: JSON.stringify(
      profile?.ranking?.priority_thresholds || { HOT: 80, WARM: 60, NURTURE: 40 },
      null,
      2,
    ),
  }
}

function draftToProfile(draft, baseProfile) {
  return {
    ...baseProfile,
    objective: draft.objective.trim(),
    regions: parseCsv(draft.regions),
    countries: parseCsv(draft.countries),
    time_window_days: Number(draft.time_window_days || 90),
    domains: parseCsv(draft.domains),
    signal_types: parseCsv(draft.signal_types),
    inclusion_rules: parseLines(draft.inclusion_rules),
    exclusion_rules: parseLines(draft.exclusion_rules),
    target_output: {
      ...(baseProfile?.target_output || {}),
      min_signals: Number(draft.min_signals || 20),
      max_signals: Number(draft.max_signals || 25),
      dedupe_policy: draft.dedupe_policy.trim() || 'prefer_new',
    },
    ranking: {
      ...(baseProfile?.ranking || {}),
      categories: JSON.parse(draft.ranking_categories_json || '[]'),
      priority_thresholds: JSON.parse(draft.priority_thresholds_json || '{}'),
    },
  }
}

export default function PipelineSettingsModal({
  open,
  onClose,
  profile,
  profilePath,
  onProfileUpdated,
}) {
  const [resolvedProfile, setResolvedProfile] = useState(profile || null)
  const [resolvedProfilePath, setResolvedProfilePath] = useState(profilePath || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [savedProfiles, setSavedProfiles] = useState([])
  const [savedLoading, setSavedLoading] = useState(false)

  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState(profileToDraft(profile || null))

  useEffect(() => {
    if (!open) return
    const loadCurrentSettings = async () => {
      if (profile) {
        setResolvedProfile(profile)
        setResolvedProfilePath(profilePath || '')
        setDraft(profileToDraft(profile))
        return
      }

      setLoading(true)
      setError('')
      try {
        const res = await fetch('/api/pipeline/current-settings')
        const data = await res.json()
        if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
        const loadedProfile = data.profile || null
        setResolvedProfile(loadedProfile)
        setResolvedProfilePath(data.profile_file || profilePath || '')
        setDraft(profileToDraft(loadedProfile))
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    loadCurrentSettings()
  }, [open, profile, profilePath])

  useEffect(() => {
    if (!open) return
    const loadSavedProfiles = async () => {
      setSavedLoading(true)
      try {
        const res = await fetch('/api/pipeline/profiles')
        const data = await res.json()
        if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)
        setSavedProfiles(data.profiles || [])
      } catch (e) {
        setError(e.message)
      } finally {
        setSavedLoading(false)
      }
    }
    loadSavedProfiles()
  }, [open])

  if (!open) return null

  const selectProfile = item => {
    setResolvedProfile(item.profile || null)
    setResolvedProfilePath(item.profile_path || '')
    setDraft(profileToDraft(item.profile || null))
    setIsEditing(false)
    onProfileUpdated?.(item.profile_path || '', item.profile || null)
  }

  const startEditing = () => {
    setDraft(profileToDraft(resolvedProfile))
    setIsEditing(true)
    setError('')
  }

  const cancelEditing = () => {
    setDraft(profileToDraft(resolvedProfile))
    setIsEditing(false)
    setError('')
  }

  const saveEditedSettings = async () => {
    if (!resolvedProfile || saving) return
    setSaving(true)
    setError('')
    try {
      const payloadProfile = draftToProfile(draft, resolvedProfile)
      const res = await fetch('/api/pipeline/save-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile: payloadProfile }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`)

      setResolvedProfile(data.profile || null)
      setResolvedProfilePath(data.profile_path || '')
      setDraft(profileToDraft(data.profile || null))
      setIsEditing(false)
      onProfileUpdated?.(data.profile_path || '', data.profile || null)

      const profilesRes = await fetch('/api/pipeline/profiles')
      const profilesData = await profilesRes.json()
      if (profilesRes.ok && !profilesData.error) {
        setSavedProfiles(profilesData.profiles || [])
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const rankingRows = (resolvedProfile?.ranking?.categories || [])
    .map(c => `${c.label} (${c.weight}%)`)
    .join(', ')

  const thresholds = resolvedProfile?.ranking?.priority_thresholds
    ? `HOT ${resolvedProfile.ranking.priority_thresholds.HOT}, WARM ${resolvedProfile.ranking.priority_thresholds.WARM}, NURTURE ${resolvedProfile.ranking.priority_thresholds.NURTURE}`
    : '—'

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm p-4 md:p-6 flex items-center justify-center">
      <div className="w-full max-w-5xl rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <div>
            <h3 className="text-base font-bold text-white">Current Pipeline Settings</h3>
            <p className="text-xs text-slate-400">Choose from saved pipeline configurations or edit current settings directly.</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800">
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-4 max-h-[72vh] overflow-y-auto space-y-6">
          <div className="rounded-xl border border-slate-700 overflow-hidden">
            <div className="px-3 py-2 border-b border-slate-700 bg-slate-800/70 flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-300">Saved Configurations</p>
              {savedLoading && <p className="text-[11px] text-slate-400">Loading...</p>}
            </div>
            <div className="max-h-56 overflow-y-auto">
              <table className="w-full border-collapse">
                <thead className="sticky top-0 bg-slate-900 z-10">
                  <tr className="border-b border-slate-700">
                    <th className="px-3 py-2 text-left text-[10px] uppercase tracking-widest text-slate-400">Created</th>
                    <th className="px-3 py-2 text-left text-[10px] uppercase tracking-widest text-slate-400">Objective</th>
                    <th className="px-3 py-2 text-left text-[10px] uppercase tracking-widest text-slate-400">Output</th>
                    <th className="px-3 py-2 text-left text-[10px] uppercase tracking-widest text-slate-400">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {!savedProfiles.length && !savedLoading && (
                    <tr>
                      <td colSpan={4} className="px-3 py-3 text-sm text-slate-400">No saved profiles yet.</td>
                    </tr>
                  )}
                  {savedProfiles.map(item => (
                    <tr key={item.profile_path} className="border-b border-slate-800/70">
                      <td className="px-3 py-2 text-xs text-slate-300">{formatCreatedAt(item.created_at)}</td>
                      <td className="px-3 py-2 text-sm text-slate-200 max-w-[420px] truncate" title={item.objective}>
                        {item.objective || '—'}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-300">{item.min_signals}-{item.max_signals}</td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => selectProfile(item)}
                          className="rounded-md border border-cyan-500/40 bg-cyan-500/15 px-2 py-1 text-[11px] font-semibold text-cyan-200 hover:bg-cyan-500/25"
                        >
                          Use
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex justify-end gap-2">
            {!isEditing && (
              <button
                onClick={startEditing}
                className="rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-700/80"
              >
                Adjust Settings
              </button>
            )}
            {isEditing && (
              <>
                <button
                  onClick={cancelEditing}
                  className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-100"
                >
                  Cancel
                </button>
                <button
                  onClick={saveEditedSettings}
                  disabled={saving}
                  className="rounded-lg px-3 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-semibold disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Settings'}
                </button>
              </>
            )}
          </div>

          {resolvedProfilePath && (
            <p className="text-xs text-cyan-300 break-all">Active profile file: {resolvedProfilePath}</p>
          )}
          {loading && <p className="text-sm text-slate-300">Loading settings...</p>}
          {error && <p className="text-sm text-red-300">{error}</p>}

          {resolvedProfile && (
            <div className="overflow-hidden rounded-xl border border-slate-700">
              <table className="w-full border-collapse">
                <tbody>
                  {!isEditing && (
                    <>
                      <ReadOnlyRow label="Objective" value={resolvedProfile.objective} />
                      <ReadOnlyRow label="Regions" value={(resolvedProfile.regions || []).join(', ')} />
                      <ReadOnlyRow label="Countries" value={(resolvedProfile.countries || []).join(', ')} />
                      <ReadOnlyRow label="Time Window" value={`${resolvedProfile.time_window_days || 90} days`} />
                      <ReadOnlyRow label="Domains" value={(resolvedProfile.domains || []).join(', ')} />
                      <ReadOnlyRow label="Signal Types" value={(resolvedProfile.signal_types || []).join(', ')} />
                      <ReadOnlyRow label="Target Output" value={`${resolvedProfile.target_output?.min_signals ?? 20}-${resolvedProfile.target_output?.max_signals ?? 25}`} />
                      <ReadOnlyRow label="Dedupe Policy" value={resolvedProfile.target_output?.dedupe_policy || 'prefer_new'} />
                      <ReadOnlyRow label="Ranking Categories" value={rankingRows} />
                      <ReadOnlyRow label="Priority Thresholds" value={thresholds} />
                      <ReadOnlyRow label="Inclusion Rules" value={(resolvedProfile.inclusion_rules || []).join(' | ')} />
                      <ReadOnlyRow label="Exclusion Rules" value={(resolvedProfile.exclusion_rules || []).join(' | ')} />
                    </>
                  )}

                  {isEditing && (
                    <>
                      <EditableRow label="Objective">
                        <input className={textInputClass()} value={draft.objective} onChange={e => setDraft(prev => ({ ...prev, objective: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Regions (CSV)">
                        <input className={textInputClass()} value={draft.regions} onChange={e => setDraft(prev => ({ ...prev, regions: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Countries (CSV)">
                        <input className={textInputClass()} value={draft.countries} onChange={e => setDraft(prev => ({ ...prev, countries: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Time Window Days">
                        <input type="number" min={1} className={textInputClass()} value={draft.time_window_days} onChange={e => setDraft(prev => ({ ...prev, time_window_days: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Domains (CSV)">
                        <input className={textInputClass()} value={draft.domains} onChange={e => setDraft(prev => ({ ...prev, domains: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Signal Types (CSV)">
                        <input className={textInputClass()} value={draft.signal_types} onChange={e => setDraft(prev => ({ ...prev, signal_types: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Min Signals">
                        <input type="number" min={1} className={textInputClass()} value={draft.min_signals} onChange={e => setDraft(prev => ({ ...prev, min_signals: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Max Signals">
                        <input type="number" min={1} className={textInputClass()} value={draft.max_signals} onChange={e => setDraft(prev => ({ ...prev, max_signals: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Dedupe Policy">
                        <input className={textInputClass()} value={draft.dedupe_policy} onChange={e => setDraft(prev => ({ ...prev, dedupe_policy: e.target.value }))} />
                      </EditableRow>
                      <EditableRow label="Ranking Categories JSON">
                        <textarea
                          className={`${textInputClass()} min-h-24 font-mono text-xs`}
                          value={draft.ranking_categories_json}
                          onChange={e => setDraft(prev => ({ ...prev, ranking_categories_json: e.target.value }))}
                        />
                      </EditableRow>
                      <EditableRow label="Priority Thresholds JSON">
                        <textarea
                          className={`${textInputClass()} min-h-20 font-mono text-xs`}
                          value={draft.priority_thresholds_json}
                          onChange={e => setDraft(prev => ({ ...prev, priority_thresholds_json: e.target.value }))}
                        />
                      </EditableRow>
                      <EditableRow label="Inclusion Rules (one per line)">
                        <textarea
                          className={`${textInputClass()} min-h-24`}
                          value={draft.inclusion_rules}
                          onChange={e => setDraft(prev => ({ ...prev, inclusion_rules: e.target.value }))}
                        />
                      </EditableRow>
                      <EditableRow label="Exclusion Rules (one per line)">
                        <textarea
                          className={`${textInputClass()} min-h-24`}
                          value={draft.exclusion_rules}
                          onChange={e => setDraft(prev => ({ ...prev, exclusion_rules: e.target.value }))}
                        />
                      </EditableRow>
                    </>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
