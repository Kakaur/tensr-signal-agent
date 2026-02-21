import { useState, useCallback } from 'react'

export function usePipeline({ onComplete }) {
  const [running, setRunning] = useState(false)
  const [logs, setLogs] = useState([])

  const runPipeline = useCallback(async runOptions => {
    if (running) return
    setRunning(true)
    setLogs([])

    const options = typeof runOptions === 'string'
      ? { profilePath: runOptions }
      : (runOptions || {})

    try {
      const payload = {}
      if (options.runAllProfiles) {
        payload.run_all_profiles = true
      } else if (Array.isArray(options.profilePaths) && options.profilePaths.length > 0) {
        payload.profile_paths = options.profilePaths
      } else if (options.profilePath) {
        payload.profile_path = options.profilePath
      }

      const res = await fetch('/api/run-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setLogs([`Error: ${err.error || 'Unknown error'}`])
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6).trim()
            if (payload === '[DONE]') break
            try {
              const msg = JSON.parse(payload)
              if (msg.log) setLogs(prev => [...prev, msg.log])
            } catch { /* skip malformed */ }
          }
        }
      }
    } catch (e) {
      setLogs(prev => [...prev, `Connection error: ${e.message}`])
    } finally {
      setRunning(false)
      onComplete?.()
    }
  }, [running, onComplete])

  return { running, logs, runPipeline }
}
