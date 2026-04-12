import { useEffect, useState, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import { MediaGrid } from '../components/workspace/MediaGrid'
import { MediaUploader } from '../components/workspace/MediaUploader'
import { BackstoryEditor } from '../components/workspace/BackstoryEditor'
import { MakeMovieButton } from '../components/workspace/MakeMovieButton'
import { StatusBadge } from '../components/scenes/StatusBadge'
import { useScenes } from '../hooks/useScenes'
import { useMediaUpload } from '../hooks/useMediaUpload'
import { usePipeline } from '../hooks/usePipeline'
import type { Scene } from '../types/scene'

export function SceneWorkspace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { fetchScene, updateScene } = useScenes()
  const { uploadMedia, deleteMedia, uploading } = useMediaUpload(id || '')
  const pipeline = usePipeline(id || '')
  const [scene, setScene] = useState<Scene | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingTitle, setEditingTitle] = useState(false)
  const [triggering, setTriggering] = useState(false)

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

  const handleMakeMovie = async () => {
    setTriggering(true)
    const ok = await pipeline.triggerAnalysis()
    setTriggering(false)
    if (ok) {
      navigate(`/scenes/${id}/screenplay`)
    }
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
  const isDraft = scene.status === 'draft' || scene.status === 'ready' || scene.status === 'failed'
  const hasScreenplay = scene.status === 'screenplay_review' || scene.status === 'approved' || scene.status === 'complete'

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
          <StatusBadge status={scene.status} />
        </div>

        {/* Link to movie if complete */}
        {(scene.status === 'complete' || scene.status === 'published') && scene.final_video_url && (
          <Link
            to={`/scenes/${id}/movie`}
            className="block bg-complete/10 rounded-xl p-4 border border-complete/30 hover:border-complete transition-colors text-center"
          >
            <span className="text-complete font-semibold">
              🎬 Watch Your Movie
            </span>
          </Link>
        )}

        {/* Link to screenplay if it exists */}
        {hasScreenplay && (
          <Link
            to={`/scenes/${id}/screenplay`}
            className="block bg-surface rounded-xl p-4 border border-review/30 hover:border-review transition-colors text-center"
          >
            <span className="text-review font-semibold">
              🎬 View Screenplay {scene.status === 'screenplay_review' ? '— Ready for Review' : ''}
            </span>
          </Link>
        )}

        {/* Pipeline error */}
        {pipeline.error && (
          <div className="bg-error/10 border border-error rounded-xl p-4 text-error text-sm">
            {pipeline.error}
          </div>
        )}

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

        {/* Make My Movie — only show for draft/ready/failed scenes */}
        {isDraft && (
          <MakeMovieButton
            photoCount={photoCount}
            backstoryLength={scene.backstory?.length || 0}
            onClick={handleMakeMovie}
            disabled={triggering}
          />
        )}
      </main>
    </div>
  )
}
