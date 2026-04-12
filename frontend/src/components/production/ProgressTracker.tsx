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
}

export function ProgressTracker({ status }: ProgressTrackerProps) {
  const job = status.job
  if (!job) return null

  const stage = job.current_stage || 'queued'
  const pct = job.progress_pct || 0
  const failed = job.status === 'failed'

  return (
    <div className="bg-surface rounded-xl p-6 border border-border space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">
          {failed ? 'Something went wrong' : stageLabels[stage] || 'Working...'}
        </h2>
        {!failed && (
          <span className="text-sm text-text-secondary">{pct}%</span>
        )}
      </div>

      {!failed && (
        <div className="w-full bg-surface-elevated rounded-full h-3 overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {failed && job.error && (
        <p className="text-error text-sm">{job.error}</p>
      )}

      {!failed && pct < 100 && (
        <p className="text-text-secondary text-sm">
          This usually takes 30-60 seconds. Hang tight!
        </p>
      )}
    </div>
  )
}
