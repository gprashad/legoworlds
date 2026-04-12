interface DownloadButtonProps {
  url: string
  filename: string
}

export function DownloadButton({ url, filename }: DownloadButtonProps) {
  return (
    <a
      href={url}
      download={filename}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black rounded-xl font-semibold hover:bg-accent-hover transition-colors"
    >
      <span>⬇</span> Download Movie
    </a>
  )
}
