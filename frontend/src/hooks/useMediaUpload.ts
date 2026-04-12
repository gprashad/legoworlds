import { useState, useCallback } from 'react'
import type { SceneMedia } from '../types/scene'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useMediaUpload(sceneId: string) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const uploadMedia = useCallback(async (files: File[]): Promise<SceneMedia[]> => {
    setUploading(true)
    setError(null)
    const results: SceneMedia[] = []

    try {
      for (const file of files) {
        const formData = new FormData()
        formData.append('file', file)

        const res = await fetch(`${API_URL}/api/scenes/${sceneId}/media/upload`, {
          method: 'POST',
          body: formData,
        })

        if (!res.ok) {
          const body = await res.text()
          throw new Error(`Upload failed: ${body}`)
        }

        const media: SceneMedia = await res.json()
        results.push(media)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }

    return results
  }, [sceneId])

  const deleteMedia = useCallback(async (mediaId: string) => {
    try {
      await fetch(`${API_URL}/api/scenes/${sceneId}/media/${mediaId}`, { method: 'DELETE' })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    }
  }, [sceneId])

  return { uploadMedia, deleteMedia, uploading, error }
}
