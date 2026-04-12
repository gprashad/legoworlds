import type { PipelineStatus } from '../../types/screenplay'

interface ProgressTrackerProps {
  status: PipelineStatus
}

const stageLabels: Record<string, string> = {
  queued: 'Queued...',
  scene_analysis: 'Reading your scene...',
  screenplay: 'Writing your screenplay...',
  screenplay_revision: 'Revising your screenplay...',
  screenplay_review: 'Screenplay ready!',
  video_generation: 'Filming your scenes...',
  voice_generation: 'Recording voices...',
  assembly: 'Editing your movie...',
  complete: 'Your movie is ready!',
}

function getStageMessage(stage: string): string {
  // Handle dynamic stage names like "video_scene_2_of_4"
  const videoMatch = stage.match(/^video_scene_(\d+)_of_(\d+)$/)
  if (videoMatch) {
    return `Filming scene ${videoMatch[1]} of ${videoMatch[2]}...`
  }
  return stageLabels[stage] || 'Working...'
}

function getTimeEstimate(stage: string): string {
  if (stage.startsWith('scene_analysis') || stage === 'screenplay' || stage === 'screenplay_revision') {
    return 'Usually takes 30-60 seconds.'
  }
  if (stage.startsWith('video')) {
    return 'Video generation takes 2-5 minutes per scene.'
  }
  if (stage === 'voice_generation') {
    return 'Almost there — recording voices...'
  }
  if (stage === 'assembly') {
    return 'Final touches — stitching everything together!'
  }
  return 'Hang tight!'
}

export function ProgressTracker({ status }: ProgressTrackerProps) {
  const job = status.job
  if (!job) return null

  const stage = job.current_stage || 'queued'
  const pct = job.progress_pct || 0
  const failed = job.status === 'failed'
  const complete = job.status === 'complete'

  return (
    <div className="bg-surface rounded-xl p-6 border border-border space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">
          {failed ? 'Something went wrong' : getStageMessage(stage)}
        </h2>
        {!failed && (
          <span className="text-sm text-text-secondary">{pct}%</span>
        )}
      </div>

      {!failed && (
        <div className="w-full bg-surface-elevated rounded-full h-3 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${complete ? 'bg-complete' : 'bg-accent'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {failed && job.error && (
        <p className="text-error text-sm">{job.error}</p>
      )}

      {!failed && !complete && (
        <p className="text-text-secondary text-sm">
          {getTimeEstimate(stage)}
        </p>
      )}
    </div>
  )
}
