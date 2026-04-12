interface NarratorCardProps {
  label: string
  text: string
}

export function NarratorCard({ label, text }: NarratorCardProps) {
  return (
    <div className="bg-surface-elevated rounded-xl border border-border p-4">
      <span className="text-xs text-text-secondary uppercase tracking-wider font-semibold">
        🎙 {label}
      </span>
      <p className="mt-2 text-text-primary italic font-mono text-sm leading-relaxed">
        "{text}"
      </p>
    </div>
  )
}
