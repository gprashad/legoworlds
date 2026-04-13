import { useState, useCallback } from 'react'
import type { SceneMedia } from '../types/scene'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function uploadWithProgress(
  url: string,
  formData: FormData,
  onProgress: (pct: number) => void,
): Promise<SceneMedia> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.responseText.slice(0, 200)}`))
      }
    }

    xhr.onerror = () => reject(new Error('Upload failed: network error'))
    xhr.ontimeout = () => reject(new Error('Upload failed: timeout'))
    xhr.timeout = 600000 // 10 min for large videos

    xhr.send(formData)
  })
}

export function useMediaUpload(sceneId: string) {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadFileName, setUploadFileName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const uploadMedia = useCallback(async (files: File[]): Promise<SceneMedia[]> => {
    setUploading(true)
    setError(null)
    setUploadProgress(0)
    const results: SceneMedia[] = []

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        setUploadFileName(file.name)
        setUploadProgress(0)

        const formData = new FormData()
        formData.append('file', file)

        const media = await uploadWithProgress(
          `${API_URL}/api/scenes/${sceneId}/media/upload`,
          formData,
          (pct) => setUploadProgress(pct),
        )
        results.push(media)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
      setUploadProgress(0)
      setUploadFileName('')
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

  return { uploadMedia, deleteMedia, uploading, uploadProgress, uploadFileName, error }
}
