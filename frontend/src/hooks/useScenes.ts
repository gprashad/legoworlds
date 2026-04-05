import { useState, useCallback } from 'react'
import { apiFetch } from '../config/api'
import type { Scene, SceneCreate, SceneUpdate } from '../types/scene'

export function useScenes() {
  const [scenes, setScenes] = useState<Scene[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchScenes = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch<Scene[]>('/api/scenes')
      setScenes(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load scenes')
    } finally {
      setLoading(false)
    }
  }, [])

  const createScene = useCallback(async (body: SceneCreate = {}): Promise<Scene | null> => {
    try {
      const scene = await apiFetch<Scene>('/api/scenes', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setScenes(prev => [scene, ...prev])
      return scene
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create scene')
      return null
    }
  }, [])

  const updateScene = useCallback(async (id: string, body: SceneUpdate): Promise<Scene | null> => {
    try {
      const scene = await apiFetch<Scene>(`/api/scenes/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      setScenes(prev => prev.map(s => s.id === id ? { ...s, ...scene } : s))
      return scene
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update scene')
      return null
    }
  }, [])

  const deleteScene = useCallback(async (id: string): Promise<boolean> => {
    try {
      await apiFetch(`/api/scenes/${id}`, { method: 'DELETE' })
      setScenes(prev => prev.filter(s => s.id !== id))
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete scene')
      return false
    }
  }, [])

  const fetchScene = useCallback(async (id: string): Promise<Scene | null> => {
    setLoading(true)
    setError(null)
    try {
      return await apiFetch<Scene>(`/api/scenes/${id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load scene')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  return { scenes, loading, error, fetchScenes, createScene, updateScene, deleteScene, fetchScene }
}
