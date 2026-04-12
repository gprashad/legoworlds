import { Link } from 'react-router-dom'
import type { Scene } from '../../types/scene'
import { StatusBadge } from './StatusBadge'

export function SceneCard({ scene }: { scene: Scene }) {
  const coverPhoto = scene.media?.find(m => m.file_type === 'photo')
  const photoCount = scene.media?.filter(m => m.file_type === 'photo').length || 0
  const isComplete = scene.status === 'complete' || scene.status === 'published'
  const linkTo = isComplete ? `/scenes/${scene.id}/movie` : `/scenes/${scene.id}`

  return (
    <Link
      to={linkTo}
      className="block bg-surface rounded-xl overflow-hidden border border-border hover:border-accent/50 transition-all hover:scale-[1.02] no-underline"
    >
      <div className="aspect-[4/3] bg-surface-elevated flex items-center justify-center overflow-hidden">
        {coverPhoto ? (
          <img
            src={coverPhoto.file_url}
            alt={scene.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <span className="text-4xl opacity-30">🧱</span>
        )}
        {scene.status === 'complete' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/30">
            <span className="text-4xl">▶</span>
          </div>
        )}
      </div>
      <div className="p-3">
        <h3 className="font-semibold text-text-primary text-sm truncate">{scene.title}</h3>
        <div className="flex items-center justify-between mt-2">
          <StatusBadge status={scene.status} />
          <span className="text-text-secondary text-xs">
            {photoCount} photo{photoCount !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </Link>
  )
}
