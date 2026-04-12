import { Link } from 'react-router-dom'
import type { SceneMedia } from '../../types/scene'

interface BehindTheScenesProps {
  sceneId: string
  media: SceneMedia[]
  hasScreenplay: boolean
}

export function BehindTheScenes({ sceneId, media, hasScreenplay }: BehindTheScenesProps) {
  const photos = media.filter(m => m.file_type === 'photo').sort((a, b) => a.sort_order - b.sort_order)

  if (photos.length === 0) return null

  return (
    <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
        Behind the Scenes
      </h3>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {photos.map(photo => (
          <img
            key={photo.id}
            src={photo.file_url}
            alt={photo.file_name || 'Build photo'}
            className="h-24 w-24 object-cover rounded-lg flex-shrink-0"
          />
        ))}
      </div>
      <div className="flex gap-3 text-sm">
        <span className="text-text-secondary">The original build</span>
        {hasScreenplay && (
          <Link
            to={`/scenes/${sceneId}/screenplay`}
            className="text-review hover:underline"
          >
            View Screenplay
          </Link>
        )}
      </div>
    </div>
  )
}
