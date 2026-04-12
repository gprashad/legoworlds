interface VideoPlayerProps {
  src: string
  title: string
}

export function VideoPlayer({ src, title }: VideoPlayerProps) {
  return (
    <div className="rounded-xl overflow-hidden bg-black">
      <video
        src={src}
        controls
        autoPlay
        className="w-full aspect-video"
        title={title}
      />
    </div>
  )
}
