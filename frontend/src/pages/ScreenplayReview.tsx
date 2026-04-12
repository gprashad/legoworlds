import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import { StoryboardCard } from '../components/screenplay/StoryboardCard'
import { NarratorCard } from '../components/screenplay/NarratorCard'
import { FeedbackForm } from '../components/screenplay/FeedbackForm'
import { GreenLightButton } from '../components/screenplay/GreenLightButton'
import { ProgressTracker } from '../components/production/ProgressTracker'
import { useScenes } from '../hooks/useScenes'
import { usePipeline } from '../hooks/usePipeline'
import type { Scene } from '../types/scene'
import type { Screenplay } from '../types/screenplay'

export function ScreenplayReview() {
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

  // If analyzing or producing, poll for status
  useEffect(() => {
    if (scene?.status === 'analyzing' || scene?.status === 'producing' || scene?.status === 'assembling' || scene?.status === 'approved') {
      pipeline.startPolling()
    }
  }, [scene?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  // When pipeline finishes, reload scene
  useEffect(() => {
    const jobStatus = pipeline.status?.job?.status
    if (jobStatus === 'awaiting_approval' || jobStatus === 'failed') {
      pipeline.stopPolling()
      loadScene()
    }
    if (jobStatus === 'complete') {
      pipeline.stopPolling()
      loadScene()
      // Navigate to movie player once we have it, for now reload scene
    }
  }, [pipeline.status?.job?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRevise = async (feedback: string) => {
    const ok = await pipeline.reviseScreenplay(feedback)
    if (ok) setScene(prev => prev ? { ...prev, status: 'analyzing' } : prev)
  }

  const handleGreenlight = async () => {
    const ok = await pipeline.greenlight()
    if (ok) {
      // Greenlight now triggers production — start polling
      setScene(prev => prev ? { ...prev, status: 'producing' } : prev)
      pipeline.fetchStatus()
      pipeline.startPolling()
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

  const isAnalyzing = scene.status === 'analyzing'
  const isProducing = scene.status === 'producing' || scene.status === 'assembling' || scene.status === 'approved'
  const isComplete = scene.status === 'complete'
  const isReviewable = scene.status === 'screenplay_review'
  const screenplay = scene.screenplay as Screenplay | null

  return (
    <div className="min-h-screen bg-bg">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {/* Title bar */}
        <div className="flex items-center justify-between">
          <Link to={`/scenes/${id}`} className="text-text-secondary hover:text-text-primary transition-colors">
            ← {scene.title}
          </Link>
          <span className="text-sm font-semibold text-review uppercase tracking-wider">
            {isProducing ? 'Production' : isComplete ? 'Complete' : 'Screenplay Review'}
          </span>
        </div>

        {/* Progress tracker while analyzing or producing */}
        {(isAnalyzing || isProducing) && pipeline.status && (
          <ProgressTracker status={pipeline.status} />
        )}

        {/* Movie complete banner */}
        {isComplete && scene.final_video_url && (
          <div className="bg-complete/10 border border-complete rounded-xl p-6 text-center space-y-4">
            <span className="text-5xl block">🎬</span>
            <h2 className="text-xl font-bold text-complete">Your movie is ready!</h2>
            <div className="space-y-3">
              <video
                src={scene.final_video_url}
                controls
                className="w-full rounded-lg"
                poster=""
              />
              <a
                href={scene.final_video_url}
                download
                className="inline-block px-6 py-3 bg-accent text-black rounded-xl font-semibold hover:bg-accent-hover transition-colors"
              >
                Download Movie
              </a>
            </div>
          </div>
        )}

        {/* Error */}
        {pipeline.error && (
          <div className="bg-error/10 border border-error rounded-xl p-4 text-error text-sm">
            {pipeline.error}
          </div>
        )}

        {/* Screenplay content */}
        {screenplay && !isAnalyzing && (
          <>
            <div className="text-center space-y-2">
              <h1 className="text-2xl font-bold text-accent">{screenplay.title}</h1>
              <p className="text-text-secondary text-sm">
                {screenplay.total_scenes} scenes · ~{screenplay.estimated_duration_seconds}s runtime
              </p>
            </div>

            {/* Narrator Intro */}
            <NarratorCard label="Narrator Intro" text={screenplay.narrator_intro} />

            {/* Scene cards */}
            <div className="space-y-4">
              {screenplay.scenes.map(s => (
                <StoryboardCard key={s.scene_number} scene={s} />
              ))}
            </div>

            {/* Narrator Outro */}
            <NarratorCard label="Narrator Outro" text={screenplay.narrator_outro} />

            {/* Credits */}
            <div className="text-center text-sm text-text-secondary space-y-1 py-4">
              <p>Directed by <span className="text-text-primary">{screenplay.credits.directed_by}</span></p>
              <p>Built by <span className="text-text-primary">{screenplay.credits.built_by}</span></p>
              <p>Produced by <span className="text-text-primary">{screenplay.credits.produced_by}</span></p>
            </div>

            {/* Feedback + Green Light — only during review */}
            {isReviewable && (
              <>
                <FeedbackForm onSubmit={handleRevise} disabled={pipeline.polling} />
                <div className="space-y-2">
                  <GreenLightButton onClick={handleGreenlight} disabled={pipeline.polling} />
                  <p className="text-center text-xs text-text-secondary">
                    Estimated production time: ~10-15 minutes
                  </p>
                </div>
              </>
            )}
          </>
        )}

        {/* No screenplay yet and not analyzing */}
        {!screenplay && !isAnalyzing && !isProducing && (
          <div className="text-center py-20 space-y-4">
            <span className="text-5xl block">🎬</span>
            <p className="text-text-secondary">No screenplay yet. Go back and hit "Make My Movie"!</p>
            <Link
              to={`/scenes/${id}`}
              className="inline-block px-6 py-3 bg-primary text-white rounded-xl font-semibold hover:bg-primary-hover transition-colors"
            >
              Back to Scene
            </Link>
          </div>
        )}
      </main>
    </div>
  )
}
