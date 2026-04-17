import { useEffect, useState, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import { MediaGrid } from '../components/workspace/MediaGrid'
import { MediaUploader } from '../components/workspace/MediaUploader'
import { BackstoryEditor } from '../components/workspace/BackstoryEditor'
import { DescriptionForm } from '../components/workspace/DescriptionForm'
import type { StructuredDescription } from '../types/shotlist'
import { MakeMovieButton } from '../components/workspace/MakeMovieButton'
import { VoiceoverRecorder } from '../components/workspace/VoiceoverRecorder'
import { Modal } from '../components/ui/Modal'
import { StatusBadge } from '../components/scenes/StatusBadge'
import { useScenes } from '../hooks/useScenes'
import { useMediaUpload } from '../hooks/useMediaUpload'
import { usePipeline } from '../hooks/usePipeline'
import type { Scene } from '../types/scene'

export function SceneWorkspace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { fetchScene, updateScene, deleteScene } = useScenes()
  const { uploadMedia, deleteMedia, uploading, uploadProgress, uploadFileName } = useMediaUpload(id || '')
  const pipeline = usePipeline(id || '')
  const [scene, setScene] = useState<Scene | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingTitle, setEditingTitle] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [suggesting, setSuggesting] = useState(false)

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

  const handleDescriptionChange = async (value: StructuredDescription) => {
    if (!id) return
    await updateScene(id, { structured_description: value as Record<string, unknown> })
    setScene(prev => prev ? { ...prev, structured_description: value as Record<string, unknown> } : prev)
  }

  const [videoProcessing, setVideoProcessing] = useState(false)

  const handleFilesSelected = async (files: File[]) => {
    const hasVideo = files.some(f => f.type.startsWith('video/'))
    const newMedia = await uploadMedia(files)
    if (newMedia.length > 0) {
      setScene(prev => prev ? { ...prev, media: [...prev.media, ...newMedia] } : prev)
    }
    // If a video was uploaded, it's being processed — poll for new frames + backstory
    if (hasVideo && newMedia.length > 0) {
      setVideoProcessing(true)
      // Poll every 3s for ~30s to pick up extracted frames + transcription
      let polls = 0
      const pollInterval = setInterval(async () => {
        polls++
        const updated = await fetchScene(id!)
        if (updated) {
          const newFrameCount = updated.media.filter(m => m.source === 'video_extract').length
          const hadFrames = scene?.media.filter(m => m.source === 'video_extract').length || 0
          if (newFrameCount > hadFrames || polls >= 10) {
            setScene(updated)
            setVideoProcessing(false)
            clearInterval(pollInterval)
          }
        }
        if (polls >= 10) {
          setVideoProcessing(false)
          clearInterval(pollInterval)
        }
      }, 3000)
    }
  }

  const handleDeleteMedia = async (mediaId: string) => {
    await deleteMedia(mediaId)
    setScene(prev => prev ? { ...prev, media: prev.media.filter(m => m.id !== mediaId) } : prev)
  }

  const handleSuggestBackstory = async () => {
    if (!id) return
    setSuggesting(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/scenes/${id}/suggest-backstory`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        const suggestion = data.suggestion
        await updateScene(id, { backstory: suggestion })
        setScene(prev => prev ? { ...prev, backstory: suggestion } : prev)
      }
    } catch {
      // silently fail
    } finally {
      setSuggesting(false)
    }
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
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6 sm:space-y-8">
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
          <div className="ml-auto">
            <button
              onClick={() => setShowDeleteModal(true)}
              className="text-text-secondary hover:text-error text-sm transition-colors"
            >
              Delete
            </button>
          </div>
        </div>

        {/* Delete confirmation modal */}
        <Modal open={showDeleteModal} onClose={() => setShowDeleteModal(false)}>
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-text-primary">Delete scene?</h3>
            <p className="text-sm text-text-secondary">
              This will permanently delete "{scene.title}" and all its photos, screenplay, and movie. This can't be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="px-4 py-2 bg-surface-elevated border border-border rounded-lg text-sm text-text-primary hover:border-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  const ok = await deleteScene(id!)
                  if (ok) navigate('/scenes')
                }}
                className="px-4 py-2 bg-error text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
              >
                Delete
              </button>
            </div>
          </div>
        </Modal>

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

        {/* Video processing indicator */}
        {videoProcessing && (
          <div className="bg-surface rounded-xl border border-accent/30 p-6 space-y-4 overflow-hidden relative">
            {/* Animated shimmer background */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-accent/5 to-transparent animate-[shimmer_2s_infinite]" style={{backgroundSize: '200% 100%'}} />

            <div className="relative flex items-center gap-4">
              <div className="relative">
                <div className="animate-spin rounded-full h-10 w-10 border-3 border-accent/20 border-t-accent" />
                <span className="absolute inset-0 flex items-center justify-center text-lg">🎬</span>
              </div>
              <div>
                <p className="text-text-primary font-semibold">Processing your video</p>
                <p className="text-text-secondary text-sm">This takes 15-30 seconds</p>
              </div>
            </div>

            <div className="relative space-y-2.5">
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-accent flex items-center justify-center text-white text-xs animate-pulse">1</div>
                <span className="text-sm text-text-primary">Extracting key frames from your video</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-accent/30 flex items-center justify-center text-white text-xs">2</div>
                <span className="text-sm text-text-secondary">Listening to your narration</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-accent/30 flex items-center justify-center text-white text-xs">3</div>
                <span className="text-sm text-text-secondary">Understanding characters and story</span>
              </div>
            </div>

            {/* Animated progress dots */}
            <div className="relative flex gap-1.5 justify-center pt-2">
              <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{animationDelay: '0ms'}} />
              <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{animationDelay: '150ms'}} />
              <div className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{animationDelay: '300ms'}} />
            </div>
          </div>
        )}

        {/* Media section */}
        <section className="bg-surface rounded-xl p-5 border border-border space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Media</h2>
          <MediaGrid media={scene.media} onDelete={handleDeleteMedia} />
          <MediaUploader onFilesSelected={handleFilesSelected} uploading={uploading} uploadProgress={uploadProgress} uploadFileName={uploadFileName} />
          <VoiceoverRecorder
            sceneId={id || ''}
            existingUrl={scene.voiceover_url}
            onRecorded={(url) => {
              updateScene(id!, { backstory: scene.backstory || '' })
              setScene(prev => prev ? { ...prev, voiceover_url: url } : prev)
            }}
            onRemoved={() => setScene(prev => prev ? { ...prev, voiceover_url: null } : prev)}
          />
        </section>

        {/* The Brief — structured description */}
        <section className="bg-surface rounded-xl p-5 border border-border">
          <DescriptionForm
            value={(scene.structured_description || {}) as StructuredDescription}
            onChange={handleDescriptionChange}
            canAutofill={Boolean(scene.scene_bible?.['_narration_intelligence'])}
            onAutofill={async () => {
              if (!id) return
              const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/scenes/${id}/autofill-brief`, { method: 'POST' })
              if (res.ok) {
                const data = await res.json()
                await updateScene(id, { structured_description: data.structured_description })
                setScene(prev => prev ? { ...prev, structured_description: data.structured_description } : prev)
              }
            }}
          />
        </section>

        {/* Legacy backstory (for video transcription + freeform notes) */}
        {scene.backstory && (
          <section className="bg-surface rounded-xl p-5 border border-border space-y-3">
            <details>
              <summary className="text-sm text-text-secondary cursor-pointer">
                Freeform notes (from video transcription or old scenes)
              </summary>
              <div className="mt-3">
                <BackstoryEditor
                  value={scene.backstory || ''}
                  onChange={handleBackstoryChange}
                />
                {photoCount > 0 && (
                  <button
                    onClick={handleSuggestBackstory}
                    disabled={suggesting}
                    className="mt-2 text-sm px-4 py-2 bg-accent/10 text-accent border border-accent/30 rounded-lg hover:bg-accent/20 transition-colors disabled:opacity-50"
                  >
                    {suggesting ? 'Looking at your photos...' : '✨ Suggest from photos'}
                  </button>
                )}
              </div>
            </details>
          </section>
        )}

        {/* Movie settings */}
        <section className="bg-surface rounded-xl p-5 border border-border space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Movie Settings</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
        {isDraft && (() => {
          const sd = (scene.structured_description || {}) as StructuredDescription
          const briefLength = (sd.what_happens || '').length + (sd.one_liner || '').length
          const effectiveLength = Math.max(briefLength, scene.backstory?.length || 0)
          return (
            <MakeMovieButton
              photoCount={photoCount}
              backstoryLength={effectiveLength}
              onClick={handleMakeMovie}
              disabled={triggering}
            />
          )
        })()}
      </main>
    </div>
  )
}
