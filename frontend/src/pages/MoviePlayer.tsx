import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import { VideoPlayer } from '../components/movie/VideoPlayer'
import { DownloadButton } from '../components/movie/DownloadButton'
import { BehindTheScenes } from '../components/movie/BehindTheScenes'
import { SharePanel } from '../components/movie/SharePanel'
import { ProgressTracker } from '../components/production/ProgressTracker'
import { useScenes } from '../hooks/useScenes'
import { usePipeline } from '../hooks/usePipeline'
import type { Scene } from '../types/scene'
import type { Screenplay } from '../types/screenplay'

export function MoviePlayer() {
  const { id } = useParams<{ id: string }>()
  const { fetchScene } = useScenes()
  const pipeline = usePipeline(id || '')
  const [scene, setScene] = useState<Scene | null>(null)
  const [loading, setLoading] = useState(true)

  const loadScene = useCallback(async () => {
    if (!id) return
    setLoading(true)
    const data = await fetchScene(id)
    if (data) setScene(data)
    setLoading(false)
  }, [id, fetchScene])

  useEffect(() => {
    loadScene()
    pipeline.fetchStatus()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // If still producing, poll
  useEffect(() => {
    if (scene && ['producing', 'assembling', 'approved'].includes(scene.status)) {
      pipeline.startPolling()
    }
  }, [scene?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reload when production completes
  useEffect(() => {
    const jobStatus = pipeline.status?.job?.status
    if (jobStatus === 'complete' || jobStatus === 'failed') {
      pipeline.stopPolling()
      loadScene()
    }
  }, [pipeline.status?.job?.status]) // eslint-disable-line react-hooks/exhaustive-deps

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

  const isProducing = ['producing', 'assembling', 'approved'].includes(scene.status)
  const isComplete = scene.status === 'complete' || scene.status === 'published'
  const screenplay = scene.screenplay as Screenplay | null

  return (
    <div className="min-h-screen bg-bg">
      <Header />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
        {/* Title bar */}
        <div className="flex items-center justify-between">
          <Link to={`/scenes/${id}`} className="text-text-secondary hover:text-text-primary transition-colors">
            ← {scene.title}
          </Link>
          <span className="text-sm font-semibold text-accent uppercase tracking-wider">
            Premiere
          </span>
        </div>

        {/* Still producing */}
        {isProducing && (
          <ProgressTracker status={pipeline.status} mode="production" />
        )}

        {/* Movie ready */}
        {isComplete && scene.final_video_url && (
          <>
            <VideoPlayer src={scene.final_video_url} title={scene.title} />

            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-xl font-bold text-text-primary">{scene.title}</h1>
                {screenplay && (
                  <p className="text-text-secondary text-sm mt-1">
                    {screenplay.total_scenes} scenes · ~{screenplay.estimated_duration_seconds}s
                    {scene.final_video_duration_seconds && ` · ${Math.floor(scene.final_video_duration_seconds / 60)}:${String(scene.final_video_duration_seconds % 60).padStart(2, '0')}`}
                  </p>
                )}
              </div>
              <DownloadButton
                url={scene.final_video_url}
                filename={`${scene.title.replace(/\s+/g, '_')}.mp4`}
              />
            </div>

            <SharePanel videoUrl={scene.final_video_url} title={scene.title} />

            <BehindTheScenes
              sceneId={scene.id}
              media={scene.media}
              hasScreenplay={!!screenplay}
            />

            {/* Re-make / sequel buttons */}
            <div className="flex gap-3 justify-center pt-4">
              <Link
                to={`/scenes/${id}`}
                className="px-5 py-2.5 bg-surface-elevated border border-border rounded-xl text-sm text-text-primary hover:border-accent transition-colors"
              >
                Back to Scene
              </Link>
            </div>
          </>
        )}

        {/* Not producing and no video */}
        {!isProducing && !isComplete && (
          <div className="text-center py-20 space-y-4">
            <span className="text-5xl block">🎬</span>
            <p className="text-text-secondary">No movie yet. Go review and green light your screenplay!</p>
            <Link
              to={`/scenes/${id}/screenplay`}
              className="inline-block px-6 py-3 bg-primary text-white rounded-xl font-semibold hover:bg-primary-hover transition-colors"
            >
              View Screenplay
            </Link>
          </div>
        )}
      </main>
    </div>
  )
}
