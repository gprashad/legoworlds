import { useState, useCallback, useRef, useEffect } from 'react'
import { apiFetch } from '../config/api'
import type { PipelineStatus } from '../types/screenplay'

export function usePipeline(sceneId: string) {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiFetch<PipelineStatus>(`/api/scenes/${sceneId}/status`)
      setStatus(data)
      return data
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch status')
      return null
    }
  }, [sceneId])

  const startPolling = useCallback(() => {
    setPolling(true)
    // Poll every 3 seconds
    intervalRef.current = setInterval(async () => {
      const data = await fetchStatus()
      if (data) {
        const jobStatus = data.job?.status
        // Stop polling when job is done
        if (jobStatus === 'awaiting_approval' || jobStatus === 'complete' || jobStatus === 'failed') {
          if (intervalRef.current) clearInterval(intervalRef.current)
          setPolling(false)
        }
      }
    }, 3000)
  }, [fetchStatus])

  const stopPolling = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    setPolling(false)
  }, [])

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  const triggerAnalysis = useCallback(async () => {
    setError(null)
    try {
      await apiFetch(`/api/scenes/${sceneId}/analyze`, { method: 'POST' })
      startPolling()
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start analysis')
      return false
    }
  }, [sceneId, startPolling])

  const reviseScreenplay = useCallback(async (feedback: string) => {
    setError(null)
    try {
      await apiFetch(`/api/scenes/${sceneId}/revise`, {
        method: 'POST',
        body: JSON.stringify({ feedback }),
      })
      startPolling()
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to revise')
      return false
    }
  }, [sceneId, startPolling])

  const greenlight = useCallback(async () => {
    setError(null)
    try {
      await apiFetch(`/api/scenes/${sceneId}/greenlight`, { method: 'POST' })
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to greenlight')
      return false
    }
  }, [sceneId])

  return {
    status,
    polling,
    error,
    fetchStatus,
    startPolling,
    stopPolling,
    triggerAnalysis,
    reviseScreenplay,
    greenlight,
  }
}
