import { useState } from 'react'

interface SharePanelProps {
  videoUrl: string
  title: string
}

export function SharePanel({ videoUrl, title }: SharePanelProps) {
  const [copied, setCopied] = useState(false)

  const caption = `Check out "${title}" — made with Lego Worlds! #LegoWorlds #LegoAnimation #BrickFilm`

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(videoUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
      const input = document.createElement('input')
      input.value = videoUrl
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
        Share Your Movie
      </h3>

      <p className="text-text-primary text-sm">{caption}</p>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={handleCopyLink}
          className="px-4 py-2 bg-surface-elevated border border-border rounded-lg text-sm text-text-primary hover:border-accent transition-colors"
        >
          {copied ? '✓ Copied!' : 'Copy Link'}
        </button>
        <a
          href={videoUrl}
          download={`${title.replace(/\s+/g, '_')}.mp4`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 bg-surface-elevated border border-border rounded-lg text-sm text-text-primary hover:border-accent transition-colors"
        >
          Download MP4
        </a>
      </div>

      <p className="text-xs text-text-secondary">
        Social posting (TikTok, YouTube, Instagram) coming soon!
      </p>
    </div>
  )
}
