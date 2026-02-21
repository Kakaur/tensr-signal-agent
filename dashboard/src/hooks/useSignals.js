import { useState, useEffect, useCallback } from 'react'

export function useSignals() {
  const [signals, setSignals] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [sigRes, sumRes] = await Promise.all([
        fetch('/api/signals'),
        fetch('/api/summary'),
      ])
      if (!sigRes.ok) throw new Error(`HTTP ${sigRes.status}`)
      const sigData = await sigRes.json()
      const sumData = await sumRes.json()
      setSignals(sigData.signals || [])
      setSummary(sumData)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  return { signals, summary, loading, error, refresh: fetchData }
}
