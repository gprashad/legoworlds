import type { NarratorLine } from '../../types/shotlist'

interface NarratorTimelineProps {
  lines: NarratorLine[]
  totalDuration: number
}

export function NarratorTimeline({ lines, totalDuration }: NarratorTimelineProps) {
  const sorted = [...lines].sort((a, b) => a.time_seconds - b.time_seconds)

  return (
    <div className="bg-surface-elevated rounded-xl border border-border p-5 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-2xl">🎙</span>
        <div>
          <h3 className="font-semibold text-text-primary">Trailer Narration</h3>
          <p className="text-xs text-text-secondary">Deep voice, trailer style. No character dialogue.</p>
        </div>
      </div>

      <div className="space-y-2 pl-3 border-l-2 border-accent/30">
        {sorted.map((line, i) => (
          <div key={i} className="flex gap-3 items-start">
            <span className="text-xs text-accent font-mono min-w-[3rem]">
              0:{String(Math.floor(line.time_seconds)).padStart(2, '0')}
            </span>
            <p className="text-sm text-text-primary italic font-mono flex-1">
              "{line.line}"
            </p>
          </div>
        ))}
      </div>

      <p className="text-xs text-text-secondary">
        Total runtime: ~{totalDuration}s
      </p>
    </div>
  )
}
