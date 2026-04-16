import type { Shot } from '../../types/shotlist'
import type { SceneMedia } from '../../types/scene'

interface ShotCardProps {
  shot: Shot
  media: SceneMedia[]
}

export function ShotCard({ shot, media }: ShotCardProps) {
  const photos = media.filter(m => m.file_type === 'photo').sort((a, b) => a.sort_order - b.sort_order)
  const refPhoto = photos[shot.reference_photo_index] || photos[0]

  return (
    <div className="bg-surface rounded-xl border border-border p-4 flex gap-4">
      {/* Reference photo */}
      <div className="flex-shrink-0 w-28 h-28 rounded-lg overflow-hidden bg-surface-elevated">
        {refPhoto ? (
          <img src={refPhoto.file_url} alt={`Shot ${shot.shot_number}`} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-2xl opacity-30">🎬</div>
        )}
      </div>

      {/* Shot details */}
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-text-primary text-sm">
            Shot {shot.shot_number}: {shot.type.replace(/_/g, ' ')}
          </h3>
          <span className="text-xs text-text-secondary bg-surface-elevated px-2 py-0.5 rounded-full">
            {shot.duration_seconds}s
          </span>
        </div>

        <p className="text-sm text-text-primary">{shot.description}</p>

        <div className="text-xs space-y-0.5">
          <p className="text-text-secondary">
            <span className="text-accent">Motion:</span> {shot.motion}
          </p>
          <p className="text-text-secondary">
            <span className="text-accent">Camera:</span> {shot.camera}
          </p>
          {shot.sfx_keyword && (
            <p className="text-text-secondary">
              <span className="text-accent">SFX:</span> {shot.sfx_keyword}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
