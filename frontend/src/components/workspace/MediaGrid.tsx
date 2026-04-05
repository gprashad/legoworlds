import type { SceneMedia } from '../../types/scene'

interface MediaGridProps {
  media: SceneMedia[]
  onDelete: (mediaId: string) => void
}

export function MediaGrid({ media, onDelete }: MediaGridProps) {
  if (media.length === 0) return null

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {media
        .sort((a, b) => a.sort_order - b.sort_order)
        .map(item => (
          <div key={item.id} className="relative group aspect-square rounded-lg overflow-hidden bg-surface-elevated">
            {item.file_type === 'photo' ? (
              <img
                src={item.file_url}
                alt={item.file_name || 'Photo'}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <span className="text-3xl">🎬</span>
              </div>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(item.id) }}
              className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/60 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            >
              x
            </button>
            {item.sort_order === 0 && (
              <span className="absolute bottom-1 left-1 text-[10px] bg-accent text-black px-1.5 py-0.5 rounded-full font-medium">
                Cover
              </span>
            )}
          </div>
        ))}
    </div>
  )
}
