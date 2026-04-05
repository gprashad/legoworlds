import type { SceneStatus } from '../../types/scene'

const statusConfig: Record<SceneStatus, { label: string; color: string }> = {
  draft: { label: 'Draft', color: 'bg-draft text-black' },
  ready: { label: 'Ready', color: 'bg-draft text-black' },
  analyzing: { label: 'Analyzing', color: 'bg-review text-white' },
  screenplay_review: { label: 'Review', color: 'bg-review text-white' },
  approved: { label: 'Approved', color: 'bg-greenlight text-white' },
  producing: { label: 'Producing', color: 'bg-producing text-white animate-pulse' },
  assembling: { label: 'Editing', color: 'bg-producing text-white animate-pulse' },
  complete: { label: 'Complete', color: 'bg-complete text-white' },
  published: { label: 'Published', color: 'bg-complete text-white' },
  failed: { label: 'Failed', color: 'bg-error text-white' },
}

export function StatusBadge({ status }: { status: SceneStatus }) {
  const config = statusConfig[status] || statusConfig.draft
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
      {config.label}
    </span>
  )
}
