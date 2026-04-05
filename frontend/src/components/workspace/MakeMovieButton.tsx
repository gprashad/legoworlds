interface MakeMovieButtonProps {
  photoCount: number
  backstoryLength: number
  onClick: () => void
  disabled?: boolean
}

export function MakeMovieButton({ photoCount, backstoryLength, onClick, disabled }: MakeMovieButtonProps) {
  const hasPhotos = photoCount >= 2
  const hasBackstory = backstoryLength >= 20
  const isReady = hasPhotos && hasBackstory && !disabled

  return (
    <div className="space-y-3">
      <button
        onClick={onClick}
        disabled={!isReady}
        className={`
          w-full py-4 rounded-xl text-lg font-bold transition-all
          ${isReady
            ? 'bg-primary text-white hover:bg-primary-hover active:scale-[0.98] shadow-lg shadow-primary/30'
            : 'bg-surface-elevated text-text-secondary cursor-not-allowed'}
        `}
      >
        🎬 MAKE MY MOVIE
      </button>
      <div className="flex gap-4 justify-center text-sm">
        <span className={hasPhotos ? 'text-complete' : 'text-text-secondary'}>
          {hasPhotos ? '✓' : '○'} {photoCount} photo{photoCount !== 1 ? 's' : ''} (need 2+)
        </span>
        <span className={hasBackstory ? 'text-complete' : 'text-text-secondary'}>
          {hasBackstory ? '✓' : '○'} backstory
        </span>
      </div>
    </div>
  )
}
