import { useState, useCallback } from 'react'
import { supabase } from '../config/supabase'
import { apiFetch } from '../config/api'
import type { SceneMedia } from '../types/scene'

export function useMediaUpload(sceneId: string) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const uploadMedia = useCallback(async (files: File[]): Promise<SceneMedia[]> => {
    setUploading(true)
    setError(null)
    const results: SceneMedia[] = []

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const ext = file.name.split('.').pop() || 'jpg'
        const storagePath = `scenes/${sceneId}/input/${Date.now()}_${i}.${ext}`

        // Upload to Supabase Storage
        const { error: uploadError } = await supabase.storage
          .from('legoworlds')
          .upload(storagePath, file, { contentType: file.type })

        if (uploadError) throw uploadError

        // Get public URL
        const { data: { publicUrl } } = supabase.storage
          .from('legoworlds')
          .getPublicUrl(storagePath)

        // Register with backend
        const fileType = file.type.startsWith('video/') ? 'video' : 'photo'
        const media = await apiFetch<SceneMedia>(`/api/scenes/${sceneId}/media`, {
          method: 'POST',
          body: JSON.stringify({
            file_url: publicUrl,
            file_type: fileType,
            file_name: file.name,
            file_size_bytes: file.size,
            sort_order: i,
            source: 'upload',
          }),
        })
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
      await apiFetch(`/api/scenes/${sceneId}/media/${mediaId}`, { method: 'DELETE' })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    }
  }, [sceneId])

  return { uploadMedia, deleteMedia, uploading, error }
}
