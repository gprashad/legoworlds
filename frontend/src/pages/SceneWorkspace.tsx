import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import { MediaGrid } from '../components/workspace/MediaGrid'
import { MediaUploader } from '../components/workspace/MediaUploader'
import { BackstoryEditor } from '../components/workspace/BackstoryEditor'
import { MakeMovieButton } from '../components/workspace/MakeMovieButton'
import { useScenes } from '../hooks/useScenes'
import { useMediaUpload } from '../hooks/useMediaUpload'
import type { Scene } from '../types/scene'

export function SceneWorkspace() {
  const { id } = useParams<{ id: string }>()
  const { fetchScene, updateScene } = useScenes()
  const { uploadMedia, deleteMedia, uploading } = useMediaUpload(id || '')
  const [scene, setScene] = useState<Scene | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingTitle, setEditingTitle] = useState(false)

  const loadScene = useCallback(async () => {
    if (!id) return
    setLoading(true)
    const data = await fetchScene(id)
    if (data) setScene(data)
    setLoading(false)
  }, [id, fetchScene])

  useEffect(() => {
    loadScene()
  }, [loadScene])

  const handleTitleChange = async (newTitle: string) => {
    if (!id || !newTitle.trim()) return
    setEditingTitle(false)
    await updateScene(id, { title: newTitle.trim() })
    setScene(prev => prev ? { ...prev, title: newTitle.trim() } : prev)
  }

  const handleBackstoryChange = async (value: string) => {
    if (!id) return
    await updateScene(id, { backstory: value })
    setScene(prev => prev ? { ...prev, backstory: value } : prev)
  }

  const handleFilesSelected = async (files: File[]) => {
    const newMedia = await uploadMedia(files)
    if (newMedia.length > 0) {
      setScene(prev => prev ? { ...prev, media: [...prev.media, ...newMedia] } : prev)
    }
  }

  const handleDeleteMedia = async (mediaId: string) => {
    await deleteMedia(mediaId)
    setScene(prev => prev ? { ...prev, media: prev.media.filter(m => m.id !== mediaId) } : prev)
  }

  const handleMakeMovie = () => {
    // TODO: trigger pipeline
    alert('Pipeline not yet implemented — coming next!')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-bg">
        <Header />
        <div className="flex justify-center py-20">
          <div className="animate-spin rounded-full h-10 w-10 border-4 border-accent border-t-transparent" />
        </div>
      </div>
    )
  }

  if (!scene) {
    return (
      <div className="min-h-screen bg-bg">
        <Header />
        <div className="text-center py-20 text-error">Scene not found</div>
      </div>
    )
  }

  const photoCount = scene.media.filter(m => m.file_type === 'photo').length

  return (
    <div className="min-h-screen bg-bg">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        {/* Title bar */}
        <div className="flex items-center gap-3">
          <Link to="/scenes" className="text-text-secondary hover:text-text-primary transition-colors">
            ← My Scenes
          </Link>
          <span className="text-border">|</span>
          {editingTitle ? (
            <input
              autoFocus
              defaultValue={scene.title}
              onBlur={e => handleTitleChange(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleTitleChange((e.target as HTMLInputElement).value)}
              className="bg-transparent text-xl font-bold text-text-primary border-b border-accent focus:outline-none"
            />
          ) : (
            <h1
              onClick={() => setEditingTitle(true)}
              className="text-xl font-bold text-text-primary cursor-pointer hover:text-accent transition-colors"
            >
              {scene.title}
            </h1>
          )}
        </div>

        {/* Media section */}
        <section className="bg-surface rounded-xl p-5 border border-border space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Media</h2>
          <MediaGrid media={scene.media} onDelete={handleDeleteMedia} />
          <MediaUploader onFilesSelected={handleFilesSelected} uploading={uploading} />
        </section>

        {/* Backstory section */}
        <section className="bg-surface rounded-xl p-5 border border-border">
          <BackstoryEditor
            value={scene.backstory || ''}
            onChange={handleBackstoryChange}
          />
        </section>

        {/* Movie settings */}
        <section className="bg-surface rounded-xl p-5 border border-border space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Movie Settings</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-text-secondary mb-1">Director credit</label>
              <input
                type="text"
                defaultValue={scene.director_name || 'Jackson'}
                onBlur={e => id && updateScene(id, { director_name: e.target.value })}
                className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:border-accent transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-text-secondary mb-1">Movie style</label>
              <select
                defaultValue={scene.movie_style || 'cinematic'}
                onChange={e => id && updateScene(id, { movie_style: e.target.value })}
                className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:border-accent transition-colors"
              >
                <option value="cinematic">🎬 Cinematic</option>
              </select>
            </div>
          </div>
        </section>

        {/* Make My Movie */}
        <MakeMovieButton
          photoCount={photoCount}
          backstoryLength={scene.backstory?.length || 0}
          onClick={handleMakeMovie}
        />
      </main>
    </div>
  )
}
