import type { PipelineStatus } from '../../types/screenplay'

interface ProgressTrackerProps {
  status: PipelineStatus | null
  mode?: 'analysis' | 'production'
}

interface Step {
  id: string
  label: string
  match: (stage: string) => boolean
}

const ANALYSIS_STEPS: Step[] = [
  { id: 'scene_analysis', label: 'Analyzing your photos', match: s => s === 'queued' || s === 'scene_analysis' },
  { id: 'screenplay', label: 'Writing your screenplay', match: s => s === 'screenplay' || s === 'screenplay_revision' },
  { id: 'review', label: 'Ready for your review', match: s => s === 'screenplay_review' },
]

const PRODUCTION_STEPS: Step[] = [
  { id: 'video', label: 'Filming scenes', match: s => s.startsWith('video') },
  { id: 'voice', label: 'Recording voices', match: s => s === 'voice_generation' },
  { id: 'assembly', label: 'Editing final movie', match: s => s === 'assembly' },
  { id: 'done', label: 'Movie complete!', match: s => s === 'complete' },
]

function getDetailText(stage: string): string {
  const videoMatch = stage.match(/^video_scene_(\d+)_of_(\d+)$/)
  if (videoMatch) return `Generating video for scene ${videoMatch[1]} of ${videoMatch[2]}...`

  const map: Record<string, string> = {
    queued: 'Starting up the pipeline...',
    scene_analysis: 'Claude is studying every minifig, vehicle, and building in your photos...',
    screenplay: 'Writing dialogue, camera angles, and scene directions...',
    screenplay_revision: 'Revising the screenplay with your feedback...',
    screenplay_review: 'Your screenplay is ready! Take a look below.',
    video_generation: 'Sending your scenes to the video generator...',
    voice_generation: 'Each character is getting their own voice...',
    assembly: 'Stitching title cards, slideshow, scenes, and credits together...',
    complete: 'All done!',
  }
  return map[stage] || 'Working on it...'
}

function getStepStatus(step: Step, currentStage: string, completedStages: string[], jobStatus: string): 'done' | 'active' | 'waiting' {
  if (jobStatus === 'complete' || jobStatus === 'awaiting_approval') {
    // All steps done for current mode
    return 'done'
  }
  if (step.match(currentStage)) return 'active'
  if (completedStages.some(s => step.match(s) || s === step.id)) return 'done'

  // Check ordering
  return 'waiting'
}

export function ProgressTracker({ status, mode = 'analysis' }: ProgressTrackerProps) {
  // Show a waiting state if status hasn't loaded yet
  if (!status || !status.job) {
    return (
      <div className="bg-surface rounded-xl p-6 border border-border space-y-5">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-accent border-t-transparent" />
          <h2 className="text-lg font-semibold text-text-primary">Starting pipeline...</h2>
        </div>
        <div className="w-full bg-surface-elevated rounded-full h-2 overflow-hidden">
          <div className="h-full bg-accent/50 rounded-full w-1/12 animate-pulse" />
        </div>
        <p className="text-text-secondary text-sm">Hang tight — connecting to the server...</p>
      </div>
    )
  }

  const job = status.job
  const stage = job.current_stage || 'queued'
  const pct = job.progress_pct || 0
  const failed = job.status === 'failed'
  const complete = job.status === 'complete' || job.status === 'awaiting_approval'
  const completedStages = (job.stages_completed || []) as string[]
  const steps = mode === 'production' ? PRODUCTION_STEPS : ANALYSIS_STEPS

  return (
    <div className="bg-surface rounded-xl p-6 border border-border space-y-5">
      {/* Header with animated icon */}
      <div className="flex items-center gap-3">
        {!failed && !complete && (
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-accent border-t-transparent" />
        )}
        {complete && <span className="text-xl">✅</span>}
        {failed && <span className="text-xl">❌</span>}
        <h2 className="text-lg font-semibold text-text-primary">
          {failed ? 'Something went wrong' : complete ? 'Done!' : getDetailText(stage)}
        </h2>
      </div>

      {/* Progress bar */}
      {!failed && (
        <div className="space-y-1">
          <div className="w-full bg-surface-elevated rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${complete ? 'bg-complete' : 'bg-accent'}`}
              style={{ width: `${Math.max(pct, 3)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-secondary">
            <span>{pct}% complete</span>
            {!complete && mode === 'analysis' && <span>~30-60 seconds</span>}
            {!complete && mode === 'production' && <span>~10-15 minutes</span>}
          </div>
        </div>
      )}

      {/* Step checklist */}
      <div className="space-y-2">
        {steps.map(step => {
          const stepStatus = failed ? 'waiting' : getStepStatus(step, stage, completedStages, job.status)
          return (
            <div key={step.id} className="flex items-center gap-3">
              {stepStatus === 'done' && (
                <span className="w-5 h-5 rounded-full bg-complete flex items-center justify-center text-white text-xs flex-shrink-0">✓</span>
              )}
              {stepStatus === 'active' && (
                <span className="w-5 h-5 rounded-full border-2 border-accent flex-shrink-0 animate-pulse" />
              )}
              {stepStatus === 'waiting' && (
                <span className="w-5 h-5 rounded-full border-2 border-border flex-shrink-0" />
              )}
              <span className={`text-sm ${stepStatus === 'done' ? 'text-complete' : stepStatus === 'active' ? 'text-text-primary font-medium' : 'text-text-secondary'}`}>
                {step.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Error */}
      {failed && job.error && (
        <div className="bg-error/10 rounded-lg p-3">
          <p className="text-error text-sm">{job.error}</p>
        </div>
      )}

      {/* Fun tip while waiting */}
      {!failed && !complete && (
        <p className="text-text-secondary text-xs italic border-t border-border pt-3">
          💡 Go build something new while you wait!
        </p>
      )}
    </div>
  )
}
